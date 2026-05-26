---
schema_version: 1
topic: tool_awakened_poe_trade
game: poe2
last_verified: 2026-05-26
related_topics: [tool_overview, trade_engagement, trade_filtering_for_stats]
prerequisites: []
mastery_levels:
  not_started: "Hasn't installed any price-check overlay."
  learning: "Installed Awakened PoE Trade; uses Ctrl+D for price-check, doesn't customize further."
  competent: "Uses Awakened PoE Trade for routine price-checking; configured the hotkeys; understands fuzzy matching for similar listings."
  confident: "Tuned Awakened PoE Trade's filters for build-specific stat comparisons; uses bulk-currency price-check workflows; reads its market-depth signal beyond just the price."
attributed_to: []
---

# Awakened PoE Trade (tool guide)

**Status: stub.** Modern price-check overlay — the canonical trade-engagement tool.

## Scope

Electron-based desktop overlay. Hotkey (default Ctrl+D) on any in-game item → opens overlay with current market listings. Replaces the older POE-TradeMacro AHK workflow with a more reliable, multi-language interface.

Sub-topics to be expanded:
- Install + first-run configuration (hotkey assignment, language, PoE 2 mode toggle)
- Reading the price-check results (mean, median, listing-count signal)
- The fuzzy-match toggle — when to broaden the search, when to lock it tight
- Bulk-currency check workflow
- Listing your own items via the overlay
- Performance considerations (in-game FPS impact)

## Install

Official source / download: search "Awakened PoE Trade" — actively maintained, official GitHub. (License: GPL.)

We don't fork this — Electron-app redistribution is heavier than makes sense. We link only.

## How poe2-graph reads it

`filesystem_scanner.py` detects its install (probe `awakened_poe_trade`). Presence sets the `trade_engaged` + `trade_overlay_user` tags in PLAYER.md.

## See also

- [tool_overview](tool_overview.md) — the umbrella
- [trade_engagement](trade_engagement.md) — how trade works in PoE 2
- [trade_filtering_for_stats](trade_filtering_for_stats.md) — filter discipline that pairs with the overlay
