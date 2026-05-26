"""Tests for goal decomposition + single-active rule + switch intervention."""

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


def _beat_ubers_subgoals() -> list[goals.SubGoal]:
    """Reusable test fixture — the canonical 'beat ubers' decomposition."""
    return [
        goals.SubGoal(
            id="dps_threshold",
            statement="10M+ effective DPS against pinnacle archetype",
            kind="stat_threshold",
            target={"stat": "effective_dps_vs_pinnacle", "value": 10_000_000},
            progress=0.4,
            status="in_progress",
        ),
        goals.SubGoal(
            id="ehp_threshold",
            statement="8000+ effective health pool",
            kind="stat_threshold",
            target={"stat": "effective_health_pool", "value": 8000},
            progress=1.0,
            status="done",
        ),
        goals.SubGoal(
            id="build_ready",
            statement="Build composite — stats cleared",
            kind="composite",
            depends_on=["dps_threshold", "ehp_threshold"],
        ),
        goals.SubGoal(
            id="pinnacle_atlas",
            statement="Atlas tree allocated for pinnacle access",
            kind="atlas_progression",
            progress=0.47,
            status="in_progress",
        ),
        goals.SubGoal(
            id="fragment_stockpile",
            statement="Stockpile 3 sets of pinnacle fragments",
            kind="economic",
            target={"resource": "pinnacle_fragments", "count": 3},
            progress=0.0,
        ),
        goals.SubGoal(
            id="mechanics_known",
            statement="Mechanics learned for each pinnacle boss",
            kind="knowledge",
            learning_goal_id="learn_pinnacle_mechanics",
        ),
        goals.SubGoal(
            id="first_attempt",
            statement="First pinnacle attempt (win or learn)",
            kind="milestone",
            depends_on=["build_ready", "pinnacle_atlas", "fragment_stockpile", "mechanics_known"],
        ),
    ]


# ----- SubGoal type -----

def test_subgoal_rejects_unknown_kind():
    try:
        goals.SubGoal(id="x", statement="x", kind="invented")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_subgoal_rejects_unknown_status():
    try:
        goals.SubGoal(id="x", statement="x", kind="milestone", status="weird")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_subgoal_roundtrip():
    sg = goals.SubGoal(
        id="dps",
        statement="10M DPS",
        kind="stat_threshold",
        target={"stat": "dps", "value": 10_000_000},
        depends_on=["pre"],
        progress=0.4,
        related_edges=["marginal_capability_thinking"],
    )
    d = sg.to_dict()
    sg2 = goals.SubGoal.from_dict(d)
    assert sg2.id == "dps"
    assert sg2.target["value"] == 10_000_000
    assert sg2.depends_on == ["pre"]


# ----- next_actionable traversal -----

def test_next_actionable_returns_leaf_with_no_deps():
    pg = goals.PlayerGoal(
        id="g", statement="...", type="mechanical",
        sub_goals=_beat_ubers_subgoals(),
    )
    nxt = pg.next_actionable()
    assert nxt is not None
    # dps_threshold is in_progress at 0.4; pinnacle_atlas is in_progress at 0.47
    # Both are available (no deps); pinnacle_atlas wins on higher progress
    assert nxt.id == "pinnacle_atlas"


def test_next_actionable_blocked_when_deps_unmet():
    """build_ready and first_attempt should not be reachable yet."""
    pg = goals.PlayerGoal(
        id="g", statement="...", type="mechanical",
        sub_goals=_beat_ubers_subgoals(),
    )
    nxt = pg.next_actionable()
    assert nxt.id != "build_ready"  # depends_on includes dps_threshold (still in_progress)
    assert nxt.id != "first_attempt"


def test_next_actionable_unblocks_after_deps_done():
    """When ehp + dps are both done, build_ready becomes available."""
    subs = _beat_ubers_subgoals()
    subs[0].status = "done"; subs[0].progress = 1.0  # dps_threshold done
    # ehp already done in fixture
    pg = goals.PlayerGoal(
        id="g", statement="...", type="mechanical", sub_goals=subs,
    )
    # build_ready is now available (deps met); it has progress 0 but is open
    # pinnacle_atlas is still at 0.47 in_progress, higher progress → wins
    nxt = pg.next_actionable()
    assert nxt is not None
    assert nxt.id == "pinnacle_atlas"


def test_next_actionable_returns_none_when_all_done():
    sub = goals.SubGoal(id="a", statement="x", kind="milestone", status="done", progress=1.0)
    pg = goals.PlayerGoal(id="g", statement="...", type="identity", sub_goals=[sub])
    assert pg.next_actionable() is None


