---
schema_version: 1
topic: crafting_currency_overview
game: poe2
last_verified: 2026-05-26
related_topics: [crafting, essence_crafting, runes_and_sockets, waystones, league_0_3_the_third_edict, league_0_5_return_of_the_ancients]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know what an orb is."
  learning: "Identifies common orbs by drop frequency; uses transmute/augment/regal."
  competent: "Crafts rares deliberately; knows the chaos/exalt/divine economy."
  confident: "Manages currency velocity; treats currency as a leading indicator; knows mirror-tier crafting from BeltonPoE-style frames."
attributed_to: [BeltonPoE, Empyrian]
---

# Crafting Currency Overview (PoE 2)

The orbs / shards / fragments / cores that drive PoE 2 crafting + map rolling. This guide is a reference card — depth lives in dedicated guides per surface (essences, runes, Bones at Well of Souls, etc.).

## The orb tiers (most-common to rarest)

### Common
- **Transmute Orb** — Normal → Magic (adds 1 modifier).
- **Augment Orb** — Magic + 1 mod → Magic + 2 mods.
- **Alchemy Orb** — Normal → Rare with 4 modifiers. The workhorse for league-start map rolling.
- **Regal Orb** — Magic → Rare (keeps existing mods + adds 1).
- **Whetstone (Blacksmith's)** — adds Quality to weapons.
- **Scrap (Armourer's)** — adds Quality to armour.
- **Glassblower's Bauble** — adds Quality to flasks.

### Mid-tier
- **Chaos Orb** — Rerolls a rare item's modifiers (keeps it rare; changes the mod set entirely).
- **Exalted Orb** — Adds one new modifier to a rare item (no replacement).
- **Vaal Orb** — Corrupts an item. Random outcome: minor mod, implicit mod change, brick, or major boon.
- **Artificer Orb** — Adds a socket to gear (see `runes_and_sockets`).
- **Annulment Orb** — Removes one random modifier from an item.

### Rare / high-tier
- **Divine Orb** — Rerolls the *numeric values* on existing modifiers (keeps the mod set; randomizes the rolls within range). The canonical "finish a craft to perfection" orb. Currency benchmark — divine count is the de-facto unit for high-tier wealth.
- **Mirror of Kalandra** — Creates a perfect mirror-copy of an item. The mirror itself is the rarest base currency in PoE; mirror-tier items are the apex.
- **Orb of Annulment** + **Perfect Orb** variants — endgame-only refinements.

### Currency shards
Many top-tier orbs have shards (1/20th value, drop more commonly). Examples:
- **Mirror Shard** — 20 → 1 Mirror of Kalandra
- **Exalted Shard** — 20 → 1 Exalted Orb
- **Artificer Shard** — 10 → 1 Artificer Orb

Shards stack independently and auto-combine when threshold reached.

## League-mechanic crafting currencies

Beyond base orbs, PoE 2 has crafting currencies introduced by leagues:

- **Bones** (from `league_0_3_the_third_edict`) — apply to items at the **Well of Souls**; choose one of 3 modifier rolls. Survived as a permanent crafting surface in 0.5+.
- **Runeshapes** (from `league_0_5_return_of_the_ancients`) — apply to **Ezomyte Remnants** to inscribe items, consume **Runic Ward** instead of Mana.
- **Essences** — see `essence_crafting`. Re-rolls all explicit mods + guarantees one specific mod.

## The currency-velocity discipline

Top-end players (Belton, Empyrian, Ben_) frame currency as a **flow** — not a stockpile:

1. **Currency in your stash is currency not earning** — it should be funding the next craft or held against a calculated future need.
2. **Currency-tier price ratios shift through the league** — divines are expensive Week 1 (deflated by exalts), cheaper at Week 3-4 (everyone's saved up). Track the ratio, time your purchases.
3. **The orb you need next determines the orb you should farm now** — don't farm chaos when your build wants exalts. Specialize per craft.

See `currency_velocity` edge tag for the underlying posture.

## Common mistakes

- **Hoarding Divines without a use** — every league has players sitting on 200 divines they never spent. Currency that doesn't move is dead capital.
- **Using Chaos Orbs to "fix" a rare with one bad mod** — Chaos rerolls *everything*. The right tool is Annulment (with risk) or Regal-craft a new piece.
- **Spending Exalted Orbs casually** — Exalt is one of the highest-leverage orbs because it adds without replacing. Save them for finishing crafts where the existing mods are already good.
- **Ignoring Quality currencies** — 20% quality is +20% relevant scaling. Cheap orb that delivers material value.

## See also

- `essence_crafting` — deterministic mod-guarantee crafting
- `runes_and_sockets` + `soul_cores` — gear-socketable currencies
- `waystones` — orb sink for map rolling
- `league_0_3_the_third_edict` — Bones + Well of Souls layer
- `league_0_5_return_of_the_ancients` — Runeshapes + Runic Ward layer
