"""Join layer: numeric_id ↔ string_id ↔ display data for the passive tree.

The published tree JSON identifies each node twice:
  - `skill` (uint16): used by the web URL binary format
  - `id`    (string): used by the .build JSON format

This module loads the tree once, builds the join indexes, and exposes lookups.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Optional


DATA_DIR = Path(__file__).parent / "data"


@dataclass
class Tree:
    raw: dict[str, Any]

    @cached_property
    def nodes_by_dict_key(self) -> dict[str, dict[str, Any]]:
        """The raw `tree.nodes` dict — keyed by stringified skill hash (or 'root')."""
        return self.raw["nodes"]

    @cached_property
    def nodes_by_string_id(self) -> dict[str, dict[str, Any]]:
        """Keyed by `node.id` (e.g. 'intelligence11'). Skips nodes with id=None."""
        return {n["id"]: n for n in self.raw["nodes"].values() if n.get("id")}

    @cached_property
    def nodes_by_skill_hash(self) -> dict[int, dict[str, Any]]:
        """Keyed by `node.skill` (uint16 hash). Skips the structural 'root' node."""
        return {n["skill"]: n for n in self.raw["nodes"].values() if "skill" in n}

    @cached_property
    def skill_overrides(self) -> dict[int, dict[str, Any]]:
        return {int(k): v for k, v in self.raw["skillOverrides"].items()}

    @cached_property
    def classes(self) -> list[dict[str, Any]]:
        return self.raw["classes"]

    def class_name(self, class_id: int) -> Optional[str]:
        if 0 <= class_id < len(self.classes):
            return self.classes[class_id].get("name")
        return None

    def ascendancy_name(self, class_id: int, ascendancy_id: int) -> Optional[str]:
        """Ascendancy IDs are 1-indexed; 0 means no ascendancy chosen.

        Each ascendancy entry in the tree JSON is a dict (with name + flavour +
        layout fields). Some slots are None (placeholders for unreleased
        ascendancies — observed on Ranger's middle slot).
        """
        if ascendancy_id == 0:
            return None
        cls = self.classes[class_id] if 0 <= class_id < len(self.classes) else None
        if not cls:
            return None
        ascs = cls.get("ascendancies", [])
        idx = ascendancy_id - 1
        if not (0 <= idx < len(ascs)):
            return None
        entry = ascs[idx]
        if entry is None:
            return None
        return entry.get("name") if isinstance(entry, dict) else entry

    def node_by_hash(self, node_hash: int) -> Optional[dict[str, Any]]:
        return self.nodes_by_skill_hash.get(node_hash)

    def node_by_id(self, string_id: str) -> Optional[dict[str, Any]]:
        return self.nodes_by_string_id.get(string_id)

    def hash_to_string_id(self, node_hash: int) -> Optional[str]:
        node = self.node_by_hash(node_hash)
        return node.get("id") if node else None

    def string_id_to_hash(self, string_id: str) -> Optional[int]:
        node = self.node_by_id(string_id)
        return node.get("skill") if node else None

    def override(self, override_id: int) -> Optional[dict[str, Any]]:
        return self.skill_overrides.get(override_id)

    def override_name(self, override_id: int) -> Optional[str]:
        ov = self.override(override_id)
        return ov.get("name") if ov else None


def load_passive_tree(path: Path | str | None = None) -> Tree:
    p = Path(path) if path else DATA_DIR / "passive-tree.json"
    with open(p, encoding="utf-8") as f:
        return Tree(json.load(f))


def load_atlas_tree(path: Path | str | None = None) -> Tree:
    p = Path(path) if path else DATA_DIR / "atlas-tree.json"
    with open(p, encoding="utf-8") as f:
        return Tree(json.load(f))
