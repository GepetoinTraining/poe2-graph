"""ModTier — the schema-layer mod template.

A ModTier is one entry in the catalog: the template text, value ranges per
stat, the family it belongs to, what iLvl gates it, raw weight for
probability calc, prefix/suffix bucket.

Family names mirror poe2db's `ModFamilyList` verbatim — `IncreasedLife`,
`IncreasedLifeAndMana`, `AddedFireDamageFlat`, etc. This is the join key
between a rolled `items.Modifier` and the ModTier catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Affix-bucket discriminator. Tracks how the mod was placed on the item.
AFFIX_CLASSES = (
    "normal",            # naturally rolled prefix/suffix on rare item
    "essence",           # essence-guaranteed mod
    "omen_directed",     # omen-modified outcome
    "fracture_locked",   # locked by FracturingOrb (subset of normal)
    "bench",             # crafted via well-of-souls / bench
    "corruption",        # added by Vaal Orb corruption
    "implicit_base",     # base implicit (every Diamond Wand has this)
    "implicit_corrupted", # corrupted implicit (replaces or adds via Vaal)
    "soulcore_or_rune",  # socketed via rune or soul core
    "unique",            # baked into a unique item
)


@dataclass(frozen=True)
class ModTier:
    """One mod tier from the catalog. Immutable schema, not a per-item instance.

    Identity: (family, tier). Multiple ModTiers per family form the tier ladder
    — T1 (best, highest min_ilvl) through T9 (cheapest, lowest min_ilvl).
    """
    family: str                          # e.g. "IncreasedLife" — mirrors poe2db ModFamilyList
    tier: int                            # 1 = top, ascending = cheaper
    template: str                        # e.g. "+# to maximum Life" — # marks each value slot
    value_ranges: tuple[tuple[float, float], ...]  # one (min, max) per # in template
    min_ilvl: int                        # required item level for this tier to roll
    weight: int = 0                      # raw drop weight from poe2db; 0 = unknown
    is_prefix: bool = True               # else suffix
    tags: frozenset[str] = field(default_factory=frozenset)
    affix_class: str = "normal"          # one of AFFIX_CLASSES

    def __post_init__(self) -> None:
        if self.affix_class not in AFFIX_CLASSES:
            raise ValueError(f"unknown affix_class {self.affix_class!r}; expected {AFFIX_CLASSES}")
        if self.tier < 1:
            raise ValueError(f"tier must be >= 1, got {self.tier}")

    @property
    def value_slots(self) -> int:
        """How many value slots in the template (`#` count)."""
        return self.template.count("#")
