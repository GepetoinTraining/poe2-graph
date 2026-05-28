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
import threading
import time
from typing import Any, Optional

from integrations import messenger

from . import transport_ws
from . import tools_goals
from . import tools_items
from . import tools_farm
from ._serialize import to_jsonable


# ─────────────────────────────────────────
# Active-views registry
#
# The overlay renderer maintains its own activeViews map for what's drawn on
# screen. We track a server-side mirror here so the home window — and any
# late-joining WS client — can render the current view set from a single
# snapshot rather than reconstructing it from a stream of view.render events.
# ─────────────────────────────────────────

_active_views: dict[str, dict[str, Any]] = {}
_active_views_lock = threading.Lock()


def _register_view(view_id: str, view_type: str, audience: Optional[str]) -> None:
    with _active_views_lock:
        _active_views[view_id] = {
            "view_type": view_type,
            "audience": audience,
            "started_at": time.time(),
        }


def _unregister_view(view_id: str) -> None:
    with _active_views_lock:
        _active_views.pop(view_id, None)


def get_active_views() -> list[dict[str, Any]]:
    """Return the current active-views list, ordered by start time."""
    with _active_views_lock:
        items = [{"view_id": vid, **info} for vid, info in _active_views.items()]
    items.sort(key=lambda v: v["started_at"])
    return items


def _on_render(view_id: str, view_type: str, audience: Optional[str]) -> None:
    """Hook called after a view.render emit succeeds.

    Updates the active-views registry and publishes lifecycle + state events
    so the home window can refresh both its activity log and its
    active-views list.
    """
    _register_view(view_id, view_type, audience)
    messenger.publish(
        "view.lifecycle",
        {
            "action": "render",
            "view_id": view_id,
            "view_type": view_type,
            "audience": audience,
        },
    )
    messenger.publish("views.active", {"views": get_active_views()})


def _on_dismiss(view_id: str) -> None:
    _unregister_view(view_id)
    messenger.publish(
        "view.lifecycle", {"action": "dismiss", "view_id": view_id}
    )
    messenger.publish("views.active", {"views": get_active_views()})


# Audience dial — coarse two-step for now (terse vs educational). Maps to the
# `audience` field in view payloads; views render differently per value.
_AUDIENCE_VALUES = ("1pct", "30pct")


def _vid(prefix: str) -> str:
    """Stable-ish view id. Callers can override by passing view_id."""
    return f"{prefix}_{secrets.token_hex(3)}"


def _normalize_audience(audience: Optional[str]) -> str:
    if audience is None:
        return "30pct"
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
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "item_tooltip",
            "id": vid,
            "audience": audience_n,
            "data": parsed["item"],
        },
    )
    _on_render(vid, "item_tooltip", audience_n)
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
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "goal_tracker",
            "id": vid,
            "audience": audience_n,
            "data": {"text": text, "structured": None},
        },
    )
    _on_render(vid, "goal_tracker", audience_n)
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
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "next_action_card",
            "id": vid,
            "audience": audience_n,
            "data": rec_payload["recommendation"],
        },
    )
    _on_render(vid, "next_action_card", audience_n)
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
    from datetime import datetime, timezone
    # ISO 8601 with trailing Z, matching the `map_timer.data.started_at`
    # contract in mcp_server/protocol.md. Overlay clients parse via Date().
    started_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    vid = view_id or _vid("vw_timer")
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {
            "view": "map_timer",
            "id": vid,
            "audience": audience_n,
            "data": {
                "started_at": started_at,
                "target_seconds": target_seconds,
                "elapsed_seconds": 0,
            },
        },
    )
    _on_render(vid, "map_timer", audience_n)
    return {"ok": True, "view_id": vid, "delivery": ack, "started_at": started_at}


def dismiss_view(view_id: str) -> dict[str, Any]:
    """Tell the overlay to dismiss a previously-rendered view."""
    ack = transport_ws.emit_event("view.dismiss", {"id": view_id})
    _on_dismiss(view_id)
    return {"ok": True, "view_id": view_id, "delivery": ack}


def overlay_status() -> dict[str, Any]:
    """Report whether the WS bridge is configured + live."""
    return {
        "enabled": transport_ws.is_enabled(),
        "configured_port": transport_ws.configured_port(),
        "client_count": transport_ws.client_count(),
    }


