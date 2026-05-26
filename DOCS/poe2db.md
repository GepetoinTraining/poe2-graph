---
id: poe2db
file: DOCS/poe2db.md
topic: poe2db.tw data fetcher — inline ModsView JSON pattern (no CDN), autocomplete, schema
priority: reference
modules: [poe2db_client]
tags: [poe2db, items, mods, tiers, modsview, autocomplete]
when_to_read: |
  User asks about item modifiers, mod tiers, mod weights, base item bases, mod
  families, or anything where poe2db.tw is the source of truth. Also when
  Claude needs to fetch fresh poe2db data, invalidate the cache, or
  troubleshoot the autocomplete hash.
---

# poe2db.tw client — inline ModsView JSON

## The delivery mechanism

**There is no public data CDN at `cdn.poe2db.tw`.** All `/cache2/*` paths return 403. The CDN hosts only static assets (CSS/JS/images).

The actual delivery: each category page at `https://poe2db.tw/us/{Plural_Snake_Case}` returns HTML with the full structured JSON embedded inline as `new ModsView({...giant config...});`. One HTTP GET → regex-extract → `json.loads`.

URL slugs use plural snake-case: `Amulets`, `Rings`, `Belts`, `Body_Armours`, `Helmets`, `Wands`, `Spears`, `Crossbows`, `Quivers`, `Bows`. Singular slugs 404.

## Module surface

```python
import poe2db_client as p2db

# One-shot fetch
data = p2db.fetch_category("Amulets")              # extracts ModsView JSON
mods_by_section = p2db.mods_by_section(data)        # {section: [ModEntry]}
tier_ladders = p2db.tiers_by_family(mods_by_section["normal"])
                                                    # {family_key: [tiers in order]}

# Cache-aware
html = p2db.fetch_category_html("Rings", force=False)  # 24h cache TTL
data = p2db.extract_modsview(html)

# Autocomplete (gem/item/mod names)
ac = p2db.fetch_autocomplete(lang="us")
```

## ModsView config shape

Top-level keys per category (most arrays empty for items not eligible):

`baseitem`, `config`, `normal`, `corrupted`, `desecrated`, `essence`, `perfect_essence`, plus influence sources: `elder`, `shaper`, `crusader`, `redeemer`, `hunter`, `warlord`, `veiled`, `delve`, `incursion`, `bestiary`, `synthesis`, `sentinel`, `enchant`, `warbands`, `socketable`, `bonded`, `graft_corrupted`, etc.

## Mod row shape

```
{
  Name: "of the Brute",
  Level: 60,
  ModGenerationTypeID: int,
  ModFamilyList: ["IncreasedLife"],   ← stable join key
  DropChance: 9000,                    ← raw weight
  str: "+(10–19) to maximum Life",     ← HTML stat template with value range
  mod_no: "<div ...data-tag='life'...>",
  spawn_no, fossil_no, adds_no, hover, ...
}
```

Tier ladders come from grouping rows by `ModFamilyList` (or by the trailing digit on `hover`). All tier data lives in the same inline JSON — no XHR, no modal lazy-load.

## Stat-string parsing

`p2db.parse_stat_html("+<span class='mod-value'>(10—19)</span> to maximum Life")` returns `("+# to maximum Life", 10, 19)`. Em-dash handling included (em-dashes sometimes mojibake-encoded as `â€"`).

## Autocomplete URL — hash-bumped

```
https://cdn.poe2db.tw/json/autocompletecb_us.<hash>.json
```

The hash changes per poe2db data update. Current hash lives in `poe2db_client.AUTOCOMPLETE_HASH`. When the URL 404s, bump the constant — find the new hash by inspecting `<script>` tags on `https://poe2db.tw/us/` for `autocompletecb_us.` references. Discovered via natwarth's `prepare-data.sh`.

## Caching + neighborliness

- 24h on-disk cache in `data/poe2db_cache/<Category>.html`
- Match upstream `Cache-Control: max-age=86400`
- Polite throttle: 1 req/sec is more than enough
- Identifying User-Agent: `poe2-graph/0.1 (...)`

poe2db is itself a scraper of GGG's game files. Not a ToS risk — the concern is being a load problem. Cache aggressively; identify ourselves; if something looks off they can grep their logs and reach out.

## See also

- `DOCS/build-construction.md` — `build_writer` references mod info from here for the `unique` / `hint` recommendations
- `DOCS/updater.md` — `invalidate_poe2db_cache()` wipes the cache to force refetch
