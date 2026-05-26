# poe2-graph

A Claude-native toolkit for **Path of Exile 2** build planning. Reads build URLs and `.build` files, walks the passive-tree graph, plans tonight's next action, emits annotated `.build` files the game renders inline, and accumulates a transmissible model of the player's progress across leagues.

**Status**: v1.0.0 — ready for [Path of Exile 2: Return of the Ancients (0.5)](https://pathofexile2.com/) league start, **2026-05-29 17:00 UTC**.

## What it is

PoE 2 ships its build-construction game **as a graph database**. Passive tree, atlas tree, ascendancies, weapon-set specializations, and choice-resolution overrides share one schema. Sources (jewels, items, passives, skill overrides) all collapse to one flat stat table at bind time; the combat loop is source-blind.

poe2-graph trusts GGG's canonical graph data and only does graph operations on it. Maintenance scales O(1) per patch — refresh the JSON, ship. Community handoffs cover the rest:

- **NeverSink** owns item filters (MIT)
- **Path of Building Community** owns build sim + DPS calc (MIT)
- **Path-of-Tools** owns item parsing (ISC)
- **poe2db.tw** owns extracted item/mod data
- **poe-tool-dev** owns patch-version tracking (MIT)

The skill is the connective tissue: it talks to Claude, walks the graph, and points at the right community tool for each problem.

## Quick start

```bash
git clone --recurse-submodules https://github.com/GepetoinTraining/poe2-graph.git
cd poe2-graph
pip install -r requirements.txt
pytest tests/                    # 276 tests, all green
python updater.py status         # check staleness across all layers
```

Then talk to Claude about Path of Exile 2 — the skill takes it from there.

## What's inside

- **Read + write `.build` files** — GGG's official JSON format that the game renders inline via the BuildPlanner watch directory. ([SKILL.md](SKILL.md) routing → `parser`, `build_reader`, `build_writer`)
- **Goal decomposition** — five goal types, WoW-quest-tracker-style sub-goal DAG, single-active-major-goal-per-league rule with switch intervention. ([DOCS/goals.md](DOCS/goals.md))
- **Keystone composer** — `guides.recommend_next_action(player_fm, league_fm, character_fm)` returns the next sub-goal + relevant guides, creators, case studies, confidence gaps. Surfaces "what should I do tonight."
- **62 systems guides** at [`data/systems/`](data/systems/) — past leagues (0.1 → 0.5), core mechanics (waystones, trials, atlas, citadels, weapon sets, spirit, crafting), tool guides, plus 31 1%-donation stubs Pedro Garcia co-authors with Claude across play.
- **45-creator catalog** at [`data/guides/creators/`](data/guides/creators/) across 7 language communities. Optional `community_women` / `community_lgbtq` style_tags surface representation discoverability.
- **16-edge taxonomy** at [`data/guides/edge_taxonomy.yaml`](data/guides/edge_taxonomy.yaml) — postures and patterns (market_timing, posture_under_drop, miss_economy, marginal_capability_thinking, etc.) that separate skilled from beginner play. Each carries an asymptotic confidence in `[0, 1)`.
- **Filter recommender** — `neversink.recommend_filter()` picks a strictness level (regular → uber-plus-strict) + customizations based on build state. Hands off to NeverSink's actual filter; we never modify or redistribute it.
- **PoE 2 launched ~3 weeks before 0.5** — see [`data/systems/league_0_5_return_of_the_ancients.md`](data/systems/league_0_5_return_of_the_ancients.md) for the league mechanic + Fortress + expanded atlas overview.

## How it works

Three XML indexes auto-load every Claude session at `~/.claude/projects/D--poe2-graph/`:

- `EXILE.xml` — player state (PLAYER + LEAGUE + CHARACTER)
- `GUIDES.xml` — guide catalog + creators + edges
- `DOCS.xml` — chapter router (loaded on demand)

The thin [`SKILL.md`](SKILL.md) routes between [`DOCS/`](DOCS/) chapters by user intent. No encyclopedia dump per session.

## Bundled forks (submodules under `tools/`)

| Submodule | Upstream | License | Why bundled |
|---|---|---|---|
| `tools/pob-poe2` | [PathOfBuildingCommunity/PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) | MIT | Planned: headless JSON snapshot export for `pob_snapshot.py` |
| `tools/pob-poe1` | [PathOfBuildingCommunity/PathOfBuilding](https://github.com/PathOfBuildingCommunity/PathOfBuilding) | MIT | PoE 1 carry-over support |
| `tools/neversink-poe2` | [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2) | MIT | All 7 strictness levels + 5 style packs on disk |
| `tools/neversink-poe1` | [NeverSinkDev/NeverSink-Filter](https://github.com/NeverSinkDev/NeverSink-Filter) | MIT | PoE 1 reference |

Each submodule keeps its LICENSE file per upstream MIT terms.

## League-launch update worker

NeverSink pushes patch-day filter updates within hours of league launch. The included worker polls bundled forks and pulls updates automatically.

```bash
# Run from now through 24h post-launch
python worker.py --watch --interval=300 --duration=72h --log=worker.log

# Or scope to filter-only (skip large PoB clones)
python worker.py --watch --interval=300 --duration=72h \
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

`EXILE/` and `.env` are sacrosanct. The updater explicitly protects them; `.gitignore` keeps them out of commits:

- `EXILE/PLAYER.md`, `EXILE/LEAGUE_*.md`, `EXILE/CHARACTER_*.md` — your profile
- `EXILE/HISTORY.md` — Claude's append-only journal of your leagues, completed goals, case studies, catalog contributions
- `EXILE/*.diffs/` — snapshot trail
- `.env` — account name + OAuth scopes (when added)

## Non-goals

- **Not** a damage simulator. No DPS computation, no conditional stat resolution. [PoB](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) does that.
- **Not** a build planner replacement. Hand off to PoB-PoE2 for full simulation.
- **Not** a tree visualizer. Hand off to [natwarth's hosted viewer](https://natwarth.github.io/poe2-skilltree/).
- **Not** an item-filter generator. Hand off to NeverSink.

We're the connective tissue, not a reimplementation of any of these.

## Status + roadmap

**v1.0.0** ships:

- 21 Python modules, 276 tests green
- Full goal + guide + creator + edge taxonomy
- Three XML index pattern, league-launch update worker, config + history systems
- Four bundled MIT forks (PoB ×2, NeverSink ×2)

See [CHANGELOG.md](CHANGELOG.md) for the full delta + v1.1 deferred items (HTML spec sync, `pob_snapshot.py` once PoB-PoE2 headless lands upstream, ~47 future-stub topic slugs to expand, expanded test coverage for network-touching paths).

## Documentation

| Read | When |
|---|---|
| [SKILL.md](SKILL.md) | Always — Claude's session router |
| [DOCS/](DOCS/) | Chapter-by-chapter API reference |
| [data/systems/](data/systems/) | Per-mechanic teaching guides + past-league context |
| [ONBOARDING.md](ONBOARDING.md) | First-time player setup flow |
| [ATTRIBUTIONS.md](ATTRIBUTIONS.md) | Every community project we depend on |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| `poe2-graph-spec.html` + `poe2-graph-goals-guides-spec.html` | Design specs (pre-implementation; will be reconciled in v1.1) |

## Credits

Built by **Pedro Garcia** (data modeller, PoE backer since 2012, 15k+ hours played) paired with **Claude** (web for design/recognition, Claude Code for implementation). Every community project we depend on, bundle, or learn from is in [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

If your project or channel is referenced here and we got something wrong — or you should be listed and we missed you — open an issue.

## License

Skill code under this repo: **MIT**. Bundled fork content keeps its upstream LICENSE per MIT terms. Filter / build-planner / item-parser projects retain their authors' licenses.

PoE 2 game data + names referenced under fair use; Path of Exile 2 © Grinding Gear Games.
