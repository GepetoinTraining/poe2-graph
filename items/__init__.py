"""items — per-character item instance state.

The instance side of the item world: what specific item is on which
character with which rolled mods. The schema/dictionary side (what mods
CAN roll, what bases exist, the poe2db loader) lives in `catalog`.

Module layout:
  modifier.py    Modifier (rolled instance on an item) + value helpers
  socket.py      Socket, Rune, SoulCore (socketable content)
  item.py        Item (BaseType + Modifiers + sockets + crafting state)
  inventory.py   Inventory (per-character: slot → Item)
  parser.py      Ctrl+C in-game text → Item
  stash.py       Stash (broader collection — placeholder for trade ops)

Standard imports:
  from items.modifier import Modifier
  from items.socket import Socket, Rune, SoulCore
  from items.item import Item
  from items.inventory import Inventory, SLOT_IDS
  from items.parser import parse_clipboard
  from items.stash import Stash

Schema-layer symbols come from catalog/:
  from catalog.mod_tier import ModTier, AFFIX_CLASSES
  from catalog.base_type import BaseType
  from catalog.mod_pool import ModPool, possible_mods
  from catalog.hydrate import hydrate_item
"""
