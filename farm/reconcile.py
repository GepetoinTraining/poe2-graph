"""farm.reconcile — double-booked reconciliation query.

For each cycle output node, checks whether a graph_ref of type
'in_main_inventory' exists. Returns gap statistics; never auto-fixes.
"""

from __future__ import annotations

import store


def reconcile_cycle(conn, cycle_id: str) -> dict:
    """Double-booked reconciliation (§5).

    Returns:
      {
        'cycle_output_count': int,
        'main_received_count': int,
        'reconciliation_gap': int,
        'unmatched_output_ids': list[str],
      }

    If gap != 0, the caller surfaces an audit warning. We don't auto-fix.
    Status remains ACTIVE.
    """
    all_nodes = store.query_nodes(conn, graph_id=cycle_id, graph_type="farm")

    outputs = [
        n for n in all_nodes
        if n["payload"].lstrip().startswith("<output")
    ]

    cycle_output_count = len(outputs)
    main_received_count = 0
    unmatched: list[str] = []

    for output in outputs:
        refs = store.query_graph_refs(conn, referencing_node_id=output["node_id"])
        if any(r["ref_type"] == "in_main_inventory" for r in refs):
            main_received_count += 1
        else:
            unmatched.append(output["node_id"])

    return {
        "cycle_output_count": cycle_output_count,
        "main_received_count": main_received_count,
        "reconciliation_gap": cycle_output_count - main_received_count,
        "unmatched_output_ids": unmatched,
    }
