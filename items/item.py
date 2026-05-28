"""Item — the instance layer.

An Item is BaseType + rolled Modifiers + sockets + crafting state. This is
what the player picks up, equips, identifies, sells, crafts on. One Item per
row in the player's stash.

Rarity constraints:
  normal  → 0 prefixes + 0 suffixes (only implicits)
  magic   → up to 1 prefix + 1 suffix (max 2 explicits)
  rare    → up to 3 prefixes + 3 suffixes (max 6 explicits)
  unique  → fixed mod set, doesn't follow prefix/suffix rules

Corrupted items can no longer be modified by most currency (Divine, Exalt,
Chaos all refuse). Corruption is one-way; uncorrupting is impossible.

Implicits: base implicits live in BaseType. When the item is corrupted
(Vaal Orb), a corrupted implicit may be added or replace an existing implicit
— that's tracked in `Modifier.is_corrupted_implicit`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from catalog.base_type import BaseType
from items.modifier import Modifier
from items.socket import Socket, SocketContent


RARITIES = ("normal", "magic", "rare", "unique")

# Max affix counts per rarity. Implicits don't count against these.
MAX_PREFIXES = {"normal": 0, "magic": 1, "rare": 3, "unique": 6}  # uniques are fixed; 6 is a safe ceiling
MAX_SUFFIXES = {"normal": 0, "magic": 1, "rare": 3, "unique": 6}


@dataclass
class Item:
    """An instantiated item — one row in the player's stash or inventory.

    `base` is the BaseType (schema); the rest is mutable instance state.
    """
    base: BaseType
    rarity: str                         # one of RARITIES
    name: Optional[str] = None          # rare display name OR unique name
    item_level: int = 1
    quality: int = 0                    # 0-20%, modifies relevant stats

    # Modifiers split by affix bucket so MAX_PREFIXES / MAX_SUFFIXES can be enforced.
    # Implicits include base implicits PLUS corrupted implicits, all in one list.
    implicits: list[Modifier] = field(default_factory=list)
    prefixes: list[Modifier] = field(default_factory=list)
    suffixes: list[Modifier] = field(default_factory=list)

    sockets: list[Socket] = field(default_factory=list)

    # Crafting state
    corrupted: bool = False
    mirrored: bool = False              # the item is itself a Mirror copy of another
    unidentified: bool = False          # explicit mods present as roll-ranges, not scalars

    # Inferred + free-form
    requirements: dict[str, int] = field(default_factory=dict)  # {"Level": 78, "Int": 320, ...}
    note: Optional[str] = None          # player's free-form note

    def __post_init__(self) -> None:
        if self.rarity not in RARITIES:
            raise ValueError(f"rarity must be one of {RARITIES}, got {self.rarity!r}")
        if self.item_level < 1:
            raise ValueError(f"item_level must be >= 1, got {self.item_level}")
        # Quality ceiling is 50 to accommodate catalysed jewellery and similar
        # mechanics that stack quality above the baseline 20–30 range.
        if not (0 <= self.quality <= 50):
            raise ValueError(f"quality must be in [0, 50], got {self.quality}")
        # Affix-count caps per rarity. Uniques use their fixed mod set so the
        # generic ceiling of 6 in MAX_PREFIXES/MAX_SUFFIXES is a safe pass-through;
        # rare/magic/normal are strict.
        max_p = MAX_PREFIXES.get(self.rarity, 0)
        max_s = MAX_SUFFIXES.get(self.rarity, 0)
        if len(self.prefixes) > max_p:
            raise ValueError(
                f"{self.rarity} item has {len(self.prefixes)} prefixes, max is {max_p}"
            )
        if len(self.suffixes) > max_s:
            raise ValueError(
                f"{self.rarity} item has {len(self.suffixes)} suffixes, max is {max_s}"
            )

    # ---- mod accessors ----

    @property
    def all_mods(self) -> list[Modifier]:
        """All modifiers on this item, in display order (implicits → prefixes → suffixes)."""
        return [*self.implicits, *self.prefixes, *self.suffixes]

    @property
    def explicit_mods(self) -> list[Modifier]:
        """Non-implicit modifiers (the rolled prefixes + suffixes)."""
        return [*self.prefixes, *self.suffixes]

    @property
    def open_prefix_slots(self) -> int:
        return max(0, MAX_PREFIXES.get(self.rarity, 0) - len(self.prefixes))

    @property
    def open_suffix_slots(self) -> int:
        return max(0, MAX_SUFFIXES.get(self.rarity, 0) - len(self.suffixes))

    @property
    def is_full(self) -> bool:
        """True when no more affixes can be added at the current rarity."""
        return self.open_prefix_slots == 0 and self.open_suffix_slots == 0

    @property
    def has_fractured_mod(self) -> bool:
        return any(m.is_fractured for m in self.explicit_mods)

    @property
    def has_crafted_mod(self) -> bool:
        return any(m.is_crafted for m in self.explicit_mods)

    # ---- socket accessors ----

    @property
    def socket_count(self) -> int:
        return len(self.sockets)

    @property
    def open_socket_count(self) -> int:
        return sum(1 for s in self.sockets if s.is_empty)

    # ---- aggregation ----

    def aggregate_stats(self) -> dict[str, float]:
        """Sum mod values keyed by template — flat stat table for the item.

        Returns {template_string: total_value}. Multi-value templates (e.g.
        "+# to Strength and Dexterity") get rendered with all values combined
        into the key only if the template has one slot; multi-slot templates
        are keyed by (template, value_index) to avoid collision.

        NOT a DPS sim. Pure addition across rolled values.
        """
        out: dict[str, float] = {}
        for mod in self.all_mods:
            if mod.template is None:
                continue
            slots = mod.template.count("#")
            if slots == 0 or not mod.values:
                continue
            if slots == 1:
                # One value → key by template
                out[mod.template] = out.get(mod.template, 0.0) + mod.values[0]
            else:
                # Multi-slot template → key by (template, index)
                for i, v in enumerate(mod.values):
                    key = f"{mod.template}#{i}"
                    out[key] = out.get(key, 0.0) + v
        # Also include socketed runes / soul cores
        for socket in self.sockets:
            if socket.content is not None:
                # SocketContent values are positional, family is the key
                family_key = f"socket:{socket.content.family}"
                if socket.content.values:
                    out[family_key] = out.get(family_key, 0.0) + sum(socket.content.values)
        return out

    # ---- crafting state ----

    def can_accept_currency(self, op: str) -> bool:
        """Conservative check: most currency refuses corrupted items.

        `op` is the currency name in lowercase, e.g. "exalted", "divine", "chaos",
        "vaal". Returns False if the currency can't apply.
        """
        if self.mirrored:
            return False  # mirrored items can't be modified
        if self.corrupted and op in {"transmute", "augment", "regal", "alchemy",
                                       "exalted", "divine", "chaos", "annul",
                                       "essence", "omen", "fracturing"}:
            return False
        if op == "vaal":
            return not self.corrupted   # vaal corrupts; can't vaal twice
        return True