def display_cycle_status(
    cycle_id: str,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Push a cycle status card to the Electron overlay.

    Pulls live cycle data from the store. Payload data shape (the contract —
    Electron renderer reads this):
    {
        cycle_id: str,
        status: 'DECLARED'|'ACTIVE'|'CLOSED',
        farm_target: str,
        lottery_targets: list[str],
        opened_at: str | None,
        elapsed_minutes: float | None,  -- if ACTIVE, computed from opened_at
        output_count: int,
        classified: {price_me: int, gold_pile: int, unclassified: int},
    }
    """
    from datetime import datetime, timezone

    result = tools_farm.farm_get_cycle(cycle_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "delivery": None}

    cycle = result["cycle"]
    outputs = cycle.get("outputs", [])

    price_me = sum(1 for o in outputs if o.get("classification") == "price_me")
    gold_pile = sum(1 for o in outputs if o.get("classification") == "gold_pile")
    unclassified = sum(1 for o in outputs if not o.get("classification"))

    elapsed_minutes: Optional[float] = None
    opened_at = cycle.get("opened_at") or None
    if cycle.get("status") == "ACTIVE" and opened_at:
        try:
            opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            elapsed_minutes = (
                datetime.now(timezone.utc) - opened_dt
            ).total_seconds() / 60.0
        except (ValueError, TypeError):
            pass

    payload: dict[str, Any] = {
        "cycle_id": cycle_id,
        "status": cycle.get("status", ""),
        "farm_target": cycle.get("farm_target", ""),
        "lottery_targets": cycle.get("lottery_targets", []),
        "opened_at": opened_at,
        "elapsed_minutes": elapsed_minutes,
        "output_count": len(outputs),
        "classified": {
            "price_me": price_me,
            "gold_pile": gold_pile,
            "unclassified": unclassified,
        },
    }

    vid = view_id or _vid("vw_cycle")
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {"view": "cycle_status", "id": vid, "audience": audience_n, "data": payload},
    )
    _on_render(vid, "cycle_status", audience_n)
    return {"ok": True, "view_id": vid, "delivery": ack, "data": payload}


def display_classify_alert(
    cycle_id: str,
    output_id: str,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Push a 'this drop hit price_me — check Trade' alert to the overlay.

    Payload data shape:
    {
        cycle_id: str,
        output_id: str,
        item_summary: str,           -- e.g. 'Rare Waystone +rarity'
        matched_pattern: str,        -- which mod-regex triggered the alert
        suggested_trade_query: dict | None,
    }
    """
    result = tools_farm.farm_get_cycle(cycle_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "delivery": None}

    cycle = result["cycle"]
    output = next(
        (o for o in cycle.get("outputs", []) if o.get("node_id") == output_id),
        None,
    )
    if output is None:
        return {
            "ok": False,
            "error": f"Output {output_id!r} not found in cycle {cycle_id!r}",
            "delivery": None,
        }

    item_text = output.get("item", "")
    # Build a terse summary from the raw item text (first two non-blank lines).
    lines = [l.strip() for l in item_text.splitlines() if l.strip()]
    item_summary = " ".join(lines[:2]) if lines else output_id

    payload: dict[str, Any] = {
        "cycle_id": cycle_id,
        "output_id": output_id,
        "item_summary": item_summary,
        "matched_pattern": "",  # caller may set this; we surface the alert
        "suggested_trade_query": None,
    }

    vid = view_id or _vid("vw_alert")
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {"view": "classify_alert", "id": vid, "audience": audience_n, "data": payload},
    )
    _on_render(vid, "classify_alert", audience_n)
    return {"ok": True, "view_id": vid, "delivery": ack, "data": payload}


def display_reconcile_warning(
    cycle_id: str,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Push a reconcile audit card if the cycle has a gap; no-op if clean.

    Runs farm_reconcile_cycle internally. If gap == 0, returns
    {ok: True, gap: 0, view_id: None, delivery: None} without emitting
    a view — saves the player a notification when everything is fine.

    Payload data shape (only emitted when gap != 0):
    {
        cycle_id: str,
        cycle_output_count: int,
        main_received_count: int,
        reconciliation_gap: int,
        unmatched_output_ids: list[str],
    }
    """
    result = tools_farm.farm_reconcile_cycle(cycle_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "delivery": None}

    gap = result.get("reconciliation_gap", 0)
    if gap == 0:
        return {"ok": True, "gap": 0, "view_id": None, "delivery": None}

    payload: dict[str, Any] = {
        "cycle_id": cycle_id,
        "cycle_output_count": result.get("cycle_output_count", 0),
        "main_received_count": result.get("main_received_count", 0),
        "reconciliation_gap": gap,
        "unmatched_output_ids": result.get("unmatched_output_ids", []),
    }

    vid = view_id or _vid("vw_reconcile")
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {"view": "reconcile_warning", "id": vid, "audience": audience_n, "data": payload},
    )
    _on_render(vid, "reconcile_warning", audience_n)
    return {"ok": True, "view_id": vid, "delivery": ack, "data": payload}


def display_cycle_summary(
    cycle_id: str,
    *,
    audience: Optional[str] = None,
    view_id: Optional[str] = None,
) -> dict[str, Any]:
    """Push the close-cycle summary card (ROI, hit rate, div/hour) to the overlay.

    Only valid for CLOSED cycles. Returns {ok: False, error} for ACTIVE or
    DECLARED cycles.

    Payload data shape:
    {
        cycle_id: str,
        farm_target: str,
        roi: float,
        hit_rate: float,
        div_per_hour: float | None,
        time_invested_minutes: float | None,
        output_count: int,
        classified: {price_me: int, gold_pile: int},
        closed_at: str,
    }
    """
    result = tools_farm.farm_get_cycle(cycle_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "delivery": None}

    cycle = result["cycle"]
    if cycle.get("status") != "CLOSED":
        return {
            "ok": False,
            "error": f"display_cycle_summary requires a CLOSED cycle; got status={cycle.get('status')!r}",
            "delivery": None,
        }

    summary = cycle.get("summary", {})
    outputs = cycle.get("outputs", [])
    price_me = sum(1 for o in outputs if o.get("classification") == "price_me")
    gold_pile = sum(1 for o in outputs if o.get("classification") == "gold_pile")

    payload: dict[str, Any] = {
        "cycle_id": cycle_id,
        "farm_target": cycle.get("farm_target", ""),
        "roi": summary.get("roi", 0.0),
        "hit_rate": summary.get("hit_rate", 0.0),
        "div_per_hour": summary.get("div_per_hour") or None,
        "time_invested_minutes": None,
        "output_count": len(outputs),
        "classified": {"price_me": price_me, "gold_pile": gold_pile},
        "closed_at": cycle.get("closed_at", ""),
    }

    vid = view_id or _vid("vw_summary")
    audience_n = _normalize_audience(audience)
    ack = transport_ws.emit_event(
        "view.render",
        {"view": "cycle_summary", "id": vid, "audience": audience_n, "data": payload},
    )
    _on_render(vid, "cycle_summary", audience_n)
    return {"ok": True, "view_id": vid, "delivery": ack, "data": payload}
