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
| Build URL (paste, parse, decode) | `DOCS/byte-format.md` | `graph.parser`, `graph.resolvers` |
| Construct / extend / emit a build | `DOCS/build-construction.md` | `graph.allocation`, `graph.build_writer` |
| Graph paths / distances / Steiner | `DOCS/graph-queries.md` | `graph.network` |
| Set / change / decompose goals; "what to do tonight" | `DOCS/goals.md` | `goals` |
| Teach a mechanic / edge / case study | `DOCS/guides.md` | `guides`, `systems` |
| Reference a content creator | `DOCS/guides.md` § creators | `guides.load_creator` |
| Items / mods / tiers (poe2db) | `DOCS/poe2db.md` | `integrations.poe2db_client`, `catalog.poe2db_loader` |
| Parse an in-game item (Ctrl+C) | `DOCS/poe2db.md` § parsing | `items.parser`, `catalog.hydrate` |
| Gems — what color, what attribute, what role | (module docstring `catalog.gem`) | `catalog.gem`, `catalog.gem_loader` |
| Per-character inventory + stash | (module docstring `items`) | `items.inventory`, `items.stash` |
| Player profile / confidence / EXILE state | `DOCS/exile.md` | `exile` |
| First-time setup | `ONBOARDING.md` | `exile`, `integrations.filesystem_scanner` |
| Update / staleness / patch version | `DOCS/updater.md` | `infra.updater` |
| Item filter / loot filter (NeverSink) | `data/systems/tool_neversink_filter.md` | `integrations.neversink` |
| Plan tonight's next action (keystone) | `DOCS/guides.md` § keystone | `guides.recommend_next_action` |
| Install / recommend / explain a tool (PoB, Awakened PoE Trade, etc.) | `data/systems/tool_overview.md` + `tool_*.md` siblings | `integrations.filesystem_scanner` |
| Change skill behavior (update cadence, cache caps, worker settings) | `config.yaml` (user-editable) | `infra.config` |
| Look up player history (past leagues, completed goals, donations) | `EXILE/HISTORY.md` (Claude-only writes) | `history` |
| Expose toolkit as MCP tools (Claude Code, desktop bundle, overlay) | `DOCS/mcp-server.md` | `mcp_server` |
| In-game overlay window (Electron) | `DOCS/electron.md` | `electron/` (Node app) |
| Install in Claude desktop / app | `DOCS/mcpb.md` | `mcpb/` (bundle) |
| Community projects we depend on | `ATTRIBUTIONS.md` | — |

## Package layout

The Python code is grouped into five domain packages plus the `mcp_server`
surface, with a few standalone modules for cross-cutting concerns:

```
graph/         build graph + URL codec + .build IO + stat strings
items/         per-character item INSTANCE state (this Diamond Wand with these mods)
catalog/       item + gem SCHEMA — what mods CAN roll, what bases / gems exist
infra/         config.yaml loader + updater + worker (skill infrastructure, not game data)
integrations/  bridges to external tools — neversink, filesystem_scanner, poe2db_client, messenger
mcp_server/    FastMCP wrapper exposing the toolkit as MCP tools + WS bridge to overlay
electron/      Node app — Wizard installer + Overlay window (Ctrl+Alt+Space)
mcpb/          Thin .mcpb bundle for Claude desktop / app
goals.py       five goal types + decomposition DAG + WoW tracker (top-level)
guides.py      system guides + case studies + edge taxonomy + creators
exile.py       PLAYER / LEAGUE / CHARACTER state + confidence math
systems.py     legacy per-topic systems guides (predates guides.py)
creators.py    back-compat shim over guides.Creator
docs.py        DOCS.xml composer over DOCS/*.md frontmatter
history.py     append-only journal at EXILE/HISTORY.md
```

`items/` and `catalog/` are deliberately split: `catalog` is the dictionary
(what mods CAN roll on a Wand at ilvl 82), `items` is the instance (this
specific Diamond Wand on this character with these rolled mods). `catalog`
loads from poe2db; `items` parses from the in-game clipboard.

## Modules at a glance

