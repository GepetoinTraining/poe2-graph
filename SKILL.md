---
name: poe2-graph
description: |
  Read and write Path of Exile builds — passive-tree URLs, .build files (which
  the game renders inline), item/mod data, per-player profiles, decomposed
  goals, and edge-transmission case studies. Use when the user asks about PoE 2
  (or PoE 1) builds, wants planning help, asks "what should I do tonight," or
  wants to learn a mechanic.
metadata:
  type: skill
  status: phase-1-and-2-shipped
  router: true
---

# poe2-graph

A Claude-native toolkit for Path of Exile build planning. Reads build URLs and `.build` files, walks the passive-tree graph, answers planning questions, emits annotated `.build` files the game renders inline, and accumulates a transmissible model of the player's edge across leagues.

## Architectural recognition

PoE ships its build-construction game **as a graph database**. Passive tree, atlas tree, ascendancies, weapon-set specializations, and choice-resolution overrides share one schema: nodes addressable by 16-bit hash, with a `skillOverrides` table for multi-choice resolution. Sources (jewels, items, passives, skill overrides) all collapse to one flat stat table at bind time; the combat loop is source-blind.

We trust GGG's canonical graph data and only do graph operations on it. Maintenance scales O(1) per patch: refresh the JSON, ship. Community handoffs cover the rest (NeverSink filters, natwarth visualizer, Path-of-Tools item parser, poe-tool-dev patch tracker, repoe-fork for game data).

## Non-goals

- **Not** a damage simulator. No DPS computation, no conditional stat resolution. Path of Building does that.
- **Not** an OAuth connector. Phase 4 deliverable, separate skill.
- **Not** a visualizer. Hand off to natwarth's hosted tool (or future fork).
- **Not** an item-filter generator. Hand off to NeverSink.

## Session-start procedure

1. **Onboarding check** — `exile.is_onboarded()`. If False → `ONBOARDING.md`.
2. **Staleness check** — `updater.report()`. Surface flags if stale.
3. **Index XMLs are auto-loaded** at `~/.claude/projects/<project-id>/`:
   - `EXILE.xml` — player state (PLAYER + active LEAGUE + active CHARACTER)
   - `GUIDES.xml` — system guides + case studies + creators
   - `DOCS.xml` — this skill's documentation router
4. **Active goal surface** — if player has an active `PlayerGoal`, render WoW-tracker (`goals.render_goal_tracker`) to ground the conversation.
5. **Branch on user intent** (see the routing table below).

## Where to go — routing table

| User asks / mentions | Read | Modules |
|---|---|---|
| Build URL (paste, parse, decode) | `DOCS/byte-format.md` | `parser`, `resolvers` |
| Construct / extend / emit a build | `DOCS/build-construction.md` | `allocation`, `build_writer` |
| Graph paths / distances / Steiner | `DOCS/graph-queries.md` | `graph` |
| Set / change / decompose goals; "what to do tonight" | `DOCS/goals.md` | `goals` |
| Teach a mechanic / edge / case study | `DOCS/guides.md` | `guides`, `systems` |
| Reference a content creator | `DOCS/guides.md` § creators | `guides.load_creator` |
| Items / mods / tiers (poe2db) | `DOCS/poe2db.md` | `poe2db_client` |
| Player profile / confidence / EXILE state | `DOCS/exile.md` | `exile` |
| First-time setup | `ONBOARDING.md` | `exile`, `filesystem_scanner` |
| Update / staleness / patch version | `DOCS/updater.md` | `updater` |
| Item filter / loot filter (NeverSink) | `data/systems/tool_neversink_filter.md` | `neversink` |
| Plan tonight's next action (keystone) | `DOCS/guides.md` § keystone | `guides.recommend_next_action` |
| Install / recommend / explain a tool (PoB, Awakened PoE Trade, etc.) | `data/systems/tool_overview.md` + `tool_*.md` siblings | `filesystem_scanner` |
| Change skill behavior (update cadence, cache caps, worker settings) | `config.yaml` (user-editable) | `config` |
| Look up player history (past leagues, completed goals, donations) | `EXILE/HISTORY.md` (Claude-only writes) | `history` |
| Community projects we depend on | `ATTRIBUTIONS.md` | — |

## Modules at a glance

| Module | One-line |
|---|---|
| `parser.py` | v7 URL byte codec — parse + encode + round-trip |
| `build_reader.py` | `.build` JSON → typed dataclasses |
| `build_writer.py` | typed dataclasses → `.build` JSON with markup |
| `resolvers.py` | tree JSON loader + numeric/string ID joins |
| `graph.py` | NetworkX wrapper + canonical queries + Steiner |
| `allocation.py` | mutable build builder — the construction API |
| `stats.py` | stat string → (template, values, raw) tuple |
| `poe2db_client.py` | poe2db.tw ModsView fetcher + autocomplete |
| `exile.py` | PLAYER/LEAGUE/CHARACTER + EXILE.xml composer + confidence math |
| `goals.py` | five goal types + decomposition DAG + switch intervention + WoW tracker |
| `guides.py` | system guides + case studies + edge taxonomy + creators + GUIDES.xml |
| `systems.py` | legacy per-topic systems guides (precedes `guides.py`) |
| `creators.py` | back-compat shim over `guides.Creator` |
| `filesystem_scanner.py` | detect installed tools (PoB, Awakened PoE Trade, etc.) |
| `updater.py` | three-layer staleness + protected paths |
| `messenger.py` | stub for future WebSocket bridge to natwarth's viewer |
| `docs.py` | DOCS.xml composer over `DOCS/*.md` frontmatter |
| `neversink.py` | filter strictness + customization recommender (NeverSink handoff) |
| `config.py` | loads `config.yaml` — user-editable skill settings (tool tracking, update cycles, cache caps, worker defaults) |
| `history.py` | append-only journal at `EXILE/HISTORY.md` — leagues played, goals completed, case studies, donations |
| `worker.py` | league-launch update worker — polls forks for upstream changes + pulls submodules |

## Hard rules

- **One active major `PlayerGoal` per league.** When player tries to switch, surface `goals.propose_goal_switch()` intervention first.
- **EXILE/ + .env are sacrosanct.** Updater never touches them.
- **Confidence is asymptotic toward 1.0, never reaches it.** Use `exile.bump_confidence()`.
- **No DPS sim, no PoB replacement, no combat simulation.** We walk the graph and emit annotations.
- **Community handoffs are first-class.** Don't reinvent NeverSink, natwarth's viewer, Path-of-Tools, poe-tool-dev. Add credits to `ATTRIBUTIONS.md` when surfacing new ones.
- **Case studies are dual-purpose.** Authored seed corpus teaches Claude the shape; improvised cases handle the long tail; high-value improvisations curate back into the catalog.

## See also

- `ONBOARDING.md` — the 4-phase first-time flow (filesystem scan → questionnaire → artifacts → synthesize)
- `ATTRIBUTIONS.md` — durable credit trail for every community project we build on
- `poe2-graph-spec.html` + `poe2-graph-goals-guides-spec.html` — the design specs
- `DOCS/` — chapters, loaded on demand via DOCS.xml
- `tests/` — 276 tests, all green
