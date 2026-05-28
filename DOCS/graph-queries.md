---
id: graph-queries
file: DOCS/graph-queries.md
topic: Canonical NetworkX queries on the passive tree — paths, orphans, Steiner, summary
priority: reference
modules: [graph, resolvers]
tags: [graph, queries, networkx, shortest_path, steiner, summary]
when_to_read: |
  User asks about path costs, nearest unallocated notables, build diffs,
  whether allocated nodes are connected, Steiner-tree routing across multiple
  targets, full build summary (class, ascendancy, notables, keystones, dual-spec),
  or any "give me a number about the tree" question.
---

# Canonical graph queries

## Loading the graph

```python
from graph import resolvers, network as graph
tree = resolvers.load_passive_tree()
g = graph.build_graph(tree)
# → NetworkX undirected graph, 5102 nodes, 6021 edges
```

The graph builder accepts both the passive tree (top-level `edges` array) and the atlas tree (per-node `out`/`in` adjacency only). See `DOCS/byte-format.md` for atlas schema divergence.

## The playbook

| Question | Operation |
|---|---|
| Distance from class start to keystone X? | `nx.shortest_path_length(g, start, X)` |
| Which allocated nodes are orphaned? | `graph.orphans(g, build, start)` |
| Nearest unallocated notable? | `graph.nearest_unallocated_notables(g, build, tree)` |
| Optimal route through N notables? | `graph.steiner_route(g, [n1, n2, ...])` |
| Build A vs Build B diff? | `graph.diff_builds(a, b)` |
| Full summary (class, asc, notables, keystones, dual-spec)? | `graph.summarize(build, tree)` |
| Class start node for class id? | `graph.class_start_node(tree, class_id)` |
| Ascendancy start node? | `graph.ascendancy_start_node(tree, "Sorceress1")` |

## The non-connectivity warning

The passive tree is **not** one connected component. Each ascendancy is its own subgraph. `nx.is_connected(g)` returns False. `steiner_route` restricts to the component containing the first terminal — terminals in other components are silently dropped.

## Build summary shape

`graph.summarize(build, tree)` returns a `BuildSummary` with:

- `character_class` (resolved name)
- `ascendancy` (resolved name, or None)
- `total_records`
- `notables: list[str]`
- `keystones: list[str]`
- `jewel_sockets: int`
- `masteries: int`
- `attribute_choices: dict[str, int]` (e.g. `{"Intelligence": 31, "Dexterity": 5, "Strength": 3}`)
- `weapon_set_split: dict[Optional[int], int]` (e.g. `{None: 109, 1: 8, 2: 25}`)

Pedro's verified Sorceress build round-trips through this with exact counts matching the byte-format flag distribution.

## See also

- `DOCS/byte-format.md` — atlas schema differs; weapon_set is 1-indexed
- `DOCS/build-construction.md` — `Allocation` wraps these queries for mutation-friendly use
