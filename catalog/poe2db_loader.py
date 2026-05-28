"""poe2db_loader — parse poe2db's ModsView JSON into a ModPool.

poe2db ships its raw mod data as a per-category JSON dump (see
`data/reference_poe2db.md` for the shape). This module owns the messy bit:
strip HTML spans, unwrap `[Link|Text]` syntax, extract value ranges,
synthesise a template-with-# from a rendered string.

The output is a fully-built ModPool. Callers use `pool_from_modsview` to
go from raw JSON → typed catalog in one step; `catalog.mod_pool.load_pool`
wraps this together with the integrations/poe2db_client cache.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Optional

from catalog.mod_pool import ModPool
from catalog.mod_tier import ModTier


# Range syntax in poe2db's `str` field: optional outer sign + paren-wrapped
# bounds. The outer sign (when `-`) is absorbed into both bounds so the
# stored ranges carry the full numeric sign — that way `aggregate_stats`
# and tier-template comparisons all agree on the math. A `+` outer sign is
# preserved in the template instead so `+#` renders correctly.
_VALUE_RANGE_RE = re.compile(
    r"(?P<outer>[-+]?)\(\s*"
    r"(?P<lo>[-+]?\d+(?:\.\d+)?)\s*"
    r"[—–-]\s*"
    r"(?P<hi>[-+]?\d+(?:\.\d+)?)"
    r"\s*\)"
)


def pool_from_modsview(category: str, modsview_json: dict) -> ModPool:
    """Build a ModPool from a poe2db_client ModsView JSON.

    ModsView shape (per `data/reference_poe2db.md`):
      {
        "baseitem": [...],
        "normal": [...],           # standard mods (prefixes + suffixes)
        "corrupted": [...],        # corruption-only mods
        "essence": [...],          # essence-guaranteed mods
        "elder": [...], "shaper": [...], ...  # influence mods (PoE 1; may not apply to PoE 2)
        ...
      }

    Each entry in a mod-bearing list has shape:
      {
        "Name": "IncreasedLife1",
        "Level": 60,
        "ModGenerationTypeID": 1,   # 1 = prefix, 2 = suffix typically
        "ModFamilyList": "IncreasedLife",
        "DropChance": 1000,
        "str": "+(110—129) to maximum [Life]",
        ...
      }
    """
    tiers: list[ModTier] = []

    for affix_bucket, entries in modsview_json.items():
        if affix_bucket == "baseitem" or affix_bucket == "config":
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            tier = _entry_to_modtier(entry, affix_bucket)
            if tier is not None:
                tiers.append(tier)

    return ModPool(category=category, tiers=tiers)


# ---- HTML / link-bracket cleanup ----

class _HTMLStripper(HTMLParser):
    """Strip HTML tags from poe2db's `str` field, which contains spans like
    `<span class='mod-value'>+(110—129)</span> to maximum [Life]`."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def _strip_html(s: str) -> str:
    parser = _HTMLStripper()
    parser.feed(s)
    # html.unescape covers named (&amp;) + numeric (&#39;) + hex (&#xA0;) refs
    # that HTMLParser doesn't decode inside attribute or untagged text.
    return html.unescape(parser.get_text())


def _strip_link_brackets(s: str) -> str:
    """Remove poe2db's [Foo] link syntax — they wrap referenced game terms."""
    return re.sub(r"\[([^\]|]+(?:\|([^\]]+))?)\]", lambda m: m.group(2) or m.group(1), s)


# ---- entry → ModTier ----

