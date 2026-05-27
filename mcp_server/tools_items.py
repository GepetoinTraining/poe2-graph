"""Item + mod + gem tools.

Thin wrappers over items.parser, catalog.gem, catalog.mod_pool, and
guides.validate_intent. These are the per-call lookups Claude makes while
helping the player parse drops, evaluate crafts, or validate a guide import.
"""

from __future__ import annotations

from typing import Any, Optional

from catalog import gem as gem_module
from catalog.mod_pool import load_pool
from items import parser as item_parser

from ._serialize import to_jsonable


def parse_clipboard_item(text: str) -> dict[str, Any]:
    """Parse a Ctrl+C in-game item text dump into a structured Item.

    Returns a dict ready for the Electron item-tooltip view. Hydration of
    family/tier from the poe2db catalog is best-effort and silently skipped
    if the catalog is unreachable.
    """
    try:
        item = item_parser.parse_clipboard(text)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    # Best-effort hydration — fill in mod families + tiers from the catalog
    try:
        from catalog.hydrate import hydrate_item
        hydrate_item(item)
    except Exception:
        pass
    return {"ok": True, "item": to_jsonable(item)}


def query_gem(name: str, gem_class: Optional[str] = None) -> dict[str, Any]:
    """Look up a gem by display name across skill / support / spirit catalogs.

    Args:
      name: display name, e.g. "Fireball", "Acrimony", "Herald of Ash"
      gem_class: optional filter — "skill" | "support" | "spirit"

    Returns the matched Gem dict (or list of matches, since gem names can
    overlap across classes — Herald of Ash is in both skill and spirit).
    """
    classes = (gem_class,) if gem_class else gem_module.GEM_CLASSES
    matches: list[dict[str, Any]] = []
    for cls in classes:
        try:
            cat = gem_module.load_catalog(cls)
        except Exception as exc:
            matches.append({"gem_class": cls, "error": str(exc)})
            continue
        g = cat.by_name(name)
        if g is not None:
            matches.append({"gem_class": cls, "gem": to_jsonable(g)})
    return {"name": name, "matches": matches}


def query_mod_pool(
    category: str,
    ilvl: int,
    affix_class: Optional[str] = None,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    """Return ModTier candidates for an item category + item level.

    Args:
      category: poe2db category slug — e.g. "Amulets", "Wands", "Body_Armours"
      ilvl: the item's level — gates which tiers can roll
      affix_class: optional — "normal" | "essence" | "corruption" | ...
      limit: cap result count to avoid huge payloads (defaults to 200)
    """
    try:
        pool = load_pool(category)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "category": category}
    tiers = pool.possible_mods(ilvl=ilvl, affix_class=affix_class)
    truncated = len(tiers) > limit
    return {
        "ok": True,
        "category": category,
        "ilvl": ilvl,
        "affix_class": affix_class,
        "tier_count": len(tiers),
        "truncated": truncated,
        "tiers": [to_jsonable(t) for t in tiers[:limit]],
    }


def validate_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Run `guides.validate_intent` against a GuideIntent dict.

    The intent dict mirrors `guides.GuideIntent` fields: source,
    character_class, ascendancy, main_skill, support_gems, extra_skills,
    key_notables, key_keystones, etc.

    Returns a list of warnings (empty = clean).
    """
    import guides
    from graph import resolvers
    try:
        gi = guides.GuideIntent(**intent)
    except TypeError as exc:
        return {"ok": False, "error": f"intent shape mismatch: {exc}"}
    try:
        tree = resolvers.load_passive_tree()
    except Exception as exc:
        return {"ok": False, "error": f"tree load failed: {exc}"}
    warnings = guides.validate_intent(gi, tree)
    return {"ok": True, "warnings": warnings}
