---
name: poe2-graph
description: |
  Read and write Path of Exile 2 builds — passive-tree URLs, .build files
  (which the game's file watcher renders inline), and item/mod data from
  poe2db.tw. Use when the user asks about PoE 2 builds, wants to analyze a
  passive tree URL, generate a .build file for the BuildPlanner folder, or
  reason about item modifier weights and tiers.
metadata:
  type: skill
  status: phase-1-complete
---

# poe2-graph

A Claude-native toolkit for Path of Exile 2 build planning. Reads build URLs and `.build` files, walks the graph, answers planning questions, and emits annotated `.build` files the game ingests directly via its file watcher.

## Architectural recognition

PoE 2 ships its build-construction game **as a graph database**. Passive tree, atlas tree, ascendancies, weapon-set specializations, and choice-resolution overrides share one schema: nodes addressable by 16-bit hash, with a separate `skillOverrides` table for multi-choice resolution. Sources (jewels, items, passives, skill overrides) all collapse to the same flat stat table at bind time; the combat loop is source-blind.

Every other PoE 2 tool re-implements GGG's resolution layer in Lua/JS and breaks every patch. We **trust the canonical graph data GGG publishes** and only do graph operations on it. Maintenance scales O(1) per patch: refresh the JSON, ship.

**Non-goals**: we don't simulate damage, compute DPS, or replace Path of Building. We walk the graph, aggregate stat strings, emit annotations.

## Layout

```
poe2-graph/
├── SKILL.md                # this file
├── parser.py               # web URL byte codec (v7 format)
├── build_reader.py         # parse .build JSON
├── build_writer.py         # emit .build JSON with markup (phase 2 — TBD)
├── graph.py                # NetworkX wrapper + canonical queries + summary
├── resolvers.py            # numeric_id ↔ string_id ↔ display joins
├── stats.py                # stat string → structured tuple (minimal)
├── poe2db_client.py        # poe2db.tw fetcher (inline ModsView JSON)
├── data/
│   ├── passive-tree.json   # 5.3MB, 5102 nodes (5101 + structural root)
│   ├── atlas-tree.json     # 1.4MB, 988 nodes
│   ├── manifest.json       # version + fetch date + sources
│   └── poe2db_cache/       # 24h-TTL category dumps
├── examples/
│   ├── pedro-stormweaver.txt   # verified test URL (Sorceress/Stormweaver)
│   └── example.build           # GGG's reference (Pedro to drop in)
└── tests/                  # 19 tests, all green against the test corpus
```

## The v7 byte format

```
HEADER (8 bytes)
  uint32   version          (always 7)
  uint8    class             (0-11, see Tree.class_name)
  uint8    ascendancy        (1-indexed; 0 = no choice)
  uint16   record count (n)

RECORDS (variable, n entries)
  uint16   node hash
  uint16   flags
  uint8?   weapon set        if (flags & 0b00000001)
  uint16?  skill override    if (flags & 0b00000010)
```

Flag combinations observed:
- `0x0000` = plain allocation (shared across both weapon sets)
- `0x0001` = weapon-set-specific
- `0x0002` = multi-choice (Attribute, Mastery — uses skillOverrides table)
- `0x0003` = both

Higher bits are reserved by GGG.

## The two-ID reality

Each passive node has **two identifiers** in the tree JSON:
- `skill` (uint16): used by the web URL binary format
- `id` (string): used by the `.build` JSON format (e.g. `intelligence11`)

**The dict key in `tree.nodes` is the stringified skill hash, NOT the string id.** Use `tree.nodes_by_string_id` (built by indexing on `node.id`) for `.build`-format lookups. Use `tree.nodes_by_skill_hash` for URL-format lookups. See `resolvers.py`.

Ascendancy IDs are **1-indexed** in the byte format (0 = no choice). The ascendancy entries in `tree.classes[i].ascendancies` are dicts with a `name` field; some slots are `None` for unreleased ascendancies.

## The `.build` JSON format

The game's BuildPlanner directory watches for `.build` files and renders inline guidance. Schema at https://www.pathofexile.com/developer/docs/game.

`additional_text` supports nested markup: `<m>{<red>{Pick after level 30}}` = medium font + red. See `build_writer.py` (phase 2) for the markup helpers.

## Canonical query playbook

| Question | Operation |
|---|---|
| Distance from class start to keystone X? | `nx.shortest_path_length(g, start, X)` |
| Which allocated nodes are orphaned? | `graph.orphans(g, build, start)` |
| Nearest unallocated notable? | `graph.nearest_unallocated_notables(g, build, tree)` |
| Optimal route through N notables? | `graph.steiner_route(g, [n1, n2, ...])` |
| Build A vs Build B diff? | `graph.diff_builds(a, b)` |
| Full summary (class, asc, notables, keystones, dual-spec)? | `graph.summarize(build, tree)` |
| Stat aggregation? | `stats.aggregate([stats.parse(s) for s in lines])` |

## Producing a build — the Allocation API

`allocation.Allocation` is the mutable builder. Use it whenever Claude is *constructing* a build (from scratch, or extending an existing one):

```python
import resolvers, graph
from allocation import Allocation

tree = resolvers.load_passive_tree()
g = graph.build_graph(tree)

# Start fresh
alloc = Allocation.new(tree, g, "Sorceress", "Stormweaver")

# Or load an existing URL/Build and extend it
alloc = Allocation.from_url(url, tree, g)

# Mutate
alloc.allocate("intelligence11")               # by string id
alloc.allocate(54321, weapon_set=1)            # by skill hash, with weapon-set tag
alloc.allocate("attribute_node", skill_override=57022)  # multi-choice (+5 Int)
alloc.deallocate("intelligence11")

# High-level routing
alloc.extend_to("Ancestral Bond")              # auto-route shortest path
alloc.route_through("Raw Power", "Sanguimancy") # Steiner tree across targets

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
# to .build: use build_writer.from_build(alloc.to_build(), tree, ...)
```

**Invariants the Allocation maintains:**
- Class start (and ascendancy start, when set) are **implicit** per the byte format. They aren't records and don't count toward `cost_to`.
- Flags are derived from `weapon_set`/`skill_override` automatically — no need to hand-pack them.
- `extend_to` and `route_through` only allocate nodes that aren't already implicit or recorded.

**Graph topology to know:**
- The passive tree is **not** one connected component — each ascendancy is its own subgraph. Steiner across components silently drops unreachable terminals.
- The six wheel-start positions are shared across original/new class pairs: Marauder/Warrior, Witch/Sorceress, Ranger/Huntress, Duelist/Mercenary, Shadow/Monk, Templar/Druid.
- Ascendancy IDs are 1-indexed (0 = no choice). `Sorceress1` = Stormweaver, `Sorceress2` = Chronomancer, `Sorceress3` = Disciple of Varashta.

## poe2db data delivery

**There is no public CDN at `cdn.poe2db.tw`.** All `/cache2/*` paths return 403. CDN serves only static assets (CSS/JS/images).

The main site at `https://poe2db.tw/us/{Plural_Snake_Case}` returns HTML with the structured JSON embedded inline as `new ModsView({...giant config...});`. The page's rendered DOM is the *output* of that constructor — the inline JSON is the source. `poe2db_client.fetch_category("Amulets")` does the GET, extracts the JSON, returns it.

URL slugs use plural snake-case: `Amulets`, `Rings`, `Belts`, `Body_Armours`, `Helmets`, `Wands`, `Spears`, `Crossbows`. Singular slugs 404.

Tier ladders come from grouping rows by `ModFamilyList` (or trailing digit on `hover`). All tier data is in the same inline JSON — no XHR, no modal lazy-load.

## Self-updating

The skill knows how to update itself. Three layers, each independent:

| Layer | Source | Cadence |
|---|---|---|
| Skill code | This repo's GitHub | When we ship improvements |
| Tree data (passive + atlas) | `GepetoinTraining/{poe2-skilltree, atlastree}-export` forks | Per game patch |
| poe2db item/mod cache | poe2db.tw inline JSON | 24h TTL (already 24h-cached by `poe2db_client`) |

**Sacrosanct paths** that no update touches: `EXILE/`, `PLAYER.md`, `LEAGUE_*.md`, `CHARACTER_*.md`. Player data is yours.

```bash
python updater.py status              # report staleness across all layers
python updater.py update-data         # refresh tree data only
python updater.py update-skill        # git pull skill code only
python updater.py invalidate-cache    # wipe poe2db cache
python updater.py update-all          # all three
```

`data/manifest.json` carries the current `skill_version`, upstream commit refs, and the `protected_paths` list. The updater reads it at every operation and writes back updated commit refs after each pull.

## What this skill is not

- **Not** a damage simulator. We don't compute DPS, apply conditional stats, or model combat. Path of Building does that.
- **Not** an OAuth client. The MCP connector that reads live character data is a separate, post-league deliverable.
- **Not** a UI. The artifact layer (Phase 3, post-league-start) renders results visually; this skill returns data.
