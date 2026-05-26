"""Integration test against GGG's reference `.build` file.

The file at D:\\poe2-graph\\example.build is the Titan Warrior example from
pathofexile.com/developer/docs/game. Treat this as the canonical conformance
target: anything the reader/writer can't handle from this file is a real bug.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_reader  # noqa: E402
import build_writer  # noqa: E402
import resolvers  # noqa: E402


EXAMPLE = ROOT / "example.build"


def test_example_exists():
    assert EXAMPLE.exists(), "GGG's example.build must be at repo root"


def test_example_parses_clean():
    bf = build_reader.load(EXAMPLE)
    assert bf.name == "Titan Warrior"
    assert bf.author == "Grinding Gear Games"
    assert bf.ascendancy == "Warrior1"
    assert len(bf.passives) == 34
    assert len(bf.skills) == 4
    assert len(bf.inventory_slots) == 9


def test_example_passives_all_resolve_in_tree():
    """Every passive id GGG ships in the reference must exist in the tree JSON.

    If this ever fails, either the tree data is stale or GGG renamed nodes —
    investigate before relaxing the assertion.
    """
    bf = build_reader.load(EXAMPLE)
    tree = resolvers.load_passive_tree()
    missing = [p.id for p in bf.passives if not tree.node_by_id(p.id)]
    assert missing == [], f"unresolved passive ids: {missing}"


def test_example_ascendancy_node_ids_resolve():
    """Ascendancy nodes use a PascalCase id convention distinct from regular
    snake_case nodes. Confirm both resolve via the same lookup.
    """
    bf = build_reader.load(EXAMPLE)
    tree = resolvers.load_passive_tree()
    asc_ids = [p.id for p in bf.passives if p.id.startswith("Ascendancy")]
    assert len(asc_ids) == 2  # spec'd example has 2 ascendancy passives
    for aid in asc_ids:
        node = tree.node_by_id(aid)
        assert node is not None
        assert node.get("ascendancyId")


def test_example_validates_through_writer():
    """Round-trip via writer's BuildFile model produces zero warnings."""
    bf = build_reader.load(EXAMPLE)
    tree = resolvers.load_passive_tree()
    bfw = build_writer.BuildFile(
        name=bf.name,
        author=bf.author,
        description=bf.description,
        ascendancy=bf.ascendancy,
        passives=[
            build_writer.PassiveEntry(
                id=p.id,
                additional_text=p.additional_text,
                level_interval=p.level_interval,
                weapon_set=p.weapon_set,
            )
            for p in bf.passives
        ],
    )
    assert build_writer.validate(bfw, tree) == []


def test_example_mixed_passive_forms_preserved():
    """Some passives are bare strings, others are rich objects — both shapes
    should survive the reader unchanged.
    """
    bf = build_reader.load(EXAMPLE)
    bare = [p for p in bf.passives if p.additional_text is None]
    rich = [p for p in bf.passives if p.additional_text is not None]
    assert len(bare) > 0
    assert len(rich) > 0
    # Rich ones should preserve the nested markup verbatim.
    for p in rich:
        assert "{" in p.additional_text
        assert "}" in p.additional_text


def test_example_skills_with_mixed_support_forms():
    """Support skills can be bare strings or {id, additional_text} objects."""
    bf = build_reader.load(EXAMPLE)
    boneshatter = next(s for s in bf.skills if "Boneshatter" in s.id)
    # Boneshatter has two annotated support skills.
    assert len(boneshatter.support_skills) == 2
    assert all(s.additional_text for s in boneshatter.support_skills)
    earthquake = next(s for s in bf.skills if "Earthquake" in s.id)
    # Earthquake's supports are bare strings.
    assert len(earthquake.support_skills) == 2
    assert all(s.additional_text is None for s in earthquake.support_skills)
