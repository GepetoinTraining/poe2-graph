"""Allocation — the mutable builder layer over the passive tree.

This is what Claude uses when *constructing* a build (vs. parser+graph which
read an existing one). The Allocation tracks:

  - which nodes are currently allocated (by node_hash)
  - per-node weapon_set + skill_override (the same fields the byte format
    carries, so we can round-trip to URL or .build)
  - the class + ascendancy choice

Operations preserve the invariant that every record has the correct flags
derived from its weapon_set / skill_override values. Mutations are
in-place and cheap — this is meant to be used in a Claude loop where each
turn proposes a few allocations and inspects the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional, Union

import networkx as nx

from graph import network as _graph
from graph.parser import (
    Build,
    NodeRecord,
    FLAG_WEAPON_SET,
    FLAG_SKILL_OVERRIDE,
    SUPPORTED_VERSION,
    encode_url,
)
from graph.resolvers import Tree


NodeKey = Union[int, str]  # accept skill hash OR string id


def _flags_for(weapon_set: Optional[int], skill_override: Optional[int]) -> int:
    f = 0
    if weapon_set is not None:
        f |= FLAG_WEAPON_SET
    if skill_override is not None:
        f |= FLAG_SKILL_OVERRIDE
    return f


@dataclass
class Allocation:
    tree: Tree
    g: nx.Graph
    character_class: int
    ascendancy: int = 0
    records: dict[int, NodeRecord] = field(default_factory=dict)

    # ----- constructors -----

    @classmethod
    def new(
        cls,
        tree: Tree,
        g: nx.Graph,
        character_class: Union[int, str],
        ascendancy: Union[int, str, None] = None,
    ) -> "Allocation":
        """Start an empty allocation for a given class + optional ascendancy."""
        class_id = _resolve_class(tree, character_class)
        asc_id = _resolve_ascendancy(tree, class_id, ascendancy)
        return cls(tree=tree, g=g, character_class=class_id, ascendancy=asc_id)

    @classmethod
    def from_build(cls, build: Build, tree: Tree, g: nx.Graph) -> "Allocation":
        records = {r.node_hash: NodeRecord(r.node_hash, r.flags, r.weapon_set, r.skill_override) for r in build.records}
        return cls(
            tree=tree, g=g,
            character_class=build.character_class,
            ascendancy=build.ascendancy,
            records=records,
        )

    @classmethod
    def from_url(cls, url_or_code: str, tree: Tree, g: nx.Graph) -> "Allocation":
        from graph.parser import parse
        return cls.from_build(parse(url_or_code), tree, g)

    # ----- key resolution -----

    def _to_hash(self, key: NodeKey) -> int:
        if isinstance(key, int):
            return key
        h = self.tree.string_id_to_hash(key)
        if h is None:
            raise KeyError(f"unknown node id: {key!r}")
        return h

    # ----- mutations -----

    def allocate(
        self,
        key: NodeKey,
        weapon_set: Optional[int] = None,
        skill_override: Optional[int] = None,
    ) -> NodeRecord:
        """Add a node to the allocation. Idempotent: re-allocating updates flags."""
        h = self._to_hash(key)
        if h not in self.g:
            raise ValueError(f"node {key!r} (hash {h}) not in graph")
        rec = NodeRecord(
            node_hash=h,
            flags=_flags_for(weapon_set, skill_override),
            weapon_set=weapon_set,
            skill_override=skill_override,
        )
        self.records[h] = rec
        return rec

    def deallocate(self, key: NodeKey) -> bool:
        """Remove a node. Returns True if it was present."""
        h = self._to_hash(key)
        return self.records.pop(h, None) is not None

    def allocate_many(self, keys: Iterable[NodeKey]) -> None:
        for k in keys:
            self.allocate(k)

    def extend_to(self, target: NodeKey, weapon_set: Optional[int] = None) -> list[int]:
        """Allocate the shortest path from the current frontier to `target`.

        Returns the list of newly-allocated node hashes in path order. The
        class start (and ascendancy start, if set) are implicit per the byte
        format — they aren't counted or allocated as records.
        """
        target_h = self._to_hash(target)
        if target_h in self.records:
            return []

        seed = self._connected_seed()
        if not seed:
            raise ValueError("no allocated source to extend from")

        path = _shortest_path_from_any(self.g, seed, target_h)
        newly: list[int] = []
        for h in path:
            if h in seed:
                continue  # implicit (start node) or already allocated
            self.allocate(h, weapon_set=weapon_set)
            newly.append(h)
        return newly

    def route_through(self, *targets: NodeKey, include_start: bool = True) -> list[int]:
        """Allocate a Steiner-tree route covering all targets (plus the class
        start if `include_start`). Returns the list of newly-allocated hashes.
        """
        terminals: set[int] = {self._to_hash(t) for t in targets}
        if include_start:
            start = self.class_start_hash
            if start is not None:
                terminals.add(start)
        tree_nodes = _graph.steiner_route(self.g, terminals)
        newly: list[int] = []
        for h in tree_nodes:
            if h not in self.records:
                self.allocate(h)
                newly.append(h)
        return newly

    # ----- inspection -----

    @property
    def allocated(self) -> set[int]:
        return set(self.records.keys())

    @property
    def class_start_hash(self) -> Optional[int]:
        return _graph.class_start_node(self.tree, self.character_class)

    @property
    def ascendancy_key(self) -> Optional[str]:
        if self.ascendancy == 0:
            return None
        class_name = self.tree.class_name(self.character_class)
        return f"{class_name}{self.ascendancy}" if class_name else None

    def _connected_seed(self) -> set[int]:
        """Nodes we can pathfind from — allocated set ∪ class start."""
        seed = set(self.records.keys())
        start = self.class_start_hash
        if start is not None:
            seed.add(start)
        return {h for h in seed if h in self.g}

    @property
    def frontier(self) -> set[int]:
        """Unallocated nodes adjacent to any allocated node (or class start)."""
        seed = self._connected_seed()
        front: set[int] = set()
        for h in seed:
            for nbr in self.g.neighbors(h):
                if nbr not in self.records and nbr != self.class_start_hash:
                    front.add(nbr)
        return front

    @property
    def is_contiguous(self) -> bool:
        """True if every allocated node is reachable from the class start
        through the allocated subgraph (plus ascendancy start for ascendancy
        nodes).
        """
        return not self.orphans()

    def orphans(self) -> set[int]:
        """Allocated nodes not reachable from class/ascendancy start through
        the allocated subgraph.
        """
        seeds: set[int] = set()
        cs = self.class_start_hash
        if cs is not None:
            seeds.add(cs)
        if self.ascendancy_key:
            asc = _graph.ascendancy_start_node(self.tree, self.ascendancy_key)
            if asc is not None:
                seeds.add(asc)

        nodes = self.allocated | seeds
        sub = self.g.subgraph(nodes)

        reachable: set[int] = set()
        for s in seeds:
            if s in sub:
                reachable |= set(nx.node_connected_component(sub, s))

        return self.allocated - reachable

    def shortest_path_to(self, target: NodeKey) -> list[int]:
        """Path from the current frontier (or class start) to target."""
        target_h = self._to_hash(target)
        sources = self._connected_seed()
        return _shortest_path_from_any(self.g, sources, target_h)

    def cost_to(self, target: NodeKey) -> int:
        """How many *new* allocations needed to reach `target`.

        Class/ascendancy start nodes are implicit (encoded in the build header,
        not as records) — they don't count toward cost.
        """
        target_h = self._to_hash(target)
        if target_h in self.records:
            return 0
        seed = self._connected_seed()
        path = _shortest_path_from_any(self.g, seed, target_h)
        return sum(1 for h in path if h not in seed)

    # ----- node-category helpers -----

    def _node(self, h: int) -> Optional[dict]:
        return self.tree.node_by_hash(h)

    def notables(self) -> list[int]:
        return [h for h in self.records if (n := self._node(h)) and n.get("isNotable")]

    def keystones(self) -> list[int]:
        return [h for h in self.records if (n := self._node(h)) and n.get("isKeystone")]

    def jewel_sockets(self) -> list[int]:
        return [h for h in self.records if (n := self._node(h)) and n.get("isJewelSocket")]

    def masteries(self) -> list[int]:
        return [h for h in self.records if (n := self._node(h)) and n.get("isMastery")]

    def nearest_unallocated_notables(self, limit: int = 10) -> list[tuple[int, int]]:
        """Return (notable_hash, hops_from_seed) pairs, sorted by closeness."""
        seed = self._connected_seed()
        if not seed:
            return []
        notables = {
            h for h, attrs in self.g.nodes(data=True)
            if attrs.get("isNotable") and h not in self.records
        }
        out: list[tuple[int, int]] = []
        for n in notables:
            try:
                d = min(nx.shortest_path_length(self.g, s, n) for s in seed if s in self.g)
            except (nx.NetworkXNoPath, ValueError):
                continue
            out.append((n, d))
        out.sort(key=lambda x: x[1])
        return out[:limit]

    # ----- export -----

    def to_build(self) -> Build:
        return Build(
            version=SUPPORTED_VERSION,
            character_class=self.character_class,
            ascendancy=self.ascendancy,
            records=list(self.records.values()),
        )

    def to_url(self) -> str:
        return encode_url(self.to_build())

    def __len__(self) -> int:
        return len(self.records)

    def __contains__(self, key: NodeKey) -> bool:
        try:
            return self._to_hash(key) in self.records
        except KeyError:
            return False

    def __iter__(self) -> Iterator[int]:
        return iter(self.records)


# ----- module-private helpers -----

def _resolve_class(tree: Tree, key: Union[int, str]) -> int:
    if isinstance(key, int):
        return key
    for i, cls in enumerate(tree.classes):
        if cls.get("name", "").lower() == key.lower():
            return i
    raise KeyError(f"unknown class: {key!r}")


def _resolve_ascendancy(tree: Tree, class_id: int, key: Union[int, str, None]) -> int:
    if key is None or key == 0:
        return 0
    if isinstance(key, int):
        return key
    cls = tree.classes[class_id]
    for i, asc in enumerate(cls.get("ascendancies", []), start=1):
        if asc is None:
            continue
        name = asc.get("name") if isinstance(asc, dict) else asc
        if name and name.lower() == key.lower():
            return i
    raise KeyError(f"unknown ascendancy {key!r} for class id {class_id}")


def _shortest_path_from_any(g: nx.Graph, sources: set[int], target: int) -> list[int]:
    """Shortest path from any of `sources` to `target`. Returns the full path
    (including the source endpoint).
    """
    if target in sources:
        return [target]
    if not sources or target not in g:
        raise nx.NetworkXNoPath(f"no path to {target}")

    best: Optional[list[int]] = None
    best_len = float("inf")
    for s in sources:
        if s not in g:
            continue
        try:
            path = nx.shortest_path(g, s, target)
        except nx.NetworkXNoPath:
            continue
        if len(path) < best_len:
            best_len = len(path)
            best = path
    if best is None:
        raise nx.NetworkXNoPath(f"no path to {target} from any source")
    return best
