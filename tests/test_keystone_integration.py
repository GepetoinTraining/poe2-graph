"""End-to-end integration test for the keystone planning loop.

Proves the pieces compose:

  1. Load player profile (EXILE) from tmp_path
  2. Set an active PlayerGoal with sub_goals + edges
  3. Run recommend_next_action(player_fm, league_fm, character_fm)
  4. Allocate via Allocation API
  5. Emit annotated .build via build_writer
  6. Snapshot EXILE.diffs via exile.snapshot()
  7. Apply a case-study bump via guides.case_study_apply_bumps
  8. Recompose EXILE.xml + GUIDES.xml + DOCS.xml

This is the keystone test — each piece is unit-tested separately, but this
one verifies they actually integrate. If something here breaks, the
planning loop doesn't work end-to-end even if individual pieces pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import allocation  # noqa: E402
import build_writer  # noqa: E402
import docs as docs_mod  # noqa: E402
import exile  # noqa: E402
import goals  # noqa: E402
import graph as graph_mod  # noqa: E402
import guides  # noqa: E402
import resolvers  # noqa: E402


# ----- fixtures -----

@pytest.fixture
def temp_skill(tmp_path, monkeypatch):
    """Override the EXILE/ paths to point at tmp_path so the test never
    touches the real player profile."""
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    fake_exile = fake_root / "EXILE"
    fake_exile.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_exile)
    monkeypatch.setattr(exile, "DONE_FILE", fake_exile / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_root


@pytest.fixture(scope="module")
def tree_and_graph():
    """Load the actual passive tree once per module — expensive otherwise."""
    tree = resolvers.load_passive_tree()
    g = graph_mod.build_graph(tree)
    return tree, g


# ----- the keystone loop -----

def test_full_planning_loop_composes(temp_skill, tree_and_graph, tmp_path):
    """The single end-to-end test that exercises the planning loop.

    Pedro's session-2 priority #2 — this is what proves the pieces compose.
    """
    tree, g = tree_and_graph

    # ----- Step 1: bootstrap EXILE/ -----
    exile.init_skeleton()
    league_path = exile.create_league("test_league_05", game="poe2")
    char_id = "test_sorceress_01"
    char_path = exile.create_character(char_id, league_id="test_league_05", game="poe2")
    exile.set_active_character(char_id)

    # ----- Step 2: populate PLAYER.md with an active goal + sub_goals -----
    target_edges = ["posture_under_drop", "patient_pricing", "market_timing"]
    pg = goals.PlayerGoal(
        id="learn_endgame_economy",
        statement="Learn endgame economy via a mid-budget mapper",
        type="knowledge",
        horizon="leagues",
        related_edges=target_edges,
        status="active",
        sub_goals=[
            goals.SubGoal(
                id="hit_first_div",
                statement="Drop and price your first divine",
                kind="milestone",
                status="open",
                related_edges=["posture_under_drop", "patient_pricing"],
            ),
            goals.SubGoal(
                id="learn_chart_reading",
                statement="Read a poe.ninja chart as accumulation/distribution",
                kind="knowledge",
                status="open",
                depends_on=["hit_first_div"],
                related_edges=["market_timing"],
            ),
        ],
    )
    goals.add_player_goal(pg)
    goals.set_active_player_goal("learn_endgame_economy")

    # Seed knows with low confidence on some edges to make gaps detectable
    player_fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    player_fm["knows"] = {"poe2": {"posture_under_drop": 0.1, "patient_pricing": 0.0}}
    exile.write_file(exile.EXILE_DIR / "PLAYER.md", player_fm, body)

    # ----- Step 3: add a learning goal on the league -----
    lg = goals.LearningGoal(
        id="endgame_economy_basics",
        description="Learn endgame economy basics — week 1-4 strategy",
        topic="mirror_handling_v1",
        mastery="learning",
    )
    goals.add_learning_goal("test_league_05", lg)

    # Set the character to Sorceress class for the allocation step
    char_fm, char_body = exile.read_file(char_path)
    char_fm["class"] = "Sorceress"
    char_fm["ascendancy"] = "Stormweaver"
    char_fm["current_level"] = 12
    exile.write_file(char_path, char_fm, char_body)

    # ----- Step 4: run the keystone composer -----
    player_fm, _ = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    league_fm, _ = exile.read_file(league_path)
    char_fm, _ = exile.read_file(char_path)

    rec = guides.recommend_next_action(player_fm, league_fm, char_fm, game="poe2")

    # Assertions on what the composer surfaces
    assert rec.active_player_goal is not None, "active player goal not surfaced"
    assert rec.active_player_goal.id == "learn_endgame_economy"
    assert rec.next_subgoal is not None
    assert rec.next_subgoal.id == "hit_first_div"  # leaf-most available

    assert rec.next_learning_goal is not None
    assert rec.next_learning_goal.id == "endgame_economy_basics"

    assert set(rec.edges_of_interest) >= {"posture_under_drop", "patient_pricing"}

    guide_ids = {g.id for g in rec.relevant_system_guides}
    assert "mirror_handling_v1" in guide_ids

    creator_handles = {c.handle for c in rec.relevant_creators}
    assert "ben_" in creator_handles  # 0.95 on posture_under_drop

    case_ids = {cs.id for cs in rec.relevant_case_studies}
    assert "mirror_drop_day_1" in case_ids

    gap_edges = {e for e, _ in rec.confidence_gaps}
    assert "posture_under_drop" in gap_edges  # 0.1 < 0.5
    assert "patient_pricing" in gap_edges  # 0.0 < 0.5

    assert "learn_endgame_economy" in rec.rationale or "Active major" in rec.rationale

    # ----- Step 5: allocate toward a target & emit .build -----
    # Sorceress class index 2 (Witch, Sorceress, ..., depending on tree). Resolve by name.
    sorceress_class_id = None
    for i, cls in enumerate(tree.classes):
        if cls.get("name", "").lower() == "sorceress":
            sorceress_class_id = i
            break
    assert sorceress_class_id is not None, "Sorceress class not found in tree"

    alloc = allocation.Allocation.new(
        tree, g, character_class=sorceress_class_id, ascendancy=0,
    )

    # Allocate a few notables/keystones via shortest-path frontier expansion.
    # Use `frontier()` to find unallocated neighbours and pick a couple.
    frontier = alloc.frontier
    assert frontier, "Sorceress start has no frontier — graph is empty?"
    # Take three nodes to make the .build non-trivial
    targets = list(frontier)[:3]
    for h in targets:
        alloc.allocate(h, weapon_set=1)

    assert len(alloc.records) == 3, "expected 3 allocations"

    # Emit the .build with annotations sourced from the keystone composer
    build = alloc.to_build()
    annotations = {
        h: build_writer.green(f"From keystone: {rec.next_subgoal.statement}")
        for h in alloc.records
    }
    bf = build_writer.from_build(
        build, tree,
        name="Integration Test Sorceress",
        author="poe2-graph",
        description=build_writer.gold("Annotated by keystone composer"),
        annotations=annotations,
    )
    build_path = tmp_path / f"{char_id}.build"
    bf.write(build_path)

    # Validate the emitted .build round-trips cleanly
    assert build_path.exists()
    written = json.loads(build_path.read_text(encoding="utf-8"))
    assert written["name"] == "Integration Test Sorceress"
    assert "passives" in written
    assert len(written["passives"]) == 3
    # Annotations survive
    assert any(
        isinstance(p, dict) and "additional_text" in p and "keystone" in p["additional_text"]
        for p in written["passives"]
    )

    # ----- Step 6: snapshot EXILE.diffs -----
    snap_path = exile.snapshot(exile.EXILE_DIR / "PLAYER.md", label="post_allocation")
    assert snap_path.exists()
    assert snap_path.parent.name == "PLAYER.diffs"
    initial_path = exile.EXILE_DIR / "PLAYER.initial.md"
    assert initial_path.exists()  # first snapshot creates the initial

    # ----- Step 7: apply a case-study bump -----
    cs = guides.load_case_study("mirror_drop_day_1")
    assert cs is not None

    player_fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    pre_posture = (player_fm.get("knows") or {}).get("poe2", {}).get("posture_under_drop", 0.0)

    scoring = {
        "secured_the_item": True,
        "read_the_chart": True,
        "read_the_volume": False,
        "named_a_floor": True,
        "considered_option_value": True,
    }
    bumps = guides.case_study_apply_bumps(cs, scoring, player_fm, game="poe2")
    exile.write_file(exile.EXILE_DIR / "PLAYER.md", player_fm, body)

    assert "posture_under_drop" in bumps, "secured_the_item should bump posture_under_drop"
    post_posture = bumps["posture_under_drop"]
    assert post_posture > pre_posture, "bump should asymptotically increase confidence"
    assert post_posture < 1.0, "confidence never reaches 1.0"

    # ----- Step 8: recompose all three XMLs -----
    exile_xml = exile.compose_exile_xml()
    guides_xml = guides.compose_guides_xml()
    docs_xml = docs_mod.compose_docs_xml()

    # EXILE.xml shape
    assert exile_xml.startswith('<?xml')
    assert "<exile>" in exile_xml
    assert "<player " in exile_xml
    assert 'id="test_league_05"' in exile_xml
    assert f'id="{char_id}"' in exile_xml
    # Player's bumped posture_under_drop should appear in the XML
    assert "posture_under_drop" in exile_xml

    # GUIDES.xml shape
    assert "<guides>" in guides_xml
    assert "mirror_handling_v1" in guides_xml
    assert 'handle="ben_"' in guides_xml or 'handle="ghazzy"' in guides_xml

    # DOCS.xml shape — uses the real DOCS/ dir
    assert "<docs>" in docs_xml

    # ----- Step 9: snapshot after the case-study bump to capture the diff -----
    after_bump = exile.snapshot(exile.EXILE_DIR / "PLAYER.md", label="post_case_study_bump")
    assert after_bump.exists()

    diff_text = exile.diff_against_initial(exile.EXILE_DIR / "PLAYER.md")
    # Diff should be non-empty — we changed knows.poe2.posture_under_drop
    assert diff_text != ""
    assert "posture_under_drop" in diff_text

    history = exile.diff_history(exile.EXILE_DIR / "PLAYER.md")
    assert len(history) == 2, "two snapshots after the loop"


# ----- secondary integration assertion: the goal switch intervention -----

def test_keystone_handles_goal_switch_intervention(temp_skill, tree_and_graph):
    """When the player tries to switch goals while the current one has open
    sub-goals, the intervention surfaces — the keystone composer should still
    return a coherent recommendation against the *currently active* goal.
    """
    tree, g = tree_and_graph
    exile.init_skeleton()

    pg1 = goals.PlayerGoal(
        id="goal_a",
        statement="Reach pinnacle bosses on a Sorceress",
        type="mechanical",
        related_edges=["marginal_capability_thinking"],
        status="active",
        sub_goals=[
            goals.SubGoal(
                id="hit_lvl_90",
                statement="Hit level 90",
                kind="milestone",
                status="open",
                related_edges=["marginal_capability_thinking"],
            ),
        ],
    )
    goals.add_player_goal(pg1)
    goals.set_active_player_goal("goal_a")

    pg2 = goals.PlayerGoal(
        id="goal_b",
        statement="Pivot to a Warrior",
        type="identity",
        related_edges=["playstyle_authenticity"],
        status="dormant",
    )
    goals.add_player_goal(pg2)

    # Attempting to switch should surface intervention
    intervention = goals.propose_goal_switch("goal_b")
    assert intervention is not None
    assert intervention.current_goal.id == "goal_a"
    assert "level 90" in intervention.explanation().lower()

    # And the keystone should still recommend against the active (goal_a)
    player_fm, _ = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    rec = guides.recommend_next_action(player_fm)
    assert rec.active_player_goal.id == "goal_a"
    assert rec.next_subgoal.id == "hit_lvl_90"


def test_keystone_with_alloc_surfaces_character_target(temp_skill, tree_and_graph):
    """If the character has node-based goals AND an alloc is provided, the
    composer should also surface the cheapest character next-step."""
    tree, g = tree_and_graph
    exile.init_skeleton()

    char_id = "char_node_goal"
    char_path = exile.create_character(char_id, league_id="x", game="poe2")

    # Sorceress class for predictable start
    sorceress_class_id = next(
        i for i, c in enumerate(tree.classes)
        if c.get("name", "").lower() == "sorceress"
    )

    alloc = allocation.Allocation.new(
        tree, g, character_class=sorceress_class_id, ascendancy=0,
    )

    # Pick a frontier node as the character goal target
    target_hash = next(iter(alloc.frontier))
    target_node = tree.node_by_hash(target_hash)
    target_id = target_node.get("id")
    assert target_id, "frontier node has no string id"

    char_fm, char_body = exile.read_file(char_path)
    char_fm["goals_for_character"] = [
        {
            "id": "reach_first_notable",
            "kind": "reach_notable",
            "description": f"Allocate {target_id}",
            "target": target_id,
            "status": "planned",
        }
    ]
    exile.write_file(char_path, char_fm, char_body)

    # Need an active player goal so the composer doesn't short-circuit
    pg = goals.PlayerGoal(
        id="any_goal",
        statement="Any active goal",
        type="mechanical",
        status="active",
    )
    goals.add_player_goal(pg)
    goals.set_active_player_goal("any_goal")

    player_fm, _ = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    char_fm, _ = exile.read_file(char_path)
    rec = guides.recommend_next_action(player_fm, {}, char_fm, alloc=alloc)

    assert rec.next_character_target is not None
    goal, path = rec.next_character_target
    assert goal.id == "reach_first_notable"
    assert len(path) >= 1
