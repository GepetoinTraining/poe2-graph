"""poe2db.tw client — fetch structured item/mod data per category.

Each category page on poe2db.tw is an HTML response with the full structured
JSON embedded inline as `new ModsView({...});`. There is **no** CDN data
endpoint; cdn.poe2db.tw serves only static assets (CSS/JS/images).

URL pattern: https://poe2db.tw/us/{Plural_Snake_Case}
  e.g. Amulets, Rings, Belts, Body_Armours, Helmets, Wands, Spears, Crossbows.
  Singular slugs (Amulet, Ring) 404.

The site is itself a community scraper of GGG's game files; this client is its
natural complement. Be a good neighbor: identify ourselves in User-Agent, cache
24h to match their Cache-Control, throttle politely.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Optional  # noqa: F401  (Optional used in fetch_autocomplete)

USER_AGENT = "poe2-graph/0.1 (https://github.com/GepetoinTraining/poe2-graph; contact via repo issues)"
BASE_URL = "https://poe2db.tw/us"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "poe2db_cache"
CACHE_TTL_SECONDS = 24 * 60 * 60  # match upstream Cache-Control: max-age=86400

# poe2db ships a content-hashed autocomplete JSON at cdn.poe2db.tw/json/.
# The hash changes per poe2db data update. When the URL 404s, find the new
# hash by inspecting the script tags on https://poe2db.tw/us/ — search for
# "autocompletecb_us." in the page source and bump AUTOCOMPLETE_HASH.
# Discovered via natwarth's prepare-data.sh in poe2-skilltree.
AUTOCOMPLETE_HASH = "00e8df2683036f13"
AUTOCOMPLETE_URL_TEMPLATE = "https://cdn.poe2db.tw/json/autocompletecb_{lang}.{hash}.json"

# Match `new ModsView({...});` in the inline script. The body is JSON-shaped but
# the closing brace can be deep — we capture greedily up to the literal ");".
MODSVIEW_RE = re.compile(r"new\s+ModsView\(\s*(\{.*?\})\s*\);", re.DOTALL)

# Inner HTML cleanup for stat strings like:
#   "+<span class='mod-value'>(10—19)</span> to maximum Life"
MOD_VALUE_SPAN_RE = re.compile(
    r"<span\s+class=['\"]mod-value['\"][^>]*>([^<]+)</span>", re.IGNORECASE
)
TAG_RE = re.compile(r"<[^>]+>")
RANGE_RE = re.compile(r"\(([+-]?\d+(?:\.\d+)?)\s*[—–-]\s*([+-]?\d+(?:\.\d+)?)\)")
SINGLE_NUMBER_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)")


@dataclass
class ModEntry:
    """One row from a ModsView section. Multiple rows per family = tier ladder."""
    name: str
    level: int
    family: list[str]
    drop_chance: int
    template: str
    value_min: Optional[float]
    value_max: Optional[float]
    tags: list[str]
    raw: dict[str, Any]

    @property
    def tier_key(self) -> str:
        """Trailing digits on the hover/popup id distinguish tier order."""
        m = re.search(r"(\d+)$", self.raw.get("hover", ""))
        return m.group(1) if m else "0"


def _cache_path(category: str) -> Path:
    return CACHE_DIR / f"{category}.html"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS


def fetch_category_html(category: str, force: bool = False) -> str:
    """Fetch the raw HTML for an item category page, with on-disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(category)
    if not force and _cache_fresh(path):
        return path.read_text(encoding="utf-8")

    url = f"{BASE_URL}/{category}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    return html


def extract_modsview(html: str) -> dict[str, Any]:
    """Pull the JSON config out of `new ModsView({...});` in the page."""
    m = MODSVIEW_RE.search(html)
    if not m:
        raise ValueError("ModsView constructor not found in page — site may have changed")
    return json.loads(m.group(1))