def test_open_subgoals_excludes_done_and_blocked():
    pg = goals.PlayerGoal(
        id="g", statement="...", type="mechanical",
        sub_goals=_beat_ubers_subgoals(),
    )
    open_ids = {sg.id for sg in pg.open_subgoals()}
    assert "ehp_threshold" not in open_ids  # done
    assert "dps_threshold" in open_ids        # in_progress
    assert "build_ready" in open_ids          # open (even though blocked by deps)
    # build_ready and first_attempt are open but have unmet deps; they're
    # still in "open_subgoals" — open_subgoals is status-based, not
    # dependency-aware. The dep check happens in next_actionable.


# ----- single-active enforcement -----

def test_set_active_is_exclusive(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(id="a", statement="A", type="economic"))
    goals.add_player_goal(goals.PlayerGoal(id="b", statement="B", type="mechanical"))

    goals.set_active_player_goal("a")
    assert goals.active_player_goal().id == "a"

    goals.set_active_player_goal("b")
    assert goals.active_player_goal().id == "b"

    # `a` should have been demoted to dormant
    a = [g for g in goals.list_player_goals() if g.id == "a"][0]
    assert a.status == "dormant"


def test_complete_and_abandon(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(id="a", statement="A", type="economic"))
    goals.add_player_goal(goals.PlayerGoal(id="b", statement="B", type="mechanical"))

    goals.complete_player_goal("a")
    a = [g for g in goals.list_player_goals() if g.id == "a"][0]
    assert a.status == "completed"
    assert a.progress == 1.0

    goals.abandon_player_goal("b")
    b = [g for g in goals.list_player_goals() if g.id == "b"][0]
    assert b.status == "abandoned"


# ----- sub-goal lifecycle -----

def test_mark_subgoal_done_recomputes_parent_progress(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    pg = goals.PlayerGoal(
        id="ubers", statement="Beat ubers", type="mechanical",
        sub_goals=[
            goals.SubGoal(id="a", statement="A", kind="milestone"),
            goals.SubGoal(id="b", statement="B", kind="milestone"),
        ],
    )
    goals.add_player_goal(pg)
    goals.mark_subgoal_done("ubers", "a")
    refreshed = [g for g in goals.list_player_goals() if g.id == "ubers"][0]
    assert refreshed.progress == 0.5  # 1.0 + 0.0 averaged


def test_update_subgoal_progress(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    pg = goals.PlayerGoal(
        id="ubers", statement="Beat ubers", type="mechanical",
        sub_goals=[goals.SubGoal(id="dps", statement="DPS", kind="stat_threshold")],
    )
    goals.add_player_goal(pg)
    sg = goals.update_subgoal_progress("ubers", "dps", 0.4)
    assert sg.progress == 0.4
    assert sg.status == "in_progress"
    sg = goals.update_subgoal_progress("ubers", "dps", 1.0)
    assert sg.status == "done"


# ----- switch intervention -----

def test_propose_switch_returns_none_when_no_active(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(id="a", statement="A", type="economic"))
    assert goals.propose_goal_switch("b") is None


def test_propose_switch_returns_none_when_no_open_subgoals(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(
        id="a", statement="A", type="economic",
        sub_goals=[goals.SubGoal(id="x", statement="x", kind="milestone", status="done", progress=1.0)],
    ))
    goals.set_active_player_goal("a")
    assert goals.propose_goal_switch("b") is None


def test_propose_switch_returns_intervention_when_active_has_open(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    goals.add_player_goal(goals.PlayerGoal(
        id="ubers", statement="Beat ubers", type="mechanical",
        sub_goals=_beat_ubers_subgoals(),
    ))
    goals.set_active_player_goal("ubers")
    intervention = goals.propose_goal_switch("new_thing")
    assert intervention is not None
    assert intervention.current_goal.id == "ubers"
    assert intervention.proposed_goal_id == "new_thing"
    assert intervention.current_actionable is not None
    assert len(intervention.open_subgoals) >= 1
    text = intervention.explanation()
    assert "Beat ubers" in text
    assert "Open sub-goals" in text


# ----- WoW tracker rendering -----

def test_render_goal_tracker_shows_markers_and_progress(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    pg = goals.PlayerGoal(
        id="ubers", statement="Beat ubers this league", type="mechanical",
        sub_goals=_beat_ubers_subgoals(),
    )
    text = goals.render_goal_tracker(pg)
    assert "[ACTIVE GOAL] Beat ubers this league" in text
    assert "●" in text  # ehp_threshold done
    assert "◯" in text  # at least one available open sub-goal
    assert "◌" in text  # at least one blocked sub-goal
    assert "[NEXT ACTION]" in text
    # Stat threshold rendered with current/target
    assert "10.0M" in text or "10M" in text


def test_render_no_subgoals_prompts_for_decomposition(tmp_path, monkeypatch):
    pg = goals.PlayerGoal(
        id="empty", statement="Big goal, no decomposition yet", type="identity",
    )
    text = goals.render_goal_tracker(pg)
    assert "decompose" in text.lower()
