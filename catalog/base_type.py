"""BaseType — the schema layer of an item.

A BaseType is the immutable identity of "Diamond Wand iLvl 84" or
"Silken Vest iLvl 82". Carries the inherent implicits (every Diamond Wand
gets the same base implicit), the inherent tags (caster + wand + lightning),
attribute requirements, and the item class (which gates which mod pool can
roll on items of this base).

BaseTypes come from poe2db's per-category catalog dumps. We load + cache
them lazily — see `catalog.mod_pool` for the loader path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from items.modifier import Modifier


@dataclass(frozen=True)
class BaseType:
    """The immutable schema of an item base.

    Identity: (name, item_level) — though typically referenced by name; item_level
    qualifies which mod tiers can roll. Tags drive build-affinity matching.
    """
    name: str                          # display name, e.g. "Diamond Wand"
    category: str                      # poe2db category slug, e.g. "Wands"
    item_class: str                    # broader class, e.g. "OneHandWeapon" / "BodyArmour"
    implicits: tuple[Modifier, ...] = ()   # base implicits — every instance gets these
    inherent_tags: frozenset[str] = field(default_factory=frozenset)
    str_req: int = 0
    dex_req: int = 0
    int_req: int = 0
    drop_level: int = 1                # earliest level this base can drop
    max_sockets: int = 0               # default 0; weapons + body armour override

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("BaseType must have a name")


# Convenience: item-class → typical max-socket count for that class. Source of
# truth is per-base (BaseType.max_sockets), but this is the rule the game uses
# when generating bases via the catalog.
DEFAULT_MAX_SOCKETS_BY_CLASS = {
    "BodyArmour": 2,
    "TwoHandWeapon": 2,
    "OneHandWeapon": 1,
    "Helmet": 1,
    "Gloves": 1,
    "Boots": 1,
    "Quiver": 0,
    "CasterWeapon": 0,            # wands, sceptres, staves are caster — no sockets
    "Ring": 0,
    "Amulet": 0,
    "Belt": 0,
    "Shield": 1,                  # martial shields; caster shields = 0
    "Focus": 0,
    "Buckler": 1,
}


def max_sockets_for_class(item_class: str) -> int:
    """Default max sockets for an item class. BaseType can override per-base."""
    return DEFAULT_MAX_SOCKETS_BY_CLASS.get(item_class, 0)


# Tag taxonomy — non-exhaustive list of inherent_tags seen on bases.
# These drive cross-references with build archetype + stat scaling.
KNOWN_BASE_TAGS = frozenset({
    # archetype affinity
    "caster", "attacker", "minion_focused", "spirit_focused", "spell_focused",
    # damage-type bias
    "lightning", "cold", "fire", "chaos", "physical", "elemental",
    # weapon class
    "wand", "sceptre", "staff", "rune_dagger", "bow", "spear", "crossbow",
    "axe", "mace", "sword", "claw", "quarterstaff",
    # armour class
    "armour", "evasion", "energy_shield", "hybrid",
    # accessory
    "ring", "amulet", "belt", "quiver", "focus", "shield", "buckler",
})
