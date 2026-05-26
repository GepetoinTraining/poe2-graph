"""Tests for the typed PlayerGoal / LeagueGoal additions in goals.py."""

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


# ----- PlayerGoal -----

def test_player_goal_validates_type():
    try:
        goals.PlayerGoal(id="x", statement="x", type="invented")
    except ValueError:
        return
    raise AssertionError("expected ValueError on bad type")


def test_player_goal_validates_horizon():
    try:
        goals.PlayerGoal(id="x", statement="x", type="identity", horizon="centuries")
    except ValueError:
        return
    raise AssertionError("expected ValueError on bad horizon")


def test_player_goal_roundtrip(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    g = goals.PlayerGoal(
        id="mirror_tier_year",
        statement="Hit Mirror tier this year",
        type="economic",
        horizon="years",
        measurable=True,
        measure="Net worth in Mirrors >= 1",
        related_edges=["market_timing", "currency_velocity", "flow_anticipation"],
    )
    goals.add_player_goal(g)
    listed = goals.list_player_goals()
    assert len(listed) == 1
    assert listed[0].id == "mirror_tier_year"
    assert "market_timing" in listed[0].related_edges


def test_player_goal_progress_is_asymptotic(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(
        id="mt", statement="...", type="economic",
    ))
    g1 = goals.update_player_progress("mt", 0.5)
    assert g1.progress == 0.5
    g2 = goals.update_player_progress("mt", 0.5)
    assert g2.progress == 0.75


# ----- LeagueGoal -----

def test_league_goal_roundtrip(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    lg = goals.LeagueGoal(
        id="atlas_complete",
        statement="Finish the full Atlas questline",
        type="mechanical",
        measurable=True,
        deadline="league_week_3",
    )
    goals.add_league_goal("0.5", lg)
    listed = goals.list_league_goals("0.5")
    assert listed[0].id == "atlas_complete"
    assert listed[0].deadline == "league_week_3"


def test_league_goal_progress_asymptotic(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_league("0.5", game="poe2")
    goals.add_league_goal("0.5", goals.LeagueGoal(
        id="atl", statement="...", type="mechanical",
    ))
    goals.update_league_progress("0.5", "atl", 0.5)
    listed = goals.list_league_goals("0.5")
    assert listed[0].progress == 0.5


# ----- goal-goal composition -----

def test_goal_friction_detects_hc_vs_high_risk():
    pg = goals.PlayerGoal(
        id="hc_three", statement="Main hardcore for three leagues",
        type="identity", horizon="leagues",
    )
    lg = goals.LeagueGoal(
        id="san_deep", statement="Push deepest Sanctum delve possible",
        type="mechanical",
    )
    frictions = goals.goal_friction([pg], [lg])
    assert len(frictions) == 1
    assert frictions[0].player_goal_id == "hc_three"
    assert frictions[0].league_goal_id == "san_deep"


def test_goal_friction_clean_when_aligned():
    pg = goals.PlayerGoal(
        id="mt", statement="Hit Mirror tier", type="economic", horizon="years",
    )
    lg = goals.LeagueGoal(
        id="t15", statement="Speedfarm T15s by week 2", type="economic",
    )
    assert goals.goal_friction([pg], [lg]) == []


def test_related_edges_extracted():
    pg = goals.PlayerGoal(
        id="x", statement="...", type="economic",
        related_edges=["market_timing", "patient_pricing"],
    )
    assert goals.related_edges_for_goal(pg) == ["market_timing", "patient_pricing"]
