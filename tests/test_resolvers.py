from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import resolvers  # noqa: E402


def test_load_passive_tree():
    tree = resolvers.load_passive_tree()
    assert len(tree.classes) == 12
    # 5102 entries in the raw dict (including the structural 'root' node).
    # 5101 have a skill hash + string id; root has neither.
    assert len(tree.nodes_by_dict_key) == 5102
    assert len(tree.nodes_by_skill_hash) == 5101
    assert len(tree.skill_overrides) == 83


def test_class_and_ascendancy_lookups():
    tree = resolvers.load_passive_tree()
    assert tree.class_name(7) == "Sorceress"
    assert tree.ascendancy_name(7, 1) == "Stormweaver"   # 1-indexed
    assert tree.ascendancy_name(7, 0) is None             # 0 = no choice
    assert tree.ascendancy_name(6, 1) == "Titan"


def test_string_id_hash_join_is_bijective_for_known_overrides():
    """Spec §3 names three skill overrides; they should resolve by id."""
    tree = resolvers.load_passive_tree()
    assert tree.override_name(26297) == "Strength"
    assert tree.override_name(14927) == "Dexterity"
    assert tree.override_name(57022) == "Intelligence"


def test_string_id_to_hash_roundtrip():
    """Pick an arbitrary node and confirm both directions agree."""
    tree = resolvers.load_passive_tree()
    sample_id, sample_node = next(iter(tree.nodes_by_string_id.items()))
    skill_hash = tree.string_id_to_hash(sample_id)
    assert skill_hash == sample_node["skill"]
    assert tree.hash_to_string_id(skill_hash) == sample_id
