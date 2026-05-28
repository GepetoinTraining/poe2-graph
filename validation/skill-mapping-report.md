# Skill mapping report — §11 validation gate

## One-paragraph summary

The design's §11 reuse claims are largely **confirmed** for the graph core (`graph/parser.py`, `graph/resolvers.py`, `graph/network.py`, `graph/allocation.py`, `graph/stats.py`) and for the player-state surface (`exile.py`, `history.py`, `docs.py`). They are **partial** for `goals.py` (three goal types fully present, the claim of "five" is by design since the spec split them across `Goal`, `LearningGoal`, `PlayerGoal`/`SubGoal`, and `LeagueGoal`) and **partial** for `guides.py`+`systems.py` (the guide corpus exists and produces XML, but the file format is YAML, not a `.guide.graph` format). The `integrations/messenger.py` claim ("stub for future bridge — line 83 of SKILL.md") is **false**: messenger is a fully implemented, threaded pub/sub event bus with transports and a snapshot layer, not a stub; the natwarth viewer protocol occupies a documented comment block at the bottom but is gated behind `is_natwarth_viewer_available()` which always returns `False`. The `infra/worker.py` claim is **confirmed**: it is the watchdog pattern the design assumes.

---

## Module-by-module verification

---

### parser.py (design name) → `graph/parser.py` (actual)

