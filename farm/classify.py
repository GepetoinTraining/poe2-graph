"""farm.classify — mod-regex classification pass against cycle outputs.

Reads valuable_mod_edges from the craft graph; for each output node in the
cycle, sets classification='price_me' if any mod matches, else 'gold_pile'.

If no craft graph data exists the function classifies everything 'gold_pile'
and returns without error.
"""

from __future__ import annotations

import re
from typing import Optional

import store


def classify_outputs(
    conn,
    cycle_id: str,
    *,
    valuable_mod_threshold: float = 0.5,
) -> dict:
    """Run the mod-regex classification pass (§5).

    Returns summary: {'classified': N, 'price_me': K, 'gold_pile': N-K}.
    Status remains ACTIVE; classification is metadata, not state.
    """
    # 1. Collect valuable patterns from the craft graph.
    valuable_patterns: list[tuple[re.Pattern, float]] = []
    mod_edges = store.query_edges(conn, edge_type="mod_market_value")
    for edge in mod_edges:
        if edge["weight"] < valuable_mod_threshold:
            continue
        mod_node = store.get_node(conn, edge["target_id"])
        if mod_node is None:
            continue
        pattern_str = store.xml_extract(mod_node["payload"], "/mod/@pattern")
        if not pattern_str:
            pattern_str = store.xml_extract(mod_node["payload"], "/mod/pattern")
        if pattern_str:
            try:
                valuable_patterns.append((re.compile(pattern_str, re.IGNORECASE), edge["weight"]))
            except re.error:
                # malformed regex in catalog data — skip
                continue

    # 2. Walk output nodes in this cycle.
    all_nodes = store.query_nodes(conn, graph_id=cycle_id, graph_type="farm")
    price_me = 0
    gold_pile = 0

    for node in all_nodes:
        payload = node["payload"]
        # Skip non-output nodes (cycle root starts with <cycle, inputs with <input)
        p_stripped = payload.lstrip()
        if not p_stripped.startswith("<output"):
            continue

        mods = store.xml_extract(payload, "/output/mods") or ""
        classification = "gold_pile"
        for pattern, _weight in valuable_patterns:
            if pattern.search(mods):
                classification = "price_me"
                break

        new_payload = store.xml_set(payload, "/output/@classification", classification)
        store.update_node_payload(conn, node["node_id"], new_payload)

        if classification == "price_me":
            price_me += 1
        else:
            gold_pile += 1

    total = price_me + gold_pile
    return {
        "classified": total,
        "price_me": price_me,
        "gold_pile": gold_pile,
    }
