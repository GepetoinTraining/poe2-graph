# Onboarding flow

The runbook for first-time setup of a player's profile. Once complete, a `DONE` marker in `EXILE/` signals subsequent sessions to skip onboarding and load the existing files.

## Trigger

At the start of any conversation, Claude checks `exile.is_onboarded()`. If `False`, run the flow below. If `True`, skip to session start (see SKILL.md).

## The four phases

### Phase 1 — Filesystem scan (passive, ~5 seconds)

Claude runs `filesystem_scanner.scan()` which checks known paths for:

- **Path of Building Community** (`Documents\Path of Building Community\`) → `pob_user`
- **POE Overlay / Awakened PoE Trade / POE-TradeMacro** (AppData) → `trade_overlay_user`
- **Exilence Next** → `wealth_tracker_user`
- **ChaosRecipeEnhancer** → `chaos_recipe_optimizer`
- **Custom loot filter** (`Documents\My Games\Path of Exile\*.filter`) → `filter_engagement: custom` vs `default`
- **PoB data folder** (if present) → cache the path for session-start patch-aware reads

Output: a tag list with `confidence: 0.95` per detected tool (presence is hard evidence). These pre-populate `PLAYER.md`'s `tools_installed:` field and compress the questionnaire.

Consent: scanner output is reviewed with the player before any of it lands in `PLAYER.md`.

### Phase 2 — Tailored questionnaire (HTML form artifact)

Claude generates an HTML form artifact with the following sections. Fields with detected-tool evidence are pre-filled; fields without are explicit.

**Hard constraints (always asked):**
- League mode: HC / SC
- Trade or SSF
- Time budget: racing / dedicated / standard / casual
- Goal for current league (one sentence)

**PoE history (compressed when tools detected):**
- When did you start? (rough year, decade)
- Have you played PoE 2 yet?
- Default game: PoE 1 / PoE 2 / both

**Trigger questions (generated from scan):**
- If POE Overlay detected: "Do you use it for price-checking, build comparing, or both?"
- If PoB detected: "Do you typically build your own characters or follow guides?"
- If no PoB: "Have you used a build planner before? Which one?"

**Privacy:**
- Account name → stored in `.env` only, never in PLAYER.md. Player enters it here, the artifact emits a `.env` snippet to copy.

Form submits → JSON → Claude converts to YAML frontmatter for `PLAYER.md`.

### Phase 3 — Artifact requests

Claude asks the player to share:
1. **Account profile page screenshot** (identity, history, character roster)
2. **Standard currency stash** (economic posture — **scan for chase categoricals first: Mirror, Mageblood, sets of unique fragments. Then quantities.**)
3. **One best-equipped character's full loadout** (depth, archetype, crafting tier)
4. **One or two other characters with different archetypes** (range vs loyalty)
5. **Atlas tree screenshot** (endgame content preference)
6. **Current PoE 2 character if any** (this league's plan)

Each artifact emits structured tags into `PLAYER.md` / `CHARACTER_<id>.md`. Tags carry confidences calibrated from sample count (see SKILL.md confidence schema).

### Phase 4 — Synthesize & confirm

Claude composes the draft `PLAYER.md` from phases 1-3, shows it to the player, accepts edits, then:
1. `snapshot(PLAYER.md, "initial")` — captures the initial state
2. `mark_done()` — writes `EXILE/DONE`
3. `write_exile_xml()` — composes `~/.claude/projects/.../EXILE.xml`

Onboarding complete.

## Confidence calibration rules

Tags carry confidences in `[0, 1)`, with `1.0` unreachable (see `exile.bump_confidence`).

| Evidence type | Initial confidence |
|---|---|
| Filesystem tool present | 0.95 |
| Single-character archetype | 0.40 |
| Two characters confirming same archetype | 0.65 |
| Three+ characters same archetype | 0.85 |
| Player explicitly confirms in questionnaire | 0.85 |
| Player explicitly denies | bump current down by `-0.5` |
| Inferred from item modifiers | 0.30 |

Session-end reflection: at the end of each planning conversation, Claude reviews observations and bumps relevant tag confidences via `exile.update_tag(fm, section, tag, delta)`. Then `snapshot(PLAYER.md, "session_<date>")` and recompose XML.

## Re-onboarding triggers

The DONE marker is sticky, but these events warrant a partial re-onboarding:
- New league starts → `create_league(new_id)` + ask goal questions
- New character starts → `create_character(slug)` + 3-4 character-specific questions
- Player explicitly requests: "Update my profile" / "I've changed how I play"

In each case, run only the relevant subset of phases — not the full flow.

## Multi-character active/dormant — per game

Exclusivity is **per-game**, not global. Most players play both PoE 1 and PoE 2 in parallel; the system supports one `active` character in each game simultaneously. `exile.set_active_character(cid)` flips only same-game characters to dormant — other-game characters are untouched.

```python
exile.set_active_character("storm_main")   # poe2 active
exile.set_active_character("necro_main")   # poe1 active; storm_main still active
exile.active_character(game="poe2")        # -> "storm_main"
exile.active_character(game="poe1")        # -> "necro_main"
exile.active_characters()                   # -> {"poe2": "storm_main", "poe1": "necro_main"}
exile.list_characters(game="poe2")          # -> ["storm_main", "storm_alt"]
```

The active character's `build_file` is the live `.build` Claude edits when extending. Dormant characters keep their build files frozen.

## Tag namespacing — game-agnostic vs game-specific

Tags use a hybrid convention in `PLAYER.md`:

```yaml
knows:
  trade_engagement: 0.9         # game-agnostic — at section root
  poe1:
    essence_crafting: 0.85      # PoE 1 essence crafting (the original)
    atlas_routing: 0.8
  poe2:
    spirit_management: 0.4      # PoE 2 only — no PoE 1 equivalent
    runeforging: 0.0
prefers:
  hardcore: 0.6                 # player-wide tendency
  poe1:
    necromancer: 0.85
  poe2:
    caster: 0.7
```

**Rule of thumb**: if a concept exists with materially different mechanics in each game (essence crafting, attack speed mechanics, ascendancy choices) → namespace it. If it's a player-level constant (trade tendency, HC instinct, time budget) → leave it at the section root.

Update tags via `exile.update_tag(fm, section, tag, delta, game="poe2")`. Omit `game=` for game-agnostic. The composer renders these as `<tag section="knows" game="poe2" name="spirit_management" .../>` for joining against game-specific data graphs.

## File locations

- **Skill-local data**: `D:\poe2-graph\EXILE\` (PLAYER.md, LEAGUE_*.md, CHARACTER_*.md, diff logs, DONE)
- **Project-level index**: `~\.claude\projects\D--poe2-graph\EXILE.xml` (generated, never hand-edited)
- **Sensitive**: `D:\poe2-graph\.env` (gitignored; account name + OAuth scopes when added)

The split is intentional: data is git-aware (sits with the skill, can move with it), the XML is Claude-aware (sits in projects, auto-loaded into context).