- **Claim:** URL byte format → graph nodes; extends to `.X.graph` with format-specific decoders.
- **Reality:** Confirmed as the URL byte codec. The module provides `parse(url_or_code: str) -> Build`, `encode(build: Build) -> bytes`, `encode_url(build: Build, ...) -> str`, and `flag_summary(build: Build) -> dict[int, int]`. The `Build` dataclass carries `version`, `character_class`, `ascendancy`, and `records: list[NodeRecord]`. `NodeRecord` carries `node_hash` (uint16), `flags`, `weapon_set`, and `skill_override`. The codec is byte-exact (round-trip tested with Pedro's real URL). It handles the v7 binary format, decoding the base64url payload into the full record list. There is **no** format dispatcher, no `.X.graph` suffix logic, and no format-specific decoder registry. The module is hard-wired to format version 7 (line 19: `SUPPORTED_VERSION = 7`; line 88-89: raises on mismatch).
- **Verdict:** Confirmed for the existing role; the v2 extension point (format-specific decoders for `farm`, `craft`, `guide` graph types) does **not exist** — it would need to be added.
- **Gap:** No `graph_type` discriminator field. No pluggable decoder. The v2 design assumes a `.X.graph` bundle format where the `X` suffix indicates graph type — `parser.py` would need a dispatcher layer or a separate `bundle_codec.py` around it.
- **Extension strategy:** Extend in-place — add a format-version registry and a `graph_type` header field, keeping the existing `parse()` as the `passive_tree` decoder. Do not fork.

---

### resolvers.py (design name) → `graph/resolvers.py` (actual)

- **Claim:** Tree JSON loader, ID joins, node addressing primitive.
- **Reality:** Confirmed exactly. The `Tree` dataclass wraps the raw JSON with `@cached_property` indexes: `nodes_by_dict_key`, `nodes_by_string_id`, `nodes_by_skill_hash`, `skill_overrides`, `classes`. Public API (lines 49-94): `class_name(class_id)`, `ascendancy_name(class_id, ascendancy_id)`, `node_by_hash(node_hash)`, `node_by_id(string_id)`, `hash_to_string_id(node_hash)`, `string_id_to_hash(string_id)`, `override(override_id)`, `override_name(override_id)`. Module-level loaders `load_passive_tree(path)` and `load_atlas_tree(path)` return `Tree` instances. This is the canonical ID-join primitive the rest of the graph layer builds on.
- **Verdict:** Confirmed.
- **Gap:** `load_atlas_tree` exists but v2 adds `farm.graph`, `craft.graph`, `guide.graph` as new graph types — resolvers only handles `passive-tree.json` and `atlas-tree.json` formats. Both are the same node/edge shape. New graph types may need a `Tree`-compatible loader or a parallel `GraphIndex` abstraction if their schema diverges.
- **Extension strategy:** Extend in-place — add a `load_generic(path)` or `Tree.from_dict(raw)` class method if new graph types share the node/edge schema. If schemas diverge, wrap `Tree` in a protocol.

---

### graph.py (design name) → `graph/network.py` (actual)

- **Claim:** NetworkX wrapper with canonical queries + Steiner. THE graph engine. Extends to `graph_type IN ('farm','craft','guide')`.
- **Reality:** Confirmed as the canonical graph engine. `build_graph(tree: Tree) -> nx.Graph` constructs the undirected graph keyed on `skill` (uint16) hashes. Handles both edge-list schema (passive tree) and adjacency-list schema (atlas tree) at lines 34-50. Canonical queries: `allocated_hashes(build)`, `shortest_path(g, source, target)`, `shortest_path_length(g, source, target)`, `orphans(g, build, start)`, `nearest_unallocated_notables(g, build, tree, limit)`, `diff_builds(a, b)`. Steiner: `steiner_route(g, terminals) -> set[int]` at lines 140-160 — uses NetworkX's Mehlhorn 2-approximation, restricted to the connected component of the first terminal. `summarize(build, tree) -> BuildSummary` at lines 176-213 produces a typed dataclass with notables, keystones, jewel_sockets, masteries, attribute_choices, weapon_set_split.
- **Verdict:** Confirmed for the existing scope. The graph engine is general-purpose — `build_graph` accepts any `Tree` object regardless of tree type.
- **Gap:** All current consumers pass a passive-tree or atlas-tree `Tree`. A `farm.graph` or `craft.graph` node schema would need to: (a) produce a `Tree`-compatible raw dict, OR (b) produce an `nx.Graph` by another path. The `summarize` function is passive-tree-specific (it checks `isNotable`, `isKeystone`, `isJewelSocket`, `isMastery` node attributes). Any per-graph-type summary would need its own function. There is no `graph_type` attribute on the graph or its nodes.
- **Extension strategy:** Extend in-place — `build_graph` already handles schema differences. Add `graph_type`-tagged `summarize_*` variants per new graph type, or a `GraphType` enum that `summarize` dispatches on.

---

### allocation.py (design name) → `graph/allocation.py` (actual)

- **Claim:** Mutable build builder. The graph-mutation API.
- **Reality:** Confirmed as the graph-mutation API. `Allocation` dataclass (lines 49-312) wraps `Tree`, `nx.Graph`, `character_class`, `ascendancy`, and `records: dict[int, NodeRecord]`. Constructors: `Allocation.new(tree, g, character_class, ascendancy)`, `Allocation.from_build(build, tree, g)`, `Allocation.from_url(url_or_code, tree, g)`. Mutation API: `allocate(key, weapon_set, skill_override) -> NodeRecord`, `deallocate(key) -> bool`, `allocate_many(keys)`, `extend_to(target, weapon_set) -> list[int]`, `route_through(*targets, include_start) -> list[int]`. Inspection: `allocated`, `class_start_hash`, `ascendancy_key`, `frontier`, `is_contiguous`, `orphans()`, `shortest_path_to(target)`, `cost_to(target)`. Node-category helpers: `notables()`, `keystones()`, `jewel_sockets()`, `masteries()`, `nearest_unallocated_notables(limit)`. Export: `to_build() -> Build`, `to_url() -> str`.
- **Verdict:** Confirmed.
- **Gap:** `Allocation` is tightly coupled to the passive-tree node schema (its category helpers check `isNotable`, `isKeystone`, etc.). For `farm.graph` or `craft.graph`, node attributes would differ. The Turso-backed store the design proposes would need `Allocation`'s mutation log, which doesn't exist — mutations are in-place with no event log. Also, `Allocation` has no `graph_type` field; extending it to non-passive-tree uses requires at minimum passing through a different node-schema for category detection.
- **Extension strategy:** Extend in-place — add a `graph_type` parameter to `Allocation`, make category helpers configurable via a `NodeSchema` protocol. Keep the existing passive-tree code as the `passive_tree` implementation. Do not rewrite.

---

### stats.py (design name) → `graph/stats.py` (actual)

- **Claim:** Stat string parsing. Edge-payload parsing primitive.
- **Reality:** Confirmed, with a narrow scope. `Stat` dataclass (lines 29-38): `template: str` (numbers replaced by `#`, brackets stripped to display text), `values: list[float]` (numeric runs), `raw: str`. Public API: `strip_brackets(text) -> str`, `parse(text: str) -> Stat`, `aggregate(stats: list[Stat]) -> dict[str, float]`. The `aggregate` function sums values across identical templates but only for single-value stats — multi-value stats (e.g. "Adds # to # damage") are documented as needing consumer-side handling (lines 64-67).
- **Verdict:** Confirmed for what it does; **partial** for the "edge-payload parsing primitive" claim.
- **Gap:** The module parses GGG's `[link|display]` bracket syntax from tree JSON stat strings. It does NOT parse edge payloads in any broader sense — there is no edge payload schema, no serialization/deserialization for v2 edge payloads, and no awareness of `edge_taxonomy`. The v2 design's reference to `stats.py` as "edge-payload parsing primitive" is aspirational: the regex-plus-template approach here is sound for stat aggregation but would need a separate `edge_payload` schema if v2 edges carry structured payloads beyond stat strings.
- **Extension strategy:** Extend in-place with a separate `parse_edge_payload(payload: dict) -> EdgePayload` function (or a new `graph/edge_payload.py` sibling). Do not touch the stat-string parser.

---

### goals.py (design name) → `goals.py` (actual, root level)

- **Claim:** Five goal types with decomposition DAG. **This is already a `.guide.graph` implementation, just unnamed.**
- **Reality:** The claim of "five goal types" maps to four distinct classes across the module: `Goal` (character-level, 6 kinds: `reach_keystone`, `reach_notable`, `level_milestone`, `stat_threshold`, `obtain_item`, `freeform`), `LearningGoal` (league-level mastery), `PlayerGoal` (cross-league durable, with 4 types: `economic`, `mechanical`, `knowledge`, `identity`) and `SubGoal` (11 kinds: `stat_threshold`, `composite`, `atlas_progression`, `economic`, `knowledge`, `milestone`, `acquire`, `travel`, `kill`, `interact`, `freeform`), and `LeagueGoal` (in-league tactical). The "decomposition DAG" is `PlayerGoal.sub_goals: list[SubGoal]` with `SubGoal.depends_on: list[str]` forming an acyclic dependency graph. `PlayerGoal.next_actionable()` traverses it to find the leaf-most available sub-goal. `render_goal_tracker(goal: PlayerGoal) -> str` produces a WoW-tracker-style text block. The intervention system (`GoalSwitchIntervention`, `propose_goal_switch`) prevents casual major-goal switching. Goal state is stored as YAML frontmatter lists in `PLAYER.md`, `LEAGUE_*.md`, and `CHARACTER_*.md` — not as a graph format at all.
- **Verdict:** Confirmed for the goal types and decomposition DAG. **False** for the "`.guide.graph` implementation" framing — goals are stored as YAML frontmatter, there is no graph file, no graph serialization, and no `.guide.graph` schema.
- **Gap:** No XML output, no graph file format, no Turso schema. The v2 design calls for goals to become `.guide.graph` content — the CONTRACTS.md author must invent that serialization. The existing `to_dict()` / `from_dict()` API on every class is a clean starting point. `goal_friction()` (lines 905-931) implements a heuristic tension-detector between player goals and league goals — primitive, but the pattern is there. Progress rollup is manual (mean of sub-goals, line 672-677) — a Turso-backed cycle table would replace this.
- **Extension strategy:** Extend in-place — add an `to_graph_record()` method per class that emits the Turso row schema. Keep the YAML frontmatter as the Claude-readable cache; Turso becomes the query surface. Do not remove the frontmatter path until Turso is proven.

---

### guides.py + systems.py (design name) → `guides.py` + `systems.py` (actual, root level)

- **Claim:** Guide corpus. Becomes `.guide.graph` content.
- **Reality:** Two distinct modules with overlapping purposes that the routing table in SKILL.md distinguishes (lines 53, 139):
  - `guides.py`: the v2 guide corpus. `SystemGuide` dataclass loaded from `data/guides/system/*.yaml`. `CaseStudy` loaded from `data/guides/system/case_studies/*.yaml`. `Creator` from `data/guides/creators/*.yaml`. `Edge` from `data/guides/edge_taxonomy.yaml`. `GuideIntent` for per-character build intent. `recommend_next_action()` (lines 490-598) is the full keystone composer that joins player/league/character frontmatter with the guide corpus, scoring guides by edge overlap. `compose_guides_xml()` / `write_guides_xml()` produce GUIDES.xml — a complete XML composer for system guides + case studies + creators.
  - `systems.py`: the legacy per-topic guide reader. `SystemsGuide` (different from guides.`SystemGuide` — note the name collision!) loaded from `data/systems/*.md`. Carries mastery vocabulary (`not_started`, `learning`, `competent`, `confident`) and attributed-to creator references. It's still loaded when matching `LearningGoal.topic` to a system guide in `recommend_next_action()` (lines 519-522). It is NOT a replacement for guides.py's `SystemGuide` — they coexist.
- **Verdict:** Confirmed for the "guide corpus + XML composer" role. **Partial** for "becomes `.guide.graph` content" — the corpus is YAML files in `data/guides/` and `data/systems/`, not a graph file format, and there is no serialization to `.guide.graph`.
- **Gap:** The name collision between `guides.SystemGuide` (the v2 YAML system guide) and `systems.SystemsGuide` (the legacy markdown system guide) is a maintenance hazard. They have different schemas: `guides.SystemGuide` carries `transmits: list[str]` (edge names), `case_studies: list[str]`, `creators: list[dict]`, `prerequisites: list[dict]`; `systems.SystemsGuide` carries `mastery_levels: dict[str, str]` and `attributed_to: list[str]`. The migration path (noted in LEAGUE_*.md comment, line 141: "Will gradually merge into knows.<game>.<edge_name> confidence tracking") is incomplete. `compose_guides_xml()` composes the v2 corpus; `systems.py` data is NOT included in GUIDES.xml.
- **Extension strategy:** `guides.py` is the right write surface for v2. Extend `guides.SystemGuide` to include `mastery_levels` from `systems.SystemsGuide`, deprecate `systems.py` gradually. The `.guide.graph` serialization is a new layer — implement a `write_guide_graph()` that wraps `compose_guides_xml()` output into the bundle format.

---

### exile.py (design name) → `exile.py` (actual, root level)

- **Claim:** Player state with EXILE.xml composer. Becomes read path into Turso store.
- **Reality:** Confirmed and complete. `exile.py` is the master state module. It defines all EXILE paths (`SKILL_ROOT`, `EXILE_DIR`, `DONE_FILE`, `ENV_FILE`), provides `player_template()`, `league_template()`, `character_template()` for fresh skeleton creation. Frontmatter IO: `parse_frontmatter(text) -> (dict, str)`, `write_frontmatter(fm, body) -> str`, `read_file(path)`, `write_file(path, fm, body)`. Confidence math: `bump_confidence(current, delta)` (asymptotic toward 1.0, lines 227-244), `update_tag(fm, section, tag, delta, game)`, `get_tag(fm, section, tag, game)`. Diff log: `snapshot(path, label)`, `diff_against_initial(path)`, `diff_history(path)`. Onboarding: `is_onboarded()`, `mark_done()`, `init_skeleton()`. Character management: `list_characters()`, `create_character()`, `set_active_character()`, `active_character()`, `active_characters()`. League management: `list_leagues()`, `create_league()`. **EXILE.xml composer**: `compose_exile_xml() -> str` (lines 479-539), `write_exile_xml() -> Path`. The XML composer extracts all frontmatter sections (knows, prefers, unknown, goal_tags, active_mechanics, archetype_tags, defense_tags, offense_tags) into typed XML elements with confidence attributes.
- **Verdict:** Confirmed.
- **Gap:** The Turso "read path" is entirely absent — `exile.py` reads and writes YAML frontmatter Markdown files, not SQLite or Turso. The `compose_exile_xml()` function is the output surface, but there is no `read_from_turso()` or `write_to_turso()` path. Account name lives in `.env`; there is no OAuth connector (confirmed non-goal in SKILL.md line 23). The player state schema is richer than the v2 Turso `player` table would need — CONTRACTS.md author should extract the flat fields from `PLAYER.md` frontmatter as the column set.
- **Extension strategy:** Wrap, do not modify — add a `turso/exile_sync.py` that reads `exile.read_file(EXILE_DIR / "PLAYER.md")` and writes the Turso `player`, `league`, `character` tables. Keep `exile.py` as the source of truth during transition.

---

### history.py (design name) → `history.py` (actual, root level)

- **Claim:** Append-only journal. Becomes time-series queries against cycle table.
- **Reality:** Confirmed as an append-only journal, but the storage format is **Markdown with YAML frontmatter**, not SQLite. The file is `EXILE/HISTORY.md`. Public API (lines 77-264): `init() -> Path`, `append_league(league_id, started, ...)`, `append_goal_completed(goal_id, activated_at, ...)`, `append_learning_progress(learning_goal_id, league_id, mastery, ...)`, `append_case_study(case_id, scoring, bumps, ...)`, `append_donation(kind, summary, ...)`, `append_session_note(title, body_lines)`. Read API: `get_history() -> dict`, `has_completed_goal(goal_id) -> bool`, `leagues_count() -> int`, `has_seen_case_study(case_id) -> bool`. The "append" semantics are implemented by reading the YAML frontmatter, appending to a list in a specific section, and writing the file back — not a true append-only log. This is vulnerable to concurrent writes (no locking) but acceptable in a single-Claude-instance scenario. Every entry carries `appended_at` (ISO datetime) which is the timestamp field the Turso cycle table would use.
- **Verdict:** Confirmed for the append-only journal role; **partial** for "becomes time-series queries against cycle table." The existing data is queryable only by full-scan (`get_history()` returns everything). There is no indexing, no partial reads, and no range queries.
- **Gap:** No SQL primitives, no structured time-series queries. The `cycle table` concept from v2 maps to `leagues_played` + `goals_completed` rows in the frontmatter, but there is no `cycle_id` foreign key, no farming session concept, and no duration/delta tracking. The `append_at` timestamps are ISO strings, not epoch integers, and are stored as YAML strings rather than SQL columns.
- **Extension strategy:** Wrap — add a `turso/history_sync.py` that reads `history.get_history()` and upserts into Turso cycle/league/goal tables. The `HISTORY.md` append API stays as the Claude-side write surface; Turso becomes the query surface. The `appended_at` field becomes the `ts` column directly.

---

### worker.py (design name) → `infra/worker.py` (actual)

- **Claim:** League-launch update worker. Existing watchdog pattern.
- **Reality:** Confirmed exactly. The worker implements a two-phase loop: (1) `gh repo sync` to pull upstream changes into forks, (2) `git fetch origin && git reset --hard origin/HEAD` per submodule. Entrypoints: `run_once(only, sync_upstream, log_to, all_tools, interval_gate) -> int`, `watch(interval, stop_at, only, sync_upstream, log_to, ...)`. CLI: `python worker.py --watch --interval 300 --duration 72h --only tools/neversink-poe2 --log worker.log`. Per-tool intervals from `config.yaml` via `config.continuous_tools()`. Graceful Ctrl+C handling. Network errors per-iteration are caught, logged, and the loop continues (line 186: `except Exception as e: _log(...); continue`).
- **Verdict:** Confirmed.
- **Gap:** The worker is scoped to Git submodules (tool forks like NeverSink, PoB). The v2 design's "league-launch update worker" likely refers to a broader data-ingestion worker — pulling poe2db data, refreshing the Turso store, running the updater. That broader role is NOT in this module. `infra/updater.py` handles staleness detection; `worker.py` handles submodule pulls. The Turso ingestion loop would be a third worker.
- **Extension strategy:** Extend in-place — add a `DataIngestionWorker` class or a separate `infra/data_worker.py` that reuses the `watch()`/`run_once()` pattern but calls ingestion functions instead of `gh repo sync`.

---

### messenger.py (design name) → `integrations/messenger.py` (actual)

- **Claim:** Stub for a future bridge — line 83 of SKILL.md. **This design fills that stub.**
- **Reality:** **False — messenger is a fully implemented, threaded pub/sub event bus.** The SKILL.md line 83 reads "stub for future WebSocket bridge to natwarth's viewer" — which matches the *natwarth viewer protocol* documentation block at lines 239-283. But the module itself (lines 67-283) is a complete implementation with: thread-safe subscriber registry (`_subscribers`, `_subscribers_lock`), transport registry (`_transports`, `_transports_lock`), latest-event cache (`_latest_by_event`, `_latest_lock`), `publish(event_type, payload)`, `subscribe(event_type, handler) -> unsubscribe_fn`, `register_transport(fn) -> unregister_fn`, `snapshot() -> dict`, `reset()`. It also includes a full Python logging bridge (`_MessengerLogHandler`, `install_log_handler()`, `remove_log_handler()`). The *natwarth viewer protocol* section is documented at lines 239-283 — it is a spec comment block, not code — and `is_natwarth_viewer_available()` always returns `False`. The v1 event types (`server.state`, `ws.state`, `view.lifecycle`, `log.entry`) are active and wired to the Electron overlay via `transport_ws.emit_event`.
- **Verdict:** False. The "stub" claim is wrong — messenger is a production pub/sub bus. The v2 "fills that stub" claim is partially correct: v2 would fill the natwarth viewer protocol section, but it would not replace or extend the v1 event bus — it would add a second protocol on a different port (7777 vs. the MCP WS port).
- **Gap:** The natwarth viewer protocol (bidirectional `allocate`, `highlight`, `camera`, `propose_route`, `ask` → `clicked`, `typed`, `form_submit` messages on `ws://127.0.0.1:7777`) is entirely unimplemented. The v2 design says "this design fills that stub" — it would need to implement a new WS server on port 7777 with its own message-loop, distinct from the existing `transport_ws` overlay bridge.
- **Extension strategy:** Extend in-place — add `integrations/messenger_viewer.py` (or a `NatwarthViewerBridge` class in `messenger.py`) that implements the v2 viewer protocol on port 7777. Wire it as a second registered transport alongside the existing `transport_ws.emit_event`.

---

### docs.py (design name) → `docs.py` (actual, root level)

- **Claim:** DOCS.xml composer over markdown frontmatter. The precedent for XML as cross-surface format.
- **Reality:** Confirmed exactly. `DocEntry` dataclass (lines 45-65): `id`, `file`, `topic`, `priority` (reference|action|flow), `modules: list[str]`, `tags: list[str]`, `when_to_read: str`. `DocEntry.from_frontmatter(path, fm)` constructs from parsed YAML. `load_all(base_dir) -> list[DocEntry]`, `find_by_tag(tag)`, `find_by_module(module)`. `compose_docs_xml(base_dir) -> str` (lines 98-116) generates the XML index. `write_docs_xml(out_path)` writes next to EXILE.xml. The XML shape is `<docs><doc id=... file=... priority=...><topic/><when_to_read/><module name=.../><tag name=.../></doc></docs>`. This is the third XML composer alongside `exile.compose_exile_xml()` and `guides.compose_guides_xml()` — they all use `xml.sax.saxutils.escape` for safety and write to the same project directory.
- **Verdict:** Confirmed.
- **Gap:** DOCS.xml is a read-routing index, not a data surface. It is not the right precedent for Turso-backed cross-surface format — it's an at-startup cache for Claude's reading strategy. The XML composer pattern it establishes (frontmatter → XML index) is valid as a precedent, but the v2 Turso design is a write-time sync, not a read-time composition.
- **Extension strategy:** No extension needed — docs.py is stable and its role (routing index) does not change in v2.

---

## Cross-cutting findings

### Existing XML composer pattern

Three XML composers exist: `exile.compose_exile_xml()`, `guides.compose_guides_xml()`, and `docs.compose_docs_xml()`. All follow the same pattern:
- Read source data (YAML frontmatter for exile/docs, YAML config files for guides)
- Build a `list[str]` of XML lines using `xml.sax.saxutils.escape` for all user data
- Return joined string; `write_*_xml()` writes to `~/.claude/projects/<project-id>/`
- No DOM, no ElementTree — string-builder only

The pattern is consistent and working. The v2 design's "XML as cross-surface format" claim is validated by this pattern. An `.X.graph` bundle format that wraps XML would compose naturally with this precedent.

### Existing storage format

State lives in four places today:
1. `EXILE/*.md` — YAML frontmatter Markdown files for player/league/character/history. Read/written by `exile.py` and `history.py`. These are the primary source of truth.
2. `data/guides/system/*.yaml`, `data/guides/creators/*.yaml`, `data/guides/edge_taxonomy.yaml` — YAML config files read by `guides.py`. Read-only from Claude's perspective.
3. `data/systems/*.md` — frontmatter Markdown for legacy per-topic guides. Read-only.
4. `~/.claude/projects/<project-id>/*.xml` — generated XML indexes (EXILE.xml, GUIDES.xml, DOCS.xml). Write-only from the skill; read-only by Claude at session start.

There is **no SQLite, no Turso, no graph DB** — the v2 Turso backend is entirely absent from the existing code.

### Existing test patterns

Tests are in `tests/` as flat pytest modules. Patterns:
- Monkeypatching exile paths with `tmp_path` fixtures (`_temp_skill`, `_temp_exile`) — consistent across `test_goals.py`, `test_exile.py`, `test_history.py`, `test_guides.py`
- Real passive tree JSON loaded from disk (`resolvers.load_passive_tree()`) — `test_graph.py`, `test_parser.py`, `test_resolvers.py`, `test_goals.py`
- Pedro's real build URL as a verified fixture (`examples/pedro-stormweaver.txt`) — `test_parser.py`, `test_graph.py`
- No mocking of the graph layer — tests load real tree data

Tests that would break if modules are extended without care:
- `test_parser.py`: byte-exact round-trip against a real URL — adding a format-version field would break unless the test is updated
- `test_graph.py::test_build_graph_node_count`: asserts exactly 5101 nodes — fails if `build_graph` is changed to filter differently
- `test_exile.py`: 306 lines covering all frontmatter + confidence math — any schema change to `player_template()` or frontmatter field names would cascade through
- `test_history.py`: full coverage of append APIs — section key names (`leagues_played`, `goals_completed`, etc.) are asserted directly

### Naming convention for new modules

Existing convention:
- Graph layer: `graph/<role>.py` (parser, resolvers, network, allocation, stats, build_reader, build_writer)
- Infrastructure: `infra/<role>.py` (config, updater, worker)
- Integrations: `integrations/<external_system>.py` (messenger, neversink, poe2db_client, filesystem_scanner)
- Domain root: `<domain>.py` for cross-cutting modules (exile, goals, guides, history, docs, systems, creators)

New v2 modules should follow: `turso/<purpose>.py` for the DB layer, `graph/bundle_codec.py` for bundle format I/O, `infra/data_worker.py` for the ingestion worker.

---

## What the v2 architecture changes that the existing code doesn't anticipate

- **No bundle format**: there is no `.X.graph` file format, no bundle reader/writer, no format version registry. The closest analogue is the v7 URL codec in `graph/parser.py`, but it is hard-wired to one format version and one graph type.
- **No Turso / SQLite layer**: the entire Turso-backed unified store is absent. All state is YAML frontmatter on disk. The Turso `player`, `league`, `character`, `cycle`, `goal`, `event` tables are not represented anywhere in the existing schema — they need to be designed from scratch, using the frontmatter field names as the starting column set.
- **No farming session concept**: `history.py` records league-level events (leagues played, goals completed) but has no concept of a farming cycle, session duration, map timer, or per-session loot event. The `mcp_server/tools_views.py` has a `start_map_timer` tool, but there is no backing store for timer events.
- **No multi-graph routing**: every existing path through the codebase assumes `passive-tree.json` or `atlas-tree.json` as the graph source. The `graph_type IN ('farm','craft','guide')` routing the design proposes requires a graph-type discriminator at every layer: parser, resolver, build_graph, allocation, summarize, and the MCP tool layer.
- **The natwarth viewer protocol is a documented placeholder, not a stub**: implementing it requires a new WS server on port 7777, a full bidirectional message loop, and viewer-side state management (node click capture, camera sync). This is the largest net-new piece in the design.

---

## Recommendations for DOCS/contracts.md author

**What can lift directly from existing code:**

- `graph/parser.py`: `Build`, `NodeRecord`, `FLAG_WEAPON_SET`, `FLAG_SKILL_OVERRIDE` are the canonical node record schema. Use these as the Turso `node_record` row shape (`node_hash INT`, `flags INT`, `weapon_set INT?`, `skill_override INT?`).
- `exile.py`: `player_template()`, `league_template()`, `character_template()` contain the full field inventory for the Turso `player`, `league`, `character` tables — extract the frontmatter keys directly as column definitions.
- `history.py`: `append_league`, `append_goal_completed`, `append_learning_progress`, `append_case_study` function signatures define the Turso `cycle`, `goal_event`, `learning_event`, `case_study_event` row shapes. The `appended_at` field is the `ts REAL` column.
- `goals.py`: `PlayerGoal.to_dict()`, `SubGoal.to_dict()`, `LearningGoal.to_dict()`, `LeagueGoal.to_dict()` are the canonical serialization shapes — use these as Turso JSON column schemas or normalize them into rows directly.
- `guides.py`: `SystemGuide`, `CaseStudy`, `Creator`, `Edge` dataclasses define the guide catalog schema for the Turso `guide`, `case_study`, `creator`, `edge` tables.

**What needs to be invented:**

- The `.X.graph` bundle format: there is no existing schema. The DOCS/contracts.md author must define the binary/JSON envelope, the graph-type discriminator, and the version field. Suggest: JSON envelope with `{"version": 1, "graph_type": "passive_tree"|"farm"|"craft"|"guide", "payload": <type-specific>}` wrapping the existing YAML/JSON data.
- The Turso `cycle` table: the farming session concept (map timer, session duration, loot events) does not exist anywhere in the codebase. This is a net-new schema.
- The natwarth viewer protocol wire format: documented in `messenger.py` lines 251-270 as a spec comment — needs a formal JSON schema for each message type (`allocate`, `deallocate`, `highlight`, `camera`, `propose_route`, `ask`, `clicked`, `typed`, `form_submit`) with `id` (uuid) and `ts` (epoch seconds).
- The Turso migration path: there is no migration tooling, no schema versioning, and no `alembic`/`goose`-equivalent. The DOCS/contracts.md author must specify the migration strategy before any Turso code is written.
