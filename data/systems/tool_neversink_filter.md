---
schema_version: 1
topic: tool_neversink_filter
game: poe2
last_verified: 2026-05-26
related_topics: [tool_overview, farming_filters, trade_filtering_for_stats]
prerequisites: []
mastery_levels:
  not_started: "Plays without a loot filter (everything shows on the ground)."
  learning: "Installed NeverSink at default strictness; doesn't customize."
  competent: "Adjusts NeverSink strictness as character progresses; knows the 7-level ladder (regular → uber-plus-strict)."
  confident: "Customizes NeverSink for build-specific highlighting (Spirit bases, weapon bases at iLvl, currency tier alerts); pairs with the poe2-graph recommender."
attributed_to: [NeverSinkDev]
---

# NeverSink Filter (tool guide)

The canonical community loot filter for Path of Exile 2. **MIT licensed.** Maintained by NeverSinkDev.

Official: [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2)
Our fork: [GepetoinTraining/NeverSink-Filter-for-PoE2](https://github.com/GepetoinTraining/NeverSink-Filter-for-PoE2), bundled at `tools/neversink-poe2/` as a git submodule. Carries **all 7 strictness filter files** + **5 style packs** (Cobalt / CustomSounds / DarkMode / Mythic / Zen) locally — meaning the `neversink.py` recommender can hand off the actual filter file path on disk, not just a download link.

Filter source (parameterized): [NeverSinkDev/Filter-Precursors](https://github.com/NeverSinkDev/Filter-Precursors) — not currently forked; reach for it if/when we go beyond compiled-filter delivery into source-level filter generation.

## Scope

The .filter file dictates what loot shows on the ground, what plays a sound, what gets highlighted, what gets hidden. NeverSink ships 7 strictness levels:

1. **Regular** — show almost everything (leveling)
2. **Semi-strict** — filter early bases (campaign through mid-mapping)
3. **Strict** — endgame mapping noise cut
4. **Very-strict** — late endgame
5. **Uber-strict** — divine+ farming
6. **Uber-plus-strict** — top-end farming

Each level builds on the previous. Player picks the level matching their build phase and wealth tier.

## Install — PoE 2 specifically

PoE 2's filter delivery is **different from PoE 1's**:

- **PoE 1**: drop the `.filter` file into `Documents/My Games/Path of Exile/`, select in-game from the filter chooser.
- **PoE 2**: use the **in-game online filter import**. The filter is synced from a URL or pasted code; goes into `Documents/My Games/Path of Exile 2/OnlineFilters/` as an opaque-ID file.

For PoE 2 specifically:
1. Visit the NeverSink release page → copy the filter import code for your chosen strictness
2. In-game: Options → UI → Item Filter → Add Online Filter → paste the code
3. Switch to it in the filter dropdown

(If you're returning from PoE 1, the filter delivery mechanism is the main thing that's changed.)

## How poe2-graph reads it

The skill's [neversink.py](../../neversink.py) module:
- Recommends a **strictness level** based on your character level + peak wealth tier + time budget
- Recommends a **customization list** based on your class / ascendancy / active edges of interest (e.g. "highlight wand bases at iLvl 75+ — caster weapon upgrades" for a Stormweaver)
- Emits a companion `.filter.md` file alongside the `.build` — human-readable, NOT a redistribution of NeverSink's filter

We **do not modify or redistribute** NeverSink's `.filter` content. The recommendation is "download from NeverSink, then apply these customizations manually." That's the entire phase-2 community-handoff promise.

## Filter-Precursors — the source layer

`Filter-Precursors` is the parameterized source NeverSinkDev compiles the released filter from. Most players never touch it — the compiled `.filter` is what they install. But if you want to **build a custom filter from scratch** that matches the NeverSink style, Filter-Precursors is the source.

We don't currently fork Filter-Precursors. If poe2-graph ever moves into source-level filter generation (build a fully-custom filter from a player's build + edges_of_interest, hand back the source for the player to compile themselves), we fork at that point. For now: linked for reference; the compiled filters in `tools/neversink-poe2/` cover the canonical delivery path.

## Common pitfalls (new player)

- **Picking a strictness too high too early**. Uber-strict at level 60 hides currencies you need. Climb the ladder with your build.
- **Confusing the .filter file path between PoE 1 and PoE 2**. PoE 2 uses OnlineFilters/, not the user-data root. If your filter "doesn't show up," check the dropdown — you may have added it to PoE 1's directory by mistake.
- **Customizing without backing up**. The PoE 2 online-filter UI doesn't have a great revert option. Save the import code somewhere before customizing.
- **Treating the filter as static**. Your strictness needs change as your build matures. Re-import at higher strictness around level 80, 90, 95.

## See also

- [neversink.py](../../neversink.py) — the strictness + customization recommender
- [tool_overview](tool_overview.md) — the umbrella
- [farming_filters](farming_filters.md) — per-farm filter customization discipline
- [trade_filtering_for_stats](trade_filtering_for_stats.md) — the search-filter parallel discipline
