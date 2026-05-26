"""Tests for the goals+guides subspec surfaces in guides.py.

Covers: edge taxonomy loader, system_guide loader, case_study loader + bump
application, creator loader (incl. opt-out), GUIDES.xml composer.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exile  # noqa: E402
import guides  # noqa: E402


def _temp_skill(tmp_path, monkeypatch):
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_root / "EXILE")
    monkeypatch.setattr(exile, "DONE_FILE", fake_root / "EXILE" / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_root


# ----- edge taxonomy -----

def test_edge_taxonomy_loads_all_seed_edges():
    edges = guides.load_edge_taxonomy()
    names = {e.name for e in edges}
    assert "posture_under_drop" in names
    assert "market_timing" in names
    assert "miss_economy" in names
    assert len(edges) >= 12


def test_edge_names_set_matches_loader():
    assert "patient_pricing" in guides.edge_names()


# ----- system guides -----

def test_list_system_guides_finds_seed():
    sgs = guides.list_system_guides()
    assert any(g.id == "mirror_handling_v1" for g in sgs)


def test_load_system_guide_carries_metadata():
    sg = guides.load_system_guide("mirror_handling_v1")
    assert sg is not None
    assert sg.game == "poe2"
    assert sg.difficulty == "advanced"
    assert "posture_under_drop" in sg.transmits
    assert "mirror_drop_day_1" in sg.case_studies
    assert any(p.get("edge") == "market_timing" for p in sg.prerequisites)


def test_system_guides_for_edge_filters():
    matching = guides.system_guides_for_edge("posture_under_drop")
    assert any(g.id == "mirror_handling_v1" for g in matching)
    nada = guides.system_guides_for_edge("definitely_not_an_edge")
    assert nada == []


# ----- case studies -----

def test_load_case_study_full_shape():
    cs = guides.load_case_study("mirror_drop_day_1")
    assert cs is not None
    assert cs.guide == "mirror_handling_v1"
    assert "posture_under_drop" in cs.edge_tags
    assert len(cs.scoring_dimensions) >= 4
    assert cs.tag_bumps_per_dimension_hit == 0.4
    assert cs.follow_up is not None
    assert cs.follow_up.delay_hours == 72


def test_case_study_present_renders_scenario_and_decision():
    cs = guides.load_case_study("mirror_drop_day_1")
    text = guides.case_study_present(cs)
    assert "Mirror" in text
    assert "Decision point" in text


def test_case_study_apply_bumps_per_dimension(tmp_path, monkeypatch):
    """Hitting two of four dimensions should bump exactly those two edges."""
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    p = exile.EXILE_DIR / "PLAYER.md"
    fm, body = exile.read_file(p)

    cs = guides.load_case_study("mirror_drop_day_1")
    scoring = {
        "secured_the_item": True,
        "read_the_chart": False,
        "read_the_volume": False,
        "named_a_floor": True,
        "considered_option_value": False,
    }
    bumps = guides.case_study_apply_bumps(cs, scoring, fm, game="poe2")
    # Only the hit dimensions yield bumps
    assert "posture_under_drop" in bumps
    assert "patient_pricing" in bumps
    assert "market_timing" not in bumps
    # Confidence is asymptotic from 0.0
    assert 0.0 < bumps["posture_under_drop"] < 1.0


# ----- creators -----

def test_load_creator_full_shape():
    c = guides.load_creator("ghazzy")
    assert c is not None
    assert c.display_name == "Ghazzy"
    assert "youtube" in c.channels
    assert "minions" in c.specialties
    assert "poe2" in c.games
    assert c.disposition == "public"


def test_list_creators_excludes_opted_out(tmp_path):
    """Opt-out creators should be filtered out of list_creators."""
    base = tmp_path / "creators"
    base.mkdir()
    (base / "yes_handle.yaml").write_text(
        'handle: yes_handle\ndisplay_name: "Yes"\ndisposition: public\n',
        encoding="utf-8",
    )
    (base / "no_handle.yaml").write_text(
        'handle: no_handle\ndisplay_name: "No"\ndisposition: opted_out\n',
        encoding="utf-8",
    )
    listed = guides.list_creators(base_dir=base)
    handles = {c.handle for c in listed}
    assert "yes_handle" in handles
    assert "no_handle" not in handles


def test_creators_who_transmit_filters_by_confidence():
    # Ghazzy has investing_vs_gambling at 0.7
    high = guides.creators_who_transmit("investing_vs_gambling", min_confidence=0.5)
    assert any(c.handle == "ghazzy" for c in high)
    # Same edge at 0.99 confidence threshold = none of our seeds qualify
    none = guides.creators_who_transmit("investing_vs_gambling", min_confidence=0.99)
    assert none == []


# ----- GUIDES.xml composer -----

def test_compose_guides_xml_includes_seeds():
    xml = guides.compose_guides_xml()
    assert "<guides>" in xml
    assert 'id="mirror_handling_v1"' in xml
    assert 'name="posture_under_drop"' in xml
    assert 'handle="ghazzy"' in xml
    assert "<edge_taxonomy>" in xml
    assert "</guides>" in xml


def test_write_guides_xml_to_tmp(tmp_path):
    out = tmp_path / "GUIDES.xml"
    guides.write_guides_xml(out_path=out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "<guides>" in text
    assert "mirror_handling_v1" in text


# ----- keystone: recommend_next_action -----

def _player_fm_with_active_goal(edges: list[str], knows: dict | None = None) -> dict:
    """Build a player_fm with one active PlayerGoal and one open SubGoal."""
    return {
        "schema_version": 1,
        "knows": {"poe2": knows or {}},
        "player_goals": [
            {
                "id": "learn_endgame_economy",
                "statement": "Learn endgame economy through a mid-budget mapper",
                "type": "knowledge",
                "horizon": "leagues",
                "measurable": False,
                "related_edges": edges,
                "progress": 0.2,
                "status": "active",
                "sub_goals": [
                    {
                        "id": "first_divine_drop",
                        "statement": "Drop and price your first divine",
                        "kind": "milestone",
                        "status": "open",
                        "progress": 0.0,
                        "related_edges": edges,
                    }
                ],
            }
        ],
    }


def test_recommend_next_action_no_active_goal_returns_safe_default():
    rec = guides.recommend_next_action({}, {}, {})
    assert rec.active_player_goal is None
    assert rec.next_subgoal is None
    assert rec.edges_of_interest == []
    assert "No active major player goal" in rec.rationale


def test_recommend_next_action_surfaces_active_subgoal_and_edges():
    pfm = _player_fm_with_active_goal(["posture_under_drop", "market_timing"])
    rec = guides.recommend_next_action(pfm)
    assert rec.active_player_goal is not None
    assert rec.active_player_goal.id == "learn_endgame_economy"
    assert rec.next_subgoal is not None
    assert rec.next_subgoal.id == "first_divine_drop"
    assert "posture_under_drop" in rec.edges_of_interest
    assert "market_timing" in rec.edges_of_interest


def test_recommend_next_action_matches_system_guide_to_edges():
    pfm = _player_fm_with_active_goal(["posture_under_drop", "patient_pricing"])
    rec = guides.recommend_next_action(pfm)
    guide_ids = {g.id for g in rec.relevant_system_guides}
    assert "mirror_handling_v1" in guide_ids


def test_recommend_next_action_surfaces_creators_who_transmit():
    pfm = _player_fm_with_active_goal(["posture_under_drop"])
    rec = guides.recommend_next_action(pfm)
    handles = {c.handle for c in rec.relevant_creators}
    assert "ben_" in handles  # 0.95 on posture_under_drop


def test_recommend_next_action_surfaces_case_studies():
    pfm = _player_fm_with_active_goal(["posture_under_drop", "option_value_vs_face_value"])
    rec = guides.recommend_next_action(pfm)
    case_ids = {cs.id for cs in rec.relevant_case_studies}
    assert "mirror_drop_day_1" in case_ids


def test_recommend_next_action_reports_confidence_gaps():
    pfm = _player_fm_with_active_goal(
        ["posture_under_drop", "market_timing", "patient_pricing"],
        knows={"posture_under_drop": 0.8, "market_timing": 0.1},
    )
    rec = guides.recommend_next_action(pfm)
    gap_edges = {edge for edge, _ in rec.confidence_gaps}
    # market_timing (0.1) and patient_pricing (0.0) are gaps; posture_under_drop (0.8) is not
    assert "market_timing" in gap_edges
    assert "patient_pricing" in gap_edges
    assert "posture_under_drop" not in gap_edges
    # Lowest gap first
    assert rec.confidence_gaps[0][1] <= rec.confidence_gaps[-1][1]


def test_recommend_next_action_picks_lowest_mastery_learning_goal():
    pfm = {"player_goals": []}
    lfm = {
        "learning_goals": [
            {"id": "essence_crafting", "description": "Learn essence crafting", "mastery": "competent"},
            {"id": "boss_routing", "description": "Learn boss routing", "mastery": "not_started"},
            {"id": "trade", "description": "Learn trade", "mastery": "confident"},  # filtered
        ]
    }
    rec = guides.recommend_next_action(pfm, lfm, {})
    assert rec.next_learning_goal is not None
    # 'learning' > 'not_started' > 'competent' — but we only have not_started and competent
    # so not_started wins (order index 1 < 2)
    assert rec.next_learning_goal.id == "boss_routing"


def test_recommend_next_action_filters_creators_by_game():
    """A poe1-only creator must not appear in a poe2 recommendation."""
    pfm = _player_fm_with_active_goal(["posture_under_drop"])
    rec = guides.recommend_next_action(pfm, game="poe2")
    for c in rec.relevant_creators:
        assert "poe2" in c.games


def test_recommend_next_action_blocked_subgoals_yield_none_actionable():
    """If the only open sub-goal depends on an undone one, it's blocked → no actionable."""
    pfm = {
        "player_goals": [
            {
                "id": "complex_goal",
                "statement": "Multi-step goal",
                "type": "knowledge",
                "horizon": "leagues",
                "related_edges": ["market_timing"],
                "status": "active",
                "sub_goals": [
                    {"id": "step_a", "statement": "First", "kind": "milestone", "status": "open"},
                    {
                        "id": "step_b",
                        "statement": "Second",
                        "kind": "milestone",
                        "status": "open",
                        "depends_on": ["step_a"],
                    },
                ],
            }
        ]
    }
    rec = guides.recommend_next_action(pfm)
    # step_a is the leaf-most available; step_b is blocked
    assert rec.next_subgoal is not None
    assert rec.next_subgoal.id == "step_a"
