---
schema_version: 1
topic: atlas_passive_tree
game: poe2
last_verified: 2026-05-26
related_topics: [atlas, endgame, mapping, atlas_towers_and_tablets, league_0_5_return_of_the_ancients]
prerequisites: []
mastery_levels:
  not_started: "Hasn't unlocked the atlas tree yet."
  learning: "Knows the tree exists; needs guidance on which content to specialize."
  competent: "Specializes in 1-2 league mechanics with confidence; reroll points understood."
  confident: "Optimizes the tree per farming strategy; knows breakpoints, knows which nodes are bait."
attributed_to: [Steelmage, palsteron, Empyrian]
---

# Atlas Passive Tree (PoE 2)

A **separate passive tree** for the endgame. Earned by completing maps; specializes which content density and reward types your atlas produces.

## How it differs from the campaign passive tree

The atlas tree is structurally distinct (see `data/research-deleteatend/` for the schema notes):

- **No string IDs** — atlas nodes are keyed only by numeric `skill` hash. The campaign tree carries both numeric and `id` strings (`intelligence11`, etc.).
- **No top-level `edges` array** — adjacency lives only in per-node `out` and `in` lists.
- **Has `isWormhole`, `reminderText`, `flavourText`** — fields the campaign tree doesn't carry.
- **No `grantedSkill`, no `ascendancyId`** — atlas nodes don't grant active skills or ascendancies.

For tooling: the atlas tree is **not** a drop-in for the campaign tree. Build resolvers and `.build` writers must branch.

## Counts and variants

- **988 nodes** in the standard tree.
- Variants: `data.json` (standard), `league.json`, `ruthless.json`, `ruthless-league.json`. Same schema; ruthless variants carry a `"ruthless": true` flag.
- **300+ nodes** as of 0.5 (expanded from the original ~200-era tree).

## How to allocate

Points are earned **per map completion** (and from specific atlas-quest milestones). The full tree gates roughly at 100+ maps completed.

The **single-active-strategy** discipline: pick **1–2 league mechanics or content types** to specialize. The atlas tree rewards depth in 1–2 specialties more than breadth — a generalist tree never reaches the breakpoints that make any single mechanic profitable.

Common specialization clusters as of 0.5:
- **Map IIQ / IIR** — generic loot density
- **Mechanic-specific clusters** — one cluster each for major mechanics (Abyssal, Breach, Ritual, Vaal, Wisps, Strongboxes, etc.)
- **Pinnacle / boss-focused nodes** — for citadel + pinnacle progression

## Rerolling points

The atlas tree allows **point refunds** at a currency cost. Common scenarios:

- League starts → specialize in early-league economic mechanic (essence, scarabs)
- Mid-league → reroll into a mature mapping mechanic
- End-of-league → reroll into pinnacle / citadel content

This is structurally different from the campaign tree where refunds are deliberately scarce — atlas point allocation is meant to evolve.

## Common mistakes

- **Spreading across 5+ mechanics** — none reaches the threshold that makes them profitable.
- **Following a meta atlas tree without league context** — atlas-tree optimum shifts week by week as currency prices shift. Pure copy-paste underperforms; understanding the *reasoning* in a published tree adapts it.
- **Allocating mechanic clusters before unlocking the mechanic** — atlas tree nodes don't unlock the mechanic itself; they amplify a mechanic you've already encountered. Check the unlock prerequisite before allocating.

## See also

- `atlas_towers_and_tablets` — the layer that *delivers* the mechanics the tree amplifies
- `waystones` — the map currency that drives everything atlas
- `league_0_5_return_of_the_ancients` — current state of the tree (300+ nodes, Fortress hub)