def fetch_category(category: str, force: bool = False) -> dict[str, Any]:
    """One-shot: fetch HTML, extract ModsView config, return JSON."""
    return extract_modsview(fetch_category_html(category, force=force))


def autocomplete_url(lang: str = "us", hash_: Optional[str] = None) -> str:
    """Build the URL for poe2db's content-hashed autocomplete payload."""
    return AUTOCOMPLETE_URL_TEMPLATE.format(lang=lang, hash=hash_ or AUTOCOMPLETE_HASH)


def fetch_autocomplete(lang: str = "us", force: bool = False) -> dict[str, Any]:
    """Fetch poe2db's autocomplete JSON (gem/item/mod name resolution).

    Cached in `data/poe2db_cache/autocomplete_<lang>.json` with the same 24h
    TTL as category pages. Falls back to URL 404 if AUTOCOMPLETE_HASH is stale
    — bump the constant when that happens.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"autocomplete_{lang}.json"
    if not force and path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))

    url = autocomplete_url(lang)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://poe2db.tw/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def parse_stat_html(html_str: str) -> tuple[str, Optional[float], Optional[float]]:
    """Turn '+<span class=mod-value>(10—19)</span> to maximum Life' into
    ('+# to maximum Life', 10.0, 19.0).
    """
    cleaned = MOD_VALUE_SPAN_RE.sub(lambda m: m.group(1), html_str)
    cleaned = TAG_RE.sub("", cleaned)
    cleaned = unescape(cleaned)

    vmin: Optional[float] = None
    vmax: Optional[float] = None

    rng = RANGE_RE.search(cleaned)
    if rng:
        vmin = float(rng.group(1))
        vmax = float(rng.group(2))
        template = RANGE_RE.sub("#", cleaned, count=1)
    else:
        # single-number mod (e.g. "+5 to Spirit")
        num = SINGLE_NUMBER_RE.search(cleaned)
        if num:
            raw = num.group(1)
            v = float(raw)
            vmin = vmax = v
            prefix = raw[0] if raw[0] in "+-" else ""
            template = SINGLE_NUMBER_RE.sub(f"{prefix}#", cleaned, count=1)
        else:
            template = cleaned

    template = re.sub(r"\s+", " ", template).strip()
    return template, vmin, vmax


def coerce_mod(row: dict[str, Any]) -> ModEntry:
    template, vmin, vmax = parse_stat_html(row.get("str", ""))
    family = row.get("ModFamilyList") or []
    if isinstance(family, str):
        family = [family]
    tags_raw = row.get("mod_no") or ""
    tags = re.findall(r"data-tag=['\"]([^'\"]+)['\"]", tags_raw) if isinstance(tags_raw, str) else []
    return ModEntry(
        name=row.get("Name", ""),
        level=int(row.get("Level", 0) or 0),
        family=family,
        drop_chance=int(row.get("DropChance", 0) or 0),
        template=template,
        value_min=vmin,
        value_max=vmax,
        tags=tags,
        raw=row,
    )


def mods_by_section(modsview: dict[str, Any]) -> dict[str, list[ModEntry]]:
    """Group mods by their top-level section (normal/corrupted/essence/...).

    Returns only sections that have content; skips structural keys like
    `baseitem`, `config`, `gen`, `opt`.
    """
    skip = {"baseitem", "config", "gen", "opt"}
    out: dict[str, list[ModEntry]] = {}
    for key, value in modsview.items():
        if key in skip or not isinstance(value, list) or not value:
            continue
        out[key] = [coerce_mod(row) for row in value if isinstance(row, dict)]
    return out


def tiers_by_family(mods: list[ModEntry]) -> dict[tuple[str, ...], list[ModEntry]]:
    """Group an entry list by ModFamilyList — each group is a tier ladder."""
    out: dict[tuple[str, ...], list[ModEntry]] = {}
    for m in mods:
        key = tuple(m.family)
        out.setdefault(key, []).append(m)
    for ladder in out.values():
        ladder.sort(key=lambda m: int(m.tier_key))
    return out
