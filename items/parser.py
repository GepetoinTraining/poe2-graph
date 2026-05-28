"""parser — in-game Ctrl+C text → Item.

PoE 2 (like PoE 1) supports copying items to clipboard via Ctrl+C. The
output is a multi-section text format with `--------` separators between
sections. Sections appear in a fixed order:

    Item Class: ...
    Rarity: ...
    <name lines>
    --------
    <base stats: damage / armour / energy shield / etc.>
    --------
    Requirements: Level / Str / Dex / Int
    --------
    Sockets: ...                  (if any)
    --------
    Item Level: N
    --------
    <implicit mods>               (if any)
    --------
    <explicit mods>
    --------
    Corrupted                     (line, if corrupted)
    --------
    <note>                        (free-form, if added)

Section count varies — empty sections are omitted. Some mods have `(crafted)`
or `(fractured)` suffixes; corrupted implicits don't have a separate section.

This parser is "good enough" for v1 — it extracts:
  - rarity
  - name + base
  - item_level + quality
  - implicits + explicits (with crafted/fractured flags)
  - sockets (count only; rune/soul-core content not parsed yet)
  - corrupted flag

It does NOT:
  - look up ModTier in the poe2db catalog (call `catalog.hydrate.hydrate_item`
    after parsing to backfill family + tier)
  - parse rune/soul-core content (delegate to the catalog hydration step)
  - resolve unique-specific data

Future hardening will come from real PoE 2 in-game samples once we have them.
"""

from __future__ import annotations

import re
from typing import Optional

from catalog.base_type import BaseType, max_sockets_for_class
from items.item import Item, MAX_PREFIXES, MAX_SUFFIXES
from items.modifier import Modifier, extract_values, extract_value_ranges, to_template
from items.socket import Socket


# Section separator — game uses 8 dashes, but tolerant to more or less.
_SEPARATOR_RE = re.compile(r"^-{4,}\s*$", re.MULTILINE)

# Trailing tags on mod lines like "+1 to Level (crafted)" or "(fractured)".
_MOD_FLAG_RE = re.compile(r"\s*\(([a-z]+)\)\s*$")

# "Item Class: One Hand Maces" — extracts the class name.
_ITEM_CLASS_RE = re.compile(r"^Item Class:\s*(.+)$", re.MULTILINE)
_RARITY_RE = re.compile(r"^Rarity:\s*(\w+)$", re.MULTILINE)
_ITEM_LEVEL_RE = re.compile(r"^Item Level:\s*(\d+)$", re.MULTILINE)
_QUALITY_RE = re.compile(r"^Quality:\s*\+?(\d+)%", re.MULTILINE)
_SOCKETS_RE = re.compile(r"^Sockets:\s*(.+)$", re.MULTILINE)
_REQ_LEVEL_RE = re.compile(r"^Level:\s*(\d+)$", re.MULTILINE)
_REQ_ATTR_RE = re.compile(r"^(Str|Dex|Int):\s*(\d+)$", re.MULTILINE)
_CORRUPTED_RE = re.compile(r"^Corrupted\s*$", re.MULTILINE)
_MIRRORED_RE = re.compile(r"^Mirrored\s*$", re.MULTILINE)


# Item class strings the game emits → our internal item_class field.
# Coverage is non-exhaustive — extends as we encounter new in-game outputs.
_GAME_CLASS_MAP = {
    "One Hand Maces": "OneHandWeapon",
    "Two Hand Maces": "TwoHandWeapon",
    "One Hand Swords": "OneHandWeapon",
    "Two Hand Swords": "TwoHandWeapon",
    "One Hand Axes": "OneHandWeapon",
    "Two Hand Axes": "TwoHandWeapon",
    "Claws": "OneHandWeapon",
    "Daggers": "OneHandWeapon",
    "Rune Daggers": "OneHandWeapon",
    "Bows": "Bow",
    "Crossbows": "OneHandWeapon",
    "Spears": "OneHandWeapon",
    "Quarterstaves": "TwoHandWeapon",
    "Wands": "CasterWeapon",
    "Sceptres": "CasterWeapon",
    "Staves": "CasterWeapon",
    "Shields": "Shield",
    "Bucklers": "Buckler",
    "Foci": "Focus",
    "Quivers": "Quiver",
    "Body Armours": "BodyArmour",
    "Helmets": "Helmet",
    "Gloves": "Gloves",
    "Boots": "Boots",
    "Belts": "Belt",
    "Amulets": "Amulet",
    "Rings": "Ring",
    "Jewels": "Jewel",
}


