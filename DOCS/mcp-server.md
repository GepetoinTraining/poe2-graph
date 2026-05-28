---
id: mcp-server
file: DOCS/mcp-server.md
topic: FastMCP wrapper exposing the toolkit as MCP tools; localhost WS bridge for the Electron overlay
priority: reference
modules: [mcp_server, transport_ws, tools_session, tools_goals, tools_state, tools_items, tools_guides, tools_views]
tags: [mcp, mcp_server, fastmcp, tools, websocket, transport, electron, bridge, overlay, claude-code, claude-desktop]
when_to_read: |
  User asks how the MCP server is wired, what tools it exposes, how Claude
  Code / Claude desktop / the Electron overlay all share one tool surface,
  how to add a new tool, or how the WebSocket bridge to the overlay works.
  Also read when troubleshooting a "tool not found" / "server didn't start" /
  "overlay says disconnected" symptom.
---

# mcp_server — FastMCP surface + WS bridge to the overlay

## What this is

`mcp_server/` wraps the existing toolkit (`goals`, `guides`, `exile`, `items`,
`catalog`, `integrations.poe2db_client`, `integrations.neversink`) as **MCP
tools** so three surfaces can share one implementation:

- **Claude Code** — launched via the repo's `.mcp.json` (stdio transport)
- **Claude desktop / app** — installed via the `.mcpb` bundle in `mcpb/`
- **Electron overlay** — main.js spawns `python -m mcp_server.server` and
  connects to its WebSocket bridge

The local package is named `mcp_server` (not `mcp`) deliberately, so it
doesn't shadow the installed `mcp` SDK's import path.

## Layout

```
mcp_server/
├── __init__.py
├── server.py          FastMCP entry + tool registration table + stdio main()
├── tools_session.py   welcome, staleness_report
├── tools_goals.py     recommend_next_action, active_goal, next_actionable,
│                     render_goal_tracker, propose_goal_switch
├── tools_state.py     read_player, list_characters, list_leagues,
│                     active_character[s], read_character, read_active_character,
│                     read_league, set_active_character
├── tools_items.py     parse_clipboard_item, query_gem, query_mod_pool, validate_intent
├── tools_guides.py    system guides + creators + case studies + edge taxonomy
├── tools_views.py     display_* push tools — emit view.render events to overlay
├── transport_ws.py    localhost WebSocket bridge (env-gated)
├── _serialize.py      to_jsonable() — dataclass + enum + Path serialization
└── protocol.md        message envelope contract for Electron clients
```

## Entry points

```bash
# Direct stdio launch (what Claude Code does via .mcp.json):
python -m mcp_server.server

# Via the .mcpb bundle (what Claude desktop does):
python <bundle_dir>/bootstrap.py
# bootstrap.py prepends $POE2_GRAPH_ROOT to sys.path then imports mcp_server.server

# From the Electron app (what the overlay does on launch):
spawn('python', ['-m', 'mcp_server.server'], { env: { POE2_GRAPH_ROOT, POE2_MCP_WS_PORT } })
```

All three paths converge on `mcp_server.server.main()`, which:

1. Configures logging to **stderr** (stdout is the MCP transport — never log to it)
2. Calls `transport_ws.start_if_enabled()` — no-op unless `POE2_MCP_WS_PORT` is set
3. Builds the FastMCP instance via `build_server()` (factored out for tests)
4. Calls `server.run()` (blocks on stdio loop)

## Adding a new tool

1. Write a plain Python function in the appropriate `tools_*.py` (or create a new file).
2. Return JSON-serializable types — wrap dataclasses through `_serialize.to_jsonable()`.
3. Register it in `server.py:build_server()` with `mcp.tool()(your_function)`.
4. Add a one-liner to `mcpb/manifest.json`'s `tools[]` so the Claude UI advertises it.
5. Add tests in `tests/test_mcp_server.py`.

The registration table in `server.py` is the source of truth — anything not
registered there is invisible to MCP clients no matter how many top-level
imports point to it.

## WebSocket bridge (transport_ws)

Optional, env-gated. Lives alongside the stdio transport so the same server
process can serve both Claude (stdio) and the Electron overlay (WS).

| Env var | Effect |
|---|---|
| unset | Bridge disabled. `display_*` tools return `{"delivered": 0, "bridge": "disabled"}`. |
| set to a port number | Bridge binds `ws://127.0.0.1:<port>`; overlay connects on launch. |
| set to empty string | Same as unset. |

Lifecycle:

- Bridge starts in a background asyncio task; server keeps running if it
  fails to bind (port conflict, etc.) — `display_*` tools just report
  `bridge: "disabled"` so calling Claude can degrade gracefully.
- Clients send `client.hello` on connect; server replies `state.snapshot`.
- Server retains view state in memory; disconnect/reconnect resyncs via
  another `state.snapshot`.
- Multi-client safe — each connected overlay receives the same broadcast.

The wire format is documented in `mcp_server/protocol.md`. View payload schemas
will align with Path-of-Tools libs (`poe-item-display`, `poe-item-hover-react`)
once those are imported into `electron/overlay/views/`.

## display_* tools — the bridge pattern

Each `tools_views.display_*` function:

1. Calls the underlying analysis tool (`tools_items.parse_clipboard_item`,
   `tools_goals.recommend_next_action`, etc.)
2. Builds a `view.render` payload with a fresh `vw_<hex>` id
3. Emits via `transport_ws.emit_event()` — broadcasts to every connected client
4. Returns `{"ok": True, "view_id": ..., "delivery": ack, ...}` to the
   calling Claude, with `ack` containing `{"delivered": N, "bridge": "live"|"disabled"}`

The Claude side gets both the structured data AND a handle for later
`dismiss_view(view_id)`. The overlay side gets a render event it can dispatch
to the matching `electron/overlay/views/*.js` module.

## Multi-server reality

Every Claude surface launches **its own** Python MCP server process:

- Claude Code → `.mcp.json` → its own `python -m mcp_server.server`
- Claude desktop → `.mcpb` bundle → its own `python bootstrap.py`
- Electron overlay → `main.js` spawn → its own `python -m mcp_server.server`

They do **not** share in-memory state. They share **on-disk** state by all
reading `EXILE/`, `data/`, and `config.yaml` from the same `POE2_GRAPH_ROOT`.
A goal mark-done in one surface is visible to the others on their next call,
not in real time.

## Cross-references

- `DOCS/electron.md` — overlay's side of the WS bridge + Wizard installer
- `DOCS/mcpb.md` — the `.mcpb` bundle for Claude desktop / app
- `mcp_server/protocol.md` — wire format for Electron clients
- `.mcp.json` — Claude Code's launch config
- `DOCS/goals.md`, `DOCS/guides.md`, `DOCS/poe2db.md` — the analysis layer each `tools_*.py` wraps
