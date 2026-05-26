"""Main config loader for poe2-graph.

Reads `config.yaml` at the skill root into typed dataclasses. Singleton-cached
per process; call `reload()` to re-read after edits.

Schema reflects the YAML doc structure exactly — see `config.yaml` for the
authoritative comments on each field. Unknown keys are tolerated and ignored;
missing keys fall back to dataclass defaults.

Importing modules:
    from config import load
    cfg = load()
    for tool in cfg.tools:
        if tool.update_cycle.mode == "continuous":
            ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


CONFIG_PATH = Path(__file__).parent / "config.yaml"


# ----- dataclass schema -----

@dataclass
class UpdateCycle:
    """How often to check + whether to auto-pull a tool's upstream."""
    mode: str = "manual"             # off | manual | scheduled | continuous
    interval_seconds: int = 86400    # default daily
    auto_pull: bool = False


@dataclass
class ToolEntry:
    """One row in config.yaml's `tools:` list."""
    name: str
    type: str                        # bundled_fork | linked
    enabled: bool = True
    submodule_path: Optional[str] = None
    upstream: Optional[str] = None
    fork: Optional[str] = None
    detection_probe: Optional[str] = None
    update_cycle: UpdateCycle = field(default_factory=UpdateCycle)


@dataclass
class CacheCategoriesConfig:
    mode: str = "all"                # all | named_only
    named: list[str] = field(default_factory=list)


@dataclass
class Poe2dbCacheConfig:
    ttl_hours: int = 24
    max_size_mb: int = 50
    categories: CacheCategoriesConfig = field(default_factory=CacheCategoriesConfig)


@dataclass
class CacheConfig:
    poe2db: Poe2dbCacheConfig = field(default_factory=Poe2dbCacheConfig)


@dataclass
class WorkerConfig:
    default_interval_seconds: int = 600
    log_path: str = "worker.log"
    sync_upstream_default: bool = True


@dataclass
class ScannerConfig:
    run_on_session_start: bool = True
    recommend_missing_tools: bool = True


@dataclass
class Config:
    schema_version: int = 1
    tools: list[ToolEntry] = field(default_factory=list)
    cache: CacheConfig = field(default_factory=CacheConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)


# ----- conversion -----

def _to_update_cycle(d: dict) -> UpdateCycle:
    if not isinstance(d, dict):
        return UpdateCycle()
    return UpdateCycle(
        mode=str(d.get("mode", "manual")),
        interval_seconds=int(d.get("interval_seconds", 86400)),
        auto_pull=bool(d.get("auto_pull", False)),
    )


def _to_tool_entry(d: dict) -> Optional[ToolEntry]:
    if not isinstance(d, dict) or not d.get("name"):
        return None
    return ToolEntry(
        name=str(d["name"]),
        type=str(d.get("type", "linked")),
        enabled=bool(d.get("enabled", True)),
        submodule_path=d.get("submodule_path"),
        upstream=d.get("upstream"),
        fork=d.get("fork"),
        detection_probe=d.get("detection_probe"),
        update_cycle=_to_update_cycle(d.get("update_cycle") or {}),
    )


def _to_cache(d: dict) -> CacheConfig:
    if not isinstance(d, dict):
        return CacheConfig()
    poe2db_raw = d.get("poe2db") or {}
    cat_raw = poe2db_raw.get("categories") or {}
    return CacheConfig(
        poe2db=Poe2dbCacheConfig(
            ttl_hours=int(poe2db_raw.get("ttl_hours", 24)),
            max_size_mb=int(poe2db_raw.get("max_size_mb", 50)),
            categories=CacheCategoriesConfig(
                mode=str(cat_raw.get("mode", "all")),
                named=list(cat_raw.get("named") or []),
            ),
        ),
    )


def _to_worker(d: dict) -> WorkerConfig:
    if not isinstance(d, dict):
        return WorkerConfig()
    return WorkerConfig(
        default_interval_seconds=int(d.get("default_interval_seconds", 600)),
        log_path=str(d.get("log_path", "worker.log")),
        sync_upstream_default=bool(d.get("sync_upstream_default", True)),
    )


def _to_scanner(d: dict) -> ScannerConfig:
    if not isinstance(d, dict):
        return ScannerConfig()
    return ScannerConfig(
        run_on_session_start=bool(d.get("run_on_session_start", True)),
        recommend_missing_tools=bool(d.get("recommend_missing_tools", True)),
    )


def _from_dict(raw: dict) -> Config:
    if not isinstance(raw, dict):
        return Config()
    tools = []
    for t in (raw.get("tools") or []):
        entry = _to_tool_entry(t)
        if entry is not None:
            tools.append(entry)
    return Config(
        schema_version=int(raw.get("schema_version", 1)),
        tools=tools,
        cache=_to_cache(raw.get("cache") or {}),
        worker=_to_worker(raw.get("worker") or {}),
        scanner=_to_scanner(raw.get("scanner") or {}),
    )


# ----- singleton cache + public API -----

_cached: Optional[Config] = None


def load(path: Optional[Path] = None, force: bool = False) -> Config:
    """Load the config (cached). Pass force=True to re-read from disk."""
    global _cached
    if _cached is not None and not force:
        return _cached
    p = path or CONFIG_PATH
    if not p.exists():
        _cached = Config()
        return _cached
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    _cached = _from_dict(raw)
    return _cached


def reload(path: Optional[Path] = None) -> Config:
    """Force re-read from disk. Returns the new config."""
    return load(path=path, force=True)


# ----- query helpers -----

def tools_by_name(cfg: Optional[Config] = None) -> dict[str, ToolEntry]:
    c = cfg or load()
    return {t.name: t for t in c.tools}


def enabled_tools(cfg: Optional[Config] = None) -> list[ToolEntry]:
    c = cfg or load()
    return [t for t in c.tools if t.enabled]


def bundled_forks(cfg: Optional[Config] = None) -> list[ToolEntry]:
    c = cfg or load()
    return [t for t in c.tools if t.type == "bundled_fork" and t.enabled]


def continuous_tools(cfg: Optional[Config] = None) -> list[ToolEntry]:
    """Tools whose update_cycle.mode is 'continuous' — what the worker should poll."""
    c = cfg or load()
    return [t for t in c.tools if t.enabled and t.update_cycle.mode == "continuous"]
