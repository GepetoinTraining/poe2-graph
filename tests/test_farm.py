"""Tests for the farm package — farming cycle lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import store
import farm
import graphfmt


# ---- fixture ----------------------------------------------------------------

def _conn(tmp_path):
    return store.get_connection(str(tmp_path / "farm_test.db"))


# ---- 1-3: declare_cycle -----------------------------------------------------

def test_declare_cycle_inserts_root_and_inputs(tmp_path):
    conn = _conn(tmp_path)
    cycle = farm.declare_cycle(
        conn,
        cycle_id="cycle_001",
        farm_target="sekhemas_relics",
        lottery_targets=["mirror", "temporalis"],
        inputs=[{"item": "orb_of_chaos", "quantity": 200}],
        notes="test run",
    )
    assert cycle["cycle_id"] == "cycle_001"
    assert cycle["status"] == "DECLARED"
    assert cycle["farm_target"] == "sekhemas_relics"
    assert "mirror" in cycle["lottery_targets"]
    assert "temporalis" in cycle["lottery_targets"]
    assert len(cycle["inputs"]) == 1
    assert cycle["inputs"][0]["item"] == "orb_of_chaos"
    assert cycle["inputs"][0]["quantity"] == 200
    assert cycle["notes"] == "test run"


def test_declare_cycle_no_lottery_no_inputs(tmp_path):
    conn = _conn(tmp_path)
    cycle = farm.declare_cycle(conn, farm_target="breach_splinters")
    assert cycle["status"] == "DECLARED"
    assert cycle["lottery_targets"] == []
    assert cycle["inputs"] == []


def test_declare_cycle_auto_generated_ids_are_unique(tmp_path):
    conn = _conn(tmp_path)
    c1 = farm.declare_cycle(conn, farm_target="breach_splinters")
    c2 = farm.declare_cycle(conn, farm_target="ritual_omens")
    assert c1["cycle_id"] != c2["cycle_id"]


# ---- 4-5: open_cycle --------------------------------------------------------

def test_open_cycle_transitions_to_active(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_002", farm_target="sekhemas_relics")
    cycle = farm.open_cycle(conn, "cycle_002", currency_snapshot={"chaos": 500, "divine": 5})
    assert cycle["status"] == "ACTIVE"
    assert cycle["opened_at"] != ""


def test_open_cycle_on_active_raises(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_003", farm_target="sekhemas_relics")
    farm.open_cycle(conn, "cycle_003")
    try:
        farm.open_cycle(conn, "cycle_003")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---- 6-8: record_output -----------------------------------------------------

def test_record_output_appends_to_active_cycle(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_004", farm_target="sekhemas_relics")
    farm.open_cycle(conn, "cycle_004")
    out = farm.record_output(conn, "cycle_004", "Item Class: Waystones\nRarity: Rare")
    assert out["node_id"].startswith("cycle_004_output_")
    cycle = farm.get_cycle(conn, "cycle_004")
    assert len(cycle["outputs"]) == 1


def test_record_output_on_declared_raises(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_005", farm_target="sekhemas_relics")
    try:
        farm.record_output(conn, "cycle_005", "some item")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_record_output_on_closed_raises(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_006", farm_target="sekhemas_relics")
    farm.open_cycle(conn, "cycle_006")
    farm.close_cycle(conn, "cycle_006")
    try:
        farm.record_output(conn, "cycle_006", "some item")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---- 9-13: classify_outputs -------------------------------------------------

def test_classify_outputs_no_craft_graph_all_gold_pile(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_010", farm_target="breach")
    farm.open_cycle(conn, "cycle_010")
    farm.record_output(conn, "cycle_010", "some item", source="clipboard")
    farm.record_output(conn, "cycle_010", "another item")

    result = farm.classify_outputs(conn, "cycle_010")
    assert result["classified"] == 2
    assert result["price_me"] == 0
    assert result["gold_pile"] == 2


def test_classify_outputs_matching_pattern_becomes_price_me(tmp_path):
    conn = _conn(tmp_path)
    # Insert a craft graph mod node + edge
    store.insert_node(
        conn, "mod_life_regen", "craft", "craft.graph",
        '<mod pattern="life regeneration per second">life regen mod</mod>',
    )
    store.insert_edge(
        conn,
        source_id="craft.graph",
        target_id="mod_life_regen",
        graph_id="craft.graph",
        edge_type="mod_market_value",
        weight=1.0,
        payload="<edge/>",
    )

    farm.declare_cycle(conn, cycle_id="cycle_011", farm_target="breach")
    farm.open_cycle(conn, "cycle_011")

    # Manually insert an output node with matching mods
    out_id = "cycle_011_output_0"
    store.insert_node(
        conn, out_id, "farm", "cycle_011",
        '<output classification="" timestamp="2026-05-27T10:00:00Z">'
        "<item>item text</item>"
        "<mods>life regeneration per second</mods>"
        "</output>",
    )

    result = farm.classify_outputs(conn, "cycle_011")
    assert result["price_me"] == 1
    assert result["gold_pile"] == 0

    cycle = farm.get_cycle(conn, "cycle_011")
    assert cycle["outputs"][0]["classification"] == "price_me"


def test_classify_outputs_multiple_patterns_one_match_is_enough(tmp_path):
    conn = _conn(tmp_path)
    for i, pat in enumerate(["fire damage", "cold damage"]):
        store.insert_node(
            conn, f"mod_{i}", "craft", "craft.graph",
            f'<mod pattern="{pat}">mod</mod>',
        )
        store.insert_edge(
            conn,
            source_id="craft.graph",
            target_id=f"mod_{i}",
            graph_id="craft.graph",
            edge_type="mod_market_value",
            weight=0.8,
            payload="<edge/>",
        )

    farm.declare_cycle(conn, cycle_id="cycle_012", farm_target="breach")
    farm.open_cycle(conn, "cycle_012")

    out_id = "cycle_012_output_0"
    store.insert_node(
        conn, out_id, "farm", "cycle_012",
        '<output classification="" timestamp="2026-05-27T10:00:00Z">'
        "<item>item</item>"
        "<mods>fire damage to attacks</mods>"
        "</output>",
    )

    result = farm.classify_outputs(conn, "cycle_012")
    assert result["price_me"] == 1


def test_classify_outputs_threshold_filter(tmp_path):
    conn = _conn(tmp_path)
    # Edge weight 0.3 is below the default 0.5 threshold
    store.insert_node(
        conn, "mod_weak", "craft", "craft.graph",
        '<mod pattern="extra life">weak mod</mod>',
    )
    store.insert_edge(
        conn,
        source_id="craft.graph",
        target_id="mod_weak",
        graph_id="craft.graph",
        edge_type="mod_market_value",
        weight=0.3,
        payload="<edge/>",
    )

    farm.declare_cycle(conn, cycle_id="cycle_013", farm_target="breach")
    farm.open_cycle(conn, "cycle_013")

    out_id = "cycle_013_output_0"
    store.insert_node(
        conn, out_id, "farm", "cycle_013",
        '<output classification="" timestamp="2026-05-27T10:00:00Z">'
        "<item>item</item>"
        "<mods>extra life</mods>"
        "</output>",
    )

    result = farm.classify_outputs(conn, "cycle_013")
    # Pattern is below threshold -> classified as gold_pile
    assert result["gold_pile"] == 1
    assert result["price_me"] == 0


def test_classify_outputs_returns_correct_counts(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(
        conn, "mod_chaos", "craft", "craft.graph",
        '<mod pattern="chaos damage">chaos mod</mod>',
    )
    store.insert_edge(
        conn,
        source_id="craft.graph",
        target_id="mod_chaos",
        graph_id="craft.graph",
        edge_type="mod_market_value",
        weight=1.0,
        payload="<edge/>",
    )

    farm.declare_cycle(conn, cycle_id="cycle_014", farm_target="breach")
    farm.open_cycle(conn, "cycle_014")

    for i, mods_text in enumerate(["chaos damage", "fire dmg", "ice dmg"]):
        store.insert_node(
            conn, f"cycle_014_output_{i}", "farm", "cycle_014",
            f'<output classification="" timestamp="2026-05-27T10:0{i}:00Z">'
            f"<item>item</item>"
            f"<mods>{mods_text}</mods>"
            f"</output>",
        )

    result = farm.classify_outputs(conn, "cycle_014")
    assert result["classified"] == 3
    assert result["price_me"] == 1
    assert result["gold_pile"] == 2


# ---- 14-16: reconcile_cycle -------------------------------------------------

def test_reconcile_no_refs_gap_equals_output_count(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_020", farm_target="breach")
    farm.open_cycle(conn, "cycle_020")
    farm.record_output(conn, "cycle_020", "item1")
    farm.record_output(conn, "cycle_020", "item2")

    result = farm.reconcile_cycle(conn, "cycle_020")
    assert result["cycle_output_count"] == 2
    assert result["main_received_count"] == 0
    assert result["reconciliation_gap"] == 2
    assert len(result["unmatched_output_ids"]) == 2


def test_reconcile_all_referenced_gap_zero(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_021", farm_target="breach")
    farm.open_cycle(conn, "cycle_021")
    out1 = farm.record_output(conn, "cycle_021", "item1")
    out2 = farm.record_output(conn, "cycle_021", "item2")

    # Mark both as received in main inventory
    store.insert_graph_ref(conn, out1["node_id"], "main_item_001", "in_main_inventory")
    store.insert_graph_ref(conn, out2["node_id"], "main_item_002", "in_main_inventory")

    result = farm.reconcile_cycle(conn, "cycle_021")
    assert result["reconciliation_gap"] == 0
    assert result["unmatched_output_ids"] == []


def test_reconcile_partial_unmatched_ids_listed(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_022", farm_target="breach")
    farm.open_cycle(conn, "cycle_022")
    out1 = farm.record_output(conn, "cycle_022", "item1")
    out2 = farm.record_output(conn, "cycle_022", "item2")
    out3 = farm.record_output(conn, "cycle_022", "item3")

    # Only out2 received
    store.insert_graph_ref(conn, out2["node_id"], "main_item_001", "in_main_inventory")

    result = farm.reconcile_cycle(conn, "cycle_022")
    assert result["cycle_output_count"] == 3
    assert result["main_received_count"] == 1
    assert result["reconciliation_gap"] == 2
    assert out1["node_id"] in result["unmatched_output_ids"]
    assert out3["node_id"] in result["unmatched_output_ids"]
    assert out2["node_id"] not in result["unmatched_output_ids"]


# ---- 17-21: close_cycle -----------------------------------------------------

def test_close_cycle_transitions_to_closed(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_030", farm_target="breach")
    farm.open_cycle(conn, "cycle_030")
    cycle = farm.close_cycle(conn, "cycle_030")
    assert cycle["status"] == "CLOSED"
    assert cycle["closed_at"] != ""


def test_close_cycle_on_declared_raises(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_031", farm_target="breach")
    try:
        farm.close_cycle(conn, "cycle_031")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_close_cycle_computes_roi_from_snapshots(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_032", farm_target="breach")
    farm.open_cycle(conn, "cycle_032", currency_snapshot={"chaos": 1000, "divine": 0})
    cycle = farm.close_cycle(
        conn, "cycle_032",
        end_currency_snapshot={"chaos": 1200, "divine": 0},
    )
    # ROI = (1200 - 1000) / 1000 = 0.2
    assert abs(cycle["summary"]["roi"] - 0.2) < 0.001


def test_close_cycle_records_hit_rate_edge(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(
        conn, "mod_life", "craft", "craft.graph",
        '<mod pattern="maximum life">life mod</mod>',
    )
    store.insert_edge(
        conn,
        source_id="craft.graph",
        target_id="mod_life",
        graph_id="craft.graph",
        edge_type="mod_market_value",
        weight=1.0,
        payload="<edge/>",
    )

    farm.declare_cycle(conn, cycle_id="cycle_033", farm_target="breach")
    farm.open_cycle(conn, "cycle_033")

    # Insert 2 outputs manually: one matching, one not
    store.insert_node(
        conn, "cycle_033_output_0", "farm", "cycle_033",
        '<output classification="" timestamp="T1"><item>i</item><mods>maximum life</mods></output>',
    )
    store.insert_node(
        conn, "cycle_033_output_1", "farm", "cycle_033",
        '<output classification="" timestamp="T2"><item>i</item><mods>fire damage</mods></output>',
    )

    farm.classify_outputs(conn, "cycle_033")
    cycle = farm.close_cycle(conn, "cycle_033")

    # 1 price_me out of 2 -> 0.5
    assert abs(cycle["summary"]["hit_rate"] - 0.5) < 0.001


def test_close_cycle_records_div_per_hour(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_034", farm_target="breach")
    farm.open_cycle(conn, "cycle_034")
    cycle = farm.close_cycle(
        conn,
        "cycle_034",
        end_currency_snapshot={"divine": 6},
        time_invested_minutes=60.0,
    )
    # 6 divine / 1 hour = 6.0
    assert abs(cycle["summary"]["div_per_hour"] - 6.0) < 0.001


# ---- 22-25: get_cycle / list_cycles -----------------------------------------

def test_get_cycle_returns_full_dict_with_outputs(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_040", farm_target="breach")
    farm.open_cycle(conn, "cycle_040")
    farm.record_output(conn, "cycle_040", "item text")
    cycle = farm.get_cycle(conn, "cycle_040")
    assert cycle is not None
    assert len(cycle["outputs"]) == 1


def test_get_cycle_returns_none_for_unknown(tmp_path):
    conn = _conn(tmp_path)
    assert farm.get_cycle(conn, "nonexistent_cycle") is None


def test_list_cycles_filter_by_status(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_041", farm_target="breach")
    farm.declare_cycle(conn, cycle_id="cycle_042", farm_target="breach")
    farm.open_cycle(conn, "cycle_042")

    declared = farm.list_cycles(conn, status="DECLARED")
    active = farm.list_cycles(conn, status="ACTIVE")

    assert any(c["cycle_id"] == "cycle_041" for c in declared)
    assert not any(c["cycle_id"] == "cycle_042" for c in declared)
    assert any(c["cycle_id"] == "cycle_042" for c in active)


def test_list_cycles_filter_by_farm_target(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_043", farm_target="breach")
    farm.declare_cycle(conn, cycle_id="cycle_044", farm_target="sekhemas_relics")

    breach = farm.list_cycles(conn, farm_target="breach")
    assert all(c["farm_target"] == "breach" for c in breach)
    assert any(c["cycle_id"] == "cycle_043" for c in breach)
    assert not any(c["cycle_id"] == "cycle_044" for c in breach)


# ---- 26-30: export_cycle_bundle ---------------------------------------------

def test_export_cycle_bundle_writes_valid_file(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_050", farm_target="breach")
    farm.open_cycle(conn, "cycle_050")
    farm.close_cycle(conn, "cycle_050")

    out = str(tmp_path / "cycle_050.farm.graph")
    farm.export_cycle_bundle(conn, "cycle_050", out, author="TestUser")
    bundle = graphfmt.read_bundle(out)
    assert bundle["manifest"] is not None


def test_export_bundle_manifest_has_correct_fields(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_051", farm_target="breach")
    farm.open_cycle(conn, "cycle_051")
    farm.close_cycle(conn, "cycle_051")

    out = str(tmp_path / "cycle_051.farm.graph")
    farm.export_cycle_bundle(conn, "cycle_051", out, author="Pedro")
    bundle = graphfmt.read_bundle(out)
    assert bundle["manifest"]["bundle_id"] == "cycle_051"
    assert bundle["manifest"]["graph_type"] == "farm"
    assert bundle["manifest"]["author"] == "Pedro"


def test_export_bundle_contains_cycle_xml(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_052", farm_target="sekhemas")
    farm.open_cycle(conn, "cycle_052")
    farm.close_cycle(conn, "cycle_052")

    out = str(tmp_path / "cycle_052.farm.graph")
    farm.export_cycle_bundle(conn, "cycle_052", out)
    bundle = graphfmt.read_bundle(out)
    assert "cycle.xml" in bundle["contents"]
    assert "cycle_052" in bundle["contents"]["cycle.xml"]


def test_export_bundle_contains_empirical_xml(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_053", farm_target="breach")
    farm.open_cycle(conn, "cycle_053")
    farm.record_output(conn, "cycle_053", "rare waystone")
    farm.close_cycle(conn, "cycle_053")

    out = str(tmp_path / "cycle_053.farm.graph")
    farm.export_cycle_bundle(conn, "cycle_053", out)
    bundle = graphfmt.read_bundle(out)
    assert "empirical.xml" in bundle["contents"]
    # Should have measurement data since there's one output
    assert "measurement" in bundle["contents"]["empirical.xml"]


def test_export_bundle_with_build_snapshot(tmp_path):
    conn = _conn(tmp_path)
    farm.declare_cycle(conn, cycle_id="cycle_054", farm_target="breach")
    farm.open_cycle(conn, "cycle_054")
    farm.close_cycle(conn, "cycle_054")

    build_file = tmp_path / "my.build"
    # .build files are text content in the graphfmt bundle spec
    build_file.write_text("FAKE_BUILD_DATA", encoding="utf-8")

    out = str(tmp_path / "cycle_054.farm.graph")
    farm.export_cycle_bundle(conn, "cycle_054", out, build_snapshot_path=str(build_file))
    bundle = graphfmt.read_bundle(out)
    # graphfmt treats .build as text content (see bundle._TEXT_EXTENSIONS)
    assert "character.build" in bundle["contents"]
    assert "FAKE_BUILD_DATA" in bundle["contents"]["character.build"]


# ---- 31: end-to-end ---------------------------------------------------------

def test_end_to_end_full_lifecycle(tmp_path):
    conn = _conn(tmp_path)

    # Setup: one valuable mod pattern
    store.insert_node(
        conn, "mod_rarity", "craft", "craft.graph",
        '<mod pattern="increased item rarity">rarity mod</mod>',
    )
    store.insert_edge(
        conn,
        source_id="craft.graph",
        target_id="mod_rarity",
        graph_id="craft.graph",
        edge_type="mod_market_value",
        weight=1.0,
        payload="<edge/>",
    )

    # declare
    farm.declare_cycle(
        conn,
        cycle_id="e2e_cycle",
        farm_target="sekhemas_relics",
        lottery_targets=["mirror", "temporalis"],
        inputs=[{"item": "orb_of_chaos", "quantity": 200}],
    )
    assert farm.get_cycle(conn, "e2e_cycle")["status"] == "DECLARED"

    # open
    farm.open_cycle(conn, "e2e_cycle", currency_snapshot={"chaos": 1240, "divine": 18})
    assert farm.get_cycle(conn, "e2e_cycle")["status"] == "ACTIVE"

    # record 5 outputs (2 with rarity mod, 3 without)
    valuable_items = [
        "Rare Ring\n+43% increased item rarity",
        "Rare Amulet\n+60% increased item rarity",
    ]
    vendor_items = [
        "Magic Waystone",
        "Normal Gloves",
        "Magic Belt",
    ]
    outputs = []
    for item_text in valuable_items + vendor_items:
        out = farm.record_output(conn, "e2e_cycle", item_text)
        # set mods text via store so classify can read it
        raw_node = store.get_node(conn, out["node_id"])
        mods_text = "increased item rarity" if "rarity" in item_text else "no match"
        new_payload = store.xml_set(raw_node["payload"], "/output/mods", mods_text)
        store.update_node_payload(conn, out["node_id"], new_payload)
        outputs.append(out)

    # classify
    cls = farm.classify_outputs(conn, "e2e_cycle")
    assert cls["classified"] == 5
    assert cls["price_me"] == 2
    assert cls["gold_pile"] == 3

    # reconcile (no refs -> gap=5)
    rec = farm.reconcile_cycle(conn, "e2e_cycle")
    assert rec["cycle_output_count"] == 5
    assert rec["reconciliation_gap"] == 5

    # close
    cycle = farm.close_cycle(
        conn,
        "e2e_cycle",
        end_currency_snapshot={"chaos": 1440, "divine": 20},
        time_invested_minutes=90.0,
    )
    assert cycle["status"] == "CLOSED"
    assert "roi" in cycle["summary"]
    assert "hit_rate" in cycle["summary"]
    assert "div_per_hour" in cycle["summary"]

    # export
    out_path = str(tmp_path / "e2e_cycle.farm.graph")
    farm.export_cycle_bundle(conn, "e2e_cycle", out_path, author="Pedro")

    # read back and verify
    bundle = graphfmt.read_bundle(out_path)
    assert bundle["manifest"]["bundle_id"] == "e2e_cycle"
    assert bundle["manifest"]["graph_type"] == "farm"
    assert "cycle.xml" in bundle["contents"]
    assert "empirical.xml" in bundle["contents"]
    assert "CLOSED" in bundle["contents"]["cycle.xml"]
    # empirical should have 5 measurements
    assert bundle["contents"]["empirical.xml"].count("<measurement") == 5
