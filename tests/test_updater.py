"""updater tests — local logic only, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import updater  # noqa: E402


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
