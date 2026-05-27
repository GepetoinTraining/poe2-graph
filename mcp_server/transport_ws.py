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
_started: bool = False

# Optional handler for inbound events from clients (player input, view interactions).
# tools_views can register a callback here to receive events; otherwise inbound is logged + dropped.
_inbound_handler: Optional[Callable[[dict], Awaitable[None]]] = None


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
    if not _started or _loop is None:
        # Bridge not configured. Still return a structured response so tools
        # have something useful to surface ("no overlay connected").
        return {"delivered": 0, "bridge": "disabled"}
    recipients = list(_clients)
    if not recipients:
        return {"delivered": 0, "bridge": "live"}

    fut = asyncio.run_coroutine_threadsafe(_broadcast(message), _loop)
    try:
        delivered = fut.result(timeout=2.0)
    except Exception as exc:
        log.warning("broadcast failed: %s", exc)
        delivered = 0
    return {"delivered": delivered, "bridge": "live"}


def register_inbound_handler(handler: Callable[[dict], Awaitable[None]]) -> None:
    """Register an async callback for inbound client messages (player events)."""
    global _inbound_handler
    _inbound_handler = handler


# ---- internals ----

def _run_event_loop(port: int) -> None:
    """Background-thread entry: run the asyncio loop hosting the WS server."""
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        _loop.run_until_complete(_serve(port))
        _loop.run_forever()
    except Exception:
        log.exception("WS broker loop crashed")
    finally:
        _loop.close()


async def _serve(port: int) -> None:
    # Lazy import so the dep is only required when the bridge is actually enabled
    import websockets

    async def handler(ws):
        _clients.add(ws)
        log.info("client connected (%d total)", len(_clients))
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

    await websockets.serve(handler, "localhost", port)


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
