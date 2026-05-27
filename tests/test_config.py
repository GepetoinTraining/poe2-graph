"""config.yaml loader tests — no network, no real config file."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infra import config  # noqa: E402


def _write_config(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def test_load_missing_file_returns_defaults(tmp_path):
    """No config file → all defaults, no error."""
    cfg = config.load(path=tmp_path / "nope.yaml", force=True)
    assert cfg.schema_version == 1
    assert cfg.tools == []
    assert cfg.cache.poe2db.ttl_hours == 24
    assert cfg.worker.default_interval_seconds == 600
    assert cfg.scanner.run_on_session_start is True


def test_load_parses_full_tools_section(tmp_path):
    p = _write_config(tmp_path, {
        "schema_version": 1,
        "tools": [
            {
                "name": "pob-poe2",
                "type": "bundled_fork",
                "enabled": True,
                "submodule_path": "tools/pob-poe2",
                "upstream": "PathOfBuildingCommunity/PathOfBuilding-PoE2",
                "fork": "GepetoinTraining/PathOfBuilding-PoE2",
                "update_cycle": {
                    "mode": "scheduled",
                    "interval_seconds": 604800,
                    "auto_pull": False,
                },
            },
        ],
    })
    cfg = config.load(path=p, force=True)
    assert len(cfg.tools) == 1
    t = cfg.tools[0]
    assert t.name == "pob-poe2"
    assert t.type == "bundled_fork"
    assert t.submodule_path == "tools/pob-poe2"
    assert t.update_cycle.mode == "scheduled"
    assert t.update_cycle.interval_seconds == 604800
    assert t.update_cycle.auto_pull is False


def test_load_handles_partial_update_cycle(tmp_path):
    """Missing update_cycle fields default appropriately."""
    p = _write_config(tmp_path, {
        "tools": [{"name": "x", "type": "linked"}],
    })
    cfg = config.load(path=p, force=True)
    t = cfg.tools[0]
    assert t.update_cycle.mode == "manual"
    assert t.update_cycle.interval_seconds == 86400
    assert t.update_cycle.auto_pull is False


def test_load_skips_tools_without_name(tmp_path):
    """Bad tool entries should be silently skipped, not raise."""
    p = _write_config(tmp_path, {
        "tools": [
            {"type": "linked"},                    # missing name → skipped
            "not a dict",                          # wrong type → skipped
            {"name": "good", "type": "linked"},    # kept
        ],
    })
    cfg = config.load(path=p, force=True)
    assert len(cfg.tools) == 1
    assert cfg.tools[0].name == "good"


def test_load_parses_cache_section(tmp_path):
    p = _write_config(tmp_path, {
        "cache": {
            "poe2db": {
                "ttl_hours": 12,
                "max_size_mb": 100,
                "categories": {
                    "mode": "named_only",
                    "named": ["Amulets", "Rings"],
                },
            },
        },
    })
    cfg = config.load(path=p, force=True)
    assert cfg.cache.poe2db.ttl_hours == 12
    assert cfg.cache.poe2db.max_size_mb == 100
    assert cfg.cache.poe2db.categories.mode == "named_only"
    assert cfg.cache.poe2db.categories.named == ["Amulets", "Rings"]


def test_load_parses_worker_section(tmp_path):
    p = _write_config(tmp_path, {
        "worker": {
            "default_interval_seconds": 300,
            "log_path": "custom.log",
            "sync_upstream_default": False,
        },
    })
    cfg = config.load(path=p, force=True)
    assert cfg.worker.default_interval_seconds == 300
    assert cfg.worker.log_path == "custom.log"
    assert cfg.worker.sync_upstream_default is False


def test_load_tolerates_unknown_keys(tmp_path):
    """Extra keys should be ignored, not crash the loader."""
    p = _write_config(tmp_path, {
        "schema_version": 1,
        "tools": [],
        "unknown_field": {"nested": "value"},
        "another_unknown": 42,
    })
    cfg = config.load(path=p, force=True)
    assert cfg.tools == []  # loader ran fine


def test_reload_picks_up_changes(tmp_path):
    """reload() should re-read the file."""
    p = _write_config(tmp_path, {"worker": {"default_interval_seconds": 100}})
    cfg1 = config.load(path=p, force=True)
    assert cfg1.worker.default_interval_seconds == 100

    _write_config(tmp_path, {"worker": {"default_interval_seconds": 200}})
    cfg2 = config.reload(path=p)
    assert cfg2.worker.default_interval_seconds == 200


def test_tools_by_name_indexes(tmp_path):
    p = _write_config(tmp_path, {
        "tools": [
            {"name": "a", "type": "linked"},
            {"name": "b", "type": "bundled_fork"},
        ],
    })
    cfg = config.load(path=p, force=True)
    by_name = config.tools_by_name(cfg)
    assert set(by_name.keys()) == {"a", "b"}
    assert by_name["b"].type == "bundled_fork"


def test_enabled_tools_filters_disabled(tmp_path):
    p = _write_config(tmp_path, {
        "tools": [
            {"name": "on", "type": "linked", "enabled": True},
            {"name": "off", "type": "linked", "enabled": False},
        ],
    })
    cfg = config.load(path=p, force=True)
    enabled = config.enabled_tools(cfg)
    assert [t.name for t in enabled] == ["on"]


def test_bundled_forks_filters_by_type_and_enabled(tmp_path):
    p = _write_config(tmp_path, {
        "tools": [
            {"name": "fork-on", "type": "bundled_fork", "enabled": True},
            {"name": "fork-off", "type": "bundled_fork", "enabled": False},
            {"name": "linked-on", "type": "linked", "enabled": True},
        ],
    })
    cfg = config.load(path=p, force=True)
    forks = config.bundled_forks(cfg)
    assert [t.name for t in forks] == ["fork-on"]


def test_continuous_tools_filters_by_mode(tmp_path):
    p = _write_config(tmp_path, {
        "tools": [
            {"name": "watch-me", "type": "bundled_fork",
             "update_cycle": {"mode": "continuous"}},
            {"name": "skip-me", "type": "bundled_fork",
             "update_cycle": {"mode": "scheduled"}},
        ],
    })
    cfg = config.load(path=p, force=True)
    continuous = config.continuous_tools(cfg)
    assert [t.name for t in continuous] == ["watch-me"]


def test_real_config_yaml_loads_clean():
    """The shipped config.yaml at repo root must parse without errors and
    declare all four bundled forks."""
    cfg = config.load(path=ROOT / "config.yaml", force=True)
    fork_names = {t.name for t in cfg.tools if t.type == "bundled_fork"}
    assert fork_names == {"pob-poe2", "pob-poe1", "neversink-poe2", "neversink-poe1"}
    # NeverSink PoE2 should be the continuous one (league-launch polling)
    by_name = config.tools_by_name(cfg)
    assert by_name["neversink-poe2"].update_cycle.mode == "continuous"
    assert by_name["neversink-poe2"].update_cycle.auto_pull is True
