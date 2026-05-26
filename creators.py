"""Creators module — back-compat shim now backed by per-handle YAMLs.

Original implementation read `data/creators.json`. The goals+guides subspec
moved each creator into its own YAML at `data/guides/creators/<handle>.yaml`.
The richer schema (transmits, style_tags, disposition) lives in
`guides.Creator`. This module preserves the older entry points
(`ContentCreator`, `load_all`, `by_name`, `by_specialty`, `by_game`,
`save_all`) so existing call sites and tests don't break.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# The legacy single-file location stays defined for tests that pass a custom path.
CREATORS_PATH = Path(__file__).parent / "data" / "creators.json"

# The current home for creator data.
import guides


@dataclass
class ContentCreator:
    """Legacy facade over guides.Creator."""
    name: str
    channels: dict[str, str] = field(default_factory=dict)
    main_page: Optional[str] = None
    build_hub: Optional[str] = None
    live_status_url: Optional[str] = None
    specialties: list[str] = field(default_factory=list)
    games: list[str] = field(default_factory=list)
    style_notes: Optional[str] = None
    primary_language: Optional[str] = None

    @classmethod
    def from_creator(cls, c: guides.Creator) -> "ContentCreator":
        return cls(
            name=c.display_name,
            channels=dict(c.channels),
            main_page=c.home_url,
            build_hub=c.build_hub,
            live_status_url=c.live_status_url,
            specialties=list(c.specialties),
            games=list(c.games),
            style_notes=c.style_notes,
            primary_language=c.primary_language,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "ContentCreator":
        return cls(
            name=d["name"],
            channels=dict(d.get("channels") or {}),
            main_page=d.get("main_page"),
            build_hub=d.get("build_hub"),
            live_status_url=d.get("live_status_url"),
            specialties=list(d.get("specialties") or []),
            games=list(d.get("games") or []),
            style_notes=d.get("style_notes"),
            primary_language=d.get("primary_language"),
        )

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.channels:
            d["channels"] = self.channels
        for key in ("main_page", "build_hub", "live_status_url", "style_notes", "primary_language"):
            v = getattr(self, key)
            if v is not None:
                d[key] = v
        if self.specialties:
            d["specialties"] = self.specialties
        if self.games:
            d["games"] = self.games
        return d


def load_all(path: Optional[Path] = None) -> list[ContentCreator]:
    """Load all creators. If `path` points at a legacy creators.json, read it;
    otherwise read the per-handle YAMLs in `data/guides/creators/`.
    """
    if path is not None and path.exists() and path.suffix == ".json":
        # Legacy single-file path (kept for test compatibility)
        import json
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [ContentCreator.from_dict(c) for c in raw.get("creators", [])]
    # Default: per-handle YAMLs
    return [ContentCreator.from_creator(c) for c in guides.list_creators()]


def by_name(name: str, path: Optional[Path] = None) -> Optional[ContentCreator]:
    target = name.lower()
    for c in load_all(path):
        if c.name.lower() == target:
            return c
    return None


def by_specialty(tag: str, game: Optional[str] = None, path: Optional[Path] = None) -> list[ContentCreator]:
    tag_low = tag.lower()
    out: list[ContentCreator] = []
    for c in load_all(path):
        if game is not None and game not in c.games:
            continue
        if any(s.lower() == tag_low for s in c.specialties):
            out.append(c)
    return out


def by_game(game: str, path: Optional[Path] = None) -> list[ContentCreator]:
    return [c for c in load_all(path) if game in c.games]


def save_all(creators: list[ContentCreator], path: Optional[Path] = None) -> Path:
    """Save back to the legacy single-file format. Tests use this for round-trip."""
    import json
    p = path or CREATORS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "creators": [c.to_dict() for c in creators],
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
