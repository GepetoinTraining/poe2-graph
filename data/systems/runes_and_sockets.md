---
schema_version: 1
topic: runes_and_sockets
game: poe2
last_verified: 2026-05-26
related_topics: [crafting, soul_cores, gear, artificer_orb]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know runes exist."
  learning: "Knows runes go into sockets but doesn't know how to add sockets to gear."
  competent: "Sockets gear via Artificer Orb; matches runes to slots correctly."
  confident: "Plans socket allocations holistically; knows when Soul Cores beat runes; manages Artificer Shard salvage efficiently."
attributed_to: []
---

# Runes + Sockets (PoE 2)

Sockets are gear-augmentation slots. Runes (and **Soul Cores**) plug into sockets to add modifiers to your equipment.

## What a socket holds

A socket on gear accepts one of:

- **Rune** — common drop, adds a small modifier
- **Soul Core** — rare drop (from Trial of Chaos), adds a more substantial modifier
- **Idol** (where applicable) — specialized rune-class for specific slots

Together these are called **Augment Items**.

## Socket counts per gear slot

| Slot | Max sockets |
|---|---|
| Body Armour | **2** |
| Two-handed weapons (martial) | **2** |
| One-handed weapons (martial) | 1 |
| Gloves | 1 |
| Boots | 1 |
| Helmet | 1 |
| Quivers, Caster Weapons, Jewellery | **0** (cannot socket) |

**Total maximum across all gear: 7 sockets** (assuming you have a 2-socket body armour + a 2-socket 2H weapon + 1 each on gloves/boots/helmet).

## Adding sockets — the Artificer Orb

Items don't drop with sockets. You **add sockets** via the **Artificer Orb**:

1. Right-click the Artificer Orb.
2. Left-click the gear you want to socket.
3. The gear gains one socket (up to its max).

### Where Artificer Orbs come from

- **Drop directly** (rare in early game).
- **Combine 10 Artificer Shards** → 1 Artificer Orb. Shards drop more commonly.
- **Salvage Bench dismantling** — destroying a socketed item via the Salvage Bench yields 1 Artificer Shard **per destroyed socket**.

The salvage→shard→orb loop is the early-game socket-economy: salvage low-tier socketed items to fuel sockets on better gear.

## Slotting a rune

1. Pick up the rune in your inventory (left-click).
2. Left-click your equipped (or in-inventory) item with an empty socket.
3. The rune slots in. Modifier applied immediately.

## Replacing runes

You **can** replace a socketed rune with another rune or a Soul Core. **But:** the displaced rune is **permanently destroyed**. You don't get the original back.

This makes socket allocation a real commitment — plan your socketing instead of trial-and-erroring.

## What runes do

Generally:

- **In weapons** — add elemental damage, physical damage, or specific damage-type modifiers
- **In armour** — add elemental resistances, max Life, or max Mana modifiers

Different runes target different stats. Pick by what your build is short on (resistances for under-capped builds, damage for over-defensive builds).

## Soul Cores vs Runes

Soul Cores (from `soul_cores`) fit the same sockets but with broader modifier pools:

- Soul Cores can roll **rarer modifiers** unavailable from runes (Spirit, Item Rarity, etc.).
- When they give a basic stat, they're **typically better magnitude** than the rune equivalent.
- They drop rarely (Trial of Chaos exclusive) — use them in your **best gear slots**, not mid-game gear that'll be replaced.

## Common mistakes

- **Socketing low-tier gear** — the rune/orb investment doesn't transfer when you upgrade gear. Wait until the gear is keeper-tier.
- **Replacing runes for marginal upgrades** — the destroyed rune cost matters. The new rune needs to be a real upgrade, not a sidegrade.
- **Salvaging socketed gear without recovering value** — you get the Artificer Shards back, but the runes themselves are destroyed in the salvage. Move runes off before salvage if you want to preserve them (you cannot — runes are slot-locked once placed).
- **Ignoring socket count when buying gear** — a 2-socket body armour with bad stats can be better than a 0-socket one with great stats, given how much sockets contribute.

## See also

- `soul_cores` — the high-tier socketable
- `trials_of_chaos` — where Soul Cores come from
- `crafting_currency_overview` — Artificer Orbs in the broader orb taxonomy
