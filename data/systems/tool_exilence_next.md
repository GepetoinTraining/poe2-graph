---
schema_version: 1
topic: tool_exilence_next
game: poe2
last_verified: 2026-05-26
related_topics: [tool_overview, trade_guide, trade_currency_trading, currency_velocity]
prerequisites: []
mastery_levels:
  not_started: "Doesn't track wealth."
  learning: "Installed Exilence Next; reads the total wealth number occasionally."
  competent: "Tracks wealth across leagues; uses the per-tab breakdown for accounting."
  confident: "Reads Exilence Next as currency-velocity signal — what's accumulating, what's draining, what to convert. Uses snapshot history for league-phase analysis."
attributed_to: []
---

# Exilence Next (tool guide)

**Status: stub.** Wealth tracking + stash valuation across all your stash tabs.

## Scope

Standalone Windows app. Connects to your PoE account via OAuth (or session token), reads stash contents periodically, values each item by current market price, totals across all tabs. Maintains snapshot history so you can see wealth-over-time.

Sub-topics to be expanded:
- OAuth setup vs session-token setup (security trade-offs)
- Snapshot cadence (every minute is excessive; every 30 minutes is reasonable)
- Per-tab vs total wealth (the per-tab view matters for the hideout-warrior workflow)
- League-phase wealth velocity (early-league rapid accumulation, late-league plateau)
- Signal vs noise — Exilence Next overvalues unsellable rares; calibrate against actual liquid wealth
- When to engage it (typically mid-mapping onwards — early-league is too noisy)

## Install

Official: search "Exilence Next" — the main fork. Standalone exe distribution.

## How poe2-graph reads it

Filesystem scanner detects (probe `exilence_next`) → `wealth_tracker_user` tag. Deeper integration (reading snapshot history to bump `peak_wealth_tier`) is future work.

## See also

- [tool_overview](tool_overview.md) — the umbrella
- [trade_guide](trade_guide.md) — where wealth tracking fits in the broader trade discipline
- [trade_currency_trading](trade_currency_trading.md) — Exilence Next's data feeds currency-pair decisions
