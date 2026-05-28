"""Tests for mcp_server.tools_clipboard — dict-in / dict-out contract.

Uses tmp_path for an isolated queue directory and a fresh SQLite DB.
No real clipboard interaction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import store
from mcp_server import tools_clipboard, tools_farm


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Point the store to a fresh temp DB for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(store, "_DEFAULT_DB", db_path)
    return db_path


@pytest.fixture()
def queue_dir(tmp_path):
    """Return a fresh empty queue directory path."""
    qd = tmp_path / "clipboard"
    qd.mkdir()
    return qd


def _write_event(queue_dir: Path, raw_text: str, timestamp: str = "2026-05-28T10:00:00Z") -> Path:
    """Write a fake clipboard event JSON file into queue_dir."""
    from hashlib import sha256
    ts_tag = timestamp.replace(":", "").replace("-", "")
    short_hash = sha256(raw_text.encode()).hexdigest()[:8]
    fname = f"{ts_tag}_{short_hash}.json"
    event = {
        "event_type": "item_copied",
        "timestamp": timestamp,
        "raw_text": raw_text,
        "parsed": None,
        "source": "clipboard",
    }
    fpath = queue_dir / fname
    fpath.write_text(json.dumps(event), encoding="utf-8")
    return fpath


# ---- clipboard_queue_status ----

def test_queue_status_empty_queue(queue_dir):
    result = tools_clipboard.clipboard_queue_status(queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["pending_count"] == 0
    assert result["oldest_timestamp"] is None
    assert result["newest_timestamp"] is None


def test_queue_status_with_events(queue_dir):
    _write_event(queue_dir, "Item A", "2026-05-28T10:00:00Z")
    _write_event(queue_dir, "Item B", "2026-05-28T11:00:00Z")
    result = tools_clipboard.clipboard_queue_status(queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["pending_count"] == 2


def test_queue_status_nonexistent_dir(tmp_path):
    missing = str(tmp_path / "nodir")
    result = tools_clipboard.clipboard_queue_status(queue_dir=missing)
    assert result["ok"] is True
    assert result["pending_count"] == 0


# ---- clipboard_peek_queue ----

def test_peek_queue_returns_items_without_deleting(queue_dir):
    _write_event(queue_dir, "Item A")
    _write_event(queue_dir, "Item B", "2026-05-28T12:00:00Z")
    result = tools_clipboard.clipboard_peek_queue(queue_dir=str(queue_dir), limit=10)
    assert result["ok"] is True
    assert len(result["items"]) == 2
    # Files should still be present
    assert len(list(queue_dir.glob("*.json"))) == 2


def test_peek_queue_respects_limit(queue_dir):
    for i in range(5):
        _write_event(queue_dir, f"Item {i}", f"2026-05-28T{10+i:02d}:00:00Z")
    result = tools_clipboard.clipboard_peek_queue(queue_dir=str(queue_dir), limit=3)
    assert result["ok"] is True
    assert len(result["items"]) == 3


def test_peek_queue_empty(queue_dir):
    result = tools_clipboard.clipboard_peek_queue(queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["items"] == []


# ---- clipboard_clear_queue ----

def test_clear_queue_deletes_all_files(queue_dir):
    _write_event(queue_dir, "A")
    _write_event(queue_dir, "B", "2026-05-28T12:00:00Z")
    result = tools_clipboard.clipboard_clear_queue(queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["deleted_count"] == 2
    assert len(list(queue_dir.glob("*.json"))) == 0


def test_clear_queue_empty_is_ok(queue_dir):
    result = tools_clipboard.clipboard_clear_queue(queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["deleted_count"] == 0


# ---- clipboard_drain_into_cycle ----

def test_drain_into_active_cycle_ingests_and_deletes(isolated_db, queue_dir):
    # Set up an ACTIVE cycle
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)

    _write_event(queue_dir, "Item Class: Rings\nRarity: Rare\nTest Ring")
    _write_event(queue_dir, "Item Class: Wands\nRarity: Rare\nTest Wand", "2026-05-28T12:00:00Z")

    result = tools_clipboard.clipboard_drain_into_cycle(
        cid, queue_dir=str(queue_dir), max_items=10
    )
    assert result["ok"] is True
    assert result["ingested_count"] == 2
    # Files consumed
    assert len(list(queue_dir.glob("*.json"))) == 0


def test_drain_into_declared_cycle_returns_errors(isolated_db, queue_dir):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    # Do NOT open the cycle — record_output will fail
    _write_event(queue_dir, "Some item text")

    result = tools_clipboard.clipboard_drain_into_cycle(cid, queue_dir=str(queue_dir))
    assert result["ok"] is True  # drain itself succeeds
    assert result["ingested_count"] == 0
    assert len(result["errors"]) == 1


def test_drain_respects_max_items(isolated_db, queue_dir):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)

    for i in range(5):
        _write_event(queue_dir, f"Item {i}", f"2026-05-28T{10+i:02d}:00:00Z")

    result = tools_clipboard.clipboard_drain_into_cycle(cid, queue_dir=str(queue_dir), max_items=3)
    assert result["ok"] is True
    assert result["ingested_count"] == 3
    # Remaining 2 files still present
    assert len(list(queue_dir.glob("*.json"))) == 2


def test_drain_empty_queue_is_ok(isolated_db, queue_dir):
    d = tools_farm.farm_declare_cycle(farm_target="Tower")
    cid = d["cycle"]["cycle_id"]
    tools_farm.farm_open_cycle(cid)

    result = tools_clipboard.clipboard_drain_into_cycle(cid, queue_dir=str(queue_dir))
    assert result["ok"] is True
    assert result["ingested_count"] == 0
    assert result["errors"] == []
