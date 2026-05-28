"""Tests for mcp_server.tools_farm — dict-in / dict-out contract.

Uses a tmp_path-isolated SQLite DB by monkeypatching store._DEFAULT_DB.
No network required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import store
from mcp_server import tools_farm


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Point the store to a fresh temp DB for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(store, "_DEFAULT_DB", db_path)
    return db_path


# ---- farm_declare_cycle ----

def test_declare_cycle_returns_ok_with_cycle(isolated_db):
    result = tools_farm.farm_declare_cycle(farm_target="Strand Maps")
    assert result["ok"] is True
    cycle = result["cycle"]
    assert cycle["farm_target"] == "Strand Maps"
    assert cycle["status"] == "DECLARED"
    assert "cycle_id" in cycle


def test_declare_cycle_with_all_args(isolated_db):
    result = tools_farm.farm_declare_cycle(
        farm_target="Jungle Valley",
        lottery_targets=["Headhunter", "Mageblood"],
        inputs=[{"item": "Chaos Orb", "quantity": 100}],
        notes="test notes",
        cycle_id="cycle_test_explicit",
    )
    assert result["ok"] is True
    cycle = result["cycle"]
    assert cycle["cycle_id"] == "cycle_test_explicit"
    assert "Headhunter" in cycle["lottery_targets"]
    assert len(cycle["inputs"]) == 1


# ---- farm_open_cycle ----

def test_open_cycle_transitions_to_active(isolated_db):
    declared = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = declared["cycle"]["cycle_id"]
    result = tools_farm.farm_open_cycle(cid, currency_snapshot={"chaos": 500, "divine": 3})
    assert result["ok"] is True
    assert result["cycle"]["status"] == "ACTIVE"


def test_open_cycle_missing_cycle_returns_error(isolated_db):
    result = tools_farm.farm_open_cycle("cycle_does_not_exist")
    assert result["ok"] is False
    assert "error" in result


def test_open_cycle_already_active_returns_error(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    # Second open should fail
    result = tools_farm.farm_open_cycle(cid)
    assert result["ok"] is False


# ---- farm_record_output ----

def test_record_output_appends_to_active_cycle(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    result = tools_farm.farm_record_output(cid, "<item>Test Drop</item>")
    assert result["ok"] is True
    assert "output" in result


def test_record_output_on_declared_cycle_returns_error(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    result = tools_farm.farm_record_output(cid, "<item>Drop</item>")
    assert result["ok"] is False


# ---- farm_classify_outputs ----

def test_classify_outputs_returns_counts(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    tools_farm.farm_record_output(cid, "<item>Rare Sword</item>")
    tools_farm.farm_record_output(cid, "<item>Magic Ring</item>")
    result = tools_farm.farm_classify_outputs(cid)
    assert result["ok"] is True
    assert result["classified"] == 2
    assert result["price_me"] + result["gold_pile"] == 2


# ---- farm_reconcile_cycle ----

def test_reconcile_cycle_returns_gap(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    tools_farm.farm_record_output(cid, "<item>Drop A</item>")
    result = tools_farm.farm_reconcile_cycle(cid)
    assert result["ok"] is True
    assert "cycle_output_count" in result
    assert "reconciliation_gap" in result
    # No in_main_inventory refs set — gap equals output count
    assert result["reconciliation_gap"] == result["cycle_output_count"]


# ---- farm_close_cycle ----

def test_close_cycle_transitions_to_closed(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid, currency_snapshot={"chaos": 500})
    result = tools_farm.farm_close_cycle(
        cid,
        end_currency_snapshot={"chaos": 700},
        time_invested_minutes=30.0,
    )
    assert result["ok"] is True
    assert result["cycle"]["status"] == "CLOSED"


def test_close_cycle_on_declared_returns_error(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    result = tools_farm.farm_close_cycle(cid)
    assert result["ok"] is False


# ---- farm_get_cycle ----

def test_get_cycle_returns_full_dict(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Gorge")
    cid = d["cycle"]["cycle_id"]
    result = tools_farm.farm_get_cycle(cid)
    assert result["ok"] is True
    assert result["cycle"]["cycle_id"] == cid


def test_get_cycle_missing_returns_error(isolated_db):
    result = tools_farm.farm_get_cycle("cycle_nope")
    assert result["ok"] is False
    assert "error" in result


# ---- farm_list_cycles ----

def test_list_cycles_returns_all(isolated_db):
    tools_farm.farm_declare_cycle(farm_target="A")
    tools_farm.farm_declare_cycle(farm_target="B")
    result = tools_farm.farm_list_cycles()
    assert result["ok"] is True
    assert len(result["cycles"]) >= 2


def test_list_cycles_filters_by_status(isolated_db):
    d = tools_farm.farm_declare_cycle(farm_target="Gorge")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    result_active = tools_farm.farm_list_cycles(status="ACTIVE")
    assert result_active["ok"] is True
    assert all(c["status"] == "ACTIVE" for c in result_active["cycles"])


# ---- farm_export_cycle_bundle ----

def test_export_cycle_bundle_creates_file(isolated_db, tmp_path):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)
    tools_farm.farm_close_cycle(cid)
    out_path = str(tmp_path / "test_cycle.farm.graph")
    result = tools_farm.farm_export_cycle_bundle(cid, out_path)
    assert result["ok"] is True
    assert result["out_path"] == out_path
    assert Path(out_path).exists()


def test_export_cycle_bundle_missing_cycle_returns_error(isolated_db, tmp_path):
    out_path = str(tmp_path / "nope.farm.graph")
    result = tools_farm.farm_export_cycle_bundle("cycle_nope", out_path)
    assert result["ok"] is False
    assert "error" in result
