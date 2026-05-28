"""farm.lifecycle — declare, open, record, and close farming cycles.

A cycle is a dict; we never bury it in a class. Status string drives all
lifecycle gating ('DECLARED' -> 'ACTIVE' -> 'CLOSED').
"""

from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import store


# ---- helpers ----------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_cycle_id() -> str:
    """Timestamp (microseconds) + short hash to avoid same-second collisions."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    h = hashlib.sha1(ts.encode()).hexdigest()[:6]
    return f"cycle_{ts}_{h}"


def _cycle_root_payload(cycle_id: str, farm_target: str, lottery_targets: list[str],
                        declared_at: str, opened_at: str = "", closed_at: str = "",
                        status: str = "DECLARED", notes: str = "") -> str:
    """Build XML payload for the cycle root node."""
    lt_xml = "".join(f"    <target>{ET.tostring(ET.Element('_'), encoding='unicode')[1:-3]}{t}</target>\n"
                     for t in lottery_targets)
    # Use string building — lottery targets are simple strings
    lt_lines = "".join(f"    <target>{t}</target>\n" for t in lottery_targets)
    return (
        f'<cycle id="{cycle_id}" status="{status}">\n'
        f"  <farm_target>{farm_target}</farm_target>\n"
        f"  <lottery_targets>\n{lt_lines}  </lottery_targets>\n"
        f"  <declared_at>{declared_at}</declared_at>\n"
        f"  <opened_at>{opened_at}</opened_at>\n"
        f"  <closed_at>{closed_at}</closed_at>\n"
        f"  <notes>{notes}</notes>\n"
        f"</cycle>"
    )


def _input_payload(item: str, quantity: int) -> str:
    return f"<input>\n  <item>{item}</item>\n  <quantity>{quantity}</quantity>\n</input>"


def _snapshot_payload(when: str, currency: dict) -> str:
    lines = "".join(
        f'  <currency name="{name}">{amount}</currency>\n'
        for name, amount in currency.items()
    )
    return f'<snapshot when="{when}">\n{lines}</snapshot>'


def _summary_payload(description: str) -> str:
    computed_at = _now_iso()
    return f'<summary computed_at="{computed_at}">{description}</summary>'


# ---- node assembler ---------------------------------------------------------

def _build_cycle_dict(conn, cycle_id: str) -> Optional[dict]:
    """Assemble the full cycle dict from the store."""
    root_node = store.get_node(conn, cycle_id)
    if root_node is None:
        return None

    payload = root_node["payload"]
    status = store.xml_extract(payload, "/cycle/@status") or "DECLARED"
    farm_target = store.xml_extract(payload, "/cycle/farm_target") or ""
    declared_at = store.xml_extract(payload, "/cycle/declared_at") or ""
    opened_at = store.xml_extract(payload, "/cycle/opened_at") or ""
    closed_at = store.xml_extract(payload, "/cycle/closed_at") or ""
    notes = store.xml_extract(payload, "/cycle/notes") or ""

    # lottery targets from XML
    try:
        root_el = ET.fromstring(payload)
        lt_el = root_el.find("lottery_targets")
        lottery_targets = [t.text or "" for t in (lt_el or [])]
    except ET.ParseError:
        lottery_targets = []

    # child nodes in this graph
    all_nodes = store.query_nodes(conn, graph_id=cycle_id, graph_type="farm")
    inputs = []
    outputs = []
    for n in all_nodes:
        if n["node_id"] == cycle_id:
            continue
        p = n["payload"]
        if store.xml_extract(p, "/input"):
            item = store.xml_extract(p, "/input/item") or ""
            qty_str = store.xml_extract(p, "/input/quantity") or "0"
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 0
            inputs.append({"node_id": n["node_id"], "item": item, "quantity": qty})
        elif store.xml_extract(p, "/output") is not None or p.lstrip().startswith("<output"):
            classification = store.xml_extract(p, "/output/@classification") or ""
            timestamp = store.xml_extract(p, "/output/@timestamp") or ""
            item_text = store.xml_extract(p, "/output/item") or ""
            mods = store.xml_extract(p, "/output/mods") or ""
            outputs.append({
                "node_id": n["node_id"],
                "classification": classification,
                "timestamp": timestamp,
                "item": item_text,
                "mods": mods,
            })

    # summary edges (self-loops)
    summary_edges = store.query_edges(conn, graph_id=cycle_id, source_id=cycle_id)
    summary = {}
    for e in summary_edges:
        if e["edge_type"] in ("roi", "hit_rate", "div_per_hour"):
            summary[e["edge_type"]] = e["weight"]

    return {
        "cycle_id": cycle_id,
        "status": status,
        "farm_target": farm_target,
        "lottery_targets": lottery_targets,
        "declared_at": declared_at,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "notes": notes,
        "inputs": inputs,
        "outputs": outputs,
        "summary": summary,
    }


# ---- public lifecycle API ---------------------------------------------------

def declare_cycle(
    conn,
    *,
    cycle_id: Optional[str] = None,
    farm_target: str,
    lottery_targets: Optional[list[str]] = None,
    inputs: Optional[list[dict]] = None,
    notes: str = "",
) -> dict:
    """Insert a cycle root node + target nodes + lottery nodes + input nodes.
    Status: 'DECLARED'. Returns the cycle dict.
    """
    cid = cycle_id or _generate_cycle_id()
    now = _now_iso()
    lt = lottery_targets or []
    inp = inputs or []

    root_payload = _cycle_root_payload(
        cycle_id=cid,
        farm_target=farm_target,
        lottery_targets=lt,
        declared_at=now,
        status="DECLARED",
        notes=notes,
    )

    with store.transaction(conn):
        store.insert_node(conn, cid, "farm", cid, root_payload)

        for idx, item_dict in enumerate(inp):
            input_node_id = f"{cid}_input_{idx}"
            item = item_dict.get("item", "")
            quantity = int(item_dict.get("quantity", 0))
            store.insert_node(
                conn, input_node_id, "farm", cid,
                _input_payload(item, quantity)
            )

    return _build_cycle_dict(conn, cid)


def open_cycle(conn, cycle_id: str, *, currency_snapshot: Optional[dict] = None) -> dict:
    """Transition DECLARED -> ACTIVE. Records currency snapshot edge."""
    cycle = _build_cycle_dict(conn, cycle_id)
    if cycle is None:
        raise ValueError(f"Cycle {cycle_id!r} not found")
    if cycle["status"] != "DECLARED":
        raise ValueError(
            f"open_cycle requires status='DECLARED', got {cycle['status']!r}"
        )

    now = _now_iso()
    # Update root payload: status + opened_at
    root_node = store.get_node(conn, cycle_id)
    payload = root_node["payload"]
    payload = store.xml_set(payload, "/cycle/@status", "ACTIVE")
    payload = store.xml_set(payload, "/cycle/opened_at", now)
    store.update_node_payload(conn, cycle_id, payload)

    if currency_snapshot:
        snapshot_node_id = f"{cycle_id}_snap_open"
        snap_payload = _snapshot_payload("open", currency_snapshot)
        store.insert_node(conn, snapshot_node_id, "farm", cycle_id, snap_payload)
        store.insert_edge(
            conn,
            source_id=cycle_id,
            target_id=snapshot_node_id,
            graph_id=cycle_id,
            edge_type="currency_snapshot",
            weight=0.0,
            payload=snap_payload,
        )

    return _build_cycle_dict(conn, cycle_id)


def record_output(
    conn,
    cycle_id: str,
    item_payload: str,
    *,
    source: str = "clipboard",
    timestamp: Optional[str] = None,
) -> dict:
    """Append an output node to an ACTIVE cycle. Returns the output node dict."""
    cycle = _build_cycle_dict(conn, cycle_id)
    if cycle is None:
        raise ValueError(f"Cycle {cycle_id!r} not found")
    if cycle["status"] != "ACTIVE":
        raise ValueError(
            f"record_output requires status='ACTIVE', got {cycle['status']!r}"
        )

    ts = timestamp or _now_iso()
    # Count existing outputs to generate a unique id
    existing_outputs = len(cycle["outputs"])
    output_node_id = f"{cycle_id}_output_{existing_outputs}"

    # Build output XML wrapping the item payload
    output_xml = (
        f'<output classification="" timestamp="{ts}">\n'
        f"  <item><![CDATA[{item_payload}]]></item>\n"
        f"  <mods></mods>\n"
        f"</output>"
    )

    store.insert_node(conn, output_node_id, "farm", cycle_id, output_xml)

    return {
        "node_id": output_node_id,
        "classification": "",
        "timestamp": ts,
        "item": item_payload,
        "mods": "",
        "source": source,
    }


def get_cycle(conn, cycle_id: str) -> Optional[dict]:
    """Returns full cycle dict with status, targets, inputs, outputs, summary.
    None if not found.
    """
    return _build_cycle_dict(conn, cycle_id)


def list_cycles(
    conn,
    *,
    status: Optional[str] = None,
    farm_target: Optional[str] = None,
) -> list[dict]:
    """Returns list of cycle dicts (root-level fields only — not full output lists)."""
    all_nodes = store.query_nodes(conn, graph_type="farm")
    results = []
    seen = set()
    for node in all_nodes:
        # Cycle roots have node_id == graph_id
        if node["node_id"] != node["graph_id"]:
            continue
        cid = node["node_id"]
        if cid in seen:
            continue
        seen.add(cid)

        payload = node["payload"]
        # Only process cycle roots (not input/output nodes)
        if not payload.lstrip().startswith("<cycle"):
            continue

        node_status = store.xml_extract(payload, "/cycle/@status") or "DECLARED"
        node_target = store.xml_extract(payload, "/cycle/farm_target") or ""

        if status is not None and node_status != status:
            continue
        if farm_target is not None and node_target != farm_target:
            continue

        declared_at = store.xml_extract(payload, "/cycle/declared_at") or ""
        opened_at = store.xml_extract(payload, "/cycle/opened_at") or ""
        closed_at = store.xml_extract(payload, "/cycle/closed_at") or ""
        notes = store.xml_extract(payload, "/cycle/notes") or ""

        try:
            root_el = ET.fromstring(payload)
            lt_el = root_el.find("lottery_targets")
            lottery_targets = [t.text or "" for t in (lt_el or [])]
        except ET.ParseError:
            lottery_targets = []

        results.append({
            "cycle_id": cid,
            "status": node_status,
            "farm_target": node_target,
            "lottery_targets": lottery_targets,
            "declared_at": declared_at,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "notes": notes,
        })

    return results
