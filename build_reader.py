"""Parse `.build` JSON files (the format the game's file watcher consumes).

Schema is documented at pathofexile.com/developer/docs/game. This module is
forgiving: it accepts the documented shape and tolerates unknown extra fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


@dataclass
class PassiveEntry:
    """One entry under `passives`. Either a bare string id or a richer object."""
    id: str
    additional_text: Optional[str] = None
    level_interval: Optional[list[int]] = None
    weapon_set: Optional[int] = None


@dataclass
class SupportSkill:
    id: str
    additional_text: Optional[str] = None


@dataclass
class SkillEntry:
    id: str
    support_skills: list[SupportSkill] = field(default_factory=list)
    additional_text: Optional[str] = None


@dataclass
class InventorySlot:
    inventory_id: str
    additional_text: Optional[str] = None


@dataclass
class BuildFile:
    name: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    ascendancy: Optional[str] = None
    passives: list[PassiveEntry] = field(default_factory=list)
    skills: list[SkillEntry] = field(default_factory=list)
    inventory_slots: list[InventorySlot] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _coerce_passive(entry: Union[str, dict[str, Any]]) -> PassiveEntry:
    if isinstance(entry, str):
        return PassiveEntry(id=entry)
    return PassiveEntry(
        id=entry["id"],
        additional_text=entry.get("additional_text"),
        level_interval=entry.get("level_interval"),
        weapon_set=entry.get("weapon_set"),
    )


def _coerce_support(entry: Union[str, dict[str, Any]]) -> SupportSkill:
    if isinstance(entry, str):
        return SupportSkill(id=entry)
    return SupportSkill(id=entry["id"], additional_text=entry.get("additional_text"))


def _coerce_skill(entry: dict[str, Any]) -> SkillEntry:
    return SkillEntry(
        id=entry["id"],
        support_skills=[_coerce_support(s) for s in entry.get("support_skills", [])],
        additional_text=entry.get("additional_text"),
    )


def _coerce_inventory(entry: dict[str, Any]) -> InventorySlot:
    return InventorySlot(
        inventory_id=entry["inventory_id"],
        additional_text=entry.get("additional_text"),
    )


def parse(data: dict[str, Any]) -> BuildFile:
    return BuildFile(
        name=data.get("name"),
        author=data.get("author"),
        description=data.get("description"),
        ascendancy=data.get("ascendancy"),
        passives=[_coerce_passive(p) for p in data.get("passives", [])],
        skills=[_coerce_skill(s) for s in data.get("skills", [])],
        inventory_slots=[_coerce_inventory(s) for s in data.get("inventory_slots", [])],
        raw=data,
    )


def load(path: Path | str) -> BuildFile:
    with open(path, encoding="utf-8") as f:
        return parse(json.load(f))