def _entry_to_modtier(entry: dict, affix_bucket: str) -> Optional[ModTier]:
    """Convert one poe2db mod entry to a ModTier. None if entry is malformed."""
    family = entry.get("ModFamilyList") or "unknown"
    raw_str = entry.get("str") or ""
    if not raw_str:
        return None

    # Strip HTML + link brackets, then extract value ranges + build template
    text = _strip_link_brackets(_strip_html(raw_str)).strip()
    ranges: list[tuple[float, float]] = []
    template_parts: list[str] = []
    last_end = 0
    for m in _VALUE_RANGE_RE.finditer(text):
        lo = float(m.group("lo"))
        hi = float(m.group("hi"))
        outer = m.group("outer")
        if outer == "-":
            # Absorb the outer minus into the bounds — keeps the sign on the
            # stored data so aggregate_stats sums correctly. Template drops it.
            lo, hi = -lo, -hi
        ranges.append((lo, hi))
        template_parts.append(text[last_end:m.start()])
        # Preserve a leading `+` in the template so `+# to maximum Life` renders
        # with the sign; the `-` case absorbed it into the bounds above.
        template_parts.append("+#" if outer == "+" else "#")
        last_end = m.end()
    template_parts.append(text[last_end:])
    template = "".join(template_parts).strip()

    # Single-value fallback: when no `(low-high)` ranges were found, the entry
    # may be a fixed-value mod (always rolls the same number). Replace bare
    # numerics with `#` only if the template has a stat-shape signal (sign,
    # percentage, or "X to Y" structure) — without that signal, the digits
    # are likely fixed mechanical text ("Gain 1 charge") that shouldn't
    # become a placeholder.
    if "#" not in template and _looks_like_stat_template(template):
        single_value_re = re.compile(r"[-+]?\d+(?:\.\d+)?")
        new_template_parts: list[str] = []
        new_ranges: list[tuple[float, float]] = []
        last_end = 0
        for m in single_value_re.finditer(template):
            v = float(m.group(0))
            new_ranges.append((v, v))
            new_template_parts.append(template[last_end:m.start()])
            new_template_parts.append("#")
            last_end = m.end()
        if new_ranges:
            new_template_parts.append(template[last_end:])
            template = "".join(new_template_parts).strip()
            ranges = new_ranges

    # Tier number: poe2db doesn't ship an explicit tier field, so we infer
    # from the trailing digits of `Name` (`IncreasedLife10` → 10). Names
    # without trailing digits (`AddedFireDamageFlat1H` — the `1H` is a
    # one-hand suffix, not a tier) get tier=0 as a sentinel for "unknown"
    # rather than colliding with real T1.
    name = entry.get("Name") or ""
    tier_match = re.search(r"(\d+)$", name)
    tier_num = int(tier_match.group(1)) if tier_match else 0

    # `or 1` would coerce a legitimate Level=0 to 1; use is-None instead so
    # baseline mods (Level=0 / any iLvl) survive correctly.
    level_raw = entry.get("Level")
    min_ilvl = int(level_raw) if level_raw is not None else 1
    weight = int(entry.get("DropChance") or 0)

    # Affix class mapping
    affix_class_map = {
        "normal": "normal",
        "corrupted": "corruption",
        "essence": "essence",
        "perfect_essence": "essence",
        "desecrated": "normal",   # Well of Souls / bones — bucket as normal-ish for v1
        "enchant": "implicit_corrupted",
        "veiled": "normal",
        "synthesis": "normal",
    }
    affix_class = affix_class_map.get(affix_bucket, "normal")

    # ModGenerationTypeID: 1 = prefix, 2 = suffix per poe2db. Coerce via int()
    # so float 1.0 from any upstream JSON variance still classifies correctly.
    gen_type_raw = entry.get("ModGenerationTypeID")
    try:
        is_prefix = int(gen_type_raw) == 1
    except (TypeError, ValueError):
        is_prefix = True  # safe default; rares can place either type

    if not template:
        return None

    return ModTier(
        family=family,
        tier=tier_num,
        template=template,
        value_ranges=tuple(ranges) or ((0.0, 0.0),),
        min_ilvl=min_ilvl,
        weight=weight,
        is_prefix=is_prefix,
        affix_class=affix_class,
    )


def _looks_like_stat_template(template: str) -> bool:
    """True if `template` carries a stat-shape signal (`+`/`-`/`%`/` to `).

    Used to gate the single-value fallback so fixed mechanical numbers in
    flavour-text templates ("Gain 1 charge") don't get turned into `#`
    placeholders and collide with unrelated tier templates.
    """
    if "+" in template or "%" in template:
        return True
    if " to " in template.lower():
        return True
    return False
