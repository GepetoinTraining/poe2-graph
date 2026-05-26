"""Emit `.build` JSON files for the game's BuildPlanner file watcher.

The game renders the file inline: passive routing on the tree, gem hints during
crafting, gear suggestions on inventory slots. `additional_text` supports
nested markup that the client renders with fonts/colors.

Markup format (per developer docs):
  Font:    <r>, <b>, <i>, <u>     (regular, bold, italic, underline)
  Size:    <s>, <m>, <l>          (small, medium, large)
  Color:   <red>, <green>, <blue>, <gold>, <silver>, <bronze>,
           <white>, <black>, <grey>, <yellow>, <orange>, <indigo>, <violet>
           <rgb(r,g,b)>           (custom)
  Wrap:    {text}                 (braces are mandatory; tag without {} is no-op)
  Nesting: <m>{<red>{Important}}  (font then color, both wrap the same text)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from parser import Build
from resolvers import Tree


# ----- markup helpers -----

def tag(name: str, text: str) -> str:
    """Wrap text in a single markup tag. Braces are mandatory per the format."""
    return f"<{name}>{{{text}}}"


def red(text: str) -> str: return tag("red", text)
def green(text: str) -> str: return tag("green", text)
def blue(text: str) -> str: return tag("blue", text)
def gold(text: str) -> str: return tag("gold", text)
def silver(text: str) -> str: return tag("silver", text)
def grey(text: str) -> str: return tag("grey", text)
def orange(text: str) -> str: return tag("orange", text)
def yellow(text: str) -> str: return tag("yellow", text)


def bold(text: str) -> str: return tag("b", text)
def italic(text: str) -> str: return tag("i", text)
def underline(text: str) -> str: return tag("u", text)


def small(text: str) -> str: return tag("s", text)
def medium(text: str) -> str: return tag("m", text)
def large(text: str) -> str: return tag("l", text)


def rgb(r: int, g: int, b: int, text: str) -> str:
    return f"<rgb({r},{g},{b})>{{{text}}}"


# ----- buildfile model -----

# level_interval is a single int (start level) or a [start, end] pair.
LevelInterval = Union[int, list[int]]


@dataclass
class PassiveEntry:
    id: str
    additional_text: Optional[str] = None
    level_interval: Optional[LevelInterval] = None
    weapon_set: Optional[int] = None

    def to_dict(self) -> Union[str, dict[str, Any]]:
        """A bare string when no annotations are attached; richer object otherwise."""
        if (
            self.additional_text is None
            and self.level_interval is None
            and self.weapon_set is None
        ):
            return self.id
        d: dict[str, Any] = {"id": self.id}
        if self.additional_text is not None:
            d["additional_text"] = self.additional_text
        if self.level_interval is not None:
            d["level_interval"] = self.level_interval
        if self.weapon_set is not None:
            d["weapon_set"] = self.weapon_set
        return d


@dataclass
class SupportSkill:
    id: str
    additional_text: Optional[str] = None
    level_interval: Optional[LevelInterval] = None

    def to_dict(self) -> Union[str, dict[str, Any]]:
        if self.additional_text is None and self.level_interval is None:
            return self.id
        d: dict[str, Any] = {"id": self.id}
        if self.additional_text is not None:
            d["additional_text"] = self.additional_text
        if self.level_interval is not None:
            d["level_interval"] = self.level_interval
        return d


@dataclass
class SkillEntry:
    id: str
    support_skills: list[SupportSkill] = field(default_factory=list)
    additional_text: Optional[str] = None
    level_interval: Optional[LevelInterval] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id}
        if self.support_skills:
            d["support_skills"] = [s.to_dict() for s in self.support_skills]
        if self.additional_text is not None:
            d["additional_text"] = self.additional_text
        if self.level_interval is not None:
            d["level_interval"] = self.level_interval
        return d


@dataclass
class InventorySlot:
    inventory_id: str
    additional_text: Optional[str] = None
    unique: Optional[str] = None          # specific unique item name to recommend
    hint: Optional[str] = None            # short inline hint rendered next to the slot
    level_interval: Optional[LevelInterval] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"inventory_id": self.inventory_id}
        if self.additional_text is not None:
            d["additional_text"] = self.additional_text
        if self.unique is not None:
            d["unique"] = self.unique
        if self.hint is not None:
            d["hint"] = self.hint
        if self.level_interval is not None:
            d["level_interval"] = self.level_interval
        return d


@dataclass
class BuildFile:
    name: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    ascendancy: Optional[str] = None
    passives: list[PassiveEntry] = field(default_factory=list)
    skills: list[SkillEntry] = field(default_factory=list)
    inventory_slots: list[InventorySlot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.name is not None: d["name"] = self.name
        if self.author is not None: d["author"] = self.author
        if self.description is not None: d["description"] = self.description
        if self.ascendancy is not None: d["ascendancy"] = self.ascendancy
        if self.passives:
            d["passives"] = [p.to_dict() for p in self.passives]
        if self.skills:
            d["skills"] = [s.to_dict() for s in self.skills]
        if self.inventory_slots:
            d["inventory_slots"] = [s.to_dict() for s in self.inventory_slots]
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write(self, path: Path | str) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


# ----- conversion + validation -----

def ascendancy_key(tree: Tree, class_id: int, ascendancy_id: int) -> Optional[str]:
    """The ascendancy key used by .build (e.g. 'Sorceress1'), built from the
    tree JSON's ascendancyId convention. Returns None if no ascendancy chosen.
    """
    if ascendancy_id == 0:
        return None
    class_name = tree.class_name(class_id)
    if not class_name:
        return None
    return f"{class_name}{ascendancy_id}"


def from_build(
    build: Build,
    tree: Tree,
    name: str = "",
    author: str = "",
    description: str = "",
    annotations: Optional[dict[int, str]] = None,
    level_intervals: Optional[dict[int, list[int]]] = None,
) -> BuildFile:
    """Convert a parsed URL (Build) into a BuildFile.

    `annotations` maps node_hash -> additional_text string (use markup helpers).
    `level_intervals` maps node_hash -> [min_level, max_level] for progression hints.
    """
    annotations = annotations or {}
    level_intervals = level_intervals or {}

    passives: list[PassiveEntry] = []
    for r in build.records:
        string_id = tree.hash_to_string_id(r.node_hash)
        if not string_id:
            continue  # node has no .build-format id; skip
        passives.append(PassiveEntry(
            id=string_id,
            additional_text=annotations.get(r.node_hash),
            level_interval=level_intervals.get(r.node_hash),
            weapon_set=r.weapon_set,
        ))

    return BuildFile(
        name=name or f"{tree.class_name(build.character_class) or 'Build'} build",
        author=author,
        description=description,
        ascendancy=ascendancy_key(tree, build.character_class, build.ascendancy),
        passives=passives,
    )


class ValidationError(ValueError):
    pass


def validate(buildfile: BuildFile, tree: Tree) -> list[str]:
    """Return a list of validation warnings; empty if everything resolves."""
    warnings: list[str] = []
    for p in buildfile.passives:
        if not tree.node_by_id(p.id):
            warnings.append(f"unknown passive id: {p.id!r}")
        if p.level_interval is not None:
            # LevelInterval is Union[int, list[int]] — bare int is legal (start level only).
            if isinstance(p.level_interval, list):
                if len(p.level_interval) != 2 or p.level_interval[0] > p.level_interval[1]:
                    warnings.append(f"malformed level_interval on {p.id!r}: {p.level_interval}")
            elif not isinstance(p.level_interval, int):
                warnings.append(f"malformed level_interval on {p.id!r}: {p.level_interval!r} (expected int or [start, end])")
    return warnings


def assert_valid(buildfile: BuildFile, tree: Tree) -> None:
    issues = validate(buildfile, tree)
    if issues:
        raise ValidationError("buildfile validation failed:\n  " + "\n  ".join(issues))
