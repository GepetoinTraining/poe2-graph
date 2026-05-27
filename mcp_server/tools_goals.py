"""Goal-system tools: recommend_next_action, render_goal_tracker, switch intervention.

`recommend_next_action` is the flagship — composes the active player goal,
next actionable sub-goal, league learning focus, and the relevant system
guides / creators / case studies for tonight's session.
"""

from __future__ import annotations

from typing import Any, Optional

import exile
import goals
import guides

from ._serialize import to_jsonable


def _player_md_exists() -> bool:
    return (exile.EXILE_DIR / "PLAYER.md").exists()


def recommend_next_action(
    *, game: str = "poe2",
) -> dict[str, Any]:
    """The keystone composer. Reads PLAYER + active LEAGUE + active CHARACTER
    frontmatter from disk and runs `guides.recommend_next_action`.

    Args:
      game: "poe2" (default) or "poe1" — selects which game's active character to use.

    Returns the ActionRecommendation as a dict, plus the resolved-state paths
    so the caller knows which league/character contributed.
    """
    player_fm, _ = _read_player()
    league_fm, league_path = _read_active_league(game=game)
    character_fm, character_path = _read_active_character(game=game)

    rec = guides.recommend_next_action(
        player_fm=player_fm,
        league_fm=league_fm,
        character_fm=character_fm,
        game=game,
    )
    return {
        "recommendation": to_jsonable(rec),
        "resolved": {
            "league_path": str(league_path) if league_path else None,
            "character_path": str(character_path) if character_path else None,
        },
    }


def active_goal() -> Optional[dict[str, Any]]:
    """Return the active PlayerGoal as a dict, or None if there isn't one."""
    if not _player_md_exists():
        return None
    return to_jsonable(goals.active_player_goal())


def next_actionable() -> Optional[dict[str, Any]]:
    """Return the next-actionable sub-goal of the active PlayerGoal, or None."""
    if not _player_md_exists():
        return None
    active = goals.active_player_goal()
    if active is None:
        return None
    return to_jsonable(active.next_actionable())


def render_goal_tracker() -> Optional[str]:
    """WoW-tracker text rendering of the active PlayerGoal. None if no active goal."""
    if not _player_md_exists():
        return None
    active = goals.active_player_goal()
    if active is None:
        return None
    return goals.render_goal_tracker(active)


def propose_goal_switch(new_goal_id: str) -> Optional[dict[str, Any]]:
    """Surface a switch intervention if the active goal has open sub-goals.

    Returns None when the switch is clean (no intervention needed). Otherwise
    returns the intervention with the player-facing prompt + open sub-goals.
    """
    if not _player_md_exists():
        return None
    intervention = goals.propose_goal_switch(new_goal_id)
    if intervention is None:
        return None
    return {
        "current_goal_id": intervention.current_goal.id,
        "current_goal_statement": intervention.current_goal.statement,
        "proposed_goal_id": intervention.proposed_goal_id,
        "open_subgoal_count": len(intervention.open_subgoals),
        "open_subgoals": [to_jsonable(sg) for sg in intervention.open_subgoals],
        "current_actionable": to_jsonable(intervention.current_actionable),
        "prompt": intervention.prompt,
        "explanation": intervention.explanation(),
    }


# ---- internals: read state from disk ----

def _read_player() -> tuple[dict, Optional[str]]:
    path = exile.EXILE_DIR / "PLAYER.md"
    if not path.exists():
        return {}, None
    fm, _ = exile.read_file(path)
    return fm or {}, str(path)


def _read_active_league(*, game: str) -> tuple[dict, Optional[str]]:
    """Find the league for the active character of `game`. Falls back to the
    most-recently-modified LEAGUE_*.md when no active character is set."""
    cid = exile.active_character(game=game)
    if cid:
        cpath = exile.EXILE_DIR / f"CHARACTER_{cid}.md"
        if cpath.exists():
            cfm, _ = exile.read_file(cpath)
            league_id = cfm.get("league_id") if isinstance(cfm, dict) else None
            if league_id:
                lpath = exile.EXILE_DIR / f"LEAGUE_{league_id}.md"
                if lpath.exists():
                    fm, _ = exile.read_file(lpath)
                    return fm or {}, str(lpath)
    # Fallback: most-recent LEAGUE_ file
    if exile.EXILE_DIR.exists():
        leagues = sorted(
            exile.EXILE_DIR.glob("LEAGUE_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for lpath in leagues:
            if lpath.name.endswith(".initial.md"):
                continue
            fm, _ = exile.read_file(lpath)
            return fm or {}, str(lpath)
    return {}, None


def _read_active_character(*, game: str) -> tuple[dict, Optional[str]]:
    cid = exile.active_character(game=game)
    if not cid:
        return {}, None
    path = exile.EXILE_DIR / f"CHARACTER_{cid}.md"
    if not path.exists():
        return {}, None
    fm, _ = exile.read_file(path)
    return fm or {}, str(path)
