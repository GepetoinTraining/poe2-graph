"""Inventory — the per-character equipped-items state.

Parallels `graph.allocation.Allocation` for the passive tree:
  Allocation : passive tree nodes :: Inventory : equipped items.

Lives in `CHARACTER_*.md` frontmatter under an `inventory:` block (added in
v1.1 when we wire the serialization round-trip).

PoE 2 equipment slots — 11 main equipment slots plus weapon-set 2:
  Helmet, BodyArmour, Gloves, Boots
  Belt, Amulet, Ring1, Ring2
  Weapon1, Offhand1                # primary weapon set
  Weapon2, Offhand2                # secondary weapon set (dual-spec)
  Quiver (offhand variant for bows — Widowhail pattern)

Flask slots and the inventory grid itself are NOT modeled here — those
aren't equipment-stat-contributing slots in the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from items.item import Item


# Canonical slot ids. Match GGG's BuildPlanner naming where possible.
SLOT_IDS = (
    "Helmet",
    "BodyArmour",
    "Gloves",
    "Boots",
    "Belt",
    "Amulet",
    "Ring1",
    "Ring2",
    "Weapon1",
    "Offhand1",
    "Weapon2",
    "Offhand2",
    # PoE 2 doesn't add new equipment slots beyond these in 0.5
)

# Map slot → allowed item_class values. Used by Inventory.equip() validation.
SLOT_ALLOWED_CLASSES = {
    "Helmet": {"Helmet"},
    "BodyArmour": {"BodyArmour"},
    "Gloves": {"Gloves"},
    "Boots": {"Boots"},
    "Belt": {"Belt"},
    "Amulet": {"Amulet"},
    "Ring1": {"Ring"},
    "Ring2": {"Ring"},
    "Weapon1": {"OneHandWeapon", "TwoHandWeapon", "CasterWeapon", "Bow"},
    "Weapon2": {"OneHandWeapon", "TwoHandWeapon", "CasterWeapon", "Bow"},
    "Offhand1": {"Shield", "Focus", "Quiver", "Buckler", "OneHandWeapon", "CasterWeapon"},
    "Offhand2": {"Shield", "Focus", "Quiver", "Buckler", "OneHandWeapon", "CasterWeapon"},
}


@dataclass
class Inventory:
    """The character's equipped-item state. Slot id → Item.

    Use `equip(slot, item)` to place; `unequip(slot)` to remove. Stats roll
    up via `aggregate_stats()` which sums each equipped item's contribution.
    """
    items: dict[str, Item] = field(default_factory=dict)

    def __contains__(self, slot: str) -> bool:
        return slot in self.items

    def __getitem__(self, slot: str) -> Item:
        return self.items[slot]

    def __iter__(self):
        return iter(self.items.items())

    # ---- mutation ----

    def equip(self, slot: str, item: Item, *, validate: bool = True) -> None:
        """Place `item` in `slot`. Replaces any existing item without warning.

        Raises ValueError if slot is unknown or (when validate=True) if the
        item's class doesn't fit the slot.
        """
        if slot not in SLOT_IDS:
            raise ValueError(f"unknown slot {slot!r}; expected one of {SLOT_IDS}")
        if validate:
            allowed = SLOT_ALLOWED_CLASSES.get(slot)
            if allowed is not None and item.base.item_class not in allowed:
                raise ValueError(
                    f"item class {item.base.item_class!r} doesn't fit slot {slot!r} "
                    f"(allowed: {sorted(allowed)})"
                )
        self.items[slot] = item

    def unequip(self, slot: str) -> Optional[Item]:
        """Remove the item from `slot`, returning it (or None if empty)."""
        return self.items.pop(slot, None)

    def clear(self) -> None:
        self.items.clear()

    # ---- read ----

    def slots_filled(self) -> set[str]:
        return set(self.items.keys())

    def slots_empty(self) -> set[str]:
        return set(SLOT_IDS) - self.slots_filled()

    def weapon_set(self, set_number: int) -> tuple[Optional[Item], Optional[Item]]:
        """Return (main_hand, off_hand) for weapon set 1 or 2."""
        if set_number not in (1, 2):
            raise ValueError(f"weapon set must be 1 or 2, got {set_number}")
        return (self.items.get(f"Weapon{set_number}"), self.items.get(f"Offhand{set_number}"))

    # ---- aggregation ----

    def aggregate_stats(self) -> dict[str, float]:
        """Sum equipped items' mod tables. Same shape as Item.aggregate_stats().

        Cross-item totals are summed — e.g. life from chest + life from helm
        end up in the same `+# to maximum Life` bucket.
        """
        out: dict[str, float] = {}
        for item in self.items.values():
            for key, value in item.aggregate_stats().items():
                out[key] = out.get(key, 0.0) + value
        return out

    # ---- validation ----

    def validate_requirements(
        self, character_level: int, attrs: dict[str, int],
    ) -> list[str]:
        """Check each equipped item's `requirements` against character state.

        `attrs` is {"Str": ..., "Dex": ..., "Int": ...} (post-allocation).

        Returns a list of unmet-requirement messages (empty = all good).
        """
        warnings: list[str] = []
        for slot, item in self.items.items():
            for req, needed in item.requirements.items():
                if req == "Level":
                    if character_level < needed:
                        warnings.append(
                            f"{slot} ({item.base.name}): needs Level {needed}, char is {character_level}"
                        )
                elif req in ("Str", "Dex", "Int"):
                    if attrs.get(req, 0) < needed:
                        warnings.append(
                            f"{slot} ({item.base.name}): needs {req} {needed}, "
                            f"char has {attrs.get(req, 0)}"
                        )
                # Unknown requirement types are skipped silently
        return warnings
