"""Tests for the items/ package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from items.modifier import Modifier, extract_values, to_template  # noqa: E402
from catalog.mod_tier import ModTier, AFFIX_CLASSES  # noqa: E402
from catalog.base_type import BaseType, max_sockets_for_class, DEFAULT_MAX_SOCKETS_BY_CLASS  # noqa: E402
from items.socket import Socket, Rune, SoulCore  # noqa: E402
from items.item import Item, RARITIES, MAX_PREFIXES, MAX_SUFFIXES  # noqa: E402
from items.inventory import Inventory, SLOT_IDS, SLOT_ALLOWED_CLASSES  # noqa: E402
from items.parser import parse_clipboard  # noqa: E402
from catalog.mod_pool import ModPool  # noqa: E402
from catalog.poe2db_loader import _strip_html, _strip_link_brackets, pool_from_modsview  # noqa: E402
from items.stash import Stash  # noqa: E402


# ===== modifier.py =====

def test_modtier_validates_affix_class():
    with pytest.raises(ValueError, match="unknown affix_class"):
        ModTier(family="x", tier=1, template="#", value_ranges=((0, 1),),
                min_ilvl=1, affix_class="invented")


def test_modtier_rejects_zero_tier():
    with pytest.raises(ValueError, match="tier must be >= 1"):
        ModTier(family="x", tier=0, template="#", value_ranges=((0, 1),), min_ilvl=1)


def test_modtier_value_slots_counts_hashes():
    t = ModTier(family="x", tier=1, template="+# to Str and # to Dex",
                value_ranges=((1, 10), (1, 10)), min_ilvl=1)
    assert t.value_slots == 2


def test_extract_values_pulls_signed_decimals():
    assert extract_values("+12 to maximum Life") == [12.0]
    assert extract_values("-5% Cold Resistance") == [-5.0]
    assert extract_values("+10 to Str and +12 to Dex") == [10.0, 12.0]
    assert extract_values("5.5% increased") == [5.5]
    assert extract_values("No numbers here") == []


def test_to_template_replaces_values_with_hash():
    assert to_template("+12 to maximum Life") == "+# to maximum Life"
    assert to_template("+10 to Str and +12 to Dex") == "+# to Str and +# to Dex"


def test_modifier_render_with_self_template():
    m = Modifier(family="IncreasedLife", tier=1, values=[120.0],
                 template="+# to maximum Life")
    assert m.render() == "+120 to maximum Life"


def test_modifier_render_multi_value():
    m = Modifier(family="StrDexHybrid", tier=1, values=[12.0, 14.0],
                 template="+# to Strength and # to Dexterity")
    assert m.render() == "+12 to Strength and 14 to Dexterity"


def test_modifier_render_fallback_no_template():
    m = Modifier(family="x", tier=1, values=[42.0])
    assert m.render() == "42"


# ===== socket.py =====

def test_socket_starts_empty():
    s = Socket(index=1)
    assert s.is_empty
    assert s.content is None


def test_socket_fill_replaces_content():
    s = Socket(index=1)
    rune = Rune(name="Body Rune", family="IncreasedLife", values=(20.0,))
    s.fill(rune)
    assert not s.is_empty
    assert s.content is rune


def test_rune_and_soulcore_are_distinct_types():
    r = Rune(name="r", family="x")
    sc = SoulCore(name="sc", family="x")
    assert type(r).__name__ == "Rune"
    assert type(sc).__name__ == "SoulCore"


# ===== base.py =====

def test_basetype_requires_name():
    with pytest.raises(ValueError, match="must have a name"):
        BaseType(name="", category="Wands", item_class="CasterWeapon")


def test_basetype_is_hashable_and_frozen():
    b1 = BaseType(name="Diamond Wand", category="Wands", item_class="CasterWeapon")
    b2 = BaseType(name="Diamond Wand", category="Wands", item_class="CasterWeapon")
    # Identical bases → same hash; frozen so they can live in sets
    assert hash(b1) == hash(b2)
    s = {b1, b2}
    assert len(s) == 1


def test_max_sockets_for_class_known_classes():
    assert max_sockets_for_class("BodyArmour") == 2
    assert max_sockets_for_class("TwoHandWeapon") == 2
    assert max_sockets_for_class("Helmet") == 1
    assert max_sockets_for_class("Ring") == 0
    assert max_sockets_for_class("Amulet") == 0


def test_max_sockets_for_unknown_class_defaults_zero():
    assert max_sockets_for_class("InventedClass") == 0


# ===== item.py =====

def _diamond_wand_base():
    return BaseType(name="Diamond Wand", category="Wands", item_class="CasterWeapon")


def test_item_rejects_unknown_rarity():
    with pytest.raises(ValueError, match="rarity must be"):
        Item(base=_diamond_wand_base(), rarity="legendary")


def test_item_rejects_zero_item_level():
    with pytest.raises(ValueError, match="item_level must be >= 1"):
        Item(base=_diamond_wand_base(), rarity="normal", item_level=0)


def test_item_rejects_excessive_quality():
    with pytest.raises(ValueError, match="quality must be in"):
        Item(base=_diamond_wand_base(), rarity="normal", quality=50)


def test_item_open_slots_by_rarity():
    item_normal = Item(base=_diamond_wand_base(), rarity="normal")
    assert item_normal.open_prefix_slots == 0
    assert item_normal.open_suffix_slots == 0

    item_magic = Item(base=_diamond_wand_base(), rarity="magic")
    assert item_magic.open_prefix_slots == 1
    assert item_magic.open_suffix_slots == 1

    item_rare = Item(base=_diamond_wand_base(), rarity="rare")
    assert item_rare.open_prefix_slots == 3
    assert item_rare.open_suffix_slots == 3


def test_item_is_full_when_prefixes_and_suffixes_maxed():
    base = _diamond_wand_base()
    prefixes = [
        Modifier(family=f"f{i}", tier=1, values=[1.0], template="+# x")
        for i in range(3)
    ]
    suffixes = [
        Modifier(family=f"g{i}", tier=1, values=[1.0], template="+# y")
        for i in range(3)
    ]
    item = Item(base=base, rarity="rare", prefixes=prefixes, suffixes=suffixes)
    assert item.is_full
    assert item.open_prefix_slots == 0
    assert item.open_suffix_slots == 0


def test_item_aggregate_stats_sums_same_template():
    base = _diamond_wand_base()
    item = Item(
        base=base, rarity="rare", item_level=80,
        prefixes=[
            Modifier(family="IncreasedLife", tier=1, values=[100.0], template="+# to maximum Life"),
        ],
        suffixes=[
            Modifier(family="IncreasedLife", tier=2, values=[50.0], template="+# to maximum Life"),
        ],
    )
    stats = item.aggregate_stats()
    assert stats["+# to maximum Life"] == 150.0


def test_item_aggregate_stats_includes_sockets():
    base = _diamond_wand_base()
    socket = Socket(index=1, content=Rune(name="r", family="IncreasedLife", values=(20.0,)))
    item = Item(base=base, rarity="rare", item_level=80, sockets=[socket])
    stats = item.aggregate_stats()
    assert stats["socket:IncreasedLife"] == 20.0


def test_item_can_accept_currency_blocks_mirrored():
    item = Item(base=_diamond_wand_base(), rarity="rare", mirrored=True)
    assert not item.can_accept_currency("exalted")
    assert not item.can_accept_currency("divine")


def test_item_can_accept_currency_blocks_modification_on_corrupted():
    item = Item(base=_diamond_wand_base(), rarity="rare", corrupted=True)
    assert not item.can_accept_currency("exalted")
    assert not item.can_accept_currency("divine")
    assert not item.can_accept_currency("chaos")
    assert not item.can_accept_currency("vaal")  # can't vaal twice


def test_item_can_accept_vaal_on_uncorrupted():
    item = Item(base=_diamond_wand_base(), rarity="rare", corrupted=False)
    assert item.can_accept_currency("vaal")


def test_item_has_fractured_mod_detection():
    base = _diamond_wand_base()
    item = Item(
        base=base, rarity="rare",
        prefixes=[Modifier(family="x", tier=1, values=[1.0], template="+# x", is_fractured=True)],
    )
    assert item.has_fractured_mod


# ===== inventory.py =====

def test_inventory_equip_unequip_round_trip():
    inv = Inventory()
    base = BaseType(name="Iron Helmet", category="Helmets", item_class="Helmet")
    helm = Item(base=base, rarity="rare", item_level=70)
    inv.equip("Helmet", helm)
    assert "Helmet" in inv
    assert inv["Helmet"] is helm
    returned = inv.unequip("Helmet")
    assert returned is helm
    assert "Helmet" not in inv


def test_inventory_rejects_unknown_slot():
    inv = Inventory()
    base = BaseType(name="x", category="Helmets", item_class="Helmet")
    helm = Item(base=base, rarity="normal")
    with pytest.raises(ValueError, match="unknown slot"):
        inv.equip("Boomstick", helm)


def test_inventory_validates_class_to_slot():
    inv = Inventory()
    helm_base = BaseType(name="Iron Helmet", category="Helmets", item_class="Helmet")
    helm = Item(base=helm_base, rarity="normal")
    with pytest.raises(ValueError, match="doesn't fit slot"):
        inv.equip("Ring1", helm)


def test_inventory_skips_validation_when_disabled():
    inv = Inventory()
    helm_base = BaseType(name="Iron Helmet", category="Helmets", item_class="Helmet")
    helm = Item(base=helm_base, rarity="normal")
    # validate=False bypasses class check
    inv.equip("Ring1", helm, validate=False)
    assert "Ring1" in inv


def test_inventory_aggregate_stats_sums_across_slots():
    inv = Inventory()
    chest_base = BaseType(name="Silken Vest", category="Body_Armours", item_class="BodyArmour")
    helm_base = BaseType(name="Iron Helmet", category="Helmets", item_class="Helmet")
    chest = Item(
        base=chest_base, rarity="rare", item_level=80,
        prefixes=[Modifier(family="IncreasedLife", tier=1, values=[100.0], template="+# to maximum Life")],
    )
    helm = Item(
        base=helm_base, rarity="rare", item_level=80,
        prefixes=[Modifier(family="IncreasedLife", tier=2, values=[60.0], template="+# to maximum Life")],
    )
    inv.equip("BodyArmour", chest)
    inv.equip("Helmet", helm)
    stats = inv.aggregate_stats()
    assert stats["+# to maximum Life"] == 160.0


def test_inventory_weapon_set_lookup():
    inv = Inventory()
    wand_base = BaseType(name="Diamond Wand", category="Wands", item_class="CasterWeapon")
    w1 = Item(base=wand_base, rarity="rare", item_level=80)
    w2 = Item(base=wand_base, rarity="magic", item_level=80)
    inv.equip("Weapon1", w1)
    inv.equip("Weapon2", w2)
    main1, off1 = inv.weapon_set(1)
    main2, off2 = inv.weapon_set(2)
    assert main1 is w1 and off1 is None
    assert main2 is w2 and off2 is None


def test_inventory_validate_requirements_flags_underleveled():
    inv = Inventory()
    base = BaseType(name="Heavy Belt", category="Belts", item_class="Belt")
    item = Item(base=base, rarity="rare", item_level=70, requirements={"Level": 70})
    inv.equip("Belt", item)
    warnings = inv.validate_requirements(60, {"Str": 100, "Dex": 100, "Int": 100})
    assert any("Level 70" in w for w in warnings)


def test_inventory_validate_requirements_clean_when_met():
    inv = Inventory()
    base = BaseType(name="Heavy Belt", category="Belts", item_class="Belt")
    item = Item(base=base, rarity="normal", requirements={"Level": 50, "Str": 60})
    inv.equip("Belt", item)
    assert inv.validate_requirements(60, {"Str": 80, "Dex": 60, "Int": 60}) == []


def test_inventory_slots_empty_starts_with_all_slots():
    inv = Inventory()
    assert inv.slots_empty() == set(SLOT_IDS)
    assert inv.slots_filled() == set()


# ===== parser.py =====

def test_parse_clipboard_minimal_rare():
    text = """Item Class: Rings
