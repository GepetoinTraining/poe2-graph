# poe2-graph.mcpb — Claude desktop / app bundle

The `.mcpb` (MCP Bundle) format is how Claude desktop and the Claude web app
install MCP servers. It's a ZIP archive containing `manifest.json` plus the
entry script. This bundle is intentionally a *thin wrapper* — it doesn't
ship the toolkit code, only a launcher that points at your existing
poe2-graph checkout via a `user_config.poe2_graph_root` directory you pick
when installing.

Why thin instead of self-contained:

- The repo is large (PoB + NeverSink submodules, scraped poe2db cache).
- `EXILE/` is your *live* player-profile state — writes must land in the
  repo, not in Claude's bundle install dir.
- You already have the repo for the Electron overlay + Claude Code
  `.mcp.json` setup; reusing the same root keeps everything coherent.

## Files

```
mcpb/
├── manifest.json    bundle metadata + user_config + tool list
├── bootstrap.py     entry: prepends $POE2_GRAPH_ROOT to sys.path, imports mcp_server.server
└── README.md        this file
```

## Build the .mcpb

```powershell
# One-time: install the Anthropic mcpb CLI globally
npm install -g @anthropic-ai/mcpb

# From the mcpb/ directory, pack the bundle
cd D:\poe2-graph\mcpb
mcpb pack

# Output: D:\poe2-graph\mcpb\poe2-graph.mcpb
```

`mcpb pack` reads `manifest.json` from the current directory and zips
everything alongside it into `<name>.mcpb`. No extra config needed.

## Install in the Claude app

1. Open Claude desktop → Settings → Connectors (or Extensions on some
   versions).
2. Drag the `poe2-graph.mcpb` file into the connectors panel, or use the
   "Install from file" button.
3. Claude prompts for the `user_config` fields declared in `manifest.json`:
   - **poe2-graph repository root** — set to `D:\poe2-graph` (or wherever
     you cloned it).
   - **Electron overlay WebSocket port** *(optional)* — set to `8889` if
     you'll run the overlay too; leave blank for MCP-tools-only.
4. Claude restarts the MCP server with those values in the env vars
   `POE2_GRAPH_ROOT` + `POE2_MCP_WS_PORT`.

## Prerequisites on the machine

- **Python 3.11+** on `PATH` (the manifest declares `runtimes.python ">=3.11"`).
- The poe2-graph requirements: `pip install -r D:\poe2-graph\requirements.txt`
  installs `mcp`, `websockets`, `networkx`, `pyyaml`. Do this once in
  whatever Python the Claude app finds on PATH.

If `python` resolves to the wrong interpreter, the simplest fix is to edit
`manifest.json`'s `server.mcp_config.command` to the absolute path of the
right Python (e.g. `"C:\\Users\\you\\.venv\\Scripts\\python.exe"`) and
re-pack.

## Verifying after install

After Claude restarts, every tool declared in `manifest.json`'s `tools[]`
list should appear in Claude's available-tools list. Smoke test by asking
Claude:

> Call `welcome` and show me the response.

You should get back the session-start payload (onboarded flag, active
character map, suggested intents). If you set up the overlay too:

> Call `overlay_status`.

It will report whether the WebSocket bridge is bound.

## Updating the bundle

When the toolkit code changes in your checkout, you don't need to re-pack
the bundle — the wrapper just `sys.path.insert`s the live repo. Re-pack
only when `manifest.json` itself changes (new tools, new user_config,
version bump).

When you do re-pack, bump `manifest.json`'s `version` field; Claude uses
that to detect updates when you re-import.

## Known limits

- **`bootstrap.py` resolves `POE2_GRAPH_ROOT` at process start.** If you
  move the repo while Claude is running, restart the connector from the
  app's settings.
- **The bundle doesn't ship Python.** If the user's environment lacks the
  declared runtime + deps, the server fails to start with a clear error in
  stderr (which Claude surfaces in the connector's log panel).
- **One Python server per Claude surface.** Claude desktop launches its own
  via the bundle. Claude Code launches its own via `.mcp.json`. They don't
  share in-memory state — each rereads `EXILE/` from disk. This is the same
  multi-server wrinkle described in `electron/README.md`.
