"""Socket — the augment-slot layer on items.

A Socket holds one SocketContent — either a Rune (cheap, broadly available)
or a SoulCore (rare, from Trial of Chaos, broader mod pool). Sockets are
permanent: once filled, replacing the content destroys the previous occupant.

Socket counts per slot (PoE 2 0.5):
  Body Armour, 2H weapons   → max 2 sockets
  Helmet, Gloves, Boots,    → max 1 socket
  1H martial weapons        → max 1 socket
  Quivers, Caster Weapons,
  Jewellery (rings/amulet)  → 0 sockets (cannot socket)

Sockets are added to gear via the Artificer Orb (consumes 10 Artificer
Shards). See `data/systems/runes_and_sockets.md` for the player-facing
discussion + delivery mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SocketContent:
    """Base for items that can occupy a socket. Subclassed by Rune + SoulCore."""
    name: str           # display name (e.g. "Body Rune", "Soul Core of Cholotl")
    family: str         # mod family this content provides, mirrors ModFamilyList
    values: tuple[float, ...] = ()  # rolled values, frozen


@dataclass(frozen=True)
class Rune(SocketContent):
    """A common socketable. Cheap, broad-coverage mods. Removable only by
    replacement (which destroys the previous rune)."""

    def __hash__(self) -> int:
        # Default frozen-dataclass hash uses field values only, so Rune("x", "y")
        # and SoulCore("x", "y") hash equal even though `==` is False — fine for
        # sets, but dict.get(rune_x) on a dict keyed by soul_core_x would
        # collide-and-miss. Include the class name in the hash to keep buckets
        # disjoint.
        return hash((type(self).__name__, self.name, self.family, self.values))


@dataclass(frozen=True)
class SoulCore(SocketContent):
    """A rare socketable from the Trial of Chaos. Wider mod pool than Runes,
    includes spirit / item rarity / movement speed at magnitudes runes can't
    reach. Once socketed, cannot be removed (only replaced; original destroyed)."""

    def __hash__(self) -> int:
        # See Rune.__hash__ for the rationale.
        return hash((type(self).__name__, self.name, self.family, self.values))


@dataclass
class Socket:
    """One socket on an item.

    `index` is 1-based — items at most have 2 sockets so index ∈ {1, 2}.
    `content` is None for empty sockets.
    """
    index: int
    content: Optional[SocketContent] = None

    @property
    def is_empty(self) -> bool:
        return self.content is None

    def fill(self, content: SocketContent) -> None:
        """Place content in this socket. The previous occupant (if any) is
        destroyed (matches PoE 2's permanent-replace rule)."""
        self.content = content
