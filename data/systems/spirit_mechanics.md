---
schema_version: 1
topic: spirit_mechanics
game: poe2
last_verified: 2026-05-26
related_topics: [skill_gems, persistent_buffs, minions, meta_gems, auras]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know spirit exists as a resource."
  learning: "Knows spirit costs auras but unclear on how to grow the pool."
  competent: "Tracks total spirit + reservations; knows the standard amulet/body-armour spirit slots."
  confident: "Optimizes spirit allocation across persistent buffs + meta-gems + minions; identifies which gear slots scale spirit best for the build archetype."
attributed_to: []
---

# Spirit (PoE 2)

Spirit is a **reservation resource** for persistent effects: auras, buffs, permanent minions, meta-gems. It's a hard cap, not a regenerating pool.

## How spirit works

- You have a **maximum spirit pool** (e.g. 200).
- Persistent effects (auras, etc.) **reserve a flat amount** of spirit while active (e.g. Herald of Ash = 30 spirit).
- Reserved spirit reduces your **available pool** for other effects.
- Spirit doesn't regen in combat — it's a static budget you allocate.

This is structurally different from PoE 1's mana-reservation system: in PoE 2, you have a **dedicated pool for permanent effects** instead of permanently reserving your active-skill mana.

## Where spirit comes from

Sources, roughly in order of yield:

1. **Campaign progression** — defeating Acts 1-4 bosses grants permanent spirit bumps. The campaign-cleared baseline is ~100 spirit.
2. **Body Armour** — many endgame body armours grant **substantial spirit** (e.g. +30 to +80 spirit on a single piece). Body armour spirit is the biggest single source.
3. **Amulet** — amulets can roll **+spirit** as a modifier. Smaller magnitude than body armour but stacks.
4. **Sceptre** — sceptres carry spirit as a base property. Equipping a sceptre is the most direct sceptre-class spirit gain.
5. **Pinnacle uniques** + **boss drops** — some uniques carry spirit explicitly. Rare but high-magnitude.

## What spirit reserves

Spirit cost varies per effect:

- **Tier-1 persistent buff gems** (Herald of Ash, Herald of Thunder, etc.) — typically **30 spirit** each.
- **Support gems socketed in persistent buffs** — increase the reservation. Tier-1 buff + a couple of supports = 50-80 spirit total.
- **Auras** — usually 35-60 spirit per aura.
- **Permanent minions** — varies wildly. Skeletal minions ~20 spirit each; high-tier permanent minions can be 100+.
- **Meta-gems** — typically 30-60 spirit per slotted meta-gem.

## How to activate a persistent effect

1. **Socket** a persistent-buff gem (Herald, Aura, etc.) in your skill panel.
2. **Open the Skill Panel** (default: G).
3. **Right-click the icon above the socketed gem** to toggle the buff on.

Forgetting to toggle is a common new-player mistake — the gem is socketed but the effect is dormant until activated.

## Spirit budgeting

Standard endgame allocation pattern:

| Slot | Typical spirit cost |
|---|---|
| 1-2 Heralds | 30-60 each |
| 1 main aura | 35-60 |
| 1 meta-gem (optional) | 30-60 |
| 1 permanent minion (optional) | 20-100 |
| **Total budget needed** | **150-300+** |

Build target: **200-300 spirit** for full endgame configurations. Without endgame body armour spirit + amulet spirit, you'll be 100-150 short and need to drop a buff.

## Common mistakes

- **Stacking auras without spirit budget** — see "buff not active" because reservation exceeded the cap.
- **Ignoring sceptre as a spirit source** for sceptre-class builds — sceptres carry implicit spirit you'd otherwise need to find elsewhere.
- **Wasting body-armour slots on non-spirit defensive armour** for builds that need 250+ spirit. Spirit body armour vs. flat-life body armour is a real trade-off.
- **Forgetting to toggle persistent buffs** after death / zone change — some gems remain socketed but inactive. Check the Skill Panel.

## See also

- `skill_gems` — the gem layer spirit reserves against
- `weapon_sets` — sceptres on Set 1 vs Set 2 for spirit-difference
- `crafting_currency_overview` — orbs to roll spirit modifiers on amulets / armour
