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

import re
from html.parser import HTMLParser
from typing import Optional

from catalog.mod_pool import ModPool
from catalog.mod_tier import ModTier


_VALUE_RANGE_RE = re.compile(r"\(?(-?\d+(?:\.\d+)?)\s*[—–-]\s*(-?\d+(?:\.\d+)?)\)?")


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
    return parser.get_text()


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
    ranges = []
    template_parts = []
    last_end = 0
    for m in _VALUE_RANGE_RE.finditer(text):
        lo, hi = float(m.group(1)), float(m.group(2))
        ranges.append((lo, hi))
        template_parts.append(text[last_end:m.start()])
        template_parts.append("#")
        last_end = m.end()
    template_parts.append(text[last_end:])
    template = "".join(template_parts).strip()

    # Also catch single-value templates like "+# to maximum Life" (no range
    # because both ends are the same): replace bare numbers with '#'.
    if "#" not in template:
        single_value_re = re.compile(r"[-+]?\d+(?:\.\d+)?")
        new_template_parts = []
        new_ranges = []
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

    # Heuristic for tier number: trailing digit in Name field ("IncreasedLife1" → tier 9 [worst],
    # "IncreasedLife9" → tier 1 [best]? Or opposite? poe2db convention is ascending = better
    # in some places, descending in others. For v1 we use the trailing digit directly as the
    # tier and let the catalog be the source of truth.
    name = entry.get("Name") or ""
    tier_match = re.search(r"(\d+)$", name)
    tier_num = int(tier_match.group(1)) if tier_match else 1

    min_ilvl = int(entry.get("Level") or 1)
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

    # Prefix/suffix: ModGenerationTypeID is 1 = prefix, 2 = suffix per poe2db convention
    gen_type = entry.get("ModGenerationTypeID")
    is_prefix = (gen_type == 1) if isinstance(gen_type, int) else True

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
