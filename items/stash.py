"""stash — broader collection layer (beyond equipped items).

Parallels Inventory but holds items that AREN'T currently equipped on a
character. The player's actual stash spans many tabs; for now we model
a single flat collection.

Phase 1: minimal CRUD + base-name search. Phase 2 (when wired with trade)
will gain: tab tagging, per-tab pricing modes, listed-vs-not state.

This is intentionally thin in v1.0 — most stash operations are mediated by
the trade engagement layer (see `data/systems/trade_*.md`), not the items
package directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from items.item import Item


@dataclass
class Stash:
    """A collection of items not currently equipped.

    Items aren't ordered by slot like Inventory — they're a flat collection
    indexed only by insertion order. Listings, tab tagging, and trade-state
    overlays will come in v1.x.
    """
    items: list[Item] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    # ---- mutation ----

    def add(self, item: Item) -> None:
        self.items.append(item)

    def remove(self, item: Item) -> bool:
        try:
            self.items.remove(item)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        self.items.clear()

    # ---- queries ----

    def find_by_base(self, base_name: str) -> list[Item]:
        """All items whose base name matches (case-sensitive)."""
        return [i for i in self.items if i.base.name == base_name]

    def find_by_item_class(self, item_class: str) -> list[Item]:
        return [i for i in self.items if i.base.item_class == item_class]

    def find_corrupted(self) -> list[Item]:
        return [i for i in self.items if i.corrupted]

    def find_at_ilvl(self, min_ilvl: int) -> list[Item]:
        return [i for i in self.items if i.item_level >= min_ilvl]

    def find_with_family(self, family: str) -> list[Item]:
        """Items that carry a mod from `family` (any tier)."""
        return [i for i in self.items if any(m.family == family for m in i.all_mods)]
