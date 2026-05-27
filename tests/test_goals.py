from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exile  # noqa: E402
from graph import resolvers  # noqa: E402
from graph import network as graph_mod  # noqa: E402
from graph.allocation import Allocation  # noqa: E402
import goals  # noqa: E402


def _temp_skill(tmp_path, monkeypatch):
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_root / "EXILE")
    monkeypatch.setattr(exile, "DONE_FILE", fake_root / "EXILE" / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_root


def _world():
    tree = resolvers.load_passive_tree()
    g = graph_mod.build_graph(tree)
    return tree, g


def test_goal_rejects_unknown_kind():
    try:
        goals.Goal(id="x", kind="invented", description="...")
    except ValueError:
        return
    raise AssertionError("expected ValueError on bad kind")


def test_goal_roundtrip_dict():
    g = goals.Goal(
        id="ancestral_bond",
        kind="reach_keystone",
        description="reach Ancestral Bond",
        target=45202,
    )
    d = g.to_dict()
    assert d["kind"] == "reach_keystone"
    assert d["target"] == 45202
    g2 = goals.Goal.from_dict(d)
    assert g2.id == g.id
    assert g2.target == g.target


def test_add_and_list_goals(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("stormweaver", league_id="0.5", game="poe2")

    goals.add_goal("stormweaver", goals.Goal(
        id="ab", kind="reach_keystone",
        description="get Ancestral Bond", target=45202,
    ))
    goals.add_goal("stormweaver", goals.Goal(
        id="lvl90", kind="level_milestone",
        description="hit level 90", target=90,
    ))

    listed = goals.list_goals("stormweaver")
    assert len(listed) == 2
    assert {g.id for g in listed} == {"ab", "lvl90"}


def test_add_duplicate_goal_raises(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")
    goals.add_goal("c", goals.Goal(id="ab", kind="freeform", description="x"))
    try:
        goals.add_goal("c", goals.Goal(id="ab", kind="freeform", description="y"))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_mark_done(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")
    goals.add_goal("c", goals.Goal(id="ab", kind="freeform", description="x"))
    done = goals.mark_done("c", "ab")
    assert done.status == "done"
    assert done.progress == 1.0
    assert done.achieved_at is not None


def test_active_goals_filters_completed(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")
    goals.add_goal("c", goals.Goal(id="a", kind="freeform", description="x"))
    goals.add_goal("c", goals.Goal(id="b", kind="freeform", description="y"))
    goals.mark_done("c", "a")
    active = goals.active_goals("c")
    assert [g.id for g in active] == ["b"]


def test_goal_progress_for_allocated_keystone(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")

    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress", "Stormweaver")
    alloc.extend_to(45202)  # allocate Ancestral Bond

    goal = goals.Goal(
        id="ab", kind="reach_keystone",
        description="...", target=45202,
    )
    assert goals.goal_progress(goal, alloc) == 1.0


def test_next_actionable_finds_cheapest_keystone_goal(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")

    tree, g = _world()
    alloc = Allocation.new(tree, g, "Witch")  # share start with Sorceress

    goals.add_goal("c", goals.Goal(
        id="ab", kind="reach_keystone",
        description="...", target=45202,
    ))

    nxt = goals.next_actionable("c", alloc)
    assert nxt is not None
    goal, path = nxt
    assert goal.id == "ab"
    assert len(path) >= 2  # at least start + target


def test_next_actionable_returns_none_when_no_node_goals(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("c", league_id="0.5", game="poe2")
    goals.add_goal("c", goals.Goal(id="lvl", kind="level_milestone", description="...", target=90))

    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    assert goals.next_actionable("c", alloc) is None
