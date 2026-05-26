"""Systems guides — teaching artifacts per game mechanic.

A SystemsGuide explains a mechanic (essence crafting, breach, atlas passive
tree, hideout warriorhood) at a level Claude can use to teach the player. Each
guide carries a mastery vocabulary (not_started / learning / competent /
confident) so that LearningGoals can track player progress against the same
topic.

Lives in `data/systems/<topic>.md` as YAML-frontmatter markdown:

    ---
    schema_version: 1
    topic: essence_crafting
    game: poe2
    last_verified: 2026-05-26
    related_topics: [crafting, currency]
    prerequisites: []
    mastery_levels:
      not_started: "Doesn't know essences exist"
      learning: "Knows essences exist; needs walkthrough"
      competent: "Can essence-craft without guidance"
      confident: "Knows when to essence vs bench vs metacraft"
    attributed_to: [Ghazzy, Mathil]
    ---

    # Topic title

    [body — prose explanation of the mechanic]

The body is what Claude pulls into context when teaching the topic; the
frontmatter is what `LearningGoal` and the catalog system use for joins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


SYSTEMS_DIR = Path(__file__).parent / "data" / "systems"

MASTERY_LEVELS = ("not_started", "learning", "competent", "confident")


@dataclass
class SystemsGuide:
    topic: str                                # slug, matches filename stem
    game: str                                 # poe1 | poe2 | both
    body: str                                 # the markdown teaching content
    last_verified: Optional[str] = None       # ISO date
    related_topics: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    mastery_levels: dict[str, str] = field(default_factory=dict)
                                              # {level_name: description}; keys constrained to MASTERY_LEVELS
    attributed_to: list[str] = field(default_factory=list)  # creator names from creators.json

    def __post_init__(self) -> None:
        if self.game not in ("poe1", "poe2", "both"):
            raise ValueError(f"unknown game scope {self.game!r}")
        bad = [k for k in self.mastery_levels if k not in MASTERY_LEVELS]
        if bad:
            raise ValueError(f"unknown mastery levels: {bad}; expected one of {MASTERY_LEVELS}")


# ----- IO -----

_FM_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n(.*)$", re.DOTALL)


def _parse_file(path: Path) -> SystemsGuide:
    raw = path.read_text(encoding="utf-8")
    m = _FM_RE.match(raw)
    if not m:
        raise ValueError(f"{path}: no frontmatter block found")
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()

    topic = fm.get("topic") or path.stem
    return SystemsGuide(
        topic=topic,
        game=fm.get("game", "both"),
        body=body,
        last_verified=fm.get("last_verified"),
        related_topics=list(fm.get("related_topics") or []),
        prerequisites=list(fm.get("prerequisites") or []),
        mastery_levels=dict(fm.get("mastery_levels") or {}),
        attributed_to=list(fm.get("attributed_to") or []),
    )


def load(topic: str, base_dir: Optional[Path] = None) -> Optional[SystemsGuide]:
    base = base_dir or SYSTEMS_DIR
    path = base / f"{topic}.md"
    if not path.exists():
        return None
    return _parse_file(path)


def list_topics(base_dir: Optional[Path] = None) -> list[str]:
    base = base_dir or SYSTEMS_DIR
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.md"))


def load_all(base_dir: Optional[Path] = None) -> list[SystemsGuide]:
    return [_parse_file((base_dir or SYSTEMS_DIR) / f"{t}.md") for t in list_topics(base_dir)]


def by_game(game: str, base_dir: Optional[Path] = None) -> list[SystemsGuide]:
    return [g for g in load_all(base_dir) if g.game == game or g.game == "both"]


def by_related(topic: str, base_dir: Optional[Path] = None) -> list[SystemsGuide]:
    """Find guides that list `topic` in related_topics (one hop from `topic`)."""
    return [g for g in load_all(base_dir) if topic in g.related_topics]
