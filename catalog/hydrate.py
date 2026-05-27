"""hydrate — backfill family + tier on a parsed Item by template lookup.

The clipboard parser (items.parser) produces Items whose Modifiers have
`family = "unknown"` and `tier = 0`, because the in-game text doesn't say
which catalog tier matches. `hydrate_item` does the catalog lookup and
fills those in by matching each Modifier's template against the relevant
ModPool's templates.

Best-effort: mods that don't match the catalog are left as-is. Callers can
detect un-hydrated mods via `mod.family == "unknown"`.
"""

from __future__ import annotations

from typing import Optional

from catalog.mod_pool import load_pool


def hydrate_item(item, *, category: Optional[str] = None) -> None:
    """Backfill family + tier on item.all_mods by template lookup against the pool.

    `item` is mutated in-place. `category` defaults to item.base.category.
    Mods that don't match the catalog are left as-is (family = "unknown",
    tier = 0). Caller can detect un-hydrated mods via `mod.family == "unknown"`.
    """
    cat = category or item.base.category
    if not cat or cat == "Unknown":
        return
    try:
        pool = load_pool(cat)
    except Exception:
        # Network / cache miss — bail silently. Caller can retry later.
        return

    for mod in item.all_mods:
        if mod.family != "unknown" or mod.template is None:
            continue
        tier = pool.lookup_tier_by_template(mod.template)
        if tier is not None:
            mod.family = tier.family
            mod.tier = tier.tier
