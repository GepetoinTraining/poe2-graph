# Attributions

`poe2-graph` is built on top of public community work. This file tracks every project whose data, code, or design we depend on or learn from. Each entry names the GitHub handle, what we use, and the license under which we use it.

When we surface a new community project — even just as a reference architecture — it gets added here so the credit trail stays durable.

## Bundled forks (`tools/`)

The skill ships with four community projects as git submodules under `tools/`. Each is a fork under `GepetoinTraining/` of an upstream project so we can pin versions and apply patches without waiting on upstream. All are MIT licensed; LICENSE files are preserved per the upstream MIT terms inside each submodule.

| Submodule | Fork URL | Upstream | License | Why bundled |
|---|---|---|---|---|
| `tools/pob-poe2` | [GepetoinTraining/PathOfBuilding-PoE2](https://github.com/GepetoinTraining/PathOfBuilding-PoE2) | [PathOfBuildingCommunity/PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) | MIT | We plan to patch in a headless JSON snapshot exporter for `pob_snapshot.py` integration; upstream's PR #9505 is PoE 1-only |
| `tools/pob-poe1` | [GepetoinTraining/PathOfBuilding](https://github.com/GepetoinTraining/PathOfBuilding) | [PathOfBuildingCommunity/PathOfBuilding](https://github.com/PathOfBuildingCommunity/PathOfBuilding) | MIT | PoE 1 carry-over support; lower priority than PoE 2 fork |
| `tools/neversink-poe2` | [GepetoinTraining/NeverSink-Filter-for-PoE2](https://github.com/GepetoinTraining/NeverSink-Filter-for-PoE2) | [NeverSinkDev/NeverSink-Filter-for-PoE2](https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2) | MIT | Local access to all 7 strictness levels + 5 style packs (Cobalt/CustomSounds/DarkMode/Mythic/Zen); enables direct filter delivery by the `neversink.py` recommender |
| `tools/neversink-poe1` | [GepetoinTraining/NeverSink-Filter](https://github.com/GepetoinTraining/NeverSink-Filter) | [NeverSinkDev/NeverSink-Filter](https://github.com/NeverSinkDev/NeverSink-Filter) | MIT | PoE 1 reference + carry-over filters |

**Update cadence**: each submodule is pinned to a specific upstream commit. We fetch updates explicitly via `updater.py` (or `git submodule update --remote`), not on every checkout. Patches we apply live as branches on our forks and as PRs upstream.

**Patches in flight**:
- `tools/pob-poe2/` — headless JSON-RPC snapshot export (extending the PoE 1 PR #9505 pattern to PoE 2)

## The skill repo itself

[GepetoinTraining/poe2-graph](https://github.com/GepetoinTraining/poe2-graph) — the canonical home of this skill. `updater.py`'s `check_skill_version()` queries this repo for skill-code staleness.

## Data sources we consume

### grindinggear / poe2-skilltree-export & atlastree-export
The official GGG-published passive tree and atlas tree JSON exports. Cached locally in `data/passive-tree.json` and `data/atlas-tree.json`.
- License: per GGG's developer terms (no explicit OSS license; redistributed via the forks below)

### GepetoinTraining / poe2-skilltree-export & atlastree-export
Pedro's forks of the GGG exports. These are the actual repos our updater pulls from for refresh.
- Repos: https://github.com/GepetoinTraining/poe2-skilltree-export, https://github.com/GepetoinTraining/atlastree-export

### poe2db.tw
Community-extracted item, modifier, gem, and base data. We fetch via:
- Category pages: `https://poe2db.tw/us/<Plural_Snake_Case>` (inline `new ModsView(...)` JSON)
- Autocomplete: `https://cdn.poe2db.tw/json/autocompletecb_us.<hash>.json`
- Run by community contributors; no OSS license declared. Used courteously: 24h cache, identifying User-Agent, polite throttle.

### poe.ninja (PoE 2 endpoints)
`poe.ninja/poe2/api/` — build snapshots, currency prices, item prices. No auth, ~12 req / 5 min. Used for market signal.

## Code patterns we learn from or interoperate with

### Path-of-Tools / poe-item-parser & poe-item-display & poe-item-hover-react
Author: Petter Kaspersen (`petter@kaspersen.dev`). License: **ISC** (permissive).
- `poe-item-parser` parses ctrl-c item text from PoE 2 into a typed `Item` interface (`spirit`, `runes`, `charmSlots`, `attacksPerSecond`, etc.)
- `poe-item-display` is a React component that renders the parsed item visually
- Used: as the canonical schema reference for our `CHARACTER_*.md` item fields, and (when we build the browser artifact) as the rendering layer for item popups
- Repos: https://github.com/Path-of-Tools/poe-item-parser, https://github.com/Path-of-Tools/poe-item-display

### natwarth / poe2-skilltree
PoE 2 passive tree viewer (React + Vite + TypeScript + framer-motion).
- Hosted: https://natwarth.github.io/poe2-skilltree/
- License: **none declared at time of writing** (issue #2 open). We currently link to the hosted site only; no code copied. The future WebSocket messenger (see `messenger.py`) targets a fork of this viewer once a permissive license is in place.

### maximumstock / poe-stash-indexer
Rust reference architecture for ingesting the GGG Public Stash Tab API river (PoE 1 only; PoE 2 stash API doesn't exist yet). License: **MIT**.
- Reference only — not imported. Relevant for the day GGG ships a PoE 2 stash API and we want market-data ingestion in our connector phase.

### brather1ng / RePoE (and repoe-fork / repoe)
The canonical pipeline for converting GGG's GGPK game-data archive into structured JSON. License: **MIT**.
- Original repo dormant since 2022 (PoE 1 focused). Active fork at `repoe-fork/repoe` maintained as of 2026-05.
- Reference for the data-extraction pattern. When PoE 2 RePoE-style outputs ship, we adopt them and drop poe2db reliance.

### poe-tool-dev (org)
Umbrella for community tooling. License: **MIT** across the relevant repos.
- **`dat-schema`** — canonical TS schema for every game `.dat` file
- **`latest-patch-version`** — serverless poller that exposes the current PoE patch version at `latest.txt`. **We consume this in `updater.py` for game-version staleness checks.**
- **`passive-skill-tree-json`** — alternative tree JSON source
- **`awesome-poe`** — curated resource list (background)
- **`ggpk.discussion`** — GGPK format documentation

### Project-Path-of-Exile-Wiki / PyPoE
The Python library RePoE uses to parse GGPK files. License: **MIT**.
- Reference only — used transitively by the RePoE pipeline when/if we ever do our own extraction.

### NeverSinkDev / NeverSink-Filter-for-PoE2 (+ Filter-Precursors)
The canonical community loot filter for PoE 2. License: **MIT**.
- `NeverSink-Filter-for-PoE2` — the compiled, ready-to-use filter (2773★)
- `Filter-Precursors` — parameterized source from which the filter is compiled (the "source code" version)
- Used: this skill **does not generate item filters**. When the user wants one, we point them at NeverSink with optional strictness/personalization notes appropriate for their build. Filter generation is the spec's Phase 2 last bullet — explicitly deferred to NeverSink instead of reinvented.

### sergeyklay / poe2-mcp-server
Existing MCP server providing public-data PoE 2 lookups (currency prices, item prices, wiki search, meta builds). We are complementary, not a replacement: the future OAuth connector (Phase 4) covers the personal-account half of the surface area.

## Game data + mechanic references

The 62 systems guides at `data/systems/*.md` reference (without redistributing) the following community knowledge bases for accuracy:

- **Path of Exile 2 official wiki** (Fextralife) — mechanic descriptions, boss + ascendancy reference
- **PoE Wiki (poewiki.net)** — secondary mechanic reference
- **Maxroll.gg/poe2** — guide and mechanic deep-dives
- **Mobalytics.gg/poe-2** — patch reveal summaries, mechanic guides
- **Game8 (game8.co/path-of-exile-2)** — mechanic walkthroughs
- **Official Path of Exile 2 forums + Steam announcements** — patch notes + streamer interviews

The guides are authored from research, not transcription — facts cross-checked across multiple sources, language is original. If anything is wrong, it's our error not theirs.

## Pedro's 1% donation (crafting / farming / trade)

The 3 main guides + 31 stubs under `data/systems/crafting_*.md`, `data/systems/farming_*.md`, `data/systems/trade_*.md`, plus `crafting_guide.md` / `farming_guide.md` / `trade_guide.md` are **Pedro's 1% knowledge donation** to the skill. Each stub carries thoughtful frontmatter (mastery_levels, related_topics, prerequisites) and a scope-defining body marked `**Status: stub.**` — Pedro and Claude will expand each one across play sessions as the league progresses. The expansion path is intentional: the catalog grows by lived play, not by research-only authorship.

## Content creators (in `data/guides/creators/*.yaml`)

The skill ships with a curated catalog of 45 PoE content creators across 7 language communities. None of their content is included or redistributed — we cite by URL and depend on the creators' own channels. Each entry is a hint for Claude to point at the right creator for the right topic; absence isn't an anti-endorsement, just incomplete cataloguing. Disposition defaults to `public`; any creator can be flipped to `opted_out` (file preserved, hidden from `list_creators`).

**By language:**

- **English (26)** — Ghazzy, Mathil, Mobalytics (aggregator), Quin69, TarkeCat, BalorMage, DarthMicrotransaction, Ben_, Empyrian, ZiggyD, OneManaLeft / ConnerConverse, CaptainLance9, AnimePrincess, Fubgun, Subtractem, Pohx, Steelmage, TalkativeTri, palsteron, Esoro, Ziz / Zizaran, ds_lily, BeltonPoE, Kripparrian, MissMikkaa, Limealicious
- **Russian (4)** — pathofexilebota, Nextezy, GoodBoy_TV, KEPA_MITA
- **Portuguese-BR (5)** — Rakin, ProfessorLih, ChacalCoach, MalakaTV, Offcell
- **Chinese (4)** — moulei, POE魔法学院, 棱镜poe2lens, 流放之路官方号 (Tencent CN official)
- **Korean (3)** — Gamerbinu, Joseon Penguin, RAMYEON POE
- **Japanese (2)** — Mizarii (みざりー), Sentence (せんてんす)
- **Romanian (1)** — Octavia_O

**Representation tags** — creators carry optional `community_women` and `community_lgbtq` style_tags when the identity is publicly visible AND the surfacing is valuable for players who want creators like them. Current entries with these tags: ds_lily, AnimePrincess, MissMikkaa, Octavia_O, Limealicious (`community_women`); BalorMage (`community_lgbtq`, Pedro-flagged). Tags signal discoverability, not labels — absence is not a claim. Add a tag when a creator is publicly out about an identity AND that visibility is part of their public presentation.

Session-1 swarm (2026-05-26) surfaced the 25-creator non-English-heavy seed. Session 2 (same date) authored 14 more English-language creators against Pedro's recon doc + named misses (Ziz, ZiggyD), then a follow-up pass added 6 more (ds_lily, Belton, Kripparrian, MissMikkaa, Octavia_O, Limealicious) targeting Pedro's named adds + a representation search for women and LGBTQIA+ creators. Source recon doc: `data/research-deleteatend/poe2-graph-creator-recon.md`.

If your project / channel belongs on this list and we missed you, open an issue.

## When we add an entry

- Always GitHub handle / org name first, then project name
- Always note the license (or "none declared")
- One sentence on what we use or learn from
- Repo URL
- If unused-but-tracked-for-future, mark as "reference only"

This file is generated by humans, not the updater; do not auto-rewrite it. The updater scripts only refresh data files (see `data/manifest.json`).
