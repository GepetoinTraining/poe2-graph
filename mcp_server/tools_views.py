"""Display tools — push view-render events to the Electron overlay.

Phase 1 lays the wiring; the actual Electron components (build planner,
crafting planner, in-game item tooltip) get pulled in later from:
  - github.com/Path-of-Tools/poe-item-parser
  - github.com/Path-of-Tools/poe-item-display
  - github.com/Path-of-Tools/poe-item-hover-react

Until then, every `display_*` tool emits a `view.render` event over the
WebSocket bridge. If the bridge isn't connected (no overlay running), the
tool returns `{"delivered": 0, "bridge": "disabled"|"live"}` so the calling
Claude can degrade gracefully ("overlay not connected — here's the data
inline instead").

See `protocol.md` for the message envelope contract.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

from . import transport_ws
from . import tools_goals
from . import tools_items
from ._serialize import to_jsonable


# Audience dial — coarse two-step for now (terse vs educational). Maps to the
# `audience` field in view payloads; views render differently per value.
_AUDIENCE_VALUES = ("1pct", "30pct")


def _vid(prefix: str) -> str:
    """Stable-ish view id. Callers can override by passing view_id."""
    return f"{prefix}_{secrets.token_hex(3)}"


def _normalize_audience(audience: Optional[str]) -> str:
    if audience in _AUDIENCE_VALUES:
        return audience
    return "30pct"  # default to the more educational mode


def display_item_tooltip(
    clipboard_text: str,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Parse a clipboard item dump and push it to the overlay as an item tooltip."""
    parsed = tools_items.parse_clipboard_item(clipboard_text)
    if not parsed.get("ok"):
        return {"ok": False, "error": parsed.get("error"), "delivery": None}
    vid = view_id or _vid("vw_item")
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "item_tooltip",
            "id": vid,
            "audience": _normalize_audience(audience),
            "data": parsed["item"],
        },
    )
    return {"ok": True, "view_id": vid, "delivery": ack, "item": parsed["item"]}


def display_goal_tracker(
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Render the WoW-tracker for the active PlayerGoal in the overlay."""
    text = tools_goals.render_goal_tracker()
    if text is None:
        return {"ok": False, "error": "no active goal", "delivery": None}
    vid = view_id or _vid("vw_goal")
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "goal_tracker",
            "id": vid,
            "audience": _normalize_audience(audience),
            "data": {"text": text, "structured": None},
        },
    )
    return {"ok": True, "view_id": vid, "delivery": ack, "text": text}


def display_next_action_card(
    *,
    game: str = "poe2",
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Compose recommend_next_action and push as a 'next action' card."""
    rec_payload = tools_goals.recommend_next_action(game=game)
    vid = view_id or _vid("vw_next")
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "next_action_card",
            "id": vid,
            "audience": _normalize_audience(audience),
            "data": rec_payload["recommendation"],
        },
    )
    return {"ok": True, "view_id": vid, "delivery": ack, "recommendation": rec_payload["recommendation"]}


def start_map_timer(
    target_seconds: int = 240,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Push a map-timer view; Electron renders the countdown locally.

    The server only emits the start event — the overlay owns the visual tick.
    Server-side state for the timer is intentionally minimal in Phase 1.
    """
    import time
    started_at = time.time()
    vid = view_id or _vid("vw_timer")
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "map_timer",
            "id": vid,
            "audience": _normalize_audience(audience),
            "data": {
                "started_at_epoch": started_at,
                "target_seconds": target_seconds,
                "elapsed_seconds": 0,
            },
        },
    )
    return {"ok": True, "view_id": vid, "delivery": ack, "started_at_epoch": started_at}


def dismiss_view(view_id: str) -> dict[str, Any]:
    """Tell the overlay to dismiss a previously-rendered view."""
    ack = transport_ws.emit_event("view.dismiss", {"id": view_id})
    return {"ok": True, "view_id": view_id, "delivery": ack}


def overlay_status() -> dict[str, Any]:
    """Report whether the WS bridge is configured + live."""
    return {
        "enabled": transport_ws.is_enabled(),
        "configured_port": transport_ws.configured_port(),
        "client_count": len(transport_ws._clients),
    }
