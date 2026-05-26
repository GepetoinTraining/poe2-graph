from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import creators  # noqa: E402


def test_load_all_returns_seeded_creators():
    """Reads from data/guides/creators/*.yaml (per-handle layout)."""
    cs = creators.load_all()
    assert len(cs) >= 1
    names = {c.name for c in cs}
    assert "Ghazzy" in names


def test_by_name_case_insensitive():
    c = creators.by_name("ghazzy")
    assert c is not None
    assert c.name == "Ghazzy"
    assert c.channels.get("youtube")


def test_by_specialty_filters():
    summoners = creators.by_specialty("summoner")
    assert any("Ghazzy" == c.name for c in summoners)


def test_by_specialty_with_game_filter():
    poe2_starters = creators.by_specialty("league_starter", game="poe2")
    assert all("poe2" in c.games for c in poe2_starters)


def test_by_game():
    poe2_creators = creators.by_game("poe2")
    assert len(poe2_creators) >= 1


def test_save_roundtrip(tmp_path):
    target = tmp_path / "creators.json"
    new_creator = creators.ContentCreator(
        name="TestCreator",
        channels={"youtube": "https://example.com"},
        specialties=["test", "fake"],
        games=["poe2"],
    )
    creators.save_all([new_creator], path=target)

    loaded = creators.load_all(path=target)
    assert len(loaded) == 1
    assert loaded[0].name == "TestCreator"
    assert loaded[0].channels["youtube"] == "https://example.com"


def test_creator_to_dict_skips_none_fields():
    c = creators.ContentCreator(name="X")
    d = c.to_dict()
    assert "main_page" not in d
    assert "live_status_url" not in d
    assert d["name"] == "X"


def test_seed_data_via_per_handle_yamls():
    """Sanity-check the per-handle creator YAMLs load cleanly."""
    import guides
    creators_loaded = guides.list_creators()
    assert len(creators_loaded) >= 3
    handles = {c.handle for c in creators_loaded}
    assert "ghazzy" in handles
    assert "mathil" in handles
