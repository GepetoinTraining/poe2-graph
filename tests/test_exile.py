from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exile  # noqa: E402


def _temp_skill(tmp_path, monkeypatch) -> Path:
    """Redirect exile's paths into a tmp dir so tests don't touch real EXILE/."""
    fake_root = tmp_path / "skill"
    fake_root.mkdir()
    monkeypatch.setattr(exile, "SKILL_ROOT", fake_root)
    monkeypatch.setattr(exile, "EXILE_DIR", fake_root / "EXILE")
    monkeypatch.setattr(exile, "DONE_FILE", fake_root / "EXILE" / "DONE")
    monkeypatch.setattr(exile, "ENV_FILE", fake_root / ".env")
    return fake_root


# ----- confidence math -----

def test_bump_confidence_starts_at_zero():
    assert exile.bump_confidence(0.0, 0.5) == 0.5


def test_bump_confidence_asymptotic():
    assert exile.bump_confidence(0.5, 0.5) == 0.75
    assert exile.bump_confidence(0.75, 0.5) == 0.875
    assert exile.bump_confidence(0.875, 0.5) == 0.9375


def test_bump_confidence_never_reaches_one():
    c = 0.0
    for _ in range(50):
        c = exile.bump_confidence(c, 0.5)
    assert c < 1.0
    assert c > 0.999


def test_bump_confidence_negative():
    assert exile.bump_confidence(0.5, -0.5) == 0.25
    assert exile.bump_confidence(0.5, -1.0) == 0.0


