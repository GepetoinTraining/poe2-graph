"""store — unified SQLite graph store for poe2-graph v2.

Three tables hold running state for build/farm/craft/guide graphs.
Payloads are XML fragments; SQL is the projection layer for fast queries.

Public API:
    get_connection(db_path)         -- open/create DB, ensure schema
    insert_node(conn, ...)
    get_node(conn, node_id)
    update_node_payload(conn, ...)
    query_nodes(conn, *, graph_id, graph_type)
    insert_edge(conn, ...)
    query_edges(conn, *, graph_id, edge_type, source_id)
    insert_graph_ref(conn, ...)
    query_graph_refs(conn, *, referencing_node_id, referenced_node_id)
    xml_extract(payload, xpath)     -- re-exported from xml_payload
    xml_set(payload, xpath, value)  -- re-exported from xml_payload
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Optional

from store.xml_payload import xml_extract, xml_set  # noqa: F401 — re-exported

__all__ = [
    "get_connection",
    "insert_node",
    "get_node",
    "update_node_payload",
    "query_nodes",
    "insert_edge",
    "query_edges",
    "insert_graph_ref",
    "query_graph_refs",
    "xml_extract",
    "xml_set",
]

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "poe2_graph.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id    TEXT PRIMARY KEY,
    graph_type TEXT,
    graph_id   TEXT,
    payload    TEXT
);
CREATE TABLE IF NOT EXISTS edges (
    source_id  TEXT,
    target_id  TEXT,
    graph_id   TEXT,
    edge_type  TEXT,
    weight     REAL,
    payload    TEXT
);
CREATE TABLE IF NOT EXISTS graph_refs (
    referencing_node_id TEXT,
    referenced_node_id  TEXT,
    ref_type            TEXT
);
CREATE INDEX IF NOT EXISTS idx_nodes_graph_id   ON nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_nodes_graph_type  ON nodes(graph_type);
CREATE INDEX IF NOT EXISTS idx_edges_graph_id    ON edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_edges_source_id   ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_edge_type   ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_refs_referencing   ON graph_refs(referencing_node_id);
CREATE INDEX IF NOT EXISTS idx_refs_referenced    ON graph_refs(referenced_node_id);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open (or create) the SQLite DB, ensure schema, return a connection.

    row_factory is set to sqlite3.Row so callers get dict-like rows.
    Schema creation is idempotent (IF NOT EXISTS throughout).
    """
    path = Path(db_path) if db_path is not None else _DEFAULT_DB
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    with transaction(conn):
        for stmt in _SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
    return conn


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager that commits on success and rolls back on exception."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ----- nodes -----

def insert_node(
    conn: sqlite3.Connection,
    node_id: str,
    graph_type: str,
    graph_id: str,
    payload: str,
) -> None:
    """Insert a node. Raises sqlite3.IntegrityError if node_id already exists."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO nodes (node_id, graph_type, graph_id, payload) VALUES (?, ?, ?, ?)",
            (node_id, graph_type, graph_id, payload),
        )


def get_node(conn: sqlite3.Connection, node_id: str) -> Optional[dict]:
    """Return {'node_id', 'graph_type', 'graph_id', 'payload'} or None."""
    row = conn.execute(
        "SELECT node_id, graph_type, graph_id, payload FROM nodes WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def update_node_payload(conn: sqlite3.Connection, node_id: str, payload: str) -> None:
    """Replace the payload for an existing node. No-op if node_id is absent."""
    with transaction(conn):
        conn.execute(
            "UPDATE nodes SET payload = ? WHERE node_id = ?",
            (payload, node_id),
        )


def query_nodes(
    conn: sqlite3.Connection,
    *,
    graph_id: Optional[str] = None,
    graph_type: Optional[str] = None,
) -> list[dict]:
    """Return all nodes matching the given filters (AND logic). Both optional."""
    clauses: list[str] = []
    params: list = []
    if graph_id is not None:
        clauses.append("graph_id = ?")
        params.append(graph_id)
    if graph_type is not None:
        clauses.append("graph_type = ?")
        params.append(graph_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT node_id, graph_type, graph_id, payload FROM nodes {where}",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ----- edges -----

def insert_edge(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    graph_id: str,
    edge_type: str,
    weight: float,
    payload: str,
) -> None:
    """Insert an edge. Duplicate (source, target, graph_id, edge_type) is allowed —
    the design permits multi-edges (e.g. multiple craft paths between the same nodes).
    """
    with transaction(conn):
        conn.execute(
            "INSERT INTO edges (source_id, target_id, graph_id, edge_type, weight, payload)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (source_id, target_id, graph_id, edge_type, float(weight), payload),
        )


def query_edges(
    conn: sqlite3.Connection,
    *,
    graph_id: Optional[str] = None,
    edge_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> list[dict]:
    """Return edges matching the given filters (AND logic). All optional."""
    clauses: list[str] = []
    params: list = []
    if graph_id is not None:
        clauses.append("graph_id = ?")
        params.append(graph_id)
    if edge_type is not None:
        clauses.append("edge_type = ?")
        params.append(edge_type)
    if source_id is not None:
        clauses.append("source_id = ?")
        params.append(source_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT source_id, target_id, graph_id, edge_type, weight, payload FROM edges {where}",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ----- graph_refs -----

def insert_graph_ref(
    conn: sqlite3.Connection,
    referencing_node_id: str,
    referenced_node_id: str,
    ref_type: str,
) -> None:
    """Record a cross-graph reference (e.g. farm output node -> canonical item node)."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO graph_refs (referencing_node_id, referenced_node_id, ref_type)"
            " VALUES (?, ?, ?)",
            (referencing_node_id, referenced_node_id, ref_type),
        )


def query_graph_refs(
    conn: sqlite3.Connection,
    *,
    referencing_node_id: Optional[str] = None,
    referenced_node_id: Optional[str] = None,
) -> list[dict]:
    """Return graph_refs matching the given filters (AND logic). Both optional."""
    clauses: list[str] = []
    params: list = []
    if referencing_node_id is not None:
        clauses.append("referencing_node_id = ?")
        params.append(referencing_node_id)
    if referenced_node_id is not None:
        clauses.append("referenced_node_id = ?")
        params.append(referenced_node_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT referencing_node_id, referenced_node_id, ref_type FROM graph_refs {where}",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
