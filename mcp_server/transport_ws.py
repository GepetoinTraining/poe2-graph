"""WebSocket bridge to the Electron overlay (wiring stub).

Phase 1 lays the seam; Phase 2 fleshes it out. The server starts a localhost
WebSocket on `POE2_MCP_WS_PORT` (when set) and broadcasts events emitted by
`tools_views.display_*` tools. Without that env var, the bridge is a no-op
and the MCP server runs stdio-only — fine for Claude Code without Electron.

See `protocol.md` for the message envelope contract Electron clients implement.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import Awaitable, Callable
from typing import Any, Optional

log = logging.getLogger(__name__)


# Module-level state. Singleton broker; importing this module repeatedly is fine.
_clients: set[Any] = set()
_loop: Optional[asyncio.AbstractEventLoop] = None
_server_thread: Optional[threading.Thread] = None
_server_obj: Optional[Any] = None        # websockets.Server — kept so stop() can close it
_started: bool = False
# Set once the broker thread has bound the listener; emit_event gates its
# "live" branch on this so a tool that fires immediately after start_if_enabled
# returns sees "disabled" until the loop is actually accepting connections.
_ready_event: threading.Event = threading.Event()

# Optional handler for inbound events from clients (player input, view interactions).
# tools_views can register a callback here to receive events; otherwise inbound is logged + dropped.
_inbound_handler: Optional[Callable[[dict], Awaitable[None]]] = None

# Optional snapshot provider — returns the current event-bus state to seed
# a newly-connected client. messenger.snapshot is the usual implementation;
# we keep the dependency one-way (transport_ws doesn't import messenger).
_snapshot_provider: Optional[Callable[[], dict]] = None


def configured_port() -> Optional[int]:
    """Returns the configured WS port, or None to disable the bridge."""
    raw = os.environ.get("POE2_MCP_WS_PORT")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        log.warning("POE2_MCP_WS_PORT=%r is not an integer; bridge disabled", raw)
        return None


def is_enabled() -> bool:
    return configured_port() is not None


def start_if_enabled() -> None:
    """Idempotent: spin up the WS server in a background thread if configured."""
    global _started, _server_thread
    if _started:
        return
    port = configured_port()
    if port is None:
        return
    _started = True
    _server_thread = threading.Thread(
        target=_run_event_loop, args=(port,), daemon=True, name="poe2-mcp-ws"
    )
    _server_thread.start()
    log.info("WebSocket bridge starting on localhost:%d", port)


def emit_event(event: str, payload: dict) -> dict:
    """Broadcast a JSON message {event, payload} to all connected clients.

    Returns a small ack dict — number of recipients + whether the bridge is
    actually live. Tools call this from inside a synchronous MCP request, so
    we hop into the broker's event loop without blocking the caller for long.
    """
    message = {"event": event, "payload": payload}
    # Gate on `_ready_event` so a tool that fires before the broker has bound
    # its listener gets the "disabled" ack instead of timing out scheduling
    # onto a half-initialized loop. After a broker crash the finally-block
    # clears the event, so subsequent emits revert to disabled cleanly.
    if not _ready_event.is_set() or _loop is None:
        return {"delivered": 0, "bridge": "disabled"}
    if not _clients:
        return {"delivered": 0, "bridge": "live"}

    fut = asyncio.run_coroutine_threadsafe(_broadcast(message), _loop)
    try:
        delivered = fut.result(timeout=2.0)
    except Exception as exc:
        log.warning("broadcast failed: %s", exc)
        delivered = 0
    return {"delivered": delivered, "bridge": "live"}


def client_count() -> int:
    """Return the count of currently-connected WS clients.

    Public helper so tool modules don't have to reach into the private
    `_clients` set. `len()` on a CPython set is atomic; this insulates
    callers from that implementation detail.
    """
    return len(_clients)


def stop() -> None:
    """Close the WS listener (best-effort). Safe to call when disabled.

    Used by tests and explicit-shutdown paths; the daemon thread exits on
    process termination anyway, so non-test callers usually don't need it.
    """
    global _server_obj
    if _server_obj is not None and _loop is not None and _loop.is_running():
        async def _close():
            _server_obj.close()
            await _server_obj.wait_closed()
        asyncio.run_coroutine_threadsafe(_close(), _loop).result(timeout=2.0)
    _server_obj = None


def register_inbound_handler(handler: Callable[[dict], Awaitable[None]]) -> None:
    """Register an async callback for inbound client messages (player events)."""
    global _inbound_handler
    _inbound_handler = handler


def set_snapshot_provider(fn: Optional[Callable[[], dict]]) -> None:
    """Register a function returning the current event-bus snapshot.

    On new-client connect, the broker sends `{event: 'state.snapshot',
    payload: <fn()>}` so a late-joiner can render the current state without
    waiting for the next live event.

    Pass `None` to clear (used in tests). The dependency direction is
    deliberate: transport_ws doesn't import messenger; messenger registers
    here via the wiring in `mcp_server.server.main()`.
    """
    global _snapshot_provider
    _snapshot_provider = fn


# ---- internals ----

def _run_event_loop(port: int) -> None:
    """Background-thread entry: run the asyncio loop hosting the WS server."""
    global _loop, _started, _server_obj
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        _server_obj = _loop.run_until_complete(_serve(port))
        # Listener is bound — flip the readiness gate so emit_event can
        # broadcast. Without this, a tool firing synchronously after
        # start_if_enabled() races the bind and sees "disabled".
        _ready_event.set()
        _loop.run_forever()
    except Exception:
        log.exception("WS broker loop crashed")
    finally:
        try:
            _loop.close()
        except Exception:
            pass
        # Reset module state so subsequent emit_event calls revert to the
        # "disabled" branch instead of scheduling on a closed loop. Without
        # this reset a port-in-use crash leaves the bridge in a wedged state
        # that burns a 2s timeout on every display_* tool.
        _loop = None
        _server_obj = None
        _started = False
        _ready_event.clear()


async def _serve(port: int):
    """Bind the localhost WS listener. Returns the websockets.Server handle.

    The broker thread keeps the handle on the module global so `stop()` can
    cleanly close it (tests + explicit shutdown paths).
    """
    # Lazy import so the dep is only required when the bridge is actually enabled
    import websockets

    async def handler(ws):
        _clients.add(ws)
        log.info("client connected (%d total)", len(_clients))
        # Seed the new client with the current snapshot so a late-joining home
        # window can render state without waiting for the next live event.
        if _snapshot_provider is not None:
            try:
                snap = _snapshot_provider()
                await ws.send(json.dumps({"event": "state.snapshot", "payload": snap}))
            except Exception:
                log.exception("snapshot-on-connect failed")
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("non-JSON inbound message dropped: %r", raw[:200])
                    continue
                if _inbound_handler is not None:
                    try:
                        await _inbound_handler(msg)
                    except Exception:
                        log.exception("inbound handler raised")
                else:
                    log.debug("inbound message dropped (no handler): %r", msg)
        finally:
            _clients.discard(ws)
            log.info("client disconnected (%d total)", len(_clients))

    return await websockets.serve(handler, "localhost", port)


async def _broadcast(message: dict) -> int:
    """Send `message` to every connected client. Returns successful-delivery count."""
    if not _clients:
        return 0
    payload = json.dumps(message)
    delivered = 0
    dead: list[Any] = []
    for client in list(_clients):
        try:
            await client.send(payload)
            delivered += 1
        except Exception:
            dead.append(client)
    for d in dead:
        _clients.discard(d)
    return delivered
