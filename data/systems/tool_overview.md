---
schema_version: 1
topic: tool_overview
game: poe2
last_verified: 2026-05-26
related_topics: [tool_pob_poe2, tool_pob_poe1, tool_awakened_poe_trade, tool_exilence_next, tool_chaos_recipe_enhancer, tool_poe_overlay, tool_neversink_filter]
prerequisites: []
mastery_levels:
  not_started: "Plays PoE 2 without any external tools."
  learning: "Has installed one tool (usually NeverSink filter) and is figuring out the workflow."
  competent: "Uses 2-3 tools regularly, knows which problem each one solves."
  confident: "Has a deliberate tool kit per phase of play — different tools for campaign, mapping, endgame trading, mirror crafting. Knows which tools to skip."
attributed_to: []
---

# PoE 2 Tool Ecosystem (overview)

poe2-graph teaches Path of Exile 2 directly — you can play with just the skill, no other tools required. But for specific skill ceilings, dedicated community tools unlock capabilities the skill can't provide on its own. This guide is the **map of that ecosystem** — what each tool does, when to install it, and when to skip it.

## The principle

**The skill teaches the game. Tools unlock specific ceilings.** Two truths to hold:

1. You do not need any tools to play PoE 2 well. The in-game BuildPlanner, the game's filter chooser, and conversations with this skill cover the campaign through early endgame.
2. Once you're pushing a specific skill ceiling — mirror-tier crafting, optimized mapping, deep build planning — the right tool compounds your effort 10x for that ceiling.

The mistake new players make: installing every tool at once, getting overwhelmed, then bouncing off PoE entirely. The fix: install tools **when you reach the ceiling that tool unlocks**, not before.

## Decision tree — which tool for what

| You want to... | Install... | Skill ceiling unlocked |
|---|---|---|
| Plan a build before you commit to it | **PoB Community PoE 2** ([tool_pob_poe2](tool_pob_poe2.md)) | Calculated DPS / EHP / defense breakdowns; "is this build viable" before investing |
| Follow a guide that publishes PoB codes | **PoB Community PoE 2** ([tool_pob_poe2](tool_pob_poe2.md)) | Import guide-author builds directly |
| Price-check items as you find them | **Awakened PoE Trade** ([tool_awakened_poe_trade](tool_awakened_poe_trade.md)) | Ctrl-D on any item → market price overlay |
| See your total wealth across all stash tabs | **Exilence Next** ([tool_exilence_next](tool_exilence_next.md)) | Wealth tracking + per-tab valuation + history |
| Automate chaos recipe / vendor recipes | **Chaos Recipe Enhancer** ([tool_chaos_recipe_enhancer](tool_chaos_recipe_enhancer.md)) | Visual reminders + filter overlay for vendor sets |
| See atlas / character info while playing | **POE Overlay** ([tool_poe_overlay](tool_poe_overlay.md)) | In-game overlay for stash, atlas, items |
| Filter out the loot noise | **NeverSink filter** ([tool_neversink_filter](tool_neversink_filter.md)) | Hide trash drops, see only what matters |
| Plan an old PoE 1 build (carryover) | **PoB Community PoE 1** ([tool_pob_poe1](tool_pob_poe1.md)) | Same as PoB PoE 2 but for the older game |

## When to skip tools entirely

You do not need any of these for:

- **Levels 1–60 / Acts 1–3** of the campaign. Just play.
- **First time on a new class**. Learn the class's identity before optimizing.
- **Extreme casual play** (under 5 hours/week). Tool maintenance overhead exceeds tool benefit.
- **If you're getting tutorial fatigue**. Tools are second-order; the game itself is the first lesson.

The default state is "no tools." Tools enter the loop **when the player names a specific friction** the tool relieves.

## How poe2-graph integrates with each tool

| Tool | poe2-graph integration |
|---|---|
| PoB PoE 2 | Future: `pob_snapshot.py` reads PoB's calculated DPS / EHP into your CHARACTER profile. Today: paste PoB code in chat, I read the tree + gems. |
| Awakened PoE Trade | Filesystem scanner detects it → tags `trade_engaged` in PLAYER.md. Future: read its hideout config for market preferences. |
| Exilence Next | Future: read its wealth snapshots → bump `peak_wealth_tier` in PLAYER.md. |
| Chaos Recipe Enhancer | Filesystem scanner detects it. No deeper integration — it operates on its own. |
| POE Overlay | Filesystem scanner detects it. No deeper integration. |
| NeverSink filter | [neversink.py](../../neversink.py) recommender suggests strictness + customizations based on your build state. |

## Fork status — what we ship vs what we link to

poe2-graph bundles four forks as git submodules under `tools/`, all MIT-licensed:

- `tools/pob-poe2/` — fork of [PathOfBuildingCommunity/PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) (planned: headless JSON snapshot patch)
- `tools/pob-poe1/` — fork of [PathOfBuildingCommunity/PathOfBuilding](https://github.com/PathOfBuildingCommunity/PathOfBuilding)
- `tools/neversink-poe2/` — fork of [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2). Carries all 7 strictness levels + 5 style packs (Cobalt / CustomSounds / DarkMode / Mythic / Zen) locally — `neversink.py` can hand off the actual filter file, not just a download link.
- `tools/neversink-poe1/` — fork of [NeverSinkDev/NeverSink-Filter](https://github.com/NeverSinkDev/NeverSink-Filter)

For tools we don't fork (Awakened PoE Trade, Exilence Next, etc.), we link to their official sources in each tool guide. See [ATTRIBUTIONS.md](../../ATTRIBUTIONS.md) for the bundled-fork credit detail.

## See also

- [neversink.py](../../neversink.py) — filter strictness + customization recommender
- [filesystem_scanner.py](../../filesystem_scanner.py) — detects installed tools
- [ATTRIBUTIONS.md](../../ATTRIBUTIONS.md) — full credit trail
