"""Gem — skill, support, and spirit gem catalog.

The gem layer mirrors ModPool's shape: a typed catalog backed by a poe2db
page, with per-class caching. PoE 2 splits gems into three classes:

  skill   — active skills you cast / attack with (Fireball, Boneshatter, ...)
  support — modify a socketed skill; one unique support per skill;
            no level scaling (fixed at cut time)
  spirit  — persistent buffs that reserve spirit (Heralds, Auras, Meta-gems)

Each gem has a primary color tied to an attribute requirement:
  red    → Strength
  green  → Dexterity
  blue   → Intelligence

Sockets enforce the +5-attribute-per-color rule. See `data/systems/skill_gems.md`
for the player-facing mechanics; this module is the typed-data surface.

The schema/loader split mirrors mod_pool / poe2db_loader:
  catalog.gem          — Gem dataclass + GemCatalog + cache + load_catalog
  catalog.gem_loader   — parse poe2db's Skill_Gems / Support_Gems / Spirit_Gems pages
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


GEM_COLORS = ("red", "green", "blue")
GEM_CLASSES = ("skill", "support", "spirit")

GEM_COLOR_TO_ATTR = {
    "red": "Str",
    "green": "Dex",
    "blue": "Int",
}

# Map gem_class → the poe2db category slug used by `integrations.poe2db_client`.
_GEM_CLASS_TO_SLUG = {
    "skill": "Skill_Gems",
    "support": "Support_Gems",
    "spirit": "Spirit_Gems",
}


@dataclass(frozen=True)
class Gem:
    """One gem entry from the poe2db catalog. Immutable schema, not a per-character instance.

    Identity: (slug, level, gem_class). For skill gems the same slug can appear
    at multiple levels (each cut step is its own row on poe2db). Support gems
    typically have one entry per unique support (tier variants get distinct
    slugs / names rather than distinct level rows).
    """
    name: str                          # display name, e.g. "Herald of Ash"
    slug: str                          # poe2db slug, e.g. "Herald_of_Ash" — canonical id
    gem_class: str                     # one of GEM_CLASSES
    color: str                         # one of GEM_COLORS
    level: int = 1                     # gem-level marker from the catalog row
    tags: frozenset[str] = field(default_factory=frozenset)
    icon_url: Optional[str] = None     # poe2db CDN url for the gem icon

    def __post_init__(self) -> None:
        if self.color not in GEM_COLORS:
            raise ValueError(f"unknown gem color {self.color!r}; expected {GEM_COLORS}")
        if self.gem_class not in GEM_CLASSES:
            raise ValueError(f"unknown gem_class {self.gem_class!r}; expected {GEM_CLASSES}")
        if self.level < 1:
            raise ValueError(f"level must be >= 1, got {self.level}")
        if not self.name:
            raise ValueError("Gem must have a name")

    @property
    def attribute(self) -> str:
        """Primary attribute required to socket this gem ('Str' / 'Dex' / 'Int')."""
        return GEM_COLOR_TO_ATTR[self.color]


@dataclass
class GemCatalog:
    """All gems for one gem-class (skill / support / spirit)."""
    gem_class: str
    gems: list[Gem] = field(default_factory=list)

    def by_slug(self, slug: str) -> Optional[Gem]:
        """Return the first gem matching `slug`, or None.

        For skill gems with multiple level rows, returns the lowest-level entry
        (relies on insertion order matching the catalog's row order).
        """
        for g in self.gems:
            if g.slug == slug:
                return g
        return None

    def all_levels_of(self, slug: str) -> list[Gem]:
        """All Gem rows sharing this slug — the full level ladder for a skill gem."""
        return [g for g in self.gems if g.slug == slug]

    def by_name(self, name: str) -> Optional[Gem]:
        """Return the first gem matching `name` (display name, not slug)."""
        for g in self.gems:
            if g.name == name:
                return g
        return None

    def by_color(self, color: str) -> list[Gem]:
        return [g for g in self.gems if g.color == color]

    def by_tag(self, tag: str) -> list[Gem]:
        return [g for g in self.gems if tag in g.tags]

    def names(self) -> set[str]:
        return {g.name for g in self.gems}

    def slugs(self) -> set[str]:
        return {g.slug for g in self.gems}


# ---- module-level cache + loader ----

_CATALOG_CACHE: dict[str, GemCatalog] = {}


def load_catalog(gem_class: str) -> GemCatalog:
    """Load (and cache) the GemCatalog for `gem_class`.

    On cache miss: fetch via integrations.poe2db_client, parse via
    catalog.gem_loader, store.
    """
    if gem_class in _CATALOG_CACHE:
        return _CATALOG_CACHE[gem_class]
    if gem_class not in _GEM_CLASS_TO_SLUG:
        raise ValueError(
            f"unknown gem_class {gem_class!r}; expected {tuple(_GEM_CLASS_TO_SLUG)}"
        )
    # Lazy imports break the catalog.gem <-> catalog.gem_loader cycle and
    # defer the integrations dependency until first network call.
    from catalog.gem_loader import catalog_from_page
    from integrations import poe2db_client
    html = poe2db_client.fetch_category_html(_GEM_CLASS_TO_SLUG[gem_class])
    catalog = catalog_from_page(gem_class, html)
    _CATALOG_CACHE[gem_class] = catalog
    return catalog


def clear_cache() -> None:
    """Drop all cached catalogs. Useful in tests or after a poe2db cache refresh."""
    _CATALOG_CACHE.clear()


def is_known_gem(name: str, gem_class: Optional[str] = None) -> bool:
    """True if `name` matches a known gem.

    Searches the given gem_class only, or all classes if gem_class is None.
    Returns False on network/parse failures (best-effort).
    """
    classes = (gem_class,) if gem_class else GEM_CLASSES
    for cls in classes:
        try:
            cat = load_catalog(cls)
        except Exception:
            continue
        if name in cat.names():
            return True
    return False
