"""Messenger — typed pub/sub event bus between the Python toolkit and clients.

Two distinct protocols share this module under the "messenger" name:

  1. **Event bus** (active, v1)  — publish/subscribe for server lifecycle,
     WebSocket bridge state, view lifecycle, and log entries. The Electron
     home window subscribes to these to render the diagnostic surface; the
     overlay window subscribes to view.* events as before.

  2. **Natwarth viewer protocol** (planned, v2, blocked on license)  — a
     bidirectional protocol between the skill and a forked tree visualizer.
     Preserved as design documentation at the bottom of this file.

The event bus is wired up by `mcp_server.server.main()` — that's where
`transport_ws.emit_event` gets registered as the network transport. Other
in-process subscribers (the snapshot provider, future Lua bridge handlers)
register via `subscribe()`.

## Event types (v1 — active)

| Event           | Payload shape                                                       |
|-----------------|---------------------------------------------------------------------|
| `server.state`  | `{state: 'starting' | 'ready' | 'shutting_down', pid, msg?}`        |
| `ws.state`      | `{state: 'unconfigured' | 'starting' | 'bound' | 'crashed', port?}` |
| `view.lifecycle`| `{action: 'render' | 'update' | 'dismiss', view_id, view_type}`     |
| `log.entry`     | `{level, logger, message, ts}`                                      |

All events carry a `ts` (epoch seconds) field — added automatically if absent.

## Future event types (v2 — chat comms)

| Event             | Direction         | Purpose                                       |
|-------------------|-------------------|-----------------------------------------------|
| `user.message`    | client → server   | Player typed/spoke in the overlay chat        |
| `user.dismissed`  | client → server   | Player closed a view                          |
| `claude.response` | server → client   | Claude's reply, routed to a view              |
| `claude.thinking` | server → client   | "Claude is processing…" status                |

## Architecture

The bus has no wire layer of its own — `publish()` fans out to registered
transports (callables `(event_type, payload) -> None`). The MCP server
registers `transport_ws.emit_event` as the primary transport. Other modules
or tests can register additional transports without modifying messenger.

In-process subscribers are independent of the wire — they fire synchronously
in the publisher's thread. Keep handlers fast and exception-safe; exceptions
are caught and logged but otherwise swallowed.

## Snapshot

`snapshot()` returns the latest payload of each event type, keyed by type.
The WS bridge serves this on new-client connect as a `state.snapshot` event
so a late-joining home window can render the current state without waiting
for the next live event.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# ─────────────────────────────────────────
# v1 — Event bus
# ─────────────────────────────────────────

# In-process subscribers per event_type ('*' subscribes to everything).
_subscribers: dict[str, list[Callable[[dict], None]]] = {}
_subscribers_lock = threading.Lock()

# Transports for outbound delivery (e.g. transport_ws.emit_event).
_transports: list[Callable[[str, dict], Any]] = []
_transports_lock = threading.Lock()

# Latest payload of each event type — sent as `state.snapshot` to new WS clients.
_latest_by_event: dict[str, dict] = {}
_latest_lock = threading.Lock()


def publish(event_type: str, payload: dict[str, Any]) -> None:
    """Publish `event_type` with `payload` to all subscribers + transports.

    `event_type` follows `<domain>.<verb>` convention. A `ts` field is added
    to the payload if not present. Exceptions in subscribers/transports are
    caught and logged — they never propagate to the publisher.
    """
    if "ts" not in payload:
        payload["ts"] = time.time()

    # Cache as the latest of this type for snapshot()
    with _latest_lock:
        _latest_by_event[event_type] = payload

    # Fan out to in-process subscribers (type-specific + wildcard)
    with _subscribers_lock:
        handlers = list(_subscribers.get(event_type, []))
        handlers.extend(_subscribers.get("*", []))
    for handler in handlers:
        try:
            handler({"event": event_type, "payload": payload})
        except Exception:
            log.exception("subscriber for %s raised", event_type)

    # Fan out to wire transports
    with _transports_lock:
        transports = list(_transports)
    for fn in transports:
        try:
            fn(event_type, payload)
        except Exception:
            log.exception("transport %s raised for %s", fn, event_type)


def subscribe(
    event_type: str, handler: Callable[[dict], None]
) -> Callable[[], None]:
    """Register `handler` for `event_type` ('*' = all). Returns unsubscribe fn."""
    with _subscribers_lock:
        _subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe() -> None:
        with _subscribers_lock:
            try:
                _subscribers[event_type].remove(handler)
            except (KeyError, ValueError):
                pass

    return unsubscribe


def register_transport(fn: Callable[[str, dict], Any]) -> Callable[[], None]:
    """Register `fn(event_type, payload)` as an outbound transport.

    Used by `mcp_server.server.main()` to wire `transport_ws.emit_event` as
    the primary WS transport. Tests or alternative carriers register here too.
    Returns an unregister callback.
    """
    with _transports_lock:
        _transports.append(fn)

    def unregister() -> None:
        with _transports_lock:
            try:
                _transports.remove(fn)
            except ValueError:
                pass

    return unregister


def snapshot() -> dict[str, dict]:
    """Return the latest payload of each event type seen so far.

    Sent as `state.snapshot` to new WebSocket clients so a late-joining
    home window can render the current state without waiting for the next
    live event.
    """
    with _latest_lock:
        return dict(_latest_by_event)


def reset() -> None:
    """Clear all subscribers, transports, and cached state. Test-only."""
    with _subscribers_lock:
        _subscribers.clear()
    with _transports_lock:
        _transports.clear()
    with _latest_lock:
        _latest_by_event.clear()


# ─────────────────────────────────────────
# v1 — Python logging → log.entry bridge
# ─────────────────────────────────────────


class _MessengerLogHandler(logging.Handler):
    """Mirror Python log records to the `log.entry` event stream.

    Re-entry guarded: anything `publish()` does internally that logs (e.g.
    `transport_ws.emit_event` calling `log.warning` on a broadcast timeout)
    would otherwise loop back through this handler and recurse without bound.
    The thread-local `_reentry` flag short-circuits the nested emit.
    """

    def __init__(self) -> None:
        super().__init__()
        self._reentry = threading.local()

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._reentry, "active", False):
            return
        self._reentry.active = True
        try:
            publish(
                "log.entry",
                {
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "ts": record.created,
                },
            )
        except Exception:
            pass
        finally:
            self._reentry.active = False


_log_handler: Optional[_MessengerLogHandler] = None


def install_log_handler(level: int = logging.INFO) -> logging.Handler:
    """Attach the messenger log handler to the root logger. Idempotent."""
    global _log_handler
    root = logging.getLogger()
    if _log_handler is not None:
        root.removeHandler(_log_handler)
    handler = _MessengerLogHandler()
    handler.setLevel(level)
    root.addHandler(handler)
    _log_handler = handler
    return handler


def remove_log_handler() -> None:
    """Detach the messenger log handler from the root logger."""
    global _log_handler
    if _log_handler is not None:
        logging.getLogger().removeHandler(_log_handler)
        _log_handler = None


# ─────────────────────────────────────────
# v2 — Natwarth viewer protocol (planned, blocked on license)
# ─────────────────────────────────────────
#
# A separate bidirectional protocol between the skill and a forked
# poe2-skilltree visualizer. Distinct from the v1 event bus — different
# port (7777 by default), different message shapes, viewer-specific
# semantics. Blocked on permissive license from natwarth/poe2-skilltree
# (issue https://github.com/natwarth/poe2-skilltree/issues/2). Until then
# the skill emits public viewer URLs from `Allocation.to_url()`.
#
# Target architecture:
#
#     [Claude Code skill (Python)]  ←──ws://127.0.0.1:7777──→  [forked viewer (browser)]
#             │                                                     │
#        Allocation API                                          tree rendering
#        EXILE.xml updates                                       node click capture
#        build emit                                              overlay drawing
#             │                                                     │
#             └─────────────── localhost only, no cloud ────────────┘
#
# Wire format (JSON, one message per frame). Either side may originate:
#
#   → allocate       {node_hash, weapon_set?, skill_override?}
#   → deallocate     {node_hash}
#   → highlight      {nodes: [int], color}
#   → camera         {focus, zoom}
#   → propose_route  {from, to, path: [int]}
#   → ask            {prompt, options?}
#   ← clicked        {node_hash, modifiers?}
#   ← typed          {text}
#   ← form_submit    {payload}
#
# Each message carries `id` (uuid) and `ts` (epoch seconds).
# Default port: 7777. Configurable via POE2_GRAPH_WS_PORT.

NATWARTH_WS_DEFAULT_PORT = 7777


def is_natwarth_viewer_available() -> bool:
    """Return True when the natwarth-viewer bridge is implemented + connectable.

    Currently always False — blocked on viewer license.
    """
    return False
