"""Bundle entry point.

Resolves `POE2_GRAPH_ROOT` (set from `user_config.poe2_graph_root` in the
manifest), prepends it to sys.path, and hands off to the real server.

The bundle stays tiny because the actual toolkit (mcp_server/, catalog/,
items/, goals.py, guides.py, exile.py, data/, EXILE/) lives in the user's
checkout — the bundle just points Claude at it. This is intentional:

  - the repo is large (PoB submodules, NeverSink data, etc.) and we don't
    want stale snapshots inside the .mcpb
  - EXILE/ is the player's profile state — writes must land in their repo,
    not in Claude's bundle install dir
  - the user already has the repo cloned for the Electron overlay + Code
    .mcp.json setup; reusing the same root keeps everything coherent
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    root_raw = os.environ.get("POE2_GRAPH_ROOT") or os.environ.get("POE2_GRAPH_HOME")
    if not root_raw:
        print(
            "ERROR: POE2_GRAPH_ROOT is not set. The .mcpb bundle needs you to "
            "specify your poe2-graph checkout directory in the Claude app "
            "settings (user_config.poe2_graph_root).",
            file=sys.stderr,
        )
        return 2

    root = Path(root_raw).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: POE2_GRAPH_ROOT={root!s} is not a directory.", file=sys.stderr)
        return 2

    server_pkg = root / "mcp_server" / "server.py"
    if not server_pkg.is_file():
        print(
            f"ERROR: {server_pkg!s} not found. Confirm POE2_GRAPH_ROOT points "
            "at the repo root that contains mcp_server/.",
            file=sys.stderr,
        )
        return 2

    sys.path.insert(0, str(root))

    # Hand off. mcp_server.server.main() runs FastMCP on stdio + the optional
    # WS bridge; it never returns under normal operation.
    try:
        from mcp_server.server import main as run_server  # noqa: E402
    except ImportError as exc:
        print(
            f"ERROR: failed to import mcp_server.server: {exc}\n"
            f"Verify the required Python packages are installed: "
            f"pip install -r {root / 'requirements.txt'}",
            file=sys.stderr,
        )
        return 3

    run_server()
    return 0


if __name__ == "__main__":
    sys.exit(main())
