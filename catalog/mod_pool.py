"""mod_pool — typed catalog surface + per-category cache.

A ModPool is the catalog of all ModTiers for one poe2db category (Wands,
Amulets, Body_Armours, etc.). Construction lives in
`catalog.poe2db_loader` — this module owns the typed surface, the query
helpers, and the in-process cache that backs `load_pool`.

Hydration of parsed items lives in `catalog.hydrate`.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Optional

from catalog.mod_tier import ModTier


@dataclass
class ModPool:
    """The mod catalog for a single item category, indexed by family + tier."""
    category: str                       # poe2db category slug, e.g. "Amulets"
    tiers: list[ModTier] = field(default_factory=list)

    # ---- query ----

    def possible_mods(
        self,
        ilvl: int,
        rarity: str = "rare",
        *,
        affix_class: Optional[str] = None,
        include_implicit: bool = False,
        include_corruption: bool = False,
        include_unique: bool = False,
    ) -> list[ModTier]:
        """Return tier candidates eligible for an item at this iLvl + rarity.

        Filters by `min_ilvl <= ilvl`. When `affix_class` is None (the common
        case — "what could roll on this rare?") implicit-only, corruption-only,
        and unique-only affix classes are excluded by default so the result
        reflects only mods a standard craft could actually produce. Set the
        `include_*` flags to opt those back in.

        Magic items have a smaller allowed pool than rares but we don't enforce
        that here — caller decides.
        """
        out = [t for t in self.tiers if t.min_ilvl <= ilvl]
        if affix_class is not None:
            return [t for t in out if t.affix_class == affix_class]
        excluded: set[str] = set()
        if not include_implicit:
            excluded |= {"implicit_base", "implicit_corrupted"}
        if not include_corruption:
            excluded.add("corruption")
        if not include_unique:
            excluded.add("unique")
        if excluded:
            out = [t for t in out if t.affix_class not in excluded]
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

# Cache loaded ModPools per category. Lock serializes first-miss fetches so
# concurrent callers don't double-parse the same poe2db response; hits read
# the dict outside the lock (CPython dict reads are atomic).
_POOL_CACHE: dict[str, ModPool] = {}
_POOL_LOCK = threading.Lock()


def load_pool(category: str) -> ModPool:
    """Load (and cache) the ModPool for `category`.

    On cache miss: fetch via integrations.poe2db_client, parse, store.
    Thread-safe — concurrent first-misses serialize on `_POOL_LOCK`.
    """
    cached = _POOL_CACHE.get(category)
    if cached is not None:
        return cached
    with _POOL_LOCK:
        cached = _POOL_CACHE.get(category)
        if cached is not None:
            return cached
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
    with _POOL_LOCK:
        _POOL_CACHE.clear()


def possible_mods(
    category: str,
    ilvl: int,
    rarity: str = "rare",
    *,
    affix_class: Optional[str] = None,
    include_implicit: bool = False,
    include_corruption: bool = False,
    include_unique: bool = False,
) -> list[ModTier]:
    """Convenience: load pool + query in one call."""
    return load_pool(category).possible_mods(
        ilvl,
        rarity,
        affix_class=affix_class,
        include_implicit=include_implicit,
        include_corruption=include_corruption,
        include_unique=include_unique,
    )


# ---- template normalisation ----

def _templates_match(a: str, b: str) -> bool:
    """Compare two templates for equivalence.

    Whitespace-normalized; case-sensitive; punctuation-preserved.
    """
    return _normalize_template(a) == _normalize_template(b)


def _normalize_template(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()
