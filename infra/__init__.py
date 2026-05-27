"""infra — config + updater + worker.

The infrastructure layer for the skill itself (distinct from the game/player
domain). Loaded by Claude session start to validate health, fetch updates,
and (via the worker) keep bundled forks in sync with upstream.
"""

from infra.config import (
    Config, ToolEntry, UpdateCycle,
    CacheConfig, Poe2dbCacheConfig, CacheCategoriesConfig,
    WorkerConfig, ScannerConfig,
    load, reload,
    tools_by_name, enabled_tools, bundled_forks, continuous_tools,
    CONFIG_PATH,
)
from infra.updater import (
    SourceStatus, StalenessReport,
    report, load_manifest, local_version,
    check_skill_version, check_data_source, latest_game_version,
    check_tool_submodule, check_tool_submodules,
    update_tool_submodule, update_all_tool_submodules,
    sync_fork_from_upstream,
    update_data_source, update_skill_code, invalidate_poe2db_cache,
    poe2db_cache_age_days,
    PROTECTED_PATHS,
)

__all__ = [
    "Config", "ToolEntry", "UpdateCycle",
    "CacheConfig", "Poe2dbCacheConfig", "CacheCategoriesConfig",
    "WorkerConfig", "ScannerConfig",
    "load", "reload",
    "tools_by_name", "enabled_tools", "bundled_forks", "continuous_tools",
    "CONFIG_PATH",
    "SourceStatus", "StalenessReport",
    "report", "load_manifest", "local_version",
    "check_skill_version", "check_data_source", "latest_game_version",
    "check_tool_submodule", "check_tool_submodules",
    "update_tool_submodule", "update_all_tool_submodules",
    "sync_fork_from_upstream",
    "update_data_source", "update_skill_code", "invalidate_poe2db_cache",
    "poe2db_cache_age_days",
    "PROTECTED_PATHS",
]
