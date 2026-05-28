---
id: build-construction
file: DOCS/build-construction.md
topic: Allocation API + build_writer markup + .build emission for in-game BuildPlanner rendering
priority: action
modules: [allocation, build_reader, build_writer, parser]
tags: [build_construction, allocation, dot_build, markup, build_planner]
when_to_read: |
  User wants Claude to construct a build, extend an existing build URL, propose
  the next allocations, generate a .build file for the game's BuildPlanner
  folder, write markup annotations on passives or inventory slots, or convert
  between URL / Build / .build representations.
---

# Producing a build — the Allocation API + .build emission

## Mutable Allocation builder

`allocation.Allocation` is the API Claude uses when *constructing* a build (either from scratch or extending an existing one).

```python
from graph import resolvers, network as graph
from graph.allocation import Allocation

tree = resolvers.load_passive_tree()
g = graph.build_graph(tree)

# Start fresh
alloc = Allocation.new(tree, g, "Sorceress", "Stormweaver")

# Or load existing URL/Build and extend
alloc = Allocation.from_url(url, tree, g)

# Mutate
alloc.allocate("intelligence11")                          # by string id
alloc.allocate(54321, weapon_set=1)                       # by skill hash, set 1 only
alloc.allocate("attribute_node", skill_override=57022)    # multi-choice (+5 Int)
alloc.deallocate("intelligence11")

# High-level routing
alloc.extend_to("Ancestral Bond")                          # shortest path
alloc.route_through("Raw Power", "Sanguimancy")            # Steiner across targets

# Inspect
alloc.allocated                  # set[int] of node hashes
alloc.frontier                   # set[int] of adjacent unallocated nodes
alloc.is_contiguous              # bool
alloc.orphans()                  # nodes unreachable from start
alloc.notables() / keystones() / jewel_sockets() / masteries()
alloc.cost_to("Ancestral Bond")  # how many new allocations to reach a target
alloc.nearest_unallocated_notables(limit=5)

# Export
alloc.to_build()                 # parser.Build
alloc.to_url()                   # encoded pathofexile2.com URL
```

### Invariants the Allocation maintains

- Class start and ascendancy start are **implicit** per the byte format. They aren't records and don't count toward `cost_to`.
- Flags are derived from `weapon_set` / `skill_override` automatically.
- `extend_to` and `route_through` only allocate nodes that aren't already implicit or recorded.

## The `.build` file format

The game's `Documents/My Games/Path of Exile 2/BuildPlanner/` folder is watched by the client. Drop a `.build` file there and the game renders the routing inline on the tree, gem hints during crafting, gear hints on inventory slots.

Schema documented at https://www.pathofexile.com/developer/docs/game.

### Top-level fields

```json
{
  "name": "...",
  "author": "...",
  "description": "...",
  "ascendancy": "Sorceress1",
  "passives": [ ... ],
  "skills": [ ... ],
  "inventory_slots": [ ... ]
}
```

### Passive entries

Either a bare string id or a richer object:

```json
"intelligence11"
{ "id": "intelligence45",
  "additional_text": "<m>{<blue>{Pick after Crit Overload}}",
  "level_interval": [55, 65],
  "weapon_set": 1 }
```

`level_interval` accepts a single int (start level only) OR `[start, end]`.

### Inventory slots — extended schema

Beyond the v0.2 spec, slots also support:

```json
{ "inventory_id": "Weapon1",
  "unique": "Mageblood",                              // specific unique recommendation
  "hint": "Get this around level 75",                 // short inline hint
  "level_interval": [75, 90],
  "additional_text": "<silver>{Any Two Handed Mace}\n<grey>{...}" }
```

Discovered via natwarth's parser; supports also accept `level_interval`.

## Markup helpers

`build_writer` exposes the markup wrapping functions:

```python
from graph.build_writer import red, green, blue, gold, silver, grey, orange, yellow
from graph.build_writer import bold, italic, underline
from graph.build_writer import small, medium, large
from graph.build_writer import rgb, tag

medium(red("Strength +5 is recommended"))
# → "<m>{<red>{Strength +5 is recommended}}"
```

Wrap braces are mandatory — `<red>text` is a no-op; `<red>{text}` renders.

## Emitting a `.build` from an Allocation

```python
from graph.build_writer import from_build, BuildFile, PassiveEntry, InventorySlot

bf = from_build(
    alloc.to_build(),
    tree,
    name="Crit Spark Stormweaver",
    author="claude + pedro",
    description="...",
    annotations={
        # Per-node-hash annotations to inject as additional_text on passives
        54321: medium(red("Pick this BEFORE the next jewel slot")),
    },
    level_intervals={
        54321: [25, 35],
    },
)
build_writer.assert_valid(bf, tree)   # raises if any passive id doesn't resolve
bf.write("/path/to/BuildPlanner/MyBuild.build")
```

## Item-filter companion

We do **not** generate item filters. Point the player at [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2) (MIT, 2773★) with strictness recommendations appropriate to the build. See `ATTRIBUTIONS.md`.

## See also

- `DOCS/byte-format.md` — the underlying v7 URL codec
- `DOCS/graph-queries.md` — what `extend_to` / `route_through` are doing underneath
- `DOCS/goals.md` — how Allocation operations are sequenced from goal sub-goals
