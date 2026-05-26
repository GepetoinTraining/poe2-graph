---
schema_version: 1
topic: farming_filters
game: poe2
last_verified: 2026-05-26
related_topics: [farming_guide, trade_filtering_for_stats, tool_neversink_filter]
prerequisites: [farming_guide]
mastery_levels:
  not_started: "Uses a default filter."
  learning: "Adjusts strictness to match level."
  competent: "Customizes filter per farming strategy (shows what THIS farm produces)."
  confident: "Treats the filter as the visible-rules-of-engagement. Different farms get different filters. Filter changes trigger when farms rotate."
attributed_to: []
---

# Farming — Filters

**Status: stub.** 1%-knowledge topic Pedro is donating.

## Scope

**The loot filter as a farming tool**. NeverSink (or equivalent) is the base; the 1% practice is **customizing per farm**.

Sub-topics to be expanded:
- Filter-strictness vs farming-strategy match (loose filter for early league + low-level mapping; very-strict for endgame juiced maps)
- Highlighting **inputs you need next** (if farming for jewel bases, show only those bases at the iLvl that matters)
- Hiding things the current farm doesn't reward (don't show body armours when farming for jewels)
- Sound + alert tuning per farm (loud alert for the chase drop you're farming; silent for everything else)
- The "season change" filter swap — when you rotate strategy, swap filter
- Filter-fragility — too-strict filters miss the unexpected drop; too-loose wastes attention
- Custom rules for the build-relevant items (your gear archetype's specific bases at iLvl 75+)
- The interaction with `neversink.py` recommender (the recommender suggests strictness + customizations; the manual filter follows)

The filter is the **lens** between farming and trade-prep. Tune it per farm.

## See also

- `farming_guide` — the umbrella
- `trade_filtering_for_stats` — filter customization for trade prep
- `neversink.py` — the base-filter recommender
