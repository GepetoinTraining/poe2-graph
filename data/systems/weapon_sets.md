---
schema_version: 1
topic: weapon_sets
game: poe2
last_verified: 2026-05-26
related_topics: [passive_tree, skill_gems, dual_specialization]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know about dual weapon sets."
  learning: "Knows weapons can be swapped but doesn't know about set-specific passive allocation."
  competent: "Allocates weapon-set-specific passive points; uses skill-to-weapon binding for automatic swap."
  confident: "Engineers dual-specialization builds where each set has a distinct identity (e.g. clearing + bossing); knows the breakpoints where carrying two sets is better than one."
attributed_to: []
---

# Weapon Sets (PoE 2)

PoE 2's signature build-flexibility mechanic. You can carry **two distinct weapon sets** and dynamically **swap allocated passive nodes** based on which set is active. Coined *"dual specialization."*

## The core mechanic

Each character has:

- **Weapon Set 1** + **Weapon Set 2** — two complete weapon slot configurations (main hand + off-hand).
- **Weapon Set Points** — passive points you can allocate **per set** that **only count when that set is active**.

At end of campaign (level ~60–65), you should have:

- **24 Weapon Set 1 points**
- **24 Weapon Set 2 points**

These are *on top of* your normal passive tree allocation. They're a parallel layer specific to each set.

## How to allocate weapon-set points

The requirements:

1. **Have unallocated skill points** at the moment of allocation (you can't take from an existing allocation).
2. **Have Weapon Set Point Maximum > 0** (earned through campaign progress; not all 48 are available from level 1).
3. **Select which Weapon Set the point assigns to** before placing it.

In the passive tree UI:

- Set-1 allocations show with one color/icon.
- Set-2 allocations show with another.
- Nodes allocated to *both* sets count for both.
- Nodes allocated to *neither* set count globally (the default).

## Automatic weapon swapping

Each **skill** can be bound to a specific weapon set. When you activate the bound skill:

1. Character **automatically swaps to that weapon set**.
2. The **set-specific passive allocations activate**.
3. The skill executes with the correct passive tree state.

Since **0.3**, **weapon swap is instant** — zero delay between configurations.

This enables the canonical PoE 2 pattern: **one weapon set for clearing, one for bossing**. The clear-set might be a wand + spell-cascade allocation; the boss-set might be a 2H melee + crit allocation. The same character runs both vectors fluidly.

## Strategic shapes for dual specialization

| Pattern | Set 1 | Set 2 |
|---|---|---|
| Clear vs single-target | Spell-cascade caster | High-crit melee |
| Hybrid scaling | Attack-source | Spell-source |
| Phase-specific | Speed-mapping | Pinnacle-boss |
| Defense-swap | Offensive (max DPS) | Defensive (max ehp) |

The point: **each set is a complete character**, not a partial substitute.

## Common mistakes

- **Treating Set 2 as a backup weapon** — wastes the 24 points and the dynamic-swap mechanic entirely.
- **Allocating Set 2 without a clear plan** — random Set-2 allocations don't compound. Have a build-shape in mind before placing the first Set-2 point.
- **Bypassing skill→weapon binding** — manually swapping in-combat introduces fragility. Bind skills to sets so the swap is automatic.
- **Trying to share too many nodes between Set 1 and 2** — dual-allocated nodes are the *exception*, not the rule. Each set's identity should be distinct.

## When to skip dual specialization entirely

Single-set focus is sometimes correct:

- **League-start, levels 1-60** — too few points to make two builds.
- **Tight-budget builds** — 24 wasted points if Set 2 doesn't add real capability.
- **Skill-gem-poor classes** — if you can't fill both sets with meaningful skills, Set 2 is dead weight.

The 0.5 endgame is **engineered around dual specialization**, but it's optional in the campaign.

## See also

- `skill_gems` — the layer skills bind from
- `parser.py` weapon_set values — bytes 1 and 2 in the `.build` URL format (PoE 2 1-indexed; see `data/research-deleteatend/`)
