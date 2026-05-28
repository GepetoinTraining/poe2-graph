"""farm.summarize — close a cycle and compute ROI / hit-rate / div-per-hour.

close_cycle is the only exported function. It:
  1. Validates the cycle is ACTIVE.
  2. Writes end currency snapshot if given.
  3. Computes ROI, hit_rate, div_per_hour and inserts summary edges.
  4. Flips status to CLOSED.
  5. Returns the updated cycle dict.
"""

from __future__ import annotations

from typing import Optional

import store
from farm.lifecycle import (
    _build_cycle_dict,
    _now_iso,
    _snapshot_payload,
    _summary_payload,
)


def _chaos_value(snapshot: dict) -> float:
    """Very rough chaos equivalent from a currency dict.

    Uses hardcoded rates for the three currencies the design example shows.
    A real implementation would call poe_ninja; this keeps the module dependency-free.
    """
    rates = {"chaos": 1.0, "divine": 200.0, "exalted": 1.0}
    total = 0.0
    for name, amount in snapshot.items():
        total += float(amount) * rates.get(name, 1.0)
    return total


def _load_open_snapshot(conn, cycle_id: str) -> Optional[dict]:
    """Find the 'open' currency snapshot node for this cycle, return as dict."""
    snapshot_node_id = f"{cycle_id}_snap_open"
    node = store.get_node(conn, snapshot_node_id)
    if node is None:
        return None
    # Parse currencies out of the payload
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(node["payload"])
    except ET.ParseError:
        return None
    result: dict = {}
    for c in root.findall("currency"):
        name = c.get("name", "")
        try:
            result[name] = float(c.text or "0")
        except ValueError:
            result[name] = 0.0
    return result


def close_cycle(
    conn,
    cycle_id: str,
    *,
    end_currency_snapshot: Optional[dict] = None,
    time_invested_minutes: Optional[float] = None,
) -> dict:
    """Transition ACTIVE -> CLOSED. Computes summary edges."""
    cycle = _build_cycle_dict(conn, cycle_id)
    if cycle is None:
        raise ValueError(f"Cycle {cycle_id!r} not found")
    if cycle["status"] != "ACTIVE":
        raise ValueError(
            f"close_cycle requires status='ACTIVE', got {cycle['status']!r}"
        )

    now = _now_iso()

    # Write end snapshot node if given
    if end_currency_snapshot:
        snap_node_id = f"{cycle_id}_snap_close"
        snap_payload = _snapshot_payload("close", end_currency_snapshot)
        store.insert_node(conn, snap_node_id, "farm", cycle_id, snap_payload)
        store.insert_edge(
            conn,
            source_id=cycle_id,
            target_id=snap_node_id,
            graph_id=cycle_id,
            edge_type="currency_snapshot",
            weight=0.0,
            payload=snap_payload,
        )

    # --- compute summary metrics ---

    all_nodes = store.query_nodes(conn, graph_id=cycle_id, graph_type="farm")
    output_nodes = [n for n in all_nodes if n["payload"].lstrip().startswith("<output")]
    total_outputs = len(output_nodes)

    price_me_count = sum(
        1 for n in output_nodes
        if (store.xml_extract(n["payload"], "/output/@classification") or "") == "price_me"
    )

    # ROI edge
    open_snap = _load_open_snapshot(conn, cycle_id)
    if open_snap and end_currency_snapshot:
        start_value = _chaos_value(open_snap)
        end_value = _chaos_value(end_currency_snapshot)
        roi = (end_value - start_value) / start_value if start_value else 0.0
    else:
        roi = 0.0

    store.insert_edge(
        conn,
        source_id=cycle_id,
        target_id=cycle_id,
        graph_id=cycle_id,
        edge_type="roi",
        weight=roi,
        payload=_summary_payload(f"roi={roi:.4f}"),
    )

    # hit_rate edge
    hit_rate = price_me_count / total_outputs if total_outputs else 0.0
    store.insert_edge(
        conn,
        source_id=cycle_id,
        target_id=cycle_id,
        graph_id=cycle_id,
        edge_type="hit_rate",
        weight=hit_rate,
        payload=_summary_payload(f"hit_rate={hit_rate:.4f} ({price_me_count}/{total_outputs})"),
    )

    # div_per_hour edge
    if time_invested_minutes is not None and time_invested_minutes > 0:
        # Sum total div from end snapshot; fall back to open snap if no end
        snap_for_rate = end_currency_snapshot or open_snap or {}
        total_div = float(snap_for_rate.get("divine", 0))
        div_per_hour = total_div / (time_invested_minutes / 60.0)
    else:
        div_per_hour = 0.0

    store.insert_edge(
        conn,
        source_id=cycle_id,
        target_id=cycle_id,
        graph_id=cycle_id,
        edge_type="div_per_hour",
        weight=div_per_hour,
        payload=_summary_payload(f"div_per_hour={div_per_hour:.4f}"),
    )

    # Update cycle root: status + closed_at + time_invested_minutes
    root_node = store.get_node(conn, cycle_id)
    payload = root_node["payload"]
    payload = store.xml_set(payload, "/cycle/@status", "CLOSED")
    payload = store.xml_set(payload, "/cycle/closed_at", now)
    if time_invested_minutes is not None:
        payload = store.xml_set(
            payload, "/cycle/time_invested_minutes", str(time_invested_minutes)
        )
    store.update_node_payload(conn, cycle_id, payload)

    return _build_cycle_dict(conn, cycle_id)
