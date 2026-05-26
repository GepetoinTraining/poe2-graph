"""HISTORY.md append-only journal tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exile  # noqa: E402
import history  # noqa: E402


def _temp_exile(tmp_path, monkeypatch):
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    fake_exile = fake_root / "EXILE"
    fake_exile.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_exile)
    monkeypatch.setattr(exile, "DONE_FILE", fake_exile / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_exile


def test_init_creates_history_with_skeleton(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    p = history.init()
    assert p.exists()
    fm, body = exile.read_file(p)
    assert fm["schema_version"] == 1
    assert fm["leagues_played"] == []
    assert fm["goals_completed"] == []
    assert "History" in body


def test_init_is_idempotent(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.init()
    history.append_league("test_league", started="2026-05-29")
    history.init()  # should not wipe
    fm, _ = exile.read_file(history._path())
    assert len(fm["leagues_played"]) == 1


def test_append_league(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    entry = history.append_league(
        league_id="0.5_return_of_the_ancients",
        started="2026-05-29",
        ended="2026-09-15",
        final_character_id="storm_main",
        final_level=92,
        peak_wealth_estimate_div=350.5,
        highlight="first mirror-tier project completed",
    )
    assert entry["id"] == "0.5_return_of_the_ancients"
    assert entry["final_level"] == 92
    assert entry["peak_wealth_estimate_div"] == 350.5
    assert "appended_at" in entry

    fm, _ = exile.read_file(history._path())
    assert len(fm["leagues_played"]) == 1


def test_append_goal_completed(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_goal_completed(
        goal_id="learn_endgame_economy",
        activated_at="2026-05-29",
        completed_at="2026-06-15",
        sub_goals_completed=5,
        league_context="0.5_return_of_the_ancients",
    )
    fm, _ = exile.read_file(history._path())
    goals = fm["goals_completed"]
    assert len(goals) == 1
    assert goals[0]["id"] == "learn_endgame_economy"
    assert goals[0]["sub_goals_completed"] == 5


def test_append_learning_progress(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_learning_progress(
        learning_goal_id="essence_crafting",
        league_id="0.5_return_of_the_ancients",
        mastery="competent",
    )
    fm, _ = exile.read_file(history._path())
    assert fm["learning_goals_progressed"][0]["id"] == "essence_crafting"
    assert fm["learning_goals_progressed"][0]["mastery_at_progression"] == "competent"


def test_append_case_study_with_bumps(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_case_study(
        case_id="mirror_drop_day_1",
        scoring={"secured_the_item": True, "read_the_chart": False},
        bumps={"posture_under_drop": 0.4, "market_timing": 0.0},
    )
    fm, _ = exile.read_file(history._path())
    cs = fm["case_studies_completed"][0]
    assert cs["id"] == "mirror_drop_day_1"
    assert cs["scoring"]["secured_the_item"] is True
    assert cs["bumps"]["posture_under_drop"] == 0.4


def test_append_donation(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_donation(
        kind="creator",
        summary="Added Ziz/Zizaran to catalog after Pedro flagged in session 2 handover",
        details={"handle": "zizaran", "language": "en"},
    )
    fm, _ = exile.read_file(history._path())
    d = fm["donations_to_skill"][0]
    assert d["kind"] == "creator"
    assert d["details"]["handle"] == "zizaran"


def test_get_history_returns_all_sections(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_league("L1", "2026-01-01")
    history.append_goal_completed("G1", "2026-01-02")
    h = history.get_history()
    assert set(h.keys()) == {
        "leagues_played", "goals_completed", "learning_goals_progressed",
        "case_studies_completed", "donations_to_skill",
    }
    assert h["leagues_played"][0]["id"] == "L1"
    assert h["goals_completed"][0]["id"] == "G1"


def test_has_completed_goal(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    assert not history.has_completed_goal("X")
    history.append_goal_completed("X", "2026-01-01")
    assert history.has_completed_goal("X")


def test_leagues_count(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    assert history.leagues_count() == 0
    history.append_league("L1", "2026-01-01")
    history.append_league("L2", "2026-04-01")
    assert history.leagues_count() == 2


def test_has_seen_case_study(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    assert not history.has_seen_case_study("mirror_drop_day_1")
    history.append_case_study("mirror_drop_day_1", {"x": True}, {"posture": 0.4})
    assert history.has_seen_case_study("mirror_drop_day_1")


def test_append_session_note_appends_to_body(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_session_note(
        "Session 3 — 2026-05-29",
        ["League 0.5 onboarding complete", "First Stormweaver leveled to 75"],
    )
    _, body = exile.read_file(history._path())
    assert "Session 3" in body
    assert "Stormweaver" in body


def test_append_multiple_entries_preserves_order(tmp_path, monkeypatch):
    _temp_exile(tmp_path, monkeypatch)
    history.append_league("A", "2026-01-01")
    history.append_league("B", "2026-04-01")
    history.append_league("C", "2026-08-01")
    fm, _ = exile.read_file(history._path())
    assert [l["id"] for l in fm["leagues_played"]] == ["A", "B", "C"]
