---
schema_version: 1
topic: skill_gems
game: poe2
last_verified: 2026-05-26
related_topics: [gemcutting, uncut_gems, support_gems, spirit_mechanics]
prerequisites: []
mastery_levels:
  not_started: "Hasn't cut a gem yet."
  learning: "Cuts active skill gems from uncut drops; doesn't fully understand support-gem tiers or color requirements."
  competent: "Allocates support gems by color + tier; knows the support-gem-tier gates (Level 2, Level 3 uncut)."
  confident: "Optimizes gem-cutting decisions per build phase; carries forward leveled gems across alts via passable Support Gems."
attributed_to: [Ghazzy]
---

# Skill Gems + Gemcutting (PoE 2)

PoE 2 changed how gems work. **Uncut Gems** drop as raw items; you choose which gem to *create* from each uncut. Builds form by combining **Skill Gems**, **Support Gems**, and **Spirit Gems** (auras / heralds / permanent buffs).

## The gem taxonomy

Three gem categories:

1. **Skill Gems** — the active skills you cast / attack with (Fireball, Spark, Boneshatter, etc.).
2. **Support Gems** — modify a socketed skill (added cold damage, multiple projectiles, chain-on-hit, etc.). One support per unique gem; cannot be duplicated.
3. **Spirit Gems** — persistent buffs that reserve spirit (Heralds, Auras, Meta-gems). See `spirit_mechanics`.

## Cutting an uncut gem

You drop an **Uncut Skill Gem**, **Uncut Support Gem**, or **Uncut Spirit Gem**. To use it:

1. **Right-click the uncut gem** in your inventory.
2. **UI opens** showing all gems available at that gem's level.
3. **Choose the exact gem** to create.
4. The gem is cut at that level and ready to socket.

**Cutting a higher-level uncut**:

- You can **upgrade an existing gem** to a higher level by cutting a higher-level uncut on it.
- Upgrading **transfers** the existing gem's Quality + Support Sockets to the new version.

## Gem tiers (level gating)

Gems are tiered to gate content access:

- **Tier 1** uncut skill gems drop early.
- **Tier 2** at mid-campaign.
- **Tier 3** + tier-locked unique skills at endgame.

The same gem name (e.g. "Fireball") exists across tiers. Higher tier = more damage, more support sockets, more scaling potential.

**Support gem tiers** specifically:

- **Level 1 Uncut Support Gems** drop early.
- **Level 2 and Level 3 Uncut Support Gems** unlock progressively later in the campaign.
- Higher-tier supports are **strictly upgrades** in most cases.

## Support gem mechanics

- **No gem levels on supports** — supports don't scale with level; their effect is fixed at cut time.
- **Cannot be upgraded** — once cut at tier N, the support stays at tier N.
- **Color requirements** — each support has a color (red/green/blue) requiring a flat attribute amount: **+5 attribute per support of that color** in the slot.
    - 10 Strength = 2 Red supports slottable
    - 15 Strength = 3 Red supports slottable
    - Same for Dex/Green and Int/Blue
- **One unique support per skill** — you can't socket the same support twice into the same skill.

## Carrying gems across characters

A clean PoE 2 feature: **Support Gems without level restrictions can be passed down to new characters**. League-start an alt and you can hand them your leveled supports — they get the cut version immediately.

Active **Skill Gems** are level-locked and don't pass down the same way.

## Acquisition (where uncut gems come from)

Two paths:

1. **Quest rewards** — major story milestones grant uncut gems at the appropriate tier.
2. **Loot drops** — Rare and Boss enemies have a chance to drop uncut gems. Support uncuts drop more rarely than skill uncuts.

In endgame, **Uncut Skill/Support Gem Level 3** drops become the primary scaling vector.

## Common mistakes

- **Cutting a high-tier uncut early** — wasting a tier-3 uncut on a tier-1 gem locks you out of upgrading that particular gem chain. Save tier-3 uncuts for builds where you need them.
- **Ignoring support color requirements** — picking up red supports for an int-stacker build is wasted inventory. Match support color to your attribute spread.
- **Not upgrading skill gems mid-campaign** — leveled skill gems from level 1 scale poorly into act 3. Cut higher-level uncuts to upgrade.
- **Filling all sockets without thinking about supports** — a 3-link with the right supports beats a 4-link with random ones.

## See also

- `spirit_mechanics` — for the Spirit Gem subcategory
- `crafting_currency_overview` — gem-related currencies (Quality whetstones, etc.)
