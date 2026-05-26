---
schema_version: 1
topic: essence_crafting
game: poe2
last_verified: 2026-05-26
related_topics: [crafting, currency, harbinger, runes_and_sockets]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know essences exist or what they do."
  learning: "Knows essences guarantee a specific mod tier on a target stat; needs walkthrough on which essence to use when."
  competent: "Can use essences for guaranteed mods on rare items without guidance. Knows the difference between greater / lesser / standard essence tiers."
  confident: "Knows when to essence vs metacraft vs bench. Optimizes essence selection for the target stat and price point. Aware of corrupting-essence variants."
attributed_to: [Ghazzy, Mathil, BeltonPoE]
---

# Essence Crafting (PoE 2)

Essences are a deterministic-mod crafting currency. They're the **"I want THIS modifier"** option.

## What an essence does

Applied to a **normal** or **rare** item, an essence:
1. **Re-rolls all explicit modifiers** on the item.
2. **Guarantees one modifier** of a specific type at a specific tier.
3. Other modifiers roll randomly from the base pool.

The point: when you want a specific stat (life, resists, a damage type) and don't want to gamble for it, an essence is the deterministic path.

## Essence tiers

The naming has tier prefixes — the standard, the greater, the perfect line:

- **Lesser essences** — low-tier guaranteed mod. Drops early.
- **Standard essences** — mid-tier. The workhorse.
- **Greater essences** — high-tier. Drops in endgame.
- **Perfect essences** — top-tier. Rare endgame drop.

A given essence type (e.g. "Essence of Greed") exists at multiple tiers. Use the highest tier you can afford for the slot — lower tiers are usable for early-game / leveling crafts where the mod tier doesn't matter much yet.

## When to use essences vs alternatives

| Goal | Essence is the right tool | Better alternative |
|---|---|---|
| Guarantee one specific affix | ✓ | — |
| Get a specific high-tier mod + control other roll outcomes | partial | Bench-craft if available, then essence-finish |
| Maximum-roll a chase craft | ✗ | Perfect-essence + Divine + harvest finish |
| Cheap leveling rare | ✓ (lesser essence) | Transmute / Augment |

## Common mistakes

- **Using an essence on a high-iLvl base when you only have a low-tier essence** — wastes the base. Match essence tier to base intent.
- **Re-essencing repeatedly trying for a perfect side-roll** — that's gambling, not crafting. If the side-mods matter, set a stop criterion first (see `downside_discipline` edge).
- **Ignoring essence tier inflation** — endgame essences drop the lesser ones in the dust. Don't carry over old assumptions about which essences are valuable.

## Corrupting essence variants

Some essence variants apply **corrupted** outcomes (random implicit mod, possible degradation). Don't use these unless you understand the risk profile.

## See also

- `crafting_currency_overview` — where essences fit in the broader currency taxonomy
- `league_0_3_the_third_edict` — Well of Souls / Bones is an adjacent deterministic crafting surface
- `runes_and_sockets` — once the item is built, runes augment further