def parse_clipboard(text: str) -> Item:
    """Parse a single in-game Ctrl+C item dump into an Item.

    Raises ValueError if the text is unrecognizable (no Rarity, no Item Class).
    """
    # Normalize line endings and strip a leading BOM. Both arise on Windows
    # clipboard pipes and would otherwise break the anchored regexes below
    # (CR survives as part of the captured line; BOM shifts column 0).
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")

    sections = _split_sections(text)
    if not sections:
        raise ValueError("no parseable sections in input")

    # ---- Section 0 (header) — item class, rarity, name, base ----
    header = sections[0]

    class_match = _ITEM_CLASS_RE.search(header)
    rarity_match = _RARITY_RE.search(header)
    if not class_match or not rarity_match:
        raise ValueError("missing Item Class or Rarity header")

    game_class = class_match.group(1).strip()
    item_class = _GAME_CLASS_MAP.get(game_class, game_class)
    rarity = rarity_match.group(1).strip().lower()

    name, base_name = _extract_name_and_base(header, rarity)

    # ---- Scan remaining sections for the standard fields ----
    full_text = "\n".join(sections)

    if (m := _ITEM_LEVEL_RE.search(full_text)):
        item_level = int(m.group(1))
    else:
        item_level = 1

    quality_match = _QUALITY_RE.search(full_text)
    quality = int(quality_match.group(1)) if quality_match else 0

    # Requirements live in their own section; scope the regex search there so a
    # stray "Str: 5" inside a mod template can't leak into the requirements.
    requirements: dict[str, int] = {}
    req_section = _find_section(sections, "Requirements:")
    if req_section is not None:
        if (m := _REQ_LEVEL_RE.search(req_section)):
            requirements["Level"] = int(m.group(1))
        for attr_match in _REQ_ATTR_RE.finditer(req_section):
            requirements[attr_match.group(1)] = int(attr_match.group(2))

    # Corrupted / Mirrored / Unidentified are single-line footer sections.
    # Match the section content exactly so a mod template that happens to
    # contain the word "Corrupted" can't trip the flag.
    section_singletons = {sec.strip() for sec in sections}
    corrupted = "Corrupted" in section_singletons
    mirrored = "Mirrored" in section_singletons
    unidentified = "Unidentified" in section_singletons

    sockets = _parse_sockets(full_text, item_class)

    # ---- Mod sections ----
    implicits, explicits = _split_implicits_and_explicits(sections, item_class)

    # Range syntax in any modifier also flags the item as unidentified — the
    # game prints `(low-high)` only when the item hasn't been ID'd.
    if not unidentified and any(m.value_ranges for m in implicits + explicits):
        unidentified = True

    # Without catalog info we can't tell prefix from suffix on parsed mods.
    # Split explicits roughly in half (favouring prefixes for odd counts),
    # bounded by the rarity caps; the catalog hydration step reclassifies
    # via ModPool.gen_type when it runs.
    max_p = MAX_PREFIXES.get(rarity, 0)
    max_s = MAX_SUFFIXES.get(rarity, 0)
    if len(explicits) > max_p + max_s:
        raise ValueError(
            f"{rarity} item has {len(explicits)} explicit mods, max is {max_p + max_s}"
        )
    n_prefix = min(max_p, (len(explicits) + 1) // 2)
    n_suffix = len(explicits) - n_prefix
    if n_suffix > max_s:
        # More suffixes than the cap → push the excess back into prefixes
        # (room exists thanks to the total check above).
        n_prefix += n_suffix - max_s
        n_suffix = max_s
    prefixes = explicits[:n_prefix]
    suffixes = explicits[n_prefix:n_prefix + n_suffix]

    base = BaseType(
        name=base_name,
        category=_category_from_class(item_class),
        item_class=item_class,
        implicits=(),
        max_sockets=max_sockets_for_class(item_class),
    )

    return Item(
        base=base,
        rarity=rarity,
        name=name,
        item_level=item_level,
        quality=quality,
        implicits=implicits,
        prefixes=prefixes,
        suffixes=suffixes,
        sockets=sockets,
        corrupted=corrupted,
        mirrored=mirrored,
        unidentified=unidentified,
        requirements=requirements,
    )


# ---- helpers ----

def _split_sections(text: str) -> list[str]:
    """Split the clipboard text on `--------` separators."""
    sections = _SEPARATOR_RE.split(text)
    return [s.strip() for s in sections if s.strip()]


def _extract_name_and_base(header: str, rarity: str) -> tuple[Optional[str], str]:
    """Extract display name + base name from the header section.

    Format:
        Item Class: ...
        Rarity: ...
        <name lines>

    For rare/unique, the first name line is the rare/unique name + second is the base.
    For magic, the line is e.g. "Glowing Driftwood Club of Tinkering" — the base is
    embedded; we use it as-is and leave name = None.
    For normal, the line IS the base; name = None.
    """
    lines = [l.strip() for l in header.splitlines() if l.strip()]
    # Drop "Item Class:" and "Rarity:" lines
    name_lines = [l for l in lines if not l.startswith(("Item Class:", "Rarity:"))]
    if not name_lines:
        return None, ""
    if rarity in ("rare", "unique") and len(name_lines) >= 2:
        return name_lines[0], name_lines[1]
    # normal/magic: just the (decorated) base on one line
    return None, name_lines[0]


def _parse_sockets(full_text: str, item_class: str) -> list[Socket]:
    """Parse the Sockets: line if present. Doesn't decode rune content yet
    (catalog hydration step handles that)."""
    match = _SOCKETS_RE.search(full_text)
    if not match:
        return []
    socket_str = match.group(1).strip()
    # PoE prints socket markers as single-letter color codes separated by
    # spaces (and dashes for links). Token-count first; only fall back to
    # alpha-char count if split returns nothing (defensive — counting each
    # alpha char in a multi-word string like "Body Rune of Iron" would
    # report 14 sockets).
    parts = socket_str.split()
    if parts:
        count = len(parts)
    else:
        count = sum(1 for c in socket_str if c.isalpha())
    return [Socket(index=i + 1) for i in range(count)]


def _split_implicits_and_explicits(
    sections: list[str], item_class: str,
) -> tuple[list[Modifier], list[Modifier]]:
    """Find the mod-bearing sections and split them.

    Heuristic: sections that contain "+" or "%" or "to" + a number are mods.
    The FIRST such section after "Item Level:" is implicits; subsequent are
    explicits.

    Returns (implicits, explicits) — both are flat lists of un-tiered Modifiers.
    """
    # Locate the section index that contains "Item Level:"
    item_level_idx = -1
    for i, sec in enumerate(sections):
        if _ITEM_LEVEL_RE.search(sec):
            item_level_idx = i
            break

    # No Item Level marker → no reliable anchor for the mod sections. Bail
    # rather than walk the whole input from section 0 (which would scan the
    # header for mod lines and misclassify "+1 Bow"-style unique name lines
    # as modifiers).
    if item_level_idx == -1:
        return [], []

    # Mod sections come after the Item Level section
    mod_sections: list[list[str]] = []
    for sec in sections[item_level_idx + 1:]:
        lines = [l.strip() for l in sec.splitlines() if l.strip()]
        # Skip non-mod sections (Corrupted, Note, etc.)
        if any(_looks_like_mod_line(l) for l in lines):
            mod_sections.append(lines)

    if not mod_sections:
        return [], []

    # Convention: implicit-bearing item classes have one implicit section.
    # Caster weapons, helms, rings, amulets, etc. typically have implicits.
    # Without poe2db lookup, we apply a heuristic: if there's >1 mod section,
    # the first is implicits; otherwise, treat the single section as explicits.
    if len(mod_sections) >= 2:
        implicit_lines = mod_sections[0]
        explicit_lines: list[str] = []
        for sec in mod_sections[1:]:
            explicit_lines.extend(sec)
    else:
        implicit_lines = []
        explicit_lines = mod_sections[0]

    return (
        [_line_to_modifier(l, is_implicit=True) for l in implicit_lines],
        [_line_to_modifier(l, is_implicit=False) for l in explicit_lines],
    )


def _looks_like_mod_line(line: str) -> bool:
    """Heuristic: a mod line typically contains a sign, a percent, or a value+'to'."""
    if "+" in line or "-" in line or "%" in line:
        return True
    if "to" in line.lower() and any(c.isdigit() for c in line):
        return True
    return False


def _line_to_modifier(line: str, is_implicit: bool) -> Modifier:
    """Convert a single mod line to a Modifier.

    Detects `(crafted)` and `(fractured)` suffixes. Family + tier are left
    unknown — the hydration step backfills via poe2db catalog lookup.
    """
    is_crafted = False
    is_fractured = False
    is_corrupted_implicit = False

    flag_match = _MOD_FLAG_RE.search(line)
    if flag_match:
        flag = flag_match.group(1).lower()
        if flag == "crafted":
            is_crafted = True
        elif flag == "fractured":
            is_fractured = True
        elif flag == "corrupted":
            is_corrupted_implicit = True
        line = line[: flag_match.start()].strip()

    value_ranges = extract_value_ranges(line)
    # Range syntax means the mod is unidentified — leave `values` empty and
    # let the owning Item.unidentified flag mark the state.
    values = [] if value_ranges else extract_values(line)
    template = to_template(line)

    return Modifier(
        family="unknown",       # populated by catalog.hydrate.hydrate_item
        tier=0,                 # populated by catalog.hydrate.hydrate_item
        values=values,
        value_ranges=value_ranges,
        template=template,
        is_implicit=is_implicit,
        is_corrupted_implicit=is_corrupted_implicit,
        is_crafted=is_crafted,
        is_fractured=is_fractured,
    )


def _find_section(sections: list[str], header_prefix: str) -> Optional[str]:
    """Return the first section whose stripped text starts with `header_prefix`.

    Used to scope regex searches to a specific section (e.g. "Requirements:")
    so a coincidental match elsewhere in the input can't leak across.
    """
    for sec in sections:
        if sec.strip().startswith(header_prefix):
            return sec
    return None


def _category_from_class(item_class: str) -> str:
    """Map an internal item_class back to a poe2db category slug.

    Used for catalog lookups. e.g. "OneHandWeapon" → ??? (poe2db has per-base
    categories like "Wands", "Sceptres", etc. — we'd need the base name to be
    precise). For v1 this is a coarse mapping; refine in v1.1.
    """
    coarse = {
        "BodyArmour": "Body_Armours",
        "Helmet": "Helmets",
        "Gloves": "Gloves",
        "Boots": "Boots",
        "Belt": "Belts",
        "Amulet": "Amulets",
        "Ring": "Rings",
        "Quiver": "Quivers",
        "Shield": "Shields",
        "Focus": "Foci",
        "Buckler": "Bucklers",
        "Bow": "Bows",
        "CasterWeapon": "Wands",       # fallback; actual base name disambiguates
    }
    return coarse.get(item_class, "Unknown")
