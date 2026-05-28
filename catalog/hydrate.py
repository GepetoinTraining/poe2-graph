"""hydrate — backfill family + tier on a parsed Item by template lookup.

The clipboard parser (items.parser) produces Items whose Modifiers have
`family = "unknown"` and `tier = 0`, because the in-game text doesn't say
which catalog tier matches. `hydrate_item` does the catalog lookup and
fills those in by matching each Modifier's template against the relevant
ModPool's templates.

Best-effort: mods that don't match the catalog are left as-is, and the
function returns a count of un-hydrated mods so callers can detect data
loss rather than discovering silent gaps later.

Requires the `Modifier` dataclass to be mutable — hydration writes the
resolved `family` + `tier` back onto the same object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from catalog.mod_pool import load_pool

if TYPE_CHECKING:
    from items.item import Item


def hydrate_item(item: "Item", *, category: Optional[str] = None) -> tuple["Item", int]:
    """Backfill family + tier on item.all_mods by template lookup against the pool.

    `item` is mutated in-place. Returns `(item, unhydrated_count)` so the
    caller can detect partial coverage:

        item, missed = hydrate_item(item)
        if missed:
            log.warning("%d mods did not match the %s catalog", missed, cat)

    A return of 0 means every mod matched; equal to `len(item.all_mods)`
    means nothing was hydrated (likely a network / cache miss — caller can
    retry later). `category` defaults to `item.base.category`; if neither is
    set the function returns immediately with 0 (nothing to attempt).
    """
    cat = category or item.base.category
    if not cat or cat == "Unknown":
        return item, 0
    try:
        pool = load_pool(cat)
    except Exception:
        # Network / cache miss — every un-resolved mod counts as un-hydrated.
        unhydrated = sum(1 for m in item.all_mods if m.family == "unknown")
        return item, unhydrated

    unhydrated = 0
    for mod in item.all_mods:
        if mod.family != "unknown" or mod.template is None:
            continue
        tier = pool.lookup_tier_by_template(mod.template)
        if tier is not None:
            mod.family = tier.family
            mod.tier = tier.tier
        else:
            unhydrated += 1
    return item, unhydrated
