"""Session bootstrap tools: welcome, staleness_report.

The welcome tool is the single-call session-start surface that any Claude
(Web/Code/Electron-hosted) calls first. It composes onboarding state,
staleness flags, active-goal tracker, and suggested next intents.
"""

from __future__ import annotations

from typing import Any, Optional

import exile
import goals
from infra import updater

from ._serialize import to_jsonable


def welcome() -> dict[str, Any]:
    """Session-start payload.

    Returns:
      onboarded: bool — whether EXILE/DONE exists
      staleness: dict — output of updater.report() summarised
      active_character: {game: id} for each game with an active character
      active_player_goal: PlayerGoal dict (or None)
      goal_tracker_text: WoW-tracker rendering of the active goal (or None)
      suggested_intents: list[str] — short hints of what to ask Claude next
    """
    onboarded = exile.is_onboarded()

    staleness_summary: Optional[dict[str, Any]] = None
    try:
        report = updater.report()
        staleness_summary = to_jsonable(report)
    except Exception as exc:
        staleness_summary = {"error": f"staleness check failed: {exc}"}

    actives = exile.active_characters() if onboarded else {}

    active_pg = goals.active_player_goal() if onboarded else None
    goal_tracker_text: Optional[str] = None
    if active_pg is not None:
        try:
            goal_tracker_text = goals.render_goal_tracker(active_pg)
        except Exception:
            goal_tracker_text = None

    suggested = _suggested_intents(onboarded, active_pg is not None, bool(actives))

    return {
        "onboarded": onboarded,
        "staleness": staleness_summary,
        "active_characters": actives,
        "active_player_goal": to_jsonable(active_pg),
        "goal_tracker_text": goal_tracker_text,
        "suggested_intents": suggested,
    }


def staleness_report() -> dict[str, Any]:
    """Three-layer staleness check (skill version, data sources, tool submodules)."""
    try:
        return to_jsonable(updater.report())
    except Exception as exc:
        return {"error": str(exc)}


def _suggested_intents(onboarded: bool, has_active_goal: bool, has_active_character: bool) -> list[str]:
    if not onboarded:
        return [
            "Walk me through onboarding",
            "What can poe2-graph do?",
        ]
    out: list[str] = []
    if has_active_goal:
        out.append("What should I do tonight?")
        out.append("How am I doing on my active goal?")
    else:
        out.append("Set an active goal for this league")
    if has_active_character:
        out.append("Recommend next steps on my active character")
    out.append("Teach me a mechanic")
    out.append("Parse this item I copied")
    return out
