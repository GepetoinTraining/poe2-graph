---
id: byte-format
file: DOCS/byte-format.md
topic: v7 URL byte format codec, the two-ID reality, and the spec divergences from v0.2
priority: reference
modules: [parser, resolvers]
tags: [byte_format, url_parsing, v7, spec_divergence, two_id]
when_to_read: |
  User pastes or mentions a passive tree URL, asks to parse / decode / encode
  a build URL, asks about the byte format header or flags, asks why two IDs
  exist on the same node, or hits one of the spec divergences (atlas schema
  not matching passive, ascendancy as dict not string, class start as array,
  dict key vs string id, weapon_set values, structural root node).
---

# Byte format + the two-ID reality

## The v7 spec

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

Flag combinations observed in real builds:

- `0x0000` plain allocation (shared across both weapon sets)
- `0x0001` weapon-set-specific
- `0x0002` multi-choice (Attribute, Mastery — uses skillOverrides table)
- `0x0003` both

Higher bits are reserved by GGG.

## The two-ID reality

Each passive node carries two identifiers in the tree JSON:

- `skill` (uint16): used by the web URL binary format
- `id` (string): used by the `.build` JSON format (e.g. `intelligence11`)

**Critical:** the dict key in `tree.nodes` is the stringified skill hash, NOT the string id. Use `tree.nodes_by_string_id` (built by indexing on `node.id`) for `.build`-format lookups; use `tree.nodes_by_skill_hash` for URL-format lookups. See `resolvers.py`.

## Ascendancies

IDs are 1-indexed in the byte format (0 = no choice). The entries in `tree.classes[i].ascendancies` are **dicts** with a `name` field, not strings — some slots are `None` for unreleased ascendancies. Read `.name` from each.

## Class start nodes

The six wheel-start positions each carry `classStartIndex` as an **array** (not a scalar). Class pairs share starts: Marauder/Warrior, Witch/Sorceress, Ranger/Huntress, Duelist/Mercenary, Shadow/Monk, Templar/Druid. PoE 2's three new classes reuse the original six start positions.

The class start node is **implicit in the byte format** — the `class` field in the header determines start position; the start node is NOT in the records array. "Witch start → Ancestral Bond = 17 hops" means 17 *new* allocations on top of the implicit start.

## Tree connectivity

The passive tree is **not** one connected component. Each ascendancy is its own subgraph. `nx.is_connected(g)` returns False. Steiner-tree and shortest-path code must handle this — restrict to the component containing the relevant terminal or class start.

## Atlas tree divergence

Atlas tree does NOT share schema with the passive tree:

- No `id` field — only numeric `skill`
- No top-level `edges` array — only per-node `out`/`in` adjacency
- Has `isWormhole`, `reminderText`, `flavourText` (passive-tree doesn't)
- No `grantedSkill`, no `ascendancyId`

The graph builder handles both via a `tree.raw.get("edges")` fallback to adjacency walk.

## Weapon set values

Spec v0.2 said "0 or 1." Reality: values are **1 and 2** (1-indexed). Pedro's verified build shows `{1: 8, 2: 25}`. Higher values likely reserved for future GGG features (third weapon set).

## Structural root node

The `tree.nodes` dict has a `"root"` entry with no `skill` and no `id` — it's a structural placeholder for the tree's center. Net: 5102 dict entries, 5101 real nodes.

## Module surface

- `parser.parse(url)` — URL or bare code → `Build` object
- `parser.encode(build)` — `Build` → bytes
- `parser.encode_url(build)` — round-trippable URL
- `resolvers.load_passive_tree()` / `load_atlas_tree()` — cached JSON loaders
- `resolvers.Tree.nodes_by_skill_hash` / `nodes_by_string_id` / `nodes_by_dict_key` — three indexes
- `resolvers.Tree.class_name(i)` / `ascendancy_name(class_id, asc_id)` — identity resolution
- `resolvers.Tree.override(id)` / `override_name(id)` — skill-override resolution
