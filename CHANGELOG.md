# Changelog

All notable changes to poe2-graph are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [1.0.0] — 2026-05-26

First production release. Lands 3 days before PoE 2 0.5 (Return of the Ancients) league launch.

### Added — schema + content

- **Edge taxonomy** (16 edges, 5 categories): economic (7), crafting (3), discipline (2), trade (1), psychological (3). Each carries an asymptotic confidence in `[0, 1)` per the bump rule.
- **Edge-transmission system guides** (3): `mirror_handling_v1`, `playstyle_calibration_v1`, `upgrade_pacing_v1`. Wired with multiple creator references each.
- **Case studies** (3 authored): `mirror_drop_day_1`, `found_fubgun_excitement`, `mid_map_upgrade_decision`. Several TODO slots reserved across the system guides.
- **Mechanic & past-league system guides** (62 total in `data/systems/*.md`):
  - 5 past leagues — Early Access through Return of the Ancients (0.1 → 0.5)
  - 13 core mechanic guides — waystones, trials of sekhemas / chaos, atlas towers + tablets, weapon sets, spirit, skill gems, citadels, runes + sockets, soul cores, currency overview, ascendancies, trade engagement
  - 2 expanded stubs — essence_crafting, atlas_passive_tree
  - 3 main 1%-donation guides — crafting, farming, trade
  - 31 1%-donation stubs — Pedro's 1% knowledge donation across crafting (13), farming (9), trade (9), to be co-authored in play sessions
  - 8 tool guides — overview + per-tool guides for PoB-PoE2, PoB-PoE1, Awakened PoE Trade, Exilence Next, Chaos Recipe Enhancer, POE Overlay, NeverSink Filter
- **Creator catalog** (45 creators across 7 language communities): English (26), Russian (4), Portuguese-BR (5), Chinese (4), Korean (3), Japanese (2), Romanian (1). Optional `community_women` / `community_lgbtq` style_tags surface representation discoverability.

### Added — modules

- `parser.py` — v7 build-URL byte codec (parse + encode + round-trip).
- `build_reader.py` — `.build` JSON → typed dataclasses.
- `build_writer.py` — typed dataclasses → `.build` JSON with markup (color, font, size tags).
- `resolvers.py` — passive + atlas tree JSON loaders + numeric/string ID joins.
- `graph.py` — NetworkX wrapper + canonical queries + Steiner tree.
- `allocation.py` — mutable Allocation builder (the build-construction API).
- `stats.py` — stat string → (template, values, raw) tuple (no math).
- `poe2db_client.py` — poe2db.tw ModsView fetcher + autocomplete.
- `exile.py` — PLAYER / LEAGUE / CHARACTER frontmatter IO + EXILE.xml composer + confidence math (`bump_confidence` asymptotic toward 1.0).
- `goals.py` — five goal types (`Goal`, `LearningGoal`, `PlayerGoal`, `SubGoal`, `LeagueGoal`) + decomposition DAG + single-active-major rule + switch intervention + WoW-tracker rendering.
- `guides.py` — system guides + case studies + edge taxonomy + creators + GUIDES.xml composer + **`recommend_next_action`** keystone composer.
- `systems.py` — per-mechanic teaching guides over `data/systems/*.md`.
- `creators.py` — back-compat shim over `guides.Creator`.
- `filesystem_scanner.py` — detect installed tools (PoB / Awakened / Exilence / CRE / Overlay), PoE 2 install path, OnlineFilters dir.
- `updater.py` — three-layer staleness (skill / tree data / poe2db cache) + bundled-fork submodule tracking + protected paths.
- `docs.py` — DOCS.xml composer over `DOCS/*.md` frontmatter.
- `messenger.py` — stub for the future WebSocket bridge.
- `neversink.py` — filter strictness + customization recommender + local-fork file-path resolver.
- `config.py` — `config.yaml` loader with dataclasses + singleton cache + query helpers.
- `history.py` — append-only journal at `EXILE/HISTORY.md` (leagues played, goals completed, case studies, donations to catalog).
- `worker.py` — league-launch update loop. Polls bundled forks, syncs upstream → fork via `gh repo sync`, pulls fork → local submodule. Per-tool intervals from config.

### Added — infrastructure

- **Three XML indexes** auto-loaded each session at `~/.claude/projects/D--poe2-graph/`: `EXILE.xml` (player state), `GUIDES.xml` (guide catalog), `DOCS.xml` (chapter router).
- **Bundled forks** as git submodules under `tools/`: PathOfBuilding-PoE2, PathOfBuilding (PoE 1), NeverSink-Filter-for-PoE2, NeverSink-Filter (PoE 1). All MIT-licensed; LICENSE files preserved per upstream terms.
- **`config.yaml`** at repo root — user-editable. Tracks 9 tools (4 bundled forks + 5 linked), per-tool update cycles, cache caps, worker defaults, scanner settings.
- **`EXILE/HISTORY.md`** — Claude-only append-only journal. Distinct from PLAYER.md (current state) and PLAYER.diffs/ (snapshot trail).
- **Keystone integration test** (`tests/test_keystone_integration.py`) — exercises the full planning loop: bootstrap EXILE → set active PlayerGoal w/ sub-goals → `recommend_next_action` → allocate via Allocation API → emit annotated .build → snapshot diffs → apply case-study bump → recompose all 3 XMLs.
- **Tests**: 276 green. Coverage spans every shipped module + most public API.

