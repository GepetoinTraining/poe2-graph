"""updater tests — local logic only, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infra import updater  # noqa: E402


def test_version_file_exists_and_parses():
    v = updater.local_version()
    parts = v.split(".")
    assert len(parts) == 3
    for p in parts:
        int(p)  # must be integer-valued semver components


def test_manifest_has_required_keys():
    m = updater.load_manifest()
    assert "skill_version" in m
    assert "skill_repo" in m
    assert "data_sources" in m
    assert "passive_tree" in m["data_sources"]
    assert "atlas_tree" in m["data_sources"]
    for src in ("passive_tree", "atlas_tree"):
        s = m["data_sources"][src]
        assert s["repo"].startswith("https://github.com/")
        assert "last_commit" in s
        assert "fetched_at" in s


def test_manifest_declares_protected_paths():
    m = updater.load_manifest()
    assert "protected_paths" in m
    assert any(p.startswith("EXILE") for p in m["protected_paths"])
    assert any("PLAYER" in p for p in m["protected_paths"])


def test_manifest_skill_version_matches_version_file():
    m = updater.load_manifest()
    assert m["skill_version"] == updater.local_version()


def test_poe2db_cache_age_none_when_empty(tmp_path, monkeypatch):
    """Empty/missing cache returns None (not zero) so caller can distinguish."""
    monkeypatch.setattr(updater, "DATA_DIR", tmp_path)
    age = updater.poe2db_cache_age_days()
    assert age is None


def test_invalidate_poe2db_cache_handles_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "DATA_DIR", tmp_path)
    assert updater.invalidate_poe2db_cache() == 0


def test_invalidate_poe2db_cache_removes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "DATA_DIR", tmp_path)
    cache = tmp_path / "poe2db_cache"
    cache.mkdir()
    (cache / "Amulets.html").write_text("dummy")
    (cache / "Rings.html").write_text("dummy")
    assert updater.invalidate_poe2db_cache() == 2
    assert not list(cache.glob("*.html"))


def test_format_report_is_plain_text():
    """The CLI report should be readable even when remote is unreachable."""
    skill = updater.SourceStatus("skill_code", "0.1.0", None, False, "remote unreachable")
    pt = updater.SourceStatus("passive_tree", "fb64a333", "fb64a333", False)
    at = updater.SourceStatus("atlas_tree", "d535ec77", "d535ec77", False)
    r = updater.StalenessReport(skill, pt, at, poe2db_cache_age_days=0.5)
    text = updater._format_report(r)
    assert "skill_code" in text
    assert "passive_tree" in text
    assert "atlas_tree" in text
    assert "poe2db_cache" in text


def test_staleness_report_any_stale_flag():
    fresh = updater.SourceStatus("x", "a", "a", False)
    stale = updater.SourceStatus("x", "a", "b", True)
    r1 = updater.StalenessReport(fresh, fresh, fresh, 0.5)
    assert not r1.any_stale
    r2 = updater.StalenessReport(fresh, stale, fresh, 0.5)
    assert r2.any_stale


def test_staleness_report_carries_optional_game_version():
    fresh = updater.SourceStatus("x", "a", "a", False)
    r = updater.StalenessReport(fresh, fresh, fresh, 0.5, upstream_game_version="3.28.0.10")
    assert r.upstream_game_version == "3.28.0.10"

    # None is the unreachable case — must format cleanly
    r2 = updater.StalenessReport(fresh, fresh, fresh, 0.5)
    assert r2.upstream_game_version is None
    text = updater._format_report(r2)
    assert "unreachable" in text


def test_format_report_includes_game_version_when_known():
    fresh = updater.SourceStatus("x", "a", "a", False)
    r = updater.StalenessReport(fresh, fresh, fresh, 0.5, upstream_game_version="3.28.0.10")
    text = updater._format_report(r)
    assert "3.28.0.10" in text


# ----- tool submodules -----

def test_parse_gitmodules_returns_empty_when_missing(tmp_path):
    """Missing .gitmodules should return an empty list, not raise."""
    result = updater._parse_gitmodules(gm_path=tmp_path / "nope")
    assert result == []


def test_parse_gitmodules_parses_a_submodule_entry(tmp_path):
    """A canonical .gitmodules entry should decode to (name, path, url)."""
    gm = tmp_path / ".gitmodules"
    gm.write_text(
        '[submodule "tools/test-fork"]\n'
        '\tpath = tools/test-fork\n'
        '\turl = https://github.com/example/repo.git\n'
        '\tbranch = main\n',
        encoding="utf-8",
    )
    entries = updater._parse_gitmodules(gm_path=gm)
    assert len(entries) == 1
    name, path, url = entries[0]
    assert name == "tools/test-fork"
    assert path == "tools/test-fork"
    assert url == "https://github.com/example/repo.git"


def test_check_tool_submodule_uninitialized(tmp_path, monkeypatch):
    """When submodule directory doesn't exist or is empty, status is 'not initialized'."""
    monkeypatch.setattr(updater, "ROOT", tmp_path)
    status = updater.check_tool_submodule(
        name="tools/example", path="tools/example", url="https://github.com/example/repo.git",
    )
    assert status.local_ref == "(not initialized)"
    assert not status.stale
    assert "not yet cloned" in status.note


def test_staleness_report_carries_tool_submodules():
    """tool_submodules is a list-valued optional field; defaults to empty."""
    fresh = updater.SourceStatus("x", "a", "a", False)
    r1 = updater.StalenessReport(fresh, fresh, fresh, 0.5)
    assert r1.tool_submodules == []
    assert not r1.any_stale

    submod_stale = updater.SourceStatus("tools/x", "a", "b", True)
    r2 = updater.StalenessReport(fresh, fresh, fresh, 0.5, tool_submodules=[submod_stale])
    assert r2.tool_submodules == [submod_stale]
    assert r2.any_stale  # any-stale must reflect submodules too


def test_format_report_renders_tool_submodules():
    """The formatter should include a bundled-forks section when submodules exist."""
    fresh = updater.SourceStatus("x", "a", "a", False)
    submod = updater.SourceStatus("tools/pob-poe2", "abcdef12", "abcdef12", False)
    r = updater.StalenessReport(fresh, fresh, fresh, 0.5, tool_submodules=[submod])
    text = updater._format_report(r)
    assert "Bundled forks" in text
    assert "tools/pob-poe2" in text


def test_manifest_protects_tools_dir():
    """Bundled forks live under tools/ — must be on the protected paths list."""
    m = updater.load_manifest()
    assert any("tools" in p for p in m["protected_paths"])
