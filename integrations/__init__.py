"""integrations — bridges to external tools and community data sources.

Distinct from `tools/` (root-level git submodules of bundled forks).
This is the Python code that:
  - Recommends NeverSink filter strictness + customizations (neversink.py)
  - Detects installed third-party tools on disk (filesystem_scanner.py)
  - Fetches item / mod data from poe2db.tw (poe2db_client.py)
  - Stub for future WebSocket bridge to natwarth's viewer (messenger.py)
"""

from integrations.filesystem_scanner import scan, summary, found_tags, tools_per_game
from integrations.neversink import (
    FilterRecommendation, recommend_filter, render_recommendation,
    write_recommendation, fetch_latest_release_url,
    local_filter_files_dir, local_filter_path,
    STRICTNESS_LEVELS, NEVERSINK_REPO, NEVERSINK_REPO_URL, NEVERSINK_RELEASES_LATEST,
)

__all__ = [
    "scan", "summary", "found_tags", "tools_per_game",
    "FilterRecommendation", "recommend_filter", "render_recommendation",
    "write_recommendation", "fetch_latest_release_url",
    "local_filter_files_dir", "local_filter_path",
    "STRICTNESS_LEVELS", "NEVERSINK_REPO", "NEVERSINK_REPO_URL", "NEVERSINK_RELEASES_LATEST",
]
