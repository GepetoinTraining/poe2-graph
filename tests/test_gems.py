"""Tests for the catalog/ gem catalog + loader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog.gem import (  # noqa: E402
    Gem, GemCatalog, GEM_COLORS, GEM_CLASSES, GEM_COLOR_TO_ATTR,
    load_catalog, clear_cache, is_known_gem,
)
from catalog.gem_loader import catalog_from_page, _parse_tags  # noqa: E402


# ===== Gem dataclass =====

def test_gem_basic_construction():
    g = Gem(name="Fireball", slug="Fireball", gem_class="skill", color="blue")
    assert g.name == "Fireball"
    assert g.slug == "Fireball"
    assert g.gem_class == "skill"
    assert g.color == "blue"
    assert g.level == 1  # default
    assert g.tags == frozenset()
    assert g.icon_url is None


def test_gem_attribute_maps_color_to_attr():
    assert Gem("X", "x", "skill", "red").attribute == "Str"
    assert Gem("Y", "y", "skill", "green").attribute == "Dex"
    assert Gem("Z", "z", "skill", "blue").attribute == "Int"


def test_gem_rejects_unknown_color():
    with pytest.raises(ValueError, match="unknown gem color"):
        Gem(name="X", slug="x", gem_class="skill", color="purple")


def test_gem_rejects_unknown_class():
    with pytest.raises(ValueError, match="unknown gem_class"):
        Gem(name="X", slug="x", gem_class="weapon", color="red")


def test_gem_rejects_zero_level():
    with pytest.raises(ValueError, match="level must be >= 1"):
        Gem(name="X", slug="x", gem_class="skill", color="red", level=0)


def test_gem_rejects_empty_name():
    with pytest.raises(ValueError, match="must have a name"):
        Gem(name="", slug="x", gem_class="skill", color="red")


def test_gem_color_constants_match_attr_map():
    # Every color must have an attribute mapping
    assert set(GEM_COLOR_TO_ATTR) == set(GEM_COLORS)


# ===== GemCatalog queries =====

def _fake_catalog() -> GemCatalog:
    return GemCatalog(
        gem_class="skill",
        gems=[
            Gem("Fireball", "Fireball", "skill", "blue", tags=frozenset({"Spell", "Fire", "Projectile"})),
            Gem("Fireball", "Fireball", "skill", "blue", level=5, tags=frozenset({"Spell", "Fire", "Projectile"})),
            Gem("Boneshatter", "Boneshatter", "skill", "red", tags=frozenset({"Attack", "Melee"})),
            Gem("Spark", "Spark", "skill", "blue", tags=frozenset({"Spell", "Lightning"})),
        ],
    )


def test_catalog_by_slug_returns_first_match():
    cat = _fake_catalog()
    g = cat.by_slug("Fireball")
    assert g is not None
    assert g.level == 1  # the lower-level row, which is first


def test_catalog_by_slug_missing_returns_none():
    assert _fake_catalog().by_slug("Nonexistent") is None


def test_catalog_all_levels_of_returns_ladder():
    levels = _fake_catalog().all_levels_of("Fireball")
    assert [g.level for g in levels] == [1, 5]


def test_catalog_by_name():
    cat = _fake_catalog()
    assert cat.by_name("Spark") is not None
    assert cat.by_name("Spark").slug == "Spark"
    assert cat.by_name("Missing") is None


def test_catalog_by_color():
    cat = _fake_catalog()
    blues = cat.by_color("blue")
    assert {g.slug for g in blues} == {"Fireball", "Spark"}
    reds = cat.by_color("red")
    assert {g.slug for g in reds} == {"Boneshatter"}


def test_catalog_by_tag():
    cat = _fake_catalog()
    spells = cat.by_tag("Spell")
    assert {g.slug for g in spells} == {"Fireball", "Spark"}
    fire = cat.by_tag("Fire")
    assert {g.slug for g in fire} == {"Fireball"}


def test_catalog_names_and_slugs():
    cat = _fake_catalog()
    assert cat.names() == {"Fireball", "Boneshatter", "Spark"}
    assert cat.slugs() == {"Fireball", "Boneshatter", "Spark"}


# ===== gem_loader parser =====

# Tiny fixture mirroring the real poe2db row shape. Two skill rows (one with
# a level marker, one without), plus a junk row to exercise skip-logic.
_FAKE_HTML = """
<table><thead><th><th>Name<tbody>
<tr data-filters="Buff Persistent AoE Fire Duration Herald Herald of Ash">
<td><a class="gem_red" href="/us/Herald_of_Ash"><img loading="lazy" src="https://cdn.poe2db.tw/image/foo/HeraldOfAshSkill.webp" alt="HeraldOfAshSkill" class="w1" /></a>
<td><a class="gem_red" href="/us/Herald_of_Ash">Herald of Ash</a> (1)<div class="gem_tags small">stuff</div>
<tr data-filters="Spell Lightning Projectile Spark">
<td><a class="gem_blue" href="/us/Spark"><img src="https://cdn.poe2db.tw/image/Spark.webp"/></a>
<td><a class="gem_blue" href="/us/Spark">Spark</a> (5)
<tr>
<td>not a gem row — should be skipped
</tbody></table>
""".strip()


def test_loader_parses_basic_rows():
    cat = catalog_from_page("skill", _FAKE_HTML)
    assert len(cat.gems) == 2
    assert cat.gem_class == "skill"
    by_slug = {g.slug: g for g in cat.gems}
    assert set(by_slug) == {"Herald_of_Ash", "Spark"}


def test_loader_extracts_color_name_level():
    cat = catalog_from_page("skill", _FAKE_HTML)
    herald = cat.by_slug("Herald_of_Ash")
    assert herald is not None
    assert herald.name == "Herald of Ash"
    assert herald.color == "red"
    assert herald.level == 1
    assert herald.icon_url == "https://cdn.poe2db.tw/image/foo/HeraldOfAshSkill.webp"

    spark = cat.by_slug("Spark")
    assert spark is not None
    assert spark.color == "blue"
    assert spark.level == 5


def test_loader_strips_name_from_data_filters_tags():
    cat = catalog_from_page("skill", _FAKE_HTML)
    herald = cat.by_slug("Herald_of_Ash")
    assert herald is not None
    # "Herald of Ash" suffix is stripped, leaving real tags
    assert herald.tags == frozenset({"Buff", "Persistent", "AoE", "Fire", "Duration", "Herald"})


def test_loader_skips_rows_without_data_filters():
    # The junk `<tr>` in _FAKE_HTML has no data-filters and must be ignored
    cat = catalog_from_page("skill", _FAKE_HTML)
    assert all(g.slug in ("Herald_of_Ash", "Spark") for g in cat.gems)


def test_loader_dedupes_same_slug_and_level():
    duplicated = _FAKE_HTML + "\n" + _FAKE_HTML  # two copies of every row
    cat = catalog_from_page("skill", duplicated)
    # Should still have just 2 gems, not 4
    assert len(cat.gems) == 2


def test_loader_handles_apostrophe_in_name():
    html = """
