---
id: exile
file: DOCS/exile.md
topic: PLAYER/LEAGUE/CHARACTER + EXILE.xml composer + asymptotic confidence + dual-game + diff log
priority: reference
modules: [exile]
tags: [exile, player_md, league_md, character_md, confidence, dual_game, diff_log]
when_to_read: |
  User asks about their profile, the system surfaces "what do I already know,"
  Claude needs to update tag confidences after a teaching exchange, the
  filesystem scanner returns results that should land in PLAYER.md, or a new
  character/league file needs to be created. Also when Claude reads EXILE.xml
  at session start and needs to understand what it's looking at.
---

# EXILE — the per-player profile system

## File layout

```
~/.claude/projects/<project-id>/EXILE.xml   ← generated index, auto-loaded
D:/poe2-graph/EXILE/                         ← player data, in the skill
  DONE                                       ← marker once onboarded
  PLAYER.md                                  ← durable: knowledge, prefs, capacity
  PLAYER.initial.md                          ← first-synth snapshot
  PLAYER.diffs/                              ← timestamped state log
  LEAGUE_<id>.md                             ← per-league context
  CHARACTER_<slug>.md                        ← per-character + .build companion
.env                                          ← account name (gitignored)
```

Player data is sacrosanct — the updater never touches `EXILE/*`, `PLAYER.md*`, `LEAGUE_*.md`, `CHARACTER_*.md`, or `.env`.

## Three-rate-of-change discipline

- **PLAYER.md** — years. Identity, knowledge surface, playstyle prefs, capacity signals.
- **LEAGUE_<id>.md** — months. Goal, time budget, mechanics engaged, session log.
- **CHARACTER_<slug>.md** — days/weeks. Class, ascendancy, current level, build URL + .build companion, archetype tags, milestones.

Same architectural move as the v0.3 spec's "three rates of change" recognition.

## Confidence math — asymptotic toward 1.0

Every tag carries confidence in `[0, 1)`. 1.0 is unreachable.

```python
exile.bump_confidence(current, delta) -> float
# Positive delta: new = old + (1 - old) * delta  (asymptotic toward 1)
# Negative delta: new = old + old * delta         (multiplicative decay)

# Examples:
bump_confidence(0.0, 0.5)  == 0.5
bump_confidence(0.5, 0.5)  == 0.75
bump_confidence(0.75, 0.5) == 0.875
bump_confidence(0.5, -0.3) == 0.35
```

## Dual-game support

Most players play both PoE 1 and PoE 2. Tags use a hybrid namespace:

```yaml
knows:
  trade_engagement: 0.9         # game-agnostic (player constant)
  poe1:
    essence_crafting: 0.85      # PoE 1 essence crafting (the original)
    atlas_routing: 0.8
  poe2:
    spirit_management: 0.4      # PoE 2 only
    posture_under_drop: 0.4     # edge from the taxonomy
```

Rule of thumb: namespace when mechanics differ between games (essences, attack speed, ascendancies); leave at section root for player-level constants (HC tendency, trade preference, time budget).

```python
exile.update_tag(fm, "knows", "essence_crafting", 0.5, game="poe1")  # nested
exile.update_tag(fm, "knows", "trade_engagement", 0.5)                # flat
exile.get_tag(fm, "knows", "essence_crafting", game="poe1") -> 0.5
```

Character active/dormant exclusivity is **per-game** — one PoE 1 char and one PoE 2 char can both be active at once.

## Module surface

```python
# Onboarding lifecycle
exile.is_onboarded() -> bool                          # check DONE marker
exile.init_skeleton() -> dict                         # create PLAYER.md template
exile.mark_done(notes="") -> Path                     # write DONE

# Frontmatter IO
exile.read_file(path) -> (frontmatter_dict, body_str)
exile.write_file(path, fm, body)                      # auto-bumps last_updated

# Tag confidence (the bump machinery)
exile.bump_confidence(current, delta) -> float        # asymptotic
exile.update_tag(fm, section, tag, delta, game=None) -> float
exile.get_tag(fm, section, tag, game=None) -> float

# Diff log
exile.snapshot(path, label="") -> Path                # log to .diffs/
exile.diff_against_initial(path) -> str               # unified diff vs .initial
exile.diff_history(path) -> list[Path]

# Character lifecycle (per-game exclusive)
exile.create_character(slug, league_id="", game="poe2") -> Path
exile.list_characters(game=None) -> list[str]
exile.set_active_character(slug)                      # exclusive within game
exile.active_character(game=None) -> Optional[str]
exile.active_characters() -> dict[str, str]           # {game: char_id}

# League lifecycle
exile.create_league(league_id, game="poe2") -> Path
exile.list_leagues() -> list[str]

# EXILE.xml composer
exile.compose_exile_xml() -> str
exile.write_exile_xml() -> Path                       # writes to projects/EXILE.xml
exile.project_exile_xml_path() -> Path                # the canonical location
```

## Privacy boundary

Account name, real name, OAuth tokens all live in `.env` (gitignored). Never in PLAYER.md. The XML composer never includes `.env` contents.

## See also

- `ONBOARDING.md` — the 4-phase first-time flow
- `DOCS/goals.md` — `player_goals:` / `league_goals:` are stored in these files
- `DOCS/guides.md` — edge confidence in `knows.poe2.<edge>` uses the same bump math
