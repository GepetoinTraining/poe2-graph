"""mcp_server — Model Context Protocol server wrapping the poe2-graph toolkit.

Exposes the existing analysis layer (goals, guides, exile, items, catalog,
poe2db_client, neversink) as MCP tools so Claude Web, Claude Code, and the
forthcoming Electron overlay can all share one tool surface.

Local package name is `mcp_server` (not `mcp`) to avoid shadowing the
installed `mcp` SDK's import path.

Layout:
  server.py          — FastMCP instance + tool registration + stdio entry
  tools_session.py   — welcome, staleness_report
  tools_goals.py     — recommend_next_action, render_goal_tracker, switch intervention
  tools_state.py     — read_player / read_active_character / list_characters
  tools_items.py     — parse_clipboard_item, query_gem, query_mod_pool, validate_intent
  tools_guides.py    — system guides, creators, case studies
  tools_views.py     — display_* push tools (Electron overlay)
  transport_ws.py    — WebSocket bridge to Electron (Phase 2 wiring laid)
  protocol.md        — message envelope contract for Electron-side clients

Run with:
  python -m mcp_server.server

The companion .mcp.json at the repo root points Claude Code at this entry.
"""
