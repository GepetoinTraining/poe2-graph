"""NetworkX graph built from the passive tree JSON, plus canonical queries.

The graph is keyed by node `skill` (the uint16 hash) so it composes directly with
parser output. Edges come from the tree's top-level `edges` array, which is
first-class addressable in the schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import networkx as nx
from networkx.algorithms.approximation import steiner_tree

from parser import Build, NodeRecord
from resolvers import Tree


def build_graph(tree: Tree) -> nx.Graph:
    """Build an undirected graph over node `skill` hashes.

    Atlas trees have no `edges` array — they only carry per-node `out`/`in`
    adjacency lists. We accept both schemas.
    """
    g = nx.Graph()

    for node in tree.raw["nodes"].values():
        hash_ = node.get("skill")
        if hash_ is None:
            continue
        g.add_node(hash_, **{k: v for k, v in node.items() if k not in ("out", "in")})

    edges = tree.raw.get("edges")
    if edges:
        for e in edges:
            src = _resolve_edge_endpoint(tree, e["from"])
            dst = _resolve_edge_endpoint(tree, e["to"])
            if src is not None and dst is not None:
                g.add_edge(src, dst)
    else:
        for node in tree.raw["nodes"].values():
            src = node.get("skill")
            if src is None:
                continue
            for nbr_str in node.get("out", []):
                dst_id = str(nbr_str)
                nbr_node = tree.raw["nodes"].get(dst_id)
                if nbr_node and "skill" in nbr_node:
                    g.add_edge(src, nbr_node["skill"])

    return g


def _resolve_edge_endpoint(tree: Tree, endpoint) -> Optional[int]:
    """Edges reference nodes by string id; we want the skill hash."""
    if isinstance(endpoint, int):
        return endpoint
    node = tree.raw["nodes"].get(str(endpoint))
    return node.get("skill") if node else None


def class_start_node(tree: Tree, class_id: int) -> Optional[int]:
    """The starting node hash for a given class id.

    PoE 2's six wheel-start positions are shared across original/new class
    pairs: each start node carries `classStartIndex` as a list (e.g. [1, 7]
    means both Witch and Sorceress start there). We scan that list.
    """
    if not (0 <= class_id < len(tree.classes)):
        return None
    for n in tree.raw["nodes"].values():
        csi = n.get("classStartIndex")
        if csi is None:
            continue
        if isinstance(csi, list) and class_id in csi:
            return n.get("skill")
        if csi == class_id:  # tolerate scalar form just in case
            return n.get("skill")
    return None


def ascendancy_start_node(tree: Tree, ascendancy_key: str) -> Optional[int]:
    """The starting node hash for an ascendancy (e.g. 'Sorceress1' = Stormweaver).

    Ascendancy start nodes have `isAscendancyStart: True` and an `ascendancyId`
    field matching the ascendancy key.
    """
    for n in tree.raw["nodes"].values():
        if n.get("isAscendancyStart") and n.get("ascendancyId") == ascendancy_key:
            return n.get("skill")
    return None


def allocated_hashes(build: Build) -> set[int]:
    return {r.node_hash for r in build.records}


def shortest_path(g: nx.Graph, source: int, target: int) -> list[int]:
    return nx.shortest_path(g, source, target)


def shortest_path_length(g: nx.Graph, source: int, target: int) -> int:
    return nx.shortest_path_length(g, source, target)


def orphans(g: nx.Graph, build: Build, start: int) -> set[int]:
    """Allocated nodes not connected to `start` through the allocated subgraph."""
    allocated = allocated_hashes(build) | {start}
    sub = g.subgraph(allocated)
    if start not in sub:
        return allocated - {start}
    reachable = set(nx.node_connected_component(sub, start))
    return allocated - reachable - {start}


def nearest_unallocated_notables(g: nx.Graph, build: Build, tree: Tree, limit: int = 5) -> list[tuple[int, int]]:
    """Return (notable_hash, distance) pairs reachable from any allocated node.

    Distance is hops in the full graph, ignoring allocation.
    """
    allocated = allocated_hashes(build)
    notables = {h for h, attrs in g.nodes(data=True) if attrs.get("isNotable") and h not in allocated}
    results: list[tuple[int, int]] = []
    for n in notables:
        try:
            d = min(nx.shortest_path_length(g, src, n) for src in allocated if src in g)
        except (nx.NetworkXNoPath, ValueError):
            continue
        results.append((n, d))
    results.sort(key=lambda x: x[1])
    return results[:limit]


def diff_builds(a: Build, b: Build) -> dict[str, set[int]]:
    ha, hb = allocated_hashes(a), allocated_hashes(b)
    return {"only_a": ha - hb, "only_b": hb - ha, "shared": ha & hb}


def steiner_route(g: nx.Graph, terminals: Iterable[int]) -> set[int]:
    """Approximate Steiner tree connecting all terminal nodes.

    Returns the node set of the tree (terminals + intermediate nodes needed).
    Networkx's Mehlhorn implementation 2-approximates and is good enough for
    build planning.

    The passive tree is *not* one connected component (ascendancies are
    separate). We restrict to the connected component containing the first
    terminal — terminals in other components are dropped silently.
    """
    terms = [t for t in terminals if t in g]
    if len(terms) < 2:
        return set(terms)
    component = set(nx.node_connected_component(g, terms[0]))
    in_component = [t for t in terms if t in component]
    if len(in_component) < 2:
        return set(terms)
    sub = g.subgraph(component)
    tree_sub = steiner_tree(sub, in_component)
    return set(tree_sub.nodes())


@dataclass
class BuildSummary:
    character_class: Optional[str]
    ascendancy: Optional[str]
    total_records: int
    notables: list[str]
    keystones: list[str]
    jewel_sockets: int
    masteries: int
    attribute_choices: dict[str, int]
    weapon_set_split: dict[Optional[int], int]


def summarize(build: Build, tree: Tree) -> BuildSummary:
    notables: list[str] = []
    keystones: list[str] = []
    jewel_sockets = 0
    masteries = 0
    attribute_choices: dict[str, int] = {}
    weapon_set_split: dict[Optional[int], int] = {}

    for r in build.records:
        weapon_set_split[r.weapon_set] = weapon_set_split.get(r.weapon_set, 0) + 1

        node = tree.node_by_hash(r.node_hash)
        if not node:
            continue
        if node.get("isNotable"):
            notables.append(node.get("name", "?"))
        if node.get("isKeystone"):
            keystones.append(node.get("name", "?"))
        if node.get("isJewelSocket"):
            jewel_sockets += 1
        if node.get("isMastery"):
            masteries += 1

        if r.has_skill_override and r.skill_override is not None:
            ov_name = tree.override_name(r.skill_override) or f"override_{r.skill_override}"
            attribute_choices[ov_name] = attribute_choices.get(ov_name, 0) + 1

    return BuildSummary(
        character_class=tree.class_name(build.character_class),
        ascendancy=tree.ascendancy_name(build.character_class, build.ascendancy),
        total_records=len(build.records),
        notables=sorted(notables),
        keystones=sorted(keystones),
        jewel_sockets=jewel_sockets,
        masteries=masteries,
        attribute_choices=attribute_choices,
        weapon_set_split=weapon_set_split,
    )