def test_bump_confidence_rejects_out_of_range_delta():
    try:
        exile.bump_confidence(0.5, 2.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ----- frontmatter IO -----

def test_parse_and_write_roundtrip():
    src = """---
schema_version: 1
knows:
  essence_crafting: 0.85
---

# Notes

hello
"""
    fm, body = exile.parse_frontmatter(src)
    assert fm["schema_version"] == 1
    assert fm["knows"]["essence_crafting"] == 0.85
    assert "hello" in body
    out = exile.write_frontmatter(fm, body)
    fm2, body2 = exile.parse_frontmatter(out)
    assert fm2["knows"]["essence_crafting"] == 0.85
    assert body2.strip() == body.strip()


# ----- skeleton + lifecycle -----

def test_init_skeleton_creates_player_md(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    created = exile.init_skeleton()
    assert "PLAYER.md" in created
    assert (exile.EXILE_DIR / "PLAYER.md").exists()
    fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    assert fm["schema_version"] == 1
    assert fm["knows"] == {}
    assert "free-form context" in body.lower()


def test_is_onboarded_false_initially(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    assert not exile.is_onboarded()


def test_mark_done_creates_marker(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.mark_done("test run")
    assert exile.is_onboarded()


# ----- characters -----

def test_create_and_list_characters(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("stormweaver", league_id="0.5")
    exile.create_character("titan", league_id="0.5")
    chars = exile.list_characters()
    assert chars == ["stormweaver", "titan"]


def test_set_active_character_is_exclusive(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("stormweaver", league_id="0.5")
    exile.create_character("titan", league_id="0.5")
    exile.set_active_character("stormweaver")
    assert exile.active_character() == "stormweaver"
    exile.set_active_character("titan")
    assert exile.active_character() == "titan"
    # confirm stormweaver flipped to dormant
    fm, _ = exile.read_file(exile.EXILE_DIR / "CHARACTER_stormweaver.md")
    assert fm["status"] == "dormant"


# ----- diff log -----

def test_snapshot_creates_initial_and_diff(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    p = exile.EXILE_DIR / "PLAYER.md"
    snap = exile.snapshot(p, label="first_pass")
    assert snap.exists()
    initial = p.with_name("PLAYER.initial.md")
    assert initial.exists()

    # mutate and snapshot again
    fm, body = exile.read_file(p)
    exile.update_tag(fm, "knows", "essence_crafting", 0.5)
    exile.write_file(p, fm, body)
    snap2 = exile.snapshot(p, label="after-update")
    assert snap2 != snap
    assert len(exile.diff_history(p)) == 2

    diff = exile.diff_against_initial(p)
    assert "essence_crafting" in diff


def test_update_tag_persists_through_file(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    p = exile.EXILE_DIR / "PLAYER.md"
    fm, body = exile.read_file(p)
    exile.update_tag(fm, "knows", "essence_crafting", 0.5)
    exile.update_tag(fm, "knows", "essence_crafting", 0.5)  # bump twice
    exile.write_file(p, fm, body)
    fm2, _ = exile.read_file(p)
    assert fm2["knows"]["essence_crafting"] == 0.75


# ----- xml composer -----

def test_compose_exile_xml_smoke(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    exile.update_tag(fm, "knows", "essence_crafting", 0.5)
    exile.update_tag(fm, "prefers", "caster", 0.7)
    fm["mode"] = "sc"
    fm["trade"] = "trade"
    exile.write_file(exile.EXILE_DIR / "PLAYER.md", fm, body)

    exile.create_league("0.5", game="poe2")
    exile.create_character("stormweaver", league_id="0.5", game="poe2")
    exile.set_active_character("stormweaver")

    xml = exile.compose_exile_xml()
    assert "<exile>" in xml
    assert 'name="essence_crafting"' in xml
    assert 'name="caster"' in xml
    assert 'status="active"' in xml
    assert 'id="stormweaver"' in xml
    assert 'id="0.5"' in xml
    assert 'value="sc"' in xml
    assert 'game="poe2"' in xml


# ----- per-game support -----

def test_update_tag_game_scoped_creates_nested_structure(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    p = exile.EXILE_DIR / "PLAYER.md"
    fm, body = exile.read_file(p)

    exile.update_tag(fm, "knows", "essence_crafting", 0.5, game="poe1")
    exile.update_tag(fm, "knows", "spirit_management", 0.4, game="poe2")
    exile.update_tag(fm, "knows", "trade_engagement", 0.9)  # game-agnostic
    exile.write_file(p, fm, body)

    fm2, _ = exile.read_file(p)
    assert fm2["knows"]["poe1"]["essence_crafting"] == 0.5
    assert fm2["knows"]["poe2"]["spirit_management"] == 0.4
    assert fm2["knows"]["trade_engagement"] == 0.9


def test_get_tag_handles_both_scopes(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    exile.update_tag(fm, "knows", "essence_crafting", 0.5, game="poe1")
    exile.update_tag(fm, "knows", "trade_engagement", 0.9)
    exile.write_file(exile.EXILE_DIR / "PLAYER.md", fm, body)

    fm2, _ = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    assert exile.get_tag(fm2, "knows", "essence_crafting", game="poe1") == 0.5
    assert exile.get_tag(fm2, "knows", "essence_crafting", game="poe2") == 0.0  # missing
    assert exile.get_tag(fm2, "knows", "trade_engagement") == 0.9
    assert exile.get_tag(fm2, "knows", "missing_tag") == 0.0


def test_active_character_is_per_game(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("storm_main", league_id="0.5", game="poe2")
    exile.create_character("storm_alt", league_id="0.5", game="poe2")
    exile.create_character("necro_main", league_id="3.28", game="poe1")

    # Activate one in each game
    exile.set_active_character("storm_main")
    exile.set_active_character("necro_main")

    # Both should remain active — they're in different games
    assert exile.active_character(game="poe2") == "storm_main"
    assert exile.active_character(game="poe1") == "necro_main"
    actives = exile.active_characters()
    assert actives == {"poe2": "storm_main", "poe1": "necro_main"}


def test_set_active_only_deactivates_same_game(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("storm_main", league_id="0.5", game="poe2")
    exile.create_character("storm_alt", league_id="0.5", game="poe2")
    exile.create_character("necro_main", league_id="3.28", game="poe1")

    exile.set_active_character("storm_main")
    exile.set_active_character("necro_main")

    # Now switch PoE 2 active
    exile.set_active_character("storm_alt")

    # storm_alt active, storm_main dormant, necro_main untouched (still active)
    assert exile.active_character(game="poe2") == "storm_alt"
    assert exile.active_character(game="poe1") == "necro_main"

    fm, _ = exile.read_file(exile.EXILE_DIR / "CHARACTER_storm_main.md")
    assert fm["status"] == "dormant"
    fm, _ = exile.read_file(exile.EXILE_DIR / "CHARACTER_necro_main.md")
    assert fm["status"] == "active"


def test_list_characters_filter_by_game(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    exile.create_character("storm", league_id="0.5", game="poe2")
    exile.create_character("titan", league_id="0.5", game="poe2")
    exile.create_character("necro", league_id="3.28", game="poe1")

    assert exile.list_characters() == ["necro", "storm", "titan"]
    assert exile.list_characters(game="poe2") == ["storm", "titan"]
    assert exile.list_characters(game="poe1") == ["necro"]


def test_compose_exile_xml_includes_per_game_tags(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    fm, body = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    exile.update_tag(fm, "knows", "essence_crafting", 0.5, game="poe1")
    exile.update_tag(fm, "knows", "spirit_management", 0.3, game="poe2")
    exile.update_tag(fm, "knows", "trade_engagement", 0.9)
    exile.write_file(exile.EXILE_DIR / "PLAYER.md", fm, body)

    xml = exile.compose_exile_xml()
    assert 'game="poe1" name="essence_crafting"' in xml
    assert 'game="poe2" name="spirit_management"' in xml
    # game-agnostic tag has no game attribute
    assert ('section="knows" name="trade_engagement"' in xml) or (
        'name="trade_engagement"' in xml and 'game=""' not in xml
    )


def test_write_exile_xml_writes_to_project_path(tmp_path, monkeypatch):
    _temp_skill(tmp_path, monkeypatch)
    exile.init_skeleton()
    # Redirect the output path too, so we don't write into the real ~/.claude
    fake_out = tmp_path / "fake-claude" / "EXILE.xml"
    monkeypatch.setattr(exile, "project_exile_xml_path", lambda: fake_out)
    out = exile.write_exile_xml()
    assert out == fake_out
    assert fake_out.exists()
    assert "<exile>" in fake_out.read_text(encoding="utf-8")