Rarity: Rare
Death Coil
Iron Ring
--------
Item Level: 80
--------
+20 to maximum Life
+30 to Strength (crafted)
--------
Corrupted"""
    item = parse_clipboard(text)
    assert item.rarity == "rare"
    assert item.name == "Death Coil"
    assert item.base.name == "Iron Ring"
    assert item.base.item_class == "Ring"
    assert item.item_level == 80
    assert item.corrupted is True
    # Two mods, both treated as prefixes for now (catalog hydration would split)
    assert len(item.prefixes) == 2
    # One mod is crafted
    assert any(m.is_crafted for m in item.prefixes)


def test_parse_clipboard_normal_item_no_name():
    text = """Item Class: One Hand Maces
Rarity: Normal
Driftwood Club
--------
Physical Damage: 6-11
--------
Item Level: 5"""
    item = parse_clipboard(text)
    assert item.rarity == "normal"
    assert item.name is None
    assert item.base.name == "Driftwood Club"
    assert item.item_level == 5


def test_parse_clipboard_extracts_quality():
    text = """Item Class: One Hand Maces
Rarity: Magic
Quality Driftwood Club of Tinkering
--------
Quality: +20% (augmented)
Physical Damage: 8-12
--------
Item Level: 12
--------
+5% increased Physical Damage"""
    item = parse_clipboard(text)
    assert item.quality == 20


def test_parse_clipboard_rejects_garbage():
    with pytest.raises(ValueError, match="no parseable sections"):
        parse_clipboard("")


def test_parse_clipboard_rejects_missing_class():
    text = """Rarity: Rare
