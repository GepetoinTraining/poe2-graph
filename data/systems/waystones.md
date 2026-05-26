---
schema_version: 1
topic: waystones
game: poe2
last_verified: 2026-05-26
related_topics: [mapping, atlas, atlas_towers_and_tablets, crafting_currency_overview]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know what a waystone is."
  learning: "Knows waystones open maps; doesn't know about tier, modifier slots, or rolling."
  competent: "Rolls waystones to acceptable mods; sustains map supply through atlas tree."
  confident: "Optimizes waystone rolls per atlas strategy; knows the modifier-count → reward density curve; sustains divine-tier waystone stock without bleeding currency."
attributed_to: [Steelmage, palsteron]
---

# Waystones (PoE 2)

Waystones are the **map currency** — the items you use to open endgame maps. Every map run consumes a waystone.

## What a waystone carries

A waystone is an item that has:

- **Tier** (1–15+) — the map difficulty level. Tier 1 is weakest, tier 15 is endgame, with higher tiers (16+) unlocked at very late progression.
- **Quality** (0–20%) — increases the item-rarity modifier of the map content.
- **Modifiers** (0–6) — random map mods (more monsters, more rare packs, monster damage modifiers, etc.). Each mod increases monster difficulty AND increases rewards.

## Modifier slot mechanics

- A **normal** waystone has 0 modifiers — least difficult, least rewarding.
- A **magic** waystone has up to 2 modifiers.
- A **rare** waystone has up to 6 modifiers.

**Unlocking tablet slots** (see `atlas_towers_and_tablets`):
- The first tablet slot is always available.
- **3+ modifiers** on the waystone unlocks the **second** tablet slot.
- **6 modifiers** (full rare) unlocks **all 3** tablet slots — maximum mechanic density per map.

## How to roll waystones

Standard PoE currency loop:

1. **Transmute** a normal waystone → magic (1 mod)
2. **Augment** a magic waystone → adds a 2nd mod
3. **Regal** a magic waystone → rare with 1 of the 2 mods carried over
4. **Exalt** a rare waystone → adds another mod (up to 6 total)
5. **Chaos** rerolls a rare waystone → keeps it rare, swaps the mod set

**Alchemy orbs** convert normal directly to rare with 4 random mods — the most common league-day-1 roll.

## Sustain — keeping waystones flowing

The atlas tree (see `atlas_passive_tree`) is the primary sustain mechanism:

- Map-drop-tier-modifier nodes increase the chance dropped waystones are higher tier than the map you're in.
- Map-quantity nodes increase total map drops.
- Specific atlas-passive nodes recover waystones from specific mechanics.

**Sustain breaks** when your atlas tree doesn't push enough higher-tier drops back. Common pattern: T14 map yields mostly T11–T13 waystones, and the player runs out of T15s. Diagnostic: count drops over a 10-map sample.

## Common mistakes

- **Rolling for too many mods early** — at low atlas progression, 6-mod waystones can be unbeatable. Stick to 3-4 until you have endgame gear.
- **Ignoring quality** — 20% quality is +20% item rarity, a substantial reward bump. Use whetstones / scrap.
- **Skipping waystone vendoring** — selling waystones in 3s to a vendor in specific patterns gets you alchemy / augment orbs. Cheap orb sustain.

## See also

- `atlas_towers_and_tablets` — where waystones are placed for tablet effects
- `atlas_passive_tree` — sustain mechanism
- `crafting_currency_overview` — the orbs used to roll waystones
- `league_0_5_return_of_the_ancients` — current waystone-tier ceiling
