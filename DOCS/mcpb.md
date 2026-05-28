---
id: mcpb
file: DOCS/mcpb.md
topic: Thin .mcpb bundle that installs the toolkit into Claude desktop / app
priority: reference
modules: []
tags: [mcpb, claude-desktop, claude-app, bundle, manifest, installer, user_config, bootstrap]
when_to_read: |
  User asks how to install poe2-graph into Claude desktop / the Claude app,
  how the .mcpb bundle is built, what user_config fields exist, or how
  `bootstrap.py` finds the repo. Also when troubleshooting a "tools missing
  after install" / "wrong Python" symptom.
---

# mcpb — Claude desktop / app bundle

## What this is

The `.mcpb` (**MCP Bundle**) format is how Claude desktop and the Claude web
app install MCP servers. It's a ZIP archive containing `manifest.json` + the
entry script.

**This bundle is intentionally a thin wrapper.** It does NOT ship the
toolkit code; it ships a launcher that points at your existing poe2-graph
checkout via a `user_config.poe2_graph_root` directory you pick when
installing.

Why thin instead of self-contained:

- The repo is large (PoB + NeverSink submodules, scraped poe2db cache).
- `EXILE/` is the **live** player-profile state — writes have to land in the
  repo, not in Claude's bundle install dir.
- You already have the repo for the Electron overlay + Claude Code
  `.mcp.json` setup; reusing the same root keeps everything coherent.

## Layout

```
mcpb/
├── manifest.json    bundle metadata + user_config + tools[]
├── bootstrap.py     entry: prepends $POE2_GRAPH_ROOT to sys.path, runs mcp_server.server
├── pack.py          local zip builder (alternative to the official mcpb CLI)
├── poe2-graph.mcpb  built artifact (output of `mcpb pack` or `python pack.py`)
└── README.md        same content as this chapter, kept next to the bundle
```

## Build the bundle

Two paths — pick whichever you have:

```powershell
# Path A: official Anthropic mcpb CLI (one-time install)
npm install -g @anthropic-ai/mcpb
cd D:\poe2-graph\mcpb
mcpb pack
# → D:\poe2-graph\mcpb\poe2-graph.mcpb
```

```powershell
# Path B: local pack.py (no extra deps)
cd D:\poe2-graph\mcpb
python pack.py
# → D:\poe2-graph\mcpb\poe2-graph.mcpb
```

Both produce the same artifact: a ZIP of `manifest.json` + `bootstrap.py`
(plus README). No extra config needed; `manifest.json` is the source of truth.

The Electron Wizard's step 6 invokes `pack.py` automatically, so most users
never run either by hand.

## Install in the Claude app

1. Open Claude desktop → **Settings → Connectors** (or **Extensions** on some versions).
2. Drag `poe2-graph.mcpb` into the connectors panel, or use **Install from file**.
3. Claude prompts for the `user_config` fields declared in `manifest.json`:
   - **poe2-graph repository root** *(required)* — absolute path to your
     checkout, e.g. `D:\poe2-graph`.
   - **Electron overlay WebSocket port** *(optional)* — set to a free port
     (e.g. `8889`) if you also run the overlay; leave blank for
     MCP-tools-only.
4. Claude restarts the MCP server with those values in env vars
   `POE2_GRAPH_ROOT` and `POE2_MCP_WS_PORT`.

## What `bootstrap.py` does

```python
# Pseudocode of bootstrap.py
root = os.environ["POE2_GRAPH_ROOT"]
sys.path.insert(0, root)         # repo modules win over stdlib
from mcp_server import server    # imports the toolkit from your live checkout
server.main()                    # runs FastMCP on stdio
```

The bundle's `bootstrap.py` is ~10 lines — by design. Everything beyond
"resolve the repo and hand off to `mcp_server.server`" lives in the repo, so
re-packing the bundle is rarely needed.

## When to re-pack

You do **not** need to re-pack when toolkit code changes — the wrapper
imports live from `POE2_GRAPH_ROOT`. Re-pack only when `manifest.json` itself
changes:

- New tool registered in `mcp_server/server.py` → mirror its name +
  description in `manifest.json`'s `tools[]`
- New `user_config` field
- Version bump (Claude detects updates from `manifest.json`'s `version`)

Bump the manifest `version` whenever you re-pack so Claude shows an update
prompt on re-import.

## Prereqs on the user's machine

- **Python 3.11+** on PATH (manifest declares `compatibility.runtimes.python ">=3.11"`).
- The repo's `requirements.txt` installed in whatever Python the Claude app
  finds: `pip install -r D:\poe2-graph\requirements.txt`. Pulls `mcp`,
  `websockets`, `networkx`, `pyyaml`.

If `python` resolves to the wrong interpreter (most commonly the Microsoft
Store stub on Windows, or `/usr/bin/python3` vs Homebrew's `python3` on
macOS), the cleanest fix is to edit `manifest.json`'s
`server.mcp_config.command` to the absolute path of the correct Python
binary (e.g. `"C:\\Users\\you\\.venv\\Scripts\\python.exe"`) and re-pack.

## manifest.json — the source of truth

Key fields (full file at `mcpb/manifest.json`):

| Field | Purpose |
|---|---|
| `name`, `version`, `description` | shown in Claude's connector panel |
| `server.entry_point` | `bootstrap.py` |
| `server.mcp_config.command` | the Python binary Claude invokes |
| `server.mcp_config.args` | `["${__dirname}/bootstrap.py"]` — `${__dirname}` resolves to the bundle's install location |
| `server.mcp_config.env` | passes `POE2_GRAPH_ROOT` + `POE2_MCP_WS_PORT` from `user_config` |
| `user_config.poe2_graph_root` | directory picker (required) |
| `user_config.ws_port` | string (optional, default `""`) |
| `compatibility.platforms` | `["win32","darwin","linux"]` |
| `compatibility.runtimes.python` | `">=3.11"` |
| `tools[]` | name + description for every tool registered in `mcp_server/server.py` — Claude advertises these in its tools picker |

**Keep `tools[]` in sync** with the registration table in
`mcp_server/server.py:build_server()`. A tool present in `server.py` but
absent from `tools[]` still works — but won't show in Claude's UI. A tool
present in `tools[]` but absent from `server.py` will 500 when invoked.

## Verifying after install

After Claude restarts, ask:

> Call `welcome` and show me the response.

You should get back the session-start payload (onboarded flag, active
character map, suggested intents). If you set up the overlay too:

> Call `overlay_status`.

It will report whether the WS bridge is configured + live.

## Known limits

- **`bootstrap.py` resolves `POE2_GRAPH_ROOT` at process start.** If you
  move the repo while Claude is running, restart the connector from the
  app's settings.
- **The bundle doesn't ship Python.** If the user's environment lacks the
  declared runtime + deps, the server fails to start with a clear error
  in stderr (Claude surfaces it in the connector's log panel).
- **One Python server per Claude surface.** Claude desktop launches its own
  via this bundle; Claude Code launches its own via `.mcp.json`; the
  Electron app launches a third. They share state via `EXILE/` on disk,
  not in memory.

## Cross-references

- `DOCS/mcp-server.md` — what the bundle actually launches
- `DOCS/electron.md` — the Wizard packs and installs this bundle in step 6
- `mcpb/manifest.json` — authoritative manifest (this doc summarizes it)
- `mcpb/README.md` — same content, kept next to the bundle for repo browsers
