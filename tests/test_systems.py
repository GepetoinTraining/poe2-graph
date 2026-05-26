from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import systems  # noqa: E402


def test_load_existing_topic():
    guide = systems.load("essence_crafting")
    assert guide is not None
    assert guide.topic == "essence_crafting"
    assert guide.game == "poe2"
    assert "not_started" in guide.mastery_levels
    assert "confident" in guide.mastery_levels


def test_load_missing_topic():
    assert systems.load("definitely_not_a_topic") is None


def test_list_topics_returns_seed_set():
    topics = systems.list_topics()
    assert "essence_crafting" in topics
    assert "atlas_passive_tree" in topics


def test_load_all():
    all_guides = systems.load_all()
    assert len(all_guides) >= 2
    topic_names = [g.topic for g in all_guides]
    assert "essence_crafting" in topic_names


def test_by_game_includes_both_and_specific():
    poe2_guides = systems.by_game("poe2")
    # essence_crafting is "poe2"; both essence_crafting + atlas_passive_tree
    # are tagged "poe2", so we expect both
    assert len(poe2_guides) >= 2


def test_by_related_finds_cross_references():
    crafting_related = systems.by_related("crafting")
    # essence_crafting lists "crafting" in related_topics
    topics = [g.topic for g in crafting_related]
    assert "essence_crafting" in topics


def test_mastery_level_validation(tmp_path):
    """A guide with an unknown mastery level fails to construct."""
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\n"
        "topic: bad\n"
        "game: poe2\n"
        "mastery_levels:\n"
        "  invented: x\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    try:
        systems._parse_file(bad)
    except ValueError:
        return
    raise AssertionError("expected ValueError on unknown mastery level")


def test_game_scope_validation(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\n"
        "topic: bad\n"
        "game: hexgame\n"
        "mastery_levels: {}\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    try:
        systems._parse_file(bad)
    except ValueError:
        return
    raise AssertionError("expected ValueError on unknown game scope")
