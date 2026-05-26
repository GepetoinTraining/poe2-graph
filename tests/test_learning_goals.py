from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exile  # noqa: E402
import goals  # noqa: E402


def _temp_skill(tmp_path, monkeypatch):
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_root / "EXILE")
    monkeypatch.setattr(exile, "DONE_FILE", fake_root / "EXILE" / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_root


def test_learning_goal_validates_mastery():
    try:
        goals.LearningGoal(id="x", description="...", mastery="grandmaster")
    except ValueError:
        return
    raise AssertionError("expected ValueError on invalid mastery")


def test_learning_goal_roundtrip():
    g = goals.LearningGoal(
        id="essence_crafting",
        description="learn how essences work",
        topic="essence_crafting",
        related_creators=["Ghazzy", "Mathil"],
    )
    d = g.to_dict()
    assert d["topic"] == "essence_crafting"
    assert d["related_creators"] == ["Ghazzy", "Mathil"]
    g2 = goals.LearningGoal.from_dict(d)
    assert g2.mastery == "not_started"


def test_add_and_list_learning_goals(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")

    goals.add_learning_goal("0.5", goals.LearningGoal(
        id="essence_crafting",
        description="learn essence crafting",
        topic="essence_crafting",
    ))
    goals.add_learning_goal("0.5", goals.LearningGoal(
        id="hideout_warrior",
        description="become a hideout warrior",
    ))

    listed = goals.list_learning_goals("0.5")
    assert {g.id for g in listed} == {"essence_crafting", "hideout_warrior"}


def test_advance_mastery_climbs_scale(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    goals.add_learning_goal("0.5", goals.LearningGoal(
        id="ec", description="essence crafting",
    ))

    g1 = goals.advance_mastery("0.5", "ec")
    assert g1.mastery == "learning"
    g2 = goals.advance_mastery("0.5", "ec")
    assert g2.mastery == "competent"
    g3 = goals.advance_mastery("0.5", "ec")
    assert g3.mastery == "confident"
    # Past confident — stays at confident
    g4 = goals.advance_mastery("0.5", "ec")
    assert g4.mastery == "confident"


def test_set_mastery_explicit(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    goals.add_learning_goal("0.5", goals.LearningGoal(
        id="ec", description="essence crafting",
    ))
    updated = goals.set_mastery("0.5", "ec", "competent")
    assert updated.mastery == "competent"
    assert updated.last_advanced is not None


def test_add_progress_note(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    goals.add_learning_goal("0.5", goals.LearningGoal(
        id="ec", description="essence crafting",
    ))
    goals.add_progress_note("0.5", "ec", "tried first essence in act 4")
    goals.add_progress_note("0.5", "ec", "stacked a t1 essence after kalandra's touch")
    listed = goals.list_learning_goals("0.5")
    assert len(listed[0].progress_notes) == 2
    assert "act 4" in listed[0].progress_notes[0]


def test_duplicate_learning_goal_raises(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    goals.add_learning_goal("0.5", goals.LearningGoal(id="ec", description="..."))
    try:
        goals.add_learning_goal("0.5", goals.LearningGoal(id="ec", description="..."))
    except ValueError:
        return
    raise AssertionError("expected ValueError on duplicate")