### Added — documentation

- **`SKILL.md`** — thin router (~110 lines). Loaded every session.
- **`DOCS/*.md`** — 8 chapters loaded on demand via `DOCS.xml`: byte-format, build-construction, graph-queries, goals, guides, exile, poe2db, updater.
- **`ONBOARDING.md`** — 4-phase first-time flow (filesystem scan → questionnaire → artifacts → synthesize).
- **`ATTRIBUTIONS.md`** — durable credit trail for every community project we depend on, bundle, or learn from. Now includes bundled-fork section + per-fork license + patches in flight.

### Changed

- **PoB compatibility framing**: `pob_snapshot.py` is the planned bridge module that consumes PoB-PoE2's calculated stats (eDPS, eHP) once the upstream headless JSON-RPC API ships (currently in PoE 1 PR #9505). Snapshot schema defined; reader pending.
- **`updater.py`** extended with `_parse_gitmodules`, `check_tool_submodule(s)`, `update_tool_submodule`, `sync_fork_from_upstream`, `update_all_tool_submodules`. New CLI command: `update-tools`. `StalenessReport` gained `tool_submodules: list[SourceStatus]`. `PROTECTED_PATHS` extended with `tools/` and `config.yaml`.
- **`filesystem_scanner.py`** gained `poe2_online_filters` probe — PoE 2 stores online-synced filters in `~/Documents/My Games/Path of Exile 2/OnlineFilters/` with opaque-ID filenames (different mechanism from PoE 1's `.filter` user-data convention).
- **`neversink.py`** now surfaces bundled filter file paths when `tools/neversink-poe2/` is present. Render output includes both the local-disk path and the upstream download URL.
- **History hooks**: `goals.complete_player_goal`, `goals.advance_mastery`, `guides.case_study_apply_bumps` now append to `EXILE/HISTORY.md` automatically. Best-effort — history I/O failures don't block primary flow.

### Fixed (audit pass before tag)

- **CRITICAL** `build_writer.validate()` — scalar `level_interval` (legal type per `LevelInterval = Union[int, list[int]]`) used to crash with `TypeError`. Now guarded with `isinstance(..., list)`.
- **CRITICAL** `guides.py` keystone composer — `PlayerGoal.from_dict()` / `LearningGoal.from_dict()` / `Goal.from_dict()` calls now wrapped in defensive try/except so malformed PLAYER.md entries skip silently instead of crashing `recommend_next_action`.
- Three concrete data typos: `trial_of_chaos` → `trials_of_chaos` in `league_0_1_early_access.md` + `trials_of_sekhemas.md`; `neversink` → `tool_neversink_filter` in `farming_filters.md`.
- Six dead imports removed across `guides.py`, `exile.py`, `build_writer.py`, `creators.py`.
- Doc count drift corrected across SKILL.md (test count), ATTRIBUTIONS.md (systems guide count), DOCS/graph-queries.md (node + edge count), DOCS/guides.md (edge count), DOCS/updater.md (new CLI commands), DOCS/build-construction.md (namespace prefix), ONBOARDING.md ("TBD module" stale marker).
- `manifest.json` `game_version` bumped from "0.5 pre-launch (Return of the Ancients)" to "0.5.0 Return of the Ancients" for launch.

### Known limitations carried forward to v1.1

- HTML specs (`poe2-graph-spec.html`, `poe2-graph-goals-guides-spec.html`) are pre-implementation drafts. `§8 Module surface` lists function names that diverged during implementation (code chose better names — `list_creators` vs `creator_load`, etc.). Spec-sync PR to land alongside v1.1.
- `poe-tool-dev/latest-patch-version` upstream tracker returns PoE 1's version. No equivalent PoE 2 source exists yet; `manifest.json:game_version` is manually maintained at patches.
- `~47` `related_topics:` entries across `data/systems/*.md` reference future-stub topic slugs (e.g. `huntress`, `runes_of_aldur`, `fortress`) that don't yet exist as files. These are intentional anchors for v1.1+ expansion.
- `pob_snapshot.py` referenced as planned but not yet authored. Will land alongside upstream PoB-PoE2's headless JSON-RPC API support.
- Test coverage gaps: network-touching updater functions (`sync_fork_from_upstream`, `update_tool_submodule` happy path, `update_data_source`, `check_skill_version`), `worker.watch()` end-to-end, several weak inclusion-only assertions. Comprehensive coverage pass scheduled for v1.1.
- Onboarding flow has not yet been run against a real player (Pedro himself). Templates and module surface ready; the live walk-through happens at league start.

---

## [0.1.0] — Pre-history

Internal pre-release. Spec ratification + initial skill scaffold + three-XML-index pattern + first 25-creator catalog from the multi-region swarm. Superseded by 1.0.0.
