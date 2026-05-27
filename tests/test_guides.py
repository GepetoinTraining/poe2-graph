from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph import resolvers  # noqa: E402
from graph import network as graph_mod  # noqa: E402
import guides  # noqa: E402
from catalog import gem as gem_module  # noqa: E402


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


# ===== gem-name validation =====

def test_intent_with_real_gem_names_passes():
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="real-gems",
        character_class="Sorceress",
        ascendancy="Stormweaver",
        main_skill="Spark",                  # real skill gem
        support_gems=["Acrimony"],           # real support gem
        extra_skills=["Herald of Ash"],      # real spirit gem (also in skill)
    )
    warnings = guides.validate(intent, tree)
    assert warnings == []


def test_intent_with_unknown_main_skill_warns():
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="x",
        character_class="Sorceress",
        main_skill="Fakeball The Phantom Skill",
    )
    warnings = guides.validate(intent, tree)
    assert any("Fakeball" in w and "main skill" in w for w in warnings)


def test_intent_with_unknown_support_warns():
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="x",
        character_class="Sorceress",
        support_gems=["DefinitelyNotASupport"],
    )
    warnings = guides.validate(intent, tree)
    assert any("DefinitelyNotASupport" in w and "support gem" in w for w in warnings)


def test_intent_with_unknown_extra_skill_warns():
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="x",
        character_class="Sorceress",
        extra_skills=["Phantom Skill Of Doom"],
    )
    warnings = guides.validate(intent, tree)
    assert any("Phantom Skill Of Doom" in w and "extra skill" in w for w in warnings)


def test_main_skill_resolves_as_spirit_gem():
    """Heralds live in the spirit catalog but should be valid as a main_skill."""
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="herald-build",
        character_class="Sorceress",
        main_skill="Herald of Ash",          # spirit gem
    )
    warnings = guides.validate(intent, tree)
    assert warnings == []


def test_validate_gems_false_skips_all_gem_checks():
    tree, _ = _world()
    gem_module.clear_cache()
    intent = guides.GuideIntent(
        source="x",
        character_class="Sorceress",
        main_skill="Total Nonsense",
        support_gems=["More Nonsense"],
        extra_skills=["Even More"],
    )
    warnings = guides.validate(intent, tree, validate_gems=False)
    assert warnings == []


def test_gem_validation_skipped_when_catalog_unreachable(monkeypatch):
    """Cold cache + no network must not emit false-positive 'unknown gem' warnings."""
    tree, _ = _world()
    gem_module.clear_cache()

    def fail_load(gem_class):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr("guides.load_catalog", fail_load)

    intent = guides.GuideIntent(
        source="x",
        character_class="Sorceress",
        main_skill="Anything",
        support_gems=["Whatever", "Stuff"],
        extra_skills=["More"],
    )
    warnings = guides.validate(intent, tree)
    # No gem warnings — checks were silently skipped because catalogs failed to load
    assert not any("gem" in w.lower() or "skill" in w.lower() for w in warnings)