<tr data-filters="Support Lineage Minion Amanamu's Tithe">
<td><a class="gem_red" href="/us/Amanamus_Tithe"><img src="https://cdn.poe2db.tw/x.webp"/></a>
<td><a class="gem_red" href="/us/Amanamus_Tithe">Amanamu's Tithe</a> (1)
</tbody>
""".strip()
    cat = catalog_from_page("support", html)
    assert len(cat.gems) == 1
    g = cat.gems[0]
    assert g.name == "Amanamu's Tithe"
    assert g.slug == "Amanamus_Tithe"
    assert "Amanamu's" not in g.tags  # name was stripped from filters cleanly
    assert g.tags == frozenset({"Support", "Lineage", "Minion"})


def test_parse_tags_strips_trailing_name():
    tags = _parse_tags("Buff Persistent Herald Herald of Ash", "Herald of Ash")
    assert tags == ["Buff", "Persistent", "Herald"]


def test_parse_tags_no_name_match_returns_all_tokens():
    # If the name isn't a suffix, all tokens are returned as-is
    tags = _parse_tags("Buff Persistent Herald", "Different Gem")
    assert tags == ["Buff", "Persistent", "Herald"]


# ===== load_catalog + is_known_gem (cache surface) =====

def test_load_catalog_rejects_unknown_class():
    with pytest.raises(ValueError, match="unknown gem_class"):
        load_catalog("weapon")


def test_load_catalog_uses_cache(monkeypatch):
    """load_catalog should hit the cache on a second call."""
    clear_cache()
    fake = GemCatalog(gem_class="skill", gems=[Gem("X", "X", "skill", "red")])

    calls = []

    def fake_loader(gem_class, html):
        calls.append((gem_class, html))
        return fake

    def fake_fetch(category, force=False):
        calls.append(("fetch", category))
        return "<html>fake</html>"

    monkeypatch.setattr("catalog.gem_loader.catalog_from_page", fake_loader)
    monkeypatch.setattr(
        "integrations.poe2db_client.fetch_category_html", fake_fetch
    )

    assert load_catalog("skill") is fake
    assert load_catalog("skill") is fake  # cache hit — no second fetch
    # One fetch call, one parse call
    assert sum(1 for c in calls if c[0] == "fetch") == 1


def test_is_known_gem_searches_all_classes_when_unspecified(monkeypatch):
    clear_cache()
    catalogs = {
        "skill": GemCatalog("skill", [Gem("Fireball", "Fireball", "skill", "blue")]),
        "support": GemCatalog("support", [Gem("Acrimony", "Acrimony", "support", "red")]),
        "spirit": GemCatalog("spirit", [Gem("Grim Feast", "Grim_Feast", "spirit", "blue")]),
    }

    def fake_load(gem_class):
        return catalogs[gem_class]

    monkeypatch.setattr("catalog.gem.load_catalog", fake_load)

    assert is_known_gem("Fireball")
    assert is_known_gem("Acrimony")
    assert is_known_gem("Grim Feast")
    assert not is_known_gem("Definitely Not A Gem")


def test_is_known_gem_constrained_to_class(monkeypatch):
    clear_cache()
    catalogs = {
        "skill": GemCatalog("skill", [Gem("Fireball", "Fireball", "skill", "blue")]),
        "support": GemCatalog("support", []),
        "spirit": GemCatalog("spirit", []),
    }
    monkeypatch.setattr("catalog.gem.load_catalog", lambda c: catalogs[c])

    assert is_known_gem("Fireball", gem_class="skill")
    assert not is_known_gem("Fireball", gem_class="support")


def test_is_known_gem_swallows_load_failures(monkeypatch):
    clear_cache()

    def fail(gem_class):
        raise RuntimeError("network down")

    monkeypatch.setattr("catalog.gem.load_catalog", fail)
    # Best-effort: returns False rather than propagating the network error
    assert is_known_gem("Fireball") is False
