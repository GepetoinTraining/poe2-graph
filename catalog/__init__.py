"""catalog — reference data + queries for item and gem schemas.

The catalog layer is the schema/dictionary side: what mod tiers CAN roll on
a Wand, what implicits a Diamond Wand has, what skill / support / spirit
gems exist and what color/attribute each one needs. Immutable reference
data plus query helpers, sourced from poe2db's per-category dumps.

Distinction from the `items` package:
  items/      — per-character instance state (this specific Diamond Wand
                with these 4 rolled mods, equipped in slot Weapon1)
  catalog/    — schema/dictionary (all possible mods, gems, bases, indexed
                by family / slug / category)

Module layout:
  mod_tier.py       ModTier (schema dataclass) + AFFIX_CLASSES
  base_type.py      BaseType (item-base schema)
  mod_pool.py       ModPool (per-category mod catalog) + possible_mods queries
  poe2db_loader.py  Parse poe2db's ModsView JSON into a ModPool
  hydrate.py        Backfill family + tier on a parsed Item by template lookup
  gem.py            Gem + GemCatalog (skill / support / spirit) + load_catalog
  gem_loader.py     Parse poe2db's Skill_Gems / Support_Gems / Spirit_Gems pages

Standard imports:
  from catalog.mod_tier import ModTier, AFFIX_CLASSES
  from catalog.base_type import BaseType
  from catalog.mod_pool import ModPool, possible_mods, load_pool
  from catalog.poe2db_loader import pool_from_modsview
  from catalog.hydrate import hydrate_item
  from catalog.gem import Gem, GemCatalog, load_catalog, is_known_gem
  from catalog.gem_loader import catalog_from_page
"""
