"""mod_pool — typed catalog surface + per-category cache.

A ModPool is the catalog of all ModTiers for one poe2db category (Wands,
Amulets, Body_Armours, etc.). Construction lives in
`catalog.poe2db_loader` — this module owns the typed surface, the query
helpers, and the in-process cache that backs `load_pool`.

Hydration of parsed items lives in `catalog.hydrate`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from catalog.mod_tier import ModTier


@dataclass
class ModPool:
    """The mod catalog for a single item category, indexed by family + tier."""
    category: str                       # poe2db category slug, e.g. "Amulets"
    tiers: list[ModTier] = field(default_factory=list)

    # ---- query ----

    def possible_mods(self, ilvl: int, rarity: str = "rare", *, affix_class: Optional[str] = None) -> list[ModTier]:
        """Return tier candidates eligible for an item at this iLvl + rarity.

        Filters by min_ilvl <= ilvl AND (affix_class matches OR affix_class is None).
        Magic items have a smaller allowed pool than rares but we don't enforce
        that here — caller decides.
        """
        out = [t for t in self.tiers if t.min_ilvl <= ilvl]
        if affix_class is not None:
            out = [t for t in out if t.affix_class == affix_class]
        return out

    def by_family(self, family: str) -> list[ModTier]:
        return [t for t in self.tiers if t.family == family]

    def families(self) -> set[str]:
        return {t.family for t in self.tiers}

    def lookup_tier_by_template(
        self, template: str, *, tolerance: float = 0.0,
    ) -> Optional[ModTier]:
        """Find a ModTier whose template matches `template`.

        Templates use `#` as the value placeholder. Exact-match first; if
        tolerance > 0, also accept fuzzy matches with that fraction of edit
        distance. v1 implements exact-match only; tolerance is reserved.
        """
        for tier in self.tiers:
            if _templates_match(tier.template, template):
                return tier
        return None


# ---- module-level cache + loader ----

# Cache loaded ModPools per category to avoid re-parsing on every query.
_POOL_CACHE: dict[str, ModPool] = {}


def load_pool(category: str) -> ModPool:
    """Load (and cache) the ModPool for `category`.

    On cache miss: fetch via integrations.poe2db_client, parse, store.
    """
    if category in _POOL_CACHE:
        return _POOL_CACHE[category]
    # Lazy imports break the catalog.mod_pool <-> catalog.poe2db_loader cycle
    # and defer the integrations dependency until first network call.
    from catalog.poe2db_loader import pool_from_modsview
    from integrations import poe2db_client
    raw = poe2db_client.fetch_category(category)
    pool = pool_from_modsview(category, raw)
    _POOL_CACHE[category] = pool
    return pool


def clear_cache() -> None:
    """Drop all cached pools. Useful in tests or after a poe2db cache refresh."""
    _POOL_CACHE.clear()


def possible_mods(
    category: str, ilvl: int, rarity: str = "rare", *, affix_class: Optional[str] = None,
) -> list[ModTier]:
    """Convenience: load pool + query in one call."""
    return load_pool(category).possible_mods(ilvl, rarity, affix_class=affix_class)


# ---- template normalisation ----

def _templates_match(a: str, b: str) -> bool:
    """Compare two templates for equivalence.

    Whitespace-normalized; case-sensitive; punctuation-preserved.
    """
    return _normalize_template(a) == _normalize_template(b)


def _normalize_template(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()
