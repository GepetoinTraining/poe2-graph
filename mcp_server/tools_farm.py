"""Farm cycle tools — lifecycle wrappers over the farm package.

Each function maps 1-to-1 to a farm.* public function. Args and returns are
JSON-compatible dicts (no datetimes, no dataclasses). Every tool opens a fresh
SQLite connection, does its work, and closes it before returning.
"""

from __future__ import annotations

from typing import Any, Optional

import farm
from store import get_connection


def farm_declare_cycle(
    farm_target: str,
    lottery_targets: Optional[list[str]] = None,
    inputs: Optional[list[dict]] = None,
    notes: str = "",
    cycle_id: Optional[str] = None,
) -> dict[str, Any]:
    """Declare a new farming cycle. Status starts as DECLARED.

    Returns {ok: True, cycle: {...}} with the new cycle dict including an
    auto-generated cycle_id if none was supplied. The cycle dict contains
    status, farm_target, lottery_targets, inputs, outputs (empty at this
    point), declared_at, and notes.
    """
    conn = get_connection()
    try:
        cycle = farm.declare_cycle(
            conn,
            farm_target=farm_target,
            lottery_targets=lottery_targets,
            inputs=inputs,
            notes=notes,
            cycle_id=cycle_id,
        )
        return {"ok": True, "cycle": cycle}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_open_cycle(
    cycle_id: str,
    currency_snapshot: Optional[dict] = None,
) -> dict[str, Any]:
    """Transition a DECLARED cycle to ACTIVE. Records the starting currency snapshot.

    currency_snapshot example: {"chaos": 1240, "divine": 18, "exalted": 4500}.
    Returns {ok: True, cycle: {...}} with the updated cycle dict, or
    {ok: False, error: str} if the cycle is not found or not in DECLARED status.
    """
    conn = get_connection()
    try:
        cycle = farm.open_cycle(conn, cycle_id, currency_snapshot=currency_snapshot)
        return {"ok": True, "cycle": cycle}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_record_output(
    cycle_id: str,
    item_payload_xml: str,
    source: str = "clipboard",
) -> dict[str, Any]:
    """Append an output node to an ACTIVE cycle.

    item_payload_xml is an XML fragment matching the <output> schema:
    the item text and any known mods. Returns {ok: True, output: {...}}
    with the new output node dict, or {ok: False, error: str} if the cycle
    is not ACTIVE.
    """
    conn = get_connection()
    try:
        output = farm.record_output(conn, cycle_id, item_payload_xml, source=source)
        return {"ok": True, "output": output}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_classify_outputs(
    cycle_id: str,
    valuable_mod_threshold: float = 0.5,
) -> dict[str, Any]:
    """Run the mod-regex classification pass over all outputs in a cycle.

    Reads mod_market_value edges from the craft graph to decide which outputs
    are worth pricing on trade (price_me) vs. bulk-selling (gold_pile).
    Returns {ok: True, classified: int, price_me: int, gold_pile: int}.
    Does not change the cycle status — classification is metadata only.
    """
    conn = get_connection()
    try:
        result = farm.classify_outputs(
            conn, cycle_id, valuable_mod_threshold=valuable_mod_threshold
        )
        return {"ok": True, **result}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_reconcile_cycle(cycle_id: str) -> dict[str, Any]:
    """Double-booked reconciliation check for a cycle.

    For each output node checks whether a graph_ref of type 'in_main_inventory'
    exists. Returns {ok: True, cycle_output_count, main_received_count,
    reconciliation_gap, unmatched_output_ids}. Surface an audit warning to the
    player if reconciliation_gap != 0.
    """
    conn = get_connection()
    try:
        result = farm.reconcile_cycle(conn, cycle_id)
        return {"ok": True, **result}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_close_cycle(
    cycle_id: str,
    end_currency_snapshot: Optional[dict] = None,
    time_invested_minutes: Optional[float] = None,
) -> dict[str, Any]:
    """Transition an ACTIVE cycle to CLOSED.

    Computes roi, hit_rate, and div_per_hour summary edges and stores them.
    end_currency_snapshot has the same shape as the open snapshot
    (e.g. {"chaos": 1480, "divine": 21}). time_invested_minutes drives
    div_per_hour; if omitted div_per_hour will be 0.
    Returns {ok: True, cycle: {...}} with the final cycle dict.
    """
    conn = get_connection()
    try:
        cycle = farm.close_cycle(
            conn,
            cycle_id,
            end_currency_snapshot=end_currency_snapshot,
            time_invested_minutes=time_invested_minutes,
        )
        return {"ok": True, "cycle": cycle}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def farm_get_cycle(cycle_id: str) -> dict[str, Any]:
    """Return the full cycle dict including outputs and summary edges.

    Returns {ok: True, cycle: {...}} or {ok: False, error: str} if the cycle
    is not found. The cycle dict includes status, farm_target, lottery_targets,
    inputs, outputs (each with classification and timestamp), and summary
    (roi, hit_rate, div_per_hour).
    """
    conn = get_connection()
    try:
        cycle = farm.get_cycle(conn, cycle_id)
        if cycle is None:
            return {"ok": False, "error": f"Cycle {cycle_id!r} not found"}
        return {"ok": True, "cycle": cycle}
    finally:
        conn.close()


def farm_list_cycles(
    status: Optional[str] = None,
    farm_target: Optional[str] = None,
) -> dict[str, Any]:
    """List farming cycles, optionally filtered by status and/or farm_target.

    status: DECLARED | ACTIVE | CLOSED (omit to return all).
    farm_target: exact match against the cycle's farm_target string.
    Returns {ok: True, cycles: list[dict]} — each cycle has root-level
    fields only (no full output list).
    """
    conn = get_connection()
    try:
        cycles = farm.list_cycles(conn, status=status, farm_target=farm_target)
        return {"ok": True, "cycles": cycles}
    finally:
        conn.close()


def farm_export_cycle_bundle(
    cycle_id: str,
    out_path: str,
    build_snapshot_path: Optional[str] = None,
    author: str = "Pedro",
    readme: Optional[str] = None,
) -> dict[str, Any]:
    """Export a closed cycle to a .farm.graph bundle (zip).

    out_path: destination file path for the bundle (e.g. 'exports/my_cycle.farm.graph').
    build_snapshot_path: optional path to a .build file to include in the bundle.
    author: name recorded in the bundle manifest.
    readme: optional override for the auto-generated README.md inside the bundle.
    Returns {ok: True, out_path: str} or {ok: False, error: str}.
    """
    conn = get_connection()
    try:
        result_path = farm.export_cycle_bundle(
            conn,
            cycle_id,
            out_path,
            build_snapshot_path=build_snapshot_path,
            author=author,
            readme=readme,
        )
        return {"ok": True, "out_path": result_path}
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()
