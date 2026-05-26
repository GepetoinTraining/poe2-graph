"""EXILE/HISTORY.md — Claude's append-only player journal.

This file is NOT for the player to edit directly. Claude maintains it across
sessions as the durable archive of player progress, league-by-league, goal-by-
goal, donation-by-donation. The player corrects entries via Claude conversation;
Claude writes the correction.

Distinct from:
  - PLAYER.md (the current player state — knows, prefers, constraints)
  - LEAGUE_*.md (per-league tactical context — active session-level)
  - CHARACTER_*.md (per-character build state)
  - PLAYER.diffs/ (snapshot trail of PLAYER.md changes)

HISTORY.md is the LONG horizon. PLAYER.md is now; HISTORY.md is forever.

Frontmatter is structured (queryable lists). Body is narrative summaries
written at session-end milestones.

Public API:
    history.init()                          # idempotent
    history.append_league(...)
    history.append_goal_completed(...)
    history.append_learning_progress(...)
    history.append_case_study(...)
    history.append_donation(...)
    history.append_session_note(title, lines)
    history.get_history()                   # read structured dict
    history.has_completed_goal(goal_id)
    history.leagues_count()
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import exile


HISTORY_FILENAME = "HISTORY.md"


def _path() -> Path:
    return exile.EXILE_DIR / HISTORY_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _initial_template() -> str:
    today = _today()
    fm = {
        "schema_version": 1,
        "created": today,
        "last_updated": today,
        "leagues_played": [],
        "goals_completed": [],
        "learning_goals_progressed": [],
        "case_studies_completed": [],
        "donations_to_skill": [],
    }
    body = (
        "\n# History\n\n"
        "Claude's append-only player journal. Do not edit by hand — corrections "
        "happen through conversation; Claude writes the corrected entry.\n\n"
        "## Sessions\n\n"
    )
    return exile.write_frontmatter(fm, body)


def init() -> Path:
    """Create EXILE/HISTORY.md if missing. Idempotent."""
    p = _path()
    if p.exists():
        return p
    exile.EXILE_DIR.mkdir(exist_ok=True)
    p.write_text(_initial_template(), encoding="utf-8")
    return p


# ----- internal IO -----

def _read() -> tuple[dict, str]:
    if not _path().exists():
        init()
    return exile.read_file(_path())


def _write(fm: dict, body: str) -> None:
    exile.write_file(_path(), fm, body)


def _append_entry(section: str, entry: dict) -> dict:
    fm, body = _read()
    fm.setdefault(section, []).append(entry)
    _write(fm, body)
    return entry


# ----- append APIs -----

def append_league(
    league_id: str,
    started: str,
    ended: Optional[str] = None,
    final_character_id: Optional[str] = None,
    final_level: Optional[int] = None,
    peak_wealth_estimate_div: Optional[float] = None,
    highlight: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Record a league the player participated in."""
    entry: dict = {
        "id": league_id,
        "started": started,
        "appended_at": _now_iso(),
    }
    if ended is not None:
        entry["ended"] = ended
    if final_character_id is not None:
        entry["final_character_id"] = final_character_id
    if final_level is not None:
        entry["final_level"] = int(final_level)
    if peak_wealth_estimate_div is not None:
        entry["peak_wealth_estimate_div"] = float(peak_wealth_estimate_div)
    if highlight is not None:
        entry["highlight"] = highlight
    if notes is not None:
        entry["notes"] = notes
    return _append_entry("leagues_played", entry)


def append_goal_completed(
    goal_id: str,
    activated_at: str,
    completed_at: Optional[str] = None,
    sub_goals_completed: int = 0,
    league_context: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Record a PlayerGoal that's been marked completed."""
    entry: dict = {
        "id": goal_id,
        "activated_at": activated_at,
        "completed_at": completed_at or _today(),
        "sub_goals_completed": int(sub_goals_completed),
        "appended_at": _now_iso(),
    }
    if league_context is not None:
        entry["league_context"] = league_context
    if notes is not None:
        entry["notes"] = notes
    return _append_entry("goals_completed", entry)


def append_learning_progress(
    learning_goal_id: str,
    league_id: str,
    mastery: str,
    notes: Optional[str] = None,
) -> dict:
    """Record a LearningGoal mastery bump."""
    entry: dict = {
        "id": learning_goal_id,
        "league_id": league_id,
        "advanced_at": _today(),
        "mastery_at_progression": mastery,
        "appended_at": _now_iso(),
    }
    if notes is not None:
        entry["notes"] = notes
    return _append_entry("learning_goals_progressed", entry)


def append_case_study(
    case_id: str,
    scoring: dict[str, bool],
    bumps: dict[str, float],
    notes: Optional[str] = None,
) -> dict:
    """Record a case-study scoring + the confidence bumps it produced."""
    entry: dict = {
        "id": case_id,
        "completed_at": _today(),
        "scoring": dict(scoring),
        "bumps": {k: round(float(v), 4) for k, v in bumps.items()},
        "appended_at": _now_iso(),
    }
    if notes is not None:
        entry["notes"] = notes
    return _append_entry("case_studies_completed", entry)


def append_donation(
    kind: str,
    summary: str,
    details: Optional[dict] = None,
) -> dict:
    """Record a contribution the player made to the skill's catalog.

    `kind` is free-form but the conventional values are:
      creator | system_guide_expansion | case_study | edge_taxonomy_addition |
      tool_guide_expansion | other
    """
    entry: dict = {
        "kind": kind,
        "summary": summary,
        "added_at": _today(),
        "appended_at": _now_iso(),
    }
    if details:
        entry["details"] = dict(details)
    return _append_entry("donations_to_skill", entry)


def append_session_note(title: str, body_lines: list[str]) -> None:
    """Append a narrative session summary to the body of HISTORY.md.

    Goes under the "## Sessions" header. Each call adds a new "### <title>"
    sub-section with the given bullet points.
    """
    fm, body = _read()
    section = f"\n### {title}\n\n" + "\n".join(f"- {line}" for line in body_lines) + "\n"
    new_body = body + section
    _write(fm, new_body)


# ----- read APIs -----

def get_history() -> dict[str, Any]:
    """Return the full structured history (frontmatter view)."""
    fm, _ = _read()
    return {
        "leagues_played": list(fm.get("leagues_played") or []),
        "goals_completed": list(fm.get("goals_completed") or []),
        "learning_goals_progressed": list(fm.get("learning_goals_progressed") or []),
        "case_studies_completed": list(fm.get("case_studies_completed") or []),
        "donations_to_skill": list(fm.get("donations_to_skill") or []),
    }


def has_completed_goal(goal_id: str) -> bool:
    """True if `goal_id` appears in goals_completed."""
    fm, _ = _read()
    return any(g.get("id") == goal_id for g in (fm.get("goals_completed") or []))


def leagues_count() -> int:
    """Number of leagues recorded."""
    fm, _ = _read()
    return len(fm.get("leagues_played") or [])


def has_seen_case_study(case_id: str) -> bool:
    """True if the player has already done this case study (so we don't re-run it)."""
    fm, _ = _read()
    return any(c.get("id") == case_id for c in (fm.get("case_studies_completed") or []))