Something
Else"""
    with pytest.raises(ValueError, match="missing Item Class"):
        parse_clipboard(text)


def test_parse_clipboard_fractured_flag():
    text = """Item Class: Body Armours
Rarity: Rare
Bramble Cage
Plate Vest
--------
Item Level: 82
--------
+100 to maximum Life (fractured)
+30% increased Armour"""
    item = parse_clipboard(text)
    assert item.has_fractured_mod


# ===== mod_pool.py =====

def test_strip_html_removes_spans():
    raw = "<span class='mod-value'>+12</span> to maximum Life"
    assert _strip_html(raw) == "+12 to maximum Life"


def test_strip_link_brackets_simplifies_terms():
    assert _strip_link_brackets("to maximum [Life]") == "to maximum Life"
    assert _strip_link_brackets("[Critical|Critical Strike] Chance") == "Critical Strike Chance"


def test_modpool_from_modsview_parses_basic_entries():
    fake = {
        "baseitem": [],
        "normal": [
            {
                "Name": "IncreasedLife1",
                "Level": 60,
                "ModGenerationTypeID": 1,
                "ModFamilyList": "IncreasedLife",
                "DropChance": 1000,
                "str": "+(110—129) to maximum Life",
            },
            {
                "Name": "IncreasedLife2",
                "Level": 50,
                "ModGenerationTypeID": 1,
                "ModFamilyList": "IncreasedLife",
                "DropChance": 1500,
                "str": "+(95—109) to maximum Life",
            },
        ],
    }
    pool = pool_from_modsview("Body_Armours", fake)
    assert len(pool.tiers) == 2
    families = pool.families()
    assert families == {"IncreasedLife"}


def test_modpool_possible_mods_filters_by_ilvl():
    fake = {
        "normal": [
            {"Name": "x1", "Level": 80, "ModGenerationTypeID": 1, "ModFamilyList": "x",
             "DropChance": 100, "str": "+(50—60) x"},
            {"Name": "x2", "Level": 30, "ModGenerationTypeID": 1, "ModFamilyList": "x",
             "DropChance": 100, "str": "+(20—29) x"},
        ],
    }
    pool = pool_from_modsview("test", fake)
    assert len(pool.possible_mods(ilvl=85)) == 2
    assert len(pool.possible_mods(ilvl=50)) == 1
    assert len(pool.possible_mods(ilvl=20)) == 0


def test_modpool_lookup_tier_by_template():
    fake = {
        "normal": [
            {"Name": "IncreasedLife1", "Level": 60, "ModGenerationTypeID": 1,
             "ModFamilyList": "IncreasedLife", "DropChance": 1000,
             "str": "+(110—129) to maximum Life"},
        ],
    }
    pool = pool_from_modsview("Body_Armours", fake)
    tier = pool.lookup_tier_by_template("+# to maximum Life")
    assert tier is not None
    assert tier.family == "IncreasedLife"


def test_modpool_corrupted_mods_get_corruption_affix_class():
    fake = {
        "corrupted": [
            {"Name": "VaalImplicit1", "Level": 50, "ModGenerationTypeID": 1,
             "ModFamilyList": "CorruptedFireResist", "DropChance": 1,
             "str": "+(30—40)% to Fire Resistance"},
        ],
    }
    pool = pool_from_modsview("Body_Armours", fake)
    assert pool.tiers[0].affix_class == "corruption"


# ===== stash.py =====

def _ring_item(name="Iron Ring", ilvl=70, corrupted=False):
    base = BaseType(name=name, category="Rings", item_class="Ring")
    return Item(base=base, rarity="rare", item_level=ilvl, corrupted=corrupted)


def test_stash_add_remove():
    stash = Stash()
    item = _ring_item()
    stash.add(item)
    assert len(stash) == 1
    assert stash.remove(item) is True
    assert len(stash) == 0


def test_stash_find_by_base():
    stash = Stash()
    iron = _ring_item("Iron Ring")
    gold = _ring_item("Gold Ring")
    stash.add(iron)
    stash.add(gold)
    stash.add(_ring_item("Iron Ring"))
    found = stash.find_by_base("Iron Ring")
    assert len(found) == 2


def test_stash_find_corrupted():
    stash = Stash()
    stash.add(_ring_item("Iron Ring", corrupted=False))
    stash.add(_ring_item("Gold Ring", corrupted=True))
    corrupted = stash.find_corrupted()
    assert len(corrupted) == 1
    assert corrupted[0].base.name == "Gold Ring"


def test_stash_find_at_ilvl():
    stash = Stash()
    stash.add(_ring_item("Iron Ring", ilvl=70))
    stash.add(_ring_item("Gold Ring", ilvl=82))
    stash.add(_ring_item("Diamond Ring", ilvl=85))
    high = stash.find_at_ilvl(80)
    assert len(high) == 2


def test_stash_find_with_family():
    stash = Stash()
    base = BaseType(name="Iron Ring", category="Rings", item_class="Ring")
    item = Item(
        base=base, rarity="rare", item_level=80,
        prefixes=[Modifier(family="IncreasedLife", tier=1, values=[20.0], template="+# x")],
    )
    stash.add(item)
    stash.add(_ring_item("Gold Ring"))
    found = stash.find_with_family("IncreasedLife")
    assert len(found) == 1
