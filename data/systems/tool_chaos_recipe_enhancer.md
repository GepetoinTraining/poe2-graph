---
schema_version: 1
topic: tool_chaos_recipe_enhancer
game: poe2
last_verified: 2026-05-26
related_topics: [tool_overview, farming_when_to_pick_up_rares, crafting_currency_overview]
prerequisites: []
mastery_levels:
  not_started: "Doesn't engage with the chaos recipe / vendor recipes."
  learning: "Installed CRE; sometimes turns in chaos sets when reminded."
  competent: "Uses CRE actively for vendor-set tracking; integrates with filter to highlight needed bases."
  confident: "Engages CRE only at the phase of the league where chaos recipe is currency-positive; disengages when chaos floor drops below pickup-time cost."
attributed_to: []
---

# Chaos Recipe Enhancer (tool guide)

**Status: stub.** Visual reminder + filter overlay for completing PoE's vendor recipes (chaos recipe, regal recipe, etc.).

## Scope

Standalone Windows app. Reads your stash contents, tracks which item-slot bases you have at iLvl 60-74 (the chaos-recipe range), shows you visually which slots you still need. Integrates with the loot filter to highlight pickup-priority bases.

**PoE 2 caveat**: PoE 2's vendor recipes differ from PoE 1's. CRE coverage of PoE 2 recipes may be partial; verify before relying.

Sub-topics to be expanded:
- The chaos recipe math (when chaos-floor exceeds pickup-time cost vs when it doesn't)
- Setting up stash tab integration (which tab is your recipe tab)
- Filter integration (how CRE adds its highlights on top of NeverSink)
- When to disengage — late-league chaos becomes cheap; recipe stops being worth the inventory time
- PoE 2 vs PoE 1 recipe differences

## Install

Official source: search "ChaosRecipeEnhancer" on GitHub. Standalone exe.

## How poe2-graph reads it

Filesystem scanner detects (probe `chaos_recipe_enhancer`) → `chaos_recipe_optimizer` tag. No deeper integration — CRE operates standalone.

## See also

- [tool_overview](tool_overview.md) — the umbrella
- [farming_when_to_pick_up_rares](farming_when_to_pick_up_rares.md) — the pickup-time-cost discipline CRE either compounds with or contradicts
- [crafting_currency_overview](crafting_currency_overview.md) — chaos floor vs alternatives