| Module | One-line |
|---|---|
| `graph.parser` | v7 URL byte codec — parse + encode + round-trip |
| `graph.build_reader` | `.build` JSON → typed dataclasses |
| `graph.build_writer` | typed dataclasses → `.build` JSON with markup |
| `graph.resolvers` | tree JSON loader + numeric/string ID joins |
| `graph.network` | NetworkX wrapper + canonical queries + Steiner |
| `graph.allocation` | mutable build builder — the construction API |
| `graph.stats` | stat string → (template, values, raw) tuple |
| `items.parser` | Ctrl+C in-game clipboard text → `Item` |
| `items.item` | `Item` dataclass: base + modifiers + sockets + crafting state |
| `items.modifier` | `Modifier` (rolled instance) + value/template helpers |
| `items.socket` | `Socket`, `Rune`, `SoulCore` (socketable content) |
| `items.inventory` | per-character `slot → Item` mapping (`SLOT_IDS`) |
| `items.stash` | broader item collection (placeholder for trade ops) |
| `catalog.mod_tier` | `ModTier` schema + `AFFIX_CLASSES` |
| `catalog.base_type` | `BaseType` (item-base schema) |
| `catalog.mod_pool` | per-category mod catalog + `possible_mods(ilvl, …)` |
| `catalog.poe2db_loader` | parse poe2db ModsView JSON → `ModPool` |
| `catalog.hydrate` | backfill family + tier on a parsed `Item` |
| `catalog.gem` | `Gem`, `GemCatalog` (skill / support / spirit) |
| `catalog.gem_loader` | parse poe2db Skill / Support / Spirit Gem pages |
| `integrations.poe2db_client` | poe2db.tw ModsView fetcher + autocomplete |
| `integrations.filesystem_scanner` | detect installed tools (PoB, Awakened PoE Trade, etc.) |
| `integrations.neversink` | filter strictness + customization recommender (NeverSink handoff) |
| `integrations.messenger` | stub for future WebSocket bridge to natwarth's viewer |
| `infra.config` | loads `config.yaml` — user-editable skill settings |
| `infra.updater` | three-layer staleness + protected paths |
| `infra.worker` | league-launch update worker — polls forks for upstream + pulls submodules |
| `mcp_server.server` | FastMCP entry — registers every `tools_*.py` function as an MCP tool |
| `mcp_server.tools_session` | `welcome`, `staleness_report` |
| `mcp_server.tools_goals` | `recommend_next_action`, `active_goal`, `render_goal_tracker`, `propose_goal_switch` |
| `mcp_server.tools_state` | `read_player`, `list_characters`, `read_active_character`, `set_active_character`, … |
| `mcp_server.tools_items` | `parse_clipboard_item`, `query_gem`, `query_mod_pool`, `validate_intent` |
| `mcp_server.tools_guides` | system guides, creators, case studies, edge taxonomy |
| `mcp_server.tools_views` | `display_*` push tools targeting the Electron overlay |
| `mcp_server.transport_ws` | localhost WebSocket bridge to the overlay (env-gated) |
| `goals` | five goal types + decomposition DAG + switch intervention + WoW tracker |
| `guides` | system guides + case studies + edge taxonomy + creators + GUIDES.xml |
| `systems` | legacy per-topic systems guides (precedes `guides`) |
| `creators` | back-compat shim over `guides.Creator` |
| `exile` | PLAYER/LEAGUE/CHARACTER + EXILE.xml composer + confidence math |
| `docs` | DOCS.xml composer over `DOCS/*.md` frontmatter |
| `history` | append-only journal at `EXILE/HISTORY.md` |

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
- `DOCS/` — chapters, loaded on demand via DOCS.xml. New since v1.2.0:
  `DOCS/mcp-server.md`, `DOCS/electron.md`, `DOCS/mcpb.md`
- `electron/README.md` + `mcpb/README.md` — same content as the DOCS chapters,
  kept next to the code for repo-browser convenience
- `BUGS.md` — current bug-hunter punch list (refreshed 2026-05-27)
- `tests/` — pytest suite covering every package
