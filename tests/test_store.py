"""Tests for store — unified SQLite graph store."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import store  # noqa: E402
from store.xml_payload import xml_extract, xml_set  # noqa: E402


# ----- fixtures -----

def _conn(tmp_path) -> sqlite3.Connection:
    """Fresh in-memory-ish DB per test via tmp_path."""
    return store.get_connection(str(tmp_path / "test.db"))


# ----- 1. schema creation -----

def test_schema_tables_exist(tmp_path):
    conn = _conn(tmp_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "nodes" in tables
    assert "edges" in tables
    assert "graph_refs" in tables


def test_schema_indexes_exist(tmp_path):
    conn = _conn(tmp_path)
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_nodes_graph_id" in indexes
    assert "idx_nodes_graph_type" in indexes
    assert "idx_edges_graph_id" in indexes
    assert "idx_edges_source_id" in indexes
    assert "idx_edges_edge_type" in indexes
    assert "idx_refs_referencing" in indexes
    assert "idx_refs_referenced" in indexes


def test_schema_is_idempotent(tmp_path):
    # Second get_connection on the same path must not raise.
    db_path = str(tmp_path / "test.db")
    store.get_connection(db_path)
    store.get_connection(db_path)


# ----- 2. insert + retrieve a node -----

def test_insert_and_get_node(tmp_path):
    conn = _conn(tmp_path)
    payload = "<output classification='rare'/>"
    store.insert_node(conn, "node-abc", "farm", "farm-01", payload)
    node = store.get_node(conn, "node-abc")
    assert node is not None
    assert node["node_id"] == "node-abc"
    assert node["graph_type"] == "farm"
    assert node["graph_id"] == "farm-01"
    assert node["payload"] == payload


def test_get_node_missing_returns_none(tmp_path):
    conn = _conn(tmp_path)
    assert store.get_node(conn, "does-not-exist") is None


def test_insert_node_duplicate_raises(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "n1", "build", "b1", "<x/>")
    try:
        store.insert_node(conn, "n1", "build", "b1", "<y/>")
        raise AssertionError("expected IntegrityError")
    except sqlite3.IntegrityError:
        pass


# ----- 3. update node payload preserves other fields -----

def test_update_node_payload(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "n2", "craft", "c1", "<old/>")
    store.update_node_payload(conn, "n2", "<new classification='magic'/>")
    node = store.get_node(conn, "n2")
    assert node["payload"] == "<new classification='magic'/>"
    assert node["graph_type"] == "craft"
    assert node["graph_id"] == "c1"


def test_update_node_missing_is_noop(tmp_path):
    conn = _conn(tmp_path)
    # Must not raise.
    store.update_node_payload(conn, "ghost", "<x/>")


# ----- 4. query nodes -----

def test_query_nodes_by_graph_id(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "a1", "farm", "farm-01", "<x/>")
    store.insert_node(conn, "a2", "farm", "farm-01", "<x/>")
    store.insert_node(conn, "a3", "farm", "farm-02", "<x/>")
    results = store.query_nodes(conn, graph_id="farm-01")
    assert len(results) == 2
    ids = {r["node_id"] for r in results}
    assert ids == {"a1", "a2"}


def test_query_nodes_by_graph_type(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "b1", "build", "bld-01", "<x/>")
    store.insert_node(conn, "b2", "guide", "g-01", "<x/>")
    store.insert_node(conn, "b3", "build", "bld-02", "<x/>")
    results = store.query_nodes(conn, graph_type="build")
    assert len(results) == 2
    assert all(r["graph_type"] == "build" for r in results)


def test_query_nodes_no_filter_returns_all(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "c1", "farm", "f1", "<x/>")
    store.insert_node(conn, "c2", "craft", "c1", "<x/>")
    assert len(store.query_nodes(conn)) == 2


def test_query_nodes_combined_filters(tmp_path):
    conn = _conn(tmp_path)
    store.insert_node(conn, "d1", "farm", "farm-01", "<x/>")
    store.insert_node(conn, "d2", "build", "farm-01", "<x/>")
    store.insert_node(conn, "d3", "farm", "farm-02", "<x/>")
    results = store.query_nodes(conn, graph_id="farm-01", graph_type="farm")
    assert len(results) == 1
    assert results[0]["node_id"] == "d1"


# ----- 5. edges -----

def test_insert_and_query_edges_by_graph_id(tmp_path):
    conn = _conn(tmp_path)
    store.insert_edge(conn, "s1", "t1", "farm-01", "drops", 0.05, "<edge/>")
    store.insert_edge(conn, "s2", "t2", "farm-01", "drops", 0.10, "<edge/>")
    store.insert_edge(conn, "s3", "t3", "farm-02", "drops", 0.20, "<edge/>")
    results = store.query_edges(conn, graph_id="farm-01")
    assert len(results) == 2
    assert all(r["graph_id"] == "farm-01" for r in results)


def test_query_edges_by_edge_type(tmp_path):
    conn = _conn(tmp_path)
    store.insert_edge(conn, "s1", "t1", "farm-01", "drops", 0.05, "<edge/>")
    store.insert_edge(conn, "s2", "t2", "farm-01", "crafts_to", 1.0, "<edge/>")
    results = store.query_edges(conn, edge_type="drops")
    assert len(results) == 1
    assert results[0]["source_id"] == "s1"


def test_query_edges_by_source_id(tmp_path):
    conn = _conn(tmp_path)
    store.insert_edge(conn, "src-A", "t1", "farm-01", "drops", 0.3, "<edge/>")
    store.insert_edge(conn, "src-A", "t2", "farm-01", "drops", 0.7, "<edge/>")
    store.insert_edge(conn, "src-B", "t3", "farm-01", "drops", 0.5, "<edge/>")
    results = store.query_edges(conn, source_id="src-A")
    assert len(results) == 2


def test_edge_weight_stored_as_float(tmp_path):
    conn = _conn(tmp_path)
    store.insert_edge(conn, "s", "t", "g", "drops", 0.1234, "<e/>")
    results = store.query_edges(conn, graph_id="g")
    assert abs(results[0]["weight"] - 0.1234) < 1e-9


# ----- 6. graph_refs -----

def test_insert_and_query_graph_ref_by_referencing(tmp_path):
    conn = _conn(tmp_path)
    store.insert_graph_ref(conn, "farm-node-1", "canonical-item-X", "output_of")
    results = store.query_graph_refs(conn, referencing_node_id="farm-node-1")
    assert len(results) == 1
    assert results[0]["referenced_node_id"] == "canonical-item-X"
    assert results[0]["ref_type"] == "output_of"


def test_query_graph_ref_by_referenced(tmp_path):
    conn = _conn(tmp_path)
    store.insert_graph_ref(conn, "fn1", "item-Y", "output_of")
    store.insert_graph_ref(conn, "fn2", "item-Y", "output_of")
    store.insert_graph_ref(conn, "fn3", "item-Z", "output_of")
    results = store.query_graph_refs(conn, referenced_node_id="item-Y")
    assert len(results) == 2


def test_query_graph_refs_no_filter(tmp_path):
    conn = _conn(tmp_path)
    store.insert_graph_ref(conn, "r1", "c1", "x")
    store.insert_graph_ref(conn, "r2", "c2", "x")
    assert len(store.query_graph_refs(conn)) == 2


# ----- 7. xml_extract -----

def test_xml_extract_attribute(tmp_path):
    payload = '<output classification="rare"/>'
    assert xml_extract(payload, "/output/@classification") == "rare"


def test_xml_extract_text(tmp_path):
    payload = "<mods>life regen</mods>"
    assert xml_extract(payload, "/mods") == "life regen"


def test_xml_extract_nested_attribute(tmp_path):
    payload = "<output><meta type='item'/></output>"
    assert xml_extract(payload, "/output/meta/@type") == "item"


def test_xml_extract_missing_returns_none(tmp_path):
    payload = "<output/>"
    assert xml_extract(payload, "/output/@nonexistent") is None
    assert xml_extract(payload, "/other") is None


# ----- 8. xml_set -----

def test_xml_set_creates_new_attribute(tmp_path):
    payload = "<output/>"
    new = xml_set(payload, "/output/@classification", "rare")
    assert xml_extract(new, "/output/@classification") == "rare"


def test_xml_set_modifies_existing_attribute(tmp_path):
    payload = '<output classification="normal"/>'
    new = xml_set(payload, "/output/@classification", "magic")
    assert xml_extract(new, "/output/@classification") == "magic"


def test_xml_set_text_content(tmp_path):
    payload = "<mods/>"
    new = xml_set(payload, "/mods", "flat life")
    assert xml_extract(new, "/mods") == "flat life"


def test_xml_set_creates_missing_element(tmp_path):
    payload = "<output/>"
    new = xml_set(payload, "/output/meta/@type", "currency")
    assert xml_extract(new, "/output/meta/@type") == "currency"


# ----- 9. round-trip -----

def test_roundtrip_insert_retrieve_extract(tmp_path):
    conn = _conn(tmp_path)
    payload = '<output classification="rare"><mods>flat life</mods></output>'
    store.insert_node(conn, "rt-1", "farm", "farm-99", payload)
    node = store.get_node(conn, "rt-1")
    assert xml_extract(node["payload"], "/output/@classification") == "rare"
    assert xml_extract(node["payload"], "/output/mods") == "flat life"


# ----- 10. orphan edges are allowed -----

def test_orphan_edges_allowed(tmp_path):
    conn = _conn(tmp_path)
    # Insert an edge whose source/target nodes do not exist — must succeed.
    store.insert_edge(conn, "ghost-src", "ghost-tgt", "farm-01", "drops", 0.5, "<edge/>")
    results = store.query_edges(conn, graph_id="farm-01")
    assert len(results) == 1


# ----- 11. farm cycle simulation -----

def test_farm_cycle_price_me_filter(tmp_path):
    """Simulate a 5-output farm cycle; filter to nodes classified 'price_me'."""
    conn = _conn(tmp_path)

    outputs = [
        ("out-1", '<output classification="price_me"/>'),
        ("out-2", '<output classification="vendor"/>'),
        ("out-3", '<output classification="price_me"/>'),
        ("out-4", '<output classification="vendor"/>'),
        ("out-5", '<output classification="vendor"/>'),
    ]
    for node_id, payload in outputs:
        store.insert_node(conn, node_id, "farm", "cycle-01", payload)

    # Retrieve and filter in Python using xml_extract (mirrors the §5 query pattern).
    all_nodes = store.query_nodes(conn, graph_id="cycle-01", graph_type="farm")
    price_me = [
        n for n in all_nodes
        if xml_extract(n["payload"], "/output/@classification") == "price_me"
    ]
    assert len(price_me) == 2
    assert {n["node_id"] for n in price_me} == {"out-1", "out-3"}
