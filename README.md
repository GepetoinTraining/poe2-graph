# poe2-graph

A Claude-native toolkit for **Path of Exile 2** — build planning, farming-cycle tracking, item ingestion, and an in-game decision-support HUD. Reads build URLs and `.build` files, walks the passive-tree graph, plans tonight's next action, ingests item drops via the clipboard, classifies and reconciles farming cycles, and surfaces it all in a transparent overlay rendered alongside the game.

**Status**: v1.5.0 — ready for [Path of Exile 2: Return of the Ancients (0.5)](https://pathofexile2.com/) league start, **2026-05-29 17:00 UTC**.

## What it is

PoE 2 ships its build-construction game **as a graph database**. So does its atlas, its crafting decision tree, its skill prerequisites, and its market — all of which compose on the same node-addressing scheme. poe2-graph trusts GGG's canonical data and only does graph operations on it. Maintenance scales O(1) per patch — refresh the JSON, ship.

Community handoffs cover the rest:

- **NeverSink** owns item filters (MIT)
- **Path of Building Community** owns build sim + DPS calc (MIT)
- **Path-of-Tools** owns item parsing (ISC)
- **poe2db.tw** owns extracted item/mod data
- **poe-tool-dev** owns patch-version tracking (MIT)
- **Exilence CE** owns continuous wealth tracking — see [DOCS/farming-cycles.md](DOCS/farming-cycles.md) for the explicit handoff

The skill is the connective tissue: it talks to Claude, walks the graph, and points at the right community tool for each problem.

## What's inside (v1.5)

### Build & planning surface (Phase 1 + 2 — shipped 2026-05-26)

- Read + write `.build` files — GGG's official format the game renders inline via the BuildPlanner watch directory ([DOCS/byte-format.md](DOCS/byte-format.md), [DOCS/build-construction.md](DOCS/build-construction.md))
- Goal decomposition — five goal types, WoW-quest-tracker-style sub-goal DAG, single-active-major-goal-per-league discipline with switch intervention ([DOCS/goals.md](DOCS/goals.md))
- `guides.recommend_next_action(player_fm, league_fm, character_fm)` — the keystone composer; returns the next sub-goal + relevant guides, creators, case studies, confidence gaps
- 62 systems guides at [`data/systems/`](data/systems/) — past leagues (0.1 → 0.5), core mechanics, tool guides, 31 1%-donation stubs Pedro co-authors with Claude across play
- 45-creator catalog across 7 language communities, with optional `community_women` / `community_lgbtq` style tags for representation discoverability
- 16-edge taxonomy at [`data/guides/edge_taxonomy.yaml`](data/guides/edge_taxonomy.yaml) — postures and patterns separating skilled from beginner play; each carries an asymptotic confidence in `[0, 1)`
- NeverSink filter strictness + customization recommender via `neversink.recommend_filter()`

### Graph-native v2 surface (shipped 2026-05-27)

- **Unified store** (`store/`) — three-table SQLite (`nodes` / `edges` / `graph_refs`) with XML payloads. One schema for build, farm, craft, and guide graphs. Indexed for fast aggregation; `xml_extract` / `xml_set` helpers operate on payload fragments
- **`.X.graph` bundle format** (`graphfmt/`) — magic-header dispatch (zip-bundle vs gzip-single-doc) under one extension. Bundles carry a `manifest.xml` + content xmls + media + optional README. Community-shareable: one file is a runnable artifact ([DOCS/contracts.md](DOCS/contracts.md))
- **Farm cycles** (`farm/`) — DECLARE → OPEN → EXECUTE → CLASSIFY → RECONCILE → CLOSE lifecycle. Mod-regex pricing pre-filter cuts trade-API workload by an order of magnitude. Double-booked reconciliation surfaces output-vs-inventory gaps. Cycle close computes ROI, hit-rate, and div-per-hour summary edges ([DOCS/farming-cycles.md](DOCS/farming-cycles.md))
- **Market integrations** (`integrations/`) — poe.ninja currency / unique / build-meta client with polite TTL cache + official PoE 2 Trade API client with rate-limit backoff at 80% of any window
- **Clipboard ingestion** (`integrations/clipboard_listener.py`) — daemon watches Ctrl+C, parses PoE 2 item text via the existing `items.parser`, writes events to a queue dir, drained into the active cycle on demand. Pyperclip with PowerShell fallback

### MCP + Electron rig (wired 2026-05-28)

- **60 MCP tools** exposed via `mcp_server/` — Claude Desktop drives every layer (build, goals, farm, market, clipboard, views). See [DOCS/mcp-server.md](DOCS/mcp-server.md)
- **Electron standalone** (`electron/`) — three windows (Wizard / Home / Overlay), single-instance lock, hotkey fallback chain, PID-file orphan cleanup that's careful with sibling MCP servers; spawns the MCP server and clipboard listener as managed children with respawn caps ([DOCS/electron.md](DOCS/electron.md))
- **In-game HUD** — transparent click-through overlay rendered alongside PoE 2; goal tracker, item tooltip, map timer, cycle status, classify alert, reconcile warning, cycle summary cards. Audience dial ("1pct" terse vs "30pct" educational) per view
- **Local WebSocket bridge** — MCP server pushes views to the overlay via `view.render` events; player sees cycle state without alt-tabbing
- **.mcpb bundle** at `mcpb/poe2-graph.mcpb` — thin Claude Desktop wrapper pointing at the on-disk repo via `POE2_GRAPH_ROOT` user_config ([DOCS/mcpb.md](DOCS/mcpb.md))

## Quick start

```bash
git clone --recurse-submodules https://github.com/GepetoinTraining/poe2-graph.git
cd poe2-graph
pip install -r requirements.txt
pytest tests/                    # 582 tests, all green
python -m infra.updater status   # check staleness across all layers
```

For the in-game flow, also:

```bash
# 1. Install the Claude Desktop bundle (60 tools, bundle version 0.2.0).
#    Drag mcpb/poe2-graph.mcpb into Claude Desktop's extension settings;
#    set user_config.poe2_graph_root to this checkout's absolute path.

# 2. Launch the Electron rig (overlay + MCP server + clipboard listener).
cd electron && npm install && npm start

# 3. In a Claude Desktop conversation, ask Claude to declare a farming cycle.
#    Item drops auto-flow from your clipboard via the listener queue;
#    Claude classifies and pushes summary cards to the in-game HUD.
```

Then talk to Claude about Path of Exile 2 — the skill takes it from there.

## How it works

Three XML indexes auto-load every Claude session at `~/.claude/projects/D--poe2-graph/`:

- `EXILE.xml` — player state (PLAYER + LEAGUE + CHARACTER)
- `GUIDES.xml` — guide catalog + creators + edges
- `DOCS.xml` — chapter router (loaded on demand)

The thin [`SKILL.md`](SKILL.md) routes between [`DOCS/`](DOCS/) chapters by user intent. No encyclopedia dump per session.

The rig topology:

```
Electron app (npm start)
   ├─ Wizard window     (first-run setup; only when no install marker)
   ├─ Home window       (control room: status, restart actions, hotkey display)
   ├─ Overlay window    (transparent in-game HUD; summoned via Ctrl+Alt+Space)
   ├─ MCP server child  (python -m mcp_server.server, WS-only mode)
   └─ Clipboard child   (python -m integrations.clipboard_listener)

Claude Desktop
   └─ poe2-graph.mcpb → bootstrap.py → python -m mcp_server.server (stdio)
      └─ FastMCP exposes 60 tools (read state, drive cycles, push views)
                       │
                       │ view.render over localhost WebSocket
                       ▼
                 Overlay renderer dispatches by view_type
```

The Electron-spawned server runs in WS-only mode — it pushes views to the overlay but doesn't serve stdio. The Claude-Desktop-spawned server serves stdio (Claude calls tools). Both read the same on-disk state via the unified store and the `EXILE/` profile.

## Bundled forks (submodules under `tools/`)

| Submodule | Upstream | License | Why bundled |
|---|---|---|---|
| `tools/pob-poe2` | [PathOfBuildingCommunity/PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) | MIT | Planned: headless JSON snapshot export for `pob_snapshot.py` |
| `tools/pob-poe1` | [PathOfBuildingCommunity/PathOfBuilding](https://github.com/PathOfBuildingCommunity/PathOfBuilding) | MIT | PoE 1 carry-over support |
| `tools/neversink-poe2` | [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2) | MIT | All 7 strictness levels + 5 style packs on disk |
| `tools/neversink-poe1` | [NeverSinkDev/NeverSink-Filter](https://github.com/NeverSinkDev/NeverSink-Filter) | MIT | PoE 1 reference |

Each submodule keeps its LICENSE file per upstream MIT terms.

## League-launch update worker

NeverSink pushes patch-day filter updates within hours of league launch. The worker polls bundled forks and pulls updates automatically.

```bash
# Run from now through 24h post-launch
python -m infra.worker --watch --interval=300 --duration=72h --log=worker.log

# Or scope to filter-only (skip large PoB clones)
python -m infra.worker --watch --interval=300 --duration=72h \
  --only=tools/neversink-poe2,tools/neversink-poe1
```

Each iteration: `gh repo sync` upstream → fork, then `git fetch + reset` fork → local submodule. Per-tool intervals come from [`config.yaml`](config.yaml).

## Configuration

[`config.yaml`](config.yaml) at repo root is user-editable. It tracks:

- Bundled vs linked tools, per-tool update cycles (off / manual / scheduled / continuous)
- Cache size limits + per-category caching for `poe2db_cache/`
- Worker defaults (interval, log path, sync-upstream)
- Filesystem-scanner behavior

Edit freely; Claude reads it but never overwrites silently.

## Player data — never tracked

`EXILE/` and `.env` are sacrosanct. The updater explicitly protects them; `.gitignore` keeps them out of commits. The v2 runtime state also stays local:

- `EXILE/PLAYER.md`, `EXILE/LEAGUE_*.md`, `EXILE/CHARACTER_*.md` — your profile
- `EXILE/HISTORY.md` — Claude's append-only journal of leagues, completed goals, case studies, catalog contributions
- `EXILE/*.diffs/` — snapshot trail
- `.env` — account name + OAuth scopes (when added)
- `poe2_graph.db` — unified SQLite store with live cycle / craft / build state
- `.queue/clipboard/` — pending clipboard events awaiting drain into a cycle
- `.cache/` — disk-backed caches managed by `infra.updater`, `poe_ninja`, `trade_api`

## Non-goals

- **Not** a damage simulator. No DPS computation, no conditional stat resolution. [PoB](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) does that.
- **Not** a build planner replacement. Hand off to PoB-PoE2 for full simulation.
- **Not** a tree visualizer. Hand off to [natwarth's hosted viewer](https://natwarth.github.io/poe2-skilltree/).
- **Not** an item-filter generator. Hand off to NeverSink.
- **Not** a continuous wealth tracker. Hand off to Exilence CE — cycles are the layer on top, not a replacement (see [DOCS/farming-cycles.md](DOCS/farming-cycles.md) § "When to hand off to Exilence CE").

We're the connective tissue, not a reimplementation of any of these.

## Status + roadmap

**v1.5.0** ships:

- Build & planning surface (Phase 1+2 from session 1-2)
- Graph-native v2 surface — `store/`, `graphfmt/`, `farm/`, market clients, clipboard daemon
- MCP + Electron rig — 60 tools, three windows, autospawned child processes, in-game HUD
- 582 tests green
- `.X.graph` schema vocabulary specified in [DOCS/contracts.md](DOCS/contracts.md)
- §11 validation report at [validation/skill-mapping-report.md](validation/skill-mapping-report.md)

**Deferred (post-league):**

- `electron-builder` distributable (signed `.exe` for non-developer install) — currently `npm start` from a checkout
- `farm.import_cycle_bundle` (inverse of export) — unlocks the import-and-re-run community-primitive use case
- Custom classify-bucket vocabulary beyond `valuable_mod_threshold`
- Mid-cycle currency-snapshot refresh
- Turso Cloud replication for mobile/web Claude reads of live state

See [CHANGELOG.md](CHANGELOG.md) for the cumulative delta.

## Documentation

| Read | When |
|---|---|
| [SKILL.md](SKILL.md) | Always — Claude's session router |
| [DOCS/](DOCS/) | Chapter-by-chapter; loaded on demand by `DOCS.xml` triggers |
| [DOCS/byte-format.md](DOCS/byte-format.md) | Parsing / encoding `.build` URLs |
| [DOCS/build-construction.md](DOCS/build-construction.md) | Constructing / extending / emitting builds |
| [DOCS/graph-queries.md](DOCS/graph-queries.md) | NetworkX wrapper + Steiner + canonical queries |
| [DOCS/goals.md](DOCS/goals.md) | Five goal types, decomposition DAG, switch discipline |
| [DOCS/guides.md](DOCS/guides.md) | Systems + edge taxonomy + creators + case studies |
| [DOCS/exile.md](DOCS/exile.md) | PLAYER/LEAGUE/CHARACTER state + confidence math |
| [DOCS/poe2db.md](DOCS/poe2db.md) | Item & mod catalog ingestion |
| [DOCS/updater.md](DOCS/updater.md) | Three-layer staleness + protected paths |
| [DOCS/farming-cycles.md](DOCS/farming-cycles.md) | v2: declare/open/execute/classify/reconcile/close + publish |
| [DOCS/contracts.md](DOCS/contracts.md) | v2: `.X.graph` XML schema vocabulary |
| [DOCS/mcp-server.md](DOCS/mcp-server.md) | MCP tool surface, transport, view push protocol |
| [DOCS/electron.md](DOCS/electron.md) | Rig topology, windows, hotkeys, child-process management |
| [DOCS/mcpb.md](DOCS/mcpb.md) | Claude Desktop bundle, install, user_config |
| [data/systems/](data/systems/) | Per-mechanic teaching guides + past-league context |
| [ONBOARDING.md](ONBOARDING.md) | First-time player setup flow |
| [ATTRIBUTIONS.md](ATTRIBUTIONS.md) | Every community project we depend on |
| [BUGS.md](BUGS.md) | Open bug-hunter punch list |
| [validation/skill-mapping-report.md](validation/skill-mapping-report.md) | §11 audit: v2 design claims vs existing code |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| `poe2-graph-spec.html` + `poe2-graph-goals-guides-spec.html` | Pre-implementation design specs |

## Credits

Built by **Pedro Garcia** (data modeller, PoE backer since 2012, 15k+ hours played) paired with **Claude** (web for design/recognition, Claude Code for implementation). Every community project we depend on, bundle, or learn from is in [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

If your project or channel is referenced here and we got something wrong — or you should be listed and we missed you — open an issue.

## License

Skill code under this repo: **MIT**. Bundled fork content keeps its upstream LICENSE per MIT terms. Filter / build-planner / item-parser projects retain their authors' licenses.

PoE 2 game data + names referenced under fair use; Path of Exile 2 © Grinding Gear Games.
