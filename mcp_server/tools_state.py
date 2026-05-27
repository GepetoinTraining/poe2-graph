"""Player / league / character state tools."""

from __future__ import annotations

from typing import Any, Optional

import exile

from ._serialize import to_jsonable


def read_player() -> dict[str, Any]:
    """Return PLAYER.md frontmatter + body (or {} if not onboarded)."""
    path = exile.EXILE_DIR / "PLAYER.md"
    if not path.exists():
        return {"exists": False, "frontmatter": {}, "body": ""}
    fm, body = exile.read_file(path)
    return {
        "exists": True,
        "path": str(path),
        "frontmatter": to_jsonable(fm) or {},
        "body": body,
    }


def list_characters(game: Optional[str] = None) -> list[str]:
    """Character ids, optionally filtered by game ("poe1" | "poe2")."""
    return exile.list_characters(game=game)


def list_leagues() -> list[str]:
    """League ids."""
    return exile.list_leagues()


def active_character(game: Optional[str] = None) -> Optional[str]:
    """The active character id for `game` (or any game if unspecified)."""
    return exile.active_character(game=game)


def active_characters() -> dict[str, str]:
    """{game: character_id} for each game that has an active character."""
    return exile.active_characters()


def read_character(character_id: str) -> dict[str, Any]:
    """Frontmatter + body for one character."""
    path = exile.EXILE_DIR / f"CHARACTER_{character_id}.md"
    if not path.exists():
        return {"exists": False, "character_id": character_id}
    fm, body = exile.read_file(path)
    return {
        "exists": True,
        "character_id": character_id,
        "path": str(path),
        "frontmatter": to_jsonable(fm) or {},
        "body": body,
    }


def read_active_character(game: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Frontmatter + body of the active character of `game`. None if no active."""
    cid = exile.active_character(game=game)
    if cid is None:
        return None
    return read_character(cid)


def read_league(league_id: str) -> dict[str, Any]:
    """Frontmatter + body for one league."""
    path = exile.EXILE_DIR / f"LEAGUE_{league_id}.md"
    if not path.exists():
        return {"exists": False, "league_id": league_id}
    fm, body = exile.read_file(path)
    return {
        "exists": True,
        "league_id": league_id,
        "path": str(path),
        "frontmatter": to_jsonable(fm) or {},
        "body": body,
    }


def set_active_character(character_id: str) -> dict[str, Any]:
    """Mark `character_id` active. Per-game exclusivity: same-game characters
    become dormant; characters in other games are untouched."""
    exile.set_active_character(character_id)
    return {"ok": True, "active_character": character_id}
