from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import resolvers  # noqa: E402
import graph as graph_mod  # noqa: E402
import guides  # noqa: E402


def _world():
    tree = resolvers.load_passive_tree()
    g = graph_mod.build_graph(tree)
    return tree, g


def test_intent_with_unknown_class_warns():
    tree, _ = _world()
    intent = guides.GuideIntent(
        source="test",
        character_class="Nonexistent",
    )
    warnings = guides.validate(intent, tree)
    assert any("Nonexistent" in w for w in warnings)


def test_intent_ascendancy_must_match_class():
    tree, _ = _world()
    intent = guides.GuideIntent(
        source="test",
        character_class="Sorceress",
        ascendancy="Titan",  # belongs to Warrior, not Sorceress
    )
    warnings = guides.validate(intent, tree)
    assert any("Titan" in w for w in warnings)


def test_intent_valid_passes():
    tree, _ = _world()
    intent = guides.GuideIntent(
        source="test",
        character_class="Sorceress",
        ascendancy="Stormweaver",
    )
    assert guides.validate(intent, tree) == []


def test_node_resolved_by_display_name():
    tree, _ = _world()
    intent = guides.GuideIntent(
        source="test",
        character_class="Sorceress",
        ascendancy="Stormweaver",
        key_keystones=["Ancestral Bond"],
    )
    # Should resolve cleanly
    assert guides.validate(intent, tree) == []


def test_node_unknown_warns():
    tree, _ = _world()
    intent = guides.GuideIntent(
        source="test",
        character_class="Sorceress",
        key_notables=["Definitely Not A Real Notable"],
    )
    warnings = guides.validate(intent, tree)
    assert any("Definitely Not" in w for w in warnings)


def test_intent_to_allocation_routes_through_targets():
    tree, g = _world()
    intent = guides.GuideIntent(
        source="hypothetical spark guide",
        character_class="Sorceress",
        ascendancy="Stormweaver",
        key_keystones=["Ancestral Bond"],
        damage_type="lightning",
        crit_or_not="crit",
    )
    alloc = guides.intent_to_allocation(intent, tree, g)
    assert alloc.character_class == 7  # Sorceress
    assert alloc.ascendancy == 1       # Stormweaver
    # Ancestral Bond hash = 45202; should be allocated
    assert 45202 in alloc.records


def test_intent_to_allocation_with_no_targets_is_empty():
    tree, g = _world()
    intent = guides.GuideIntent(
        source="vague guide",
        character_class="Sorceress",
        ascendancy="Stormweaver",
    )
    alloc = guides.intent_to_allocation(intent, tree, g)
    assert len(alloc) == 0


def test_intent_to_allocation_handles_multiple_targets():
    """The Steiner-tree route should connect multiple notables."""
    tree, g = _world()
    # Pick three real keystones/notables by name
    intent = guides.GuideIntent(
        source="multi-target test",
        character_class="Sorceress",
        ascendancy="Stormweaver",
        key_keystones=["Ancestral Bond"],
        key_notables=["Raw Power"],  # known notable name
    )
    warnings = guides.validate(intent, tree)
    assert warnings == []  # both should resolve

    alloc = guides.intent_to_allocation(intent, tree, g)
    assert len(alloc) >= 2
