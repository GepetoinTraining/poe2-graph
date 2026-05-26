---
id: updater
file: DOCS/updater.md
topic: Three-layer staleness detection + protected paths + latest-patch-version hook
priority: reference
modules: [updater]
tags: [updater, staleness, manifest, patch_version, refresh]
when_to_read: |
  User asks about updating the skill, refreshing data, what version they're on,
  whether a new game patch has dropped, or troubleshooting why some data feels
  stale. Also at session start when Claude runs `updater.report()` and
  surfaces any staleness flags to the player.
---

# Updater — three-layer staleness

## Three independent update layers

| Layer | Source | Cadence |
|---|---|---|
| Skill code | This repo on GitHub (when published) | When we ship improvements |
| Tree data | `GepetoinTraining/{poe2-skilltree, atlastree}-export` | Per game patch |
| poe2db item/mod cache | poe2db.tw inline JSON | 24h TTL |

Plus a fourth signal: upstream game version polled from `poe-tool-dev/latest-patch-version` (MIT-licensed serverless function that writes the current PoE patch to `latest.txt` every minute).

## Protected paths — never touched by updates

`EXILE/`, `PLAYER.md*`, `LEAGUE_*.md*`, `CHARACTER_*.md*`, `.env`. Player data is yours.

Declared in `data/manifest.json` under `protected_paths` — declarative, not buried in code.

## Module surface

```python
import updater

updater.report() -> StalenessReport
# Composes: skill_version vs remote, tree-data commits vs upstream,
# poe2db_cache age, upstream_game_version. Single GET for each.

updater.check_skill_version() -> SourceStatus
updater.check_data_source("passive_tree") -> SourceStatus
updater.poe2db_cache_age_days() -> float | None
updater.latest_game_version() -> str | None           # from poe-tool-dev

updater.update_data_source("passive_tree") -> bool    # git pull + refresh data.json
updater.update_skill_code() -> str                    # git pull on the skill itself
updater.invalidate_poe2db_cache() -> int              # wipe + force-refetch

updater.report()._format_report() -> str              # CLI / chat-friendly text
```

## CLI

```bash
python updater.py status              # report staleness across all layers
python updater.py update-data         # refresh tree data only
python updater.py update-skill        # git pull skill code only
python updater.py invalidate-cache    # wipe poe2db cache
python updater.py update-all          # skill + data + cache invalidate
python updater.py update-tools [--no-sync-upstream] [--only PATH,PATH]
                                      # sync bundled forks from upstream + pull submodules
```

For continuous polling during league launch (NeverSink filter refresh, etc.), see
`worker.py` — runs `update-tools` on a configurable cadence with per-tool intervals
sourced from `config.yaml`. League-launch usage:

```bash
python worker.py --watch --interval=300 --duration=72h --log=worker.log
```

## Manifest shape

`data/manifest.json` carries:

```json
{
  "skill_version": "0.1.0",
  "skill_repo": "https://github.com/GepetoinTraining/poe2-graph",
  "fetched_at": "2026-05-26",
  "game_version": "0.5 pre-launch (Return of the Ancients)",
  "data_sources": {
    "passive_tree": {
      "repo": "https://github.com/GepetoinTraining/poe2-skilltree-export",
      "last_commit": "fb64a33...",
      "fetched_at": "2026-05-26"
    },
    "atlas_tree": { ... }
  },
  "protected_paths": ["EXILE/", "PLAYER.md", "LEAGUE_*.md", "CHARACTER_*.md"]
}
```

The updater reads it before each operation; writes back updated commit refs after each pull.

## Session-start usage

```python
report = updater.report()
if report.any_stale:
    # Surface to the player; offer to refresh.
    print(updater._format_report(report))
# Stale skill version → ask user before pulling
# Stale tree data → safe to auto-refresh (no player data at risk)
# Stale poe2db cache → next fetch will refresh anyway
```

## See also

- `DOCS/poe2db.md` — the cache layer the updater wipes
- `DOCS/byte-format.md` — `parser.SUPPORTED_VERSION` should match the upstream tree-data's game version
- `ATTRIBUTIONS.md` — `poe-tool-dev/latest-patch-version` credit
