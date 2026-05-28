"""poe2-graph MCP server — FastMCP wrapper around the toolkit.

Registers every tool function from tools_*.py as an MCP tool. Tools are bare
functions in their respective modules; this file is the registration table
and stdio entry point.

Run:
  python -m mcp_server.server

The .mcp.json at the repo root tells Claude Code to launch this command.

Environment:
  POE2_MCP_WS_PORT  — if set, also start a localhost WebSocket bridge for
                      the Electron overlay on that port. Unset = stdio only.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

# Ensure the repo root is importable so goals/guides/exile/items/catalog resolve
# regardless of where the server is launched from.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server import (  # noqa: E402
    tools_session,
    tools_goals,
    tools_state,
    tools_items,
    tools_guides,
    tools_views,
    tools_farm,
    tools_market,
    tools_clipboard,
    transport_ws,
)


def build_server() -> FastMCP:
    """Construct the FastMCP instance with every tool registered.

    Factored out so tests can introspect the tool registry without entering
    `mcp.run()` (which would block on stdio).
    """
    mcp = FastMCP("poe2-graph")

    # --- session ---
    mcp.tool()(tools_session.welcome)
    mcp.tool()(tools_session.staleness_report)

    # --- goals ---
    mcp.tool()(tools_goals.recommend_next_action)
    mcp.tool()(tools_goals.active_goal)
    mcp.tool()(tools_goals.next_actionable)
    mcp.tool()(tools_goals.render_goal_tracker)
    mcp.tool()(tools_goals.propose_goal_switch)

    # --- state ---
    mcp.tool()(tools_state.read_player)
    mcp.tool()(tools_state.list_characters)
    mcp.tool()(tools_state.list_leagues)
    mcp.tool()(tools_state.active_character)
    mcp.tool()(tools_state.active_characters)
    mcp.tool()(tools_state.read_character)
    mcp.tool()(tools_state.read_active_character)
    mcp.tool()(tools_state.read_league)
    mcp.tool()(tools_state.set_active_character)

    # --- items + catalog ---
    mcp.tool()(tools_items.parse_clipboard_item)
    mcp.tool()(tools_items.query_gem)
    mcp.tool()(tools_items.query_mod_pool)
    mcp.tool()(tools_items.validate_intent)

    # --- guides ---
    mcp.tool()(tools_guides.load_system_guide)
    mcp.tool()(tools_guides.list_system_guides)
    mcp.tool()(tools_guides.system_guides_for_edge)
    mcp.tool()(tools_guides.load_creator)
    mcp.tool()(tools_guides.list_creators)
    mcp.tool()(tools_guides.creators_who_transmit)
    mcp.tool()(tools_guides.load_case_study)
    mcp.tool()(tools_guides.list_case_studies)
    mcp.tool()(tools_guides.load_edge_taxonomy)

    # --- farm cycles ---
    mcp.tool()(tools_farm.farm_declare_cycle)
    mcp.tool()(tools_farm.farm_open_cycle)
    mcp.tool()(tools_farm.farm_record_output)
    mcp.tool()(tools_farm.farm_classify_outputs)
    mcp.tool()(tools_farm.farm_reconcile_cycle)
    mcp.tool()(tools_farm.farm_close_cycle)
    mcp.tool()(tools_farm.farm_get_cycle)
    mcp.tool()(tools_farm.farm_list_cycles)
    mcp.tool()(tools_farm.farm_export_cycle_bundle)

    # --- market (poe.ninja + trade) ---
    mcp.tool()(tools_market.market_currency_overview)
    mcp.tool()(tools_market.market_get_chaos_value)
    mcp.tool()(tools_market.market_unique_overview)
    mcp.tool()(tools_market.market_builds_meta)
    mcp.tool()(tools_market.trade_search)
    mcp.tool()(tools_market.trade_fetch_listings)
    mcp.tool()(tools_market.trade_search_and_fetch)
    mcp.tool()(tools_market.market_clear_cache)

    # --- clipboard queue ---
    mcp.tool()(tools_clipboard.clipboard_queue_status)
    mcp.tool()(tools_clipboard.clipboard_drain_into_cycle)
    mcp.tool()(tools_clipboard.clipboard_peek_queue)
    mcp.tool()(tools_clipboard.clipboard_clear_queue)

    # --- views (Electron overlay) ---
    mcp.tool()(tools_views.display_item_tooltip)
    mcp.tool()(tools_views.display_goal_tracker)
    mcp.tool()(tools_views.display_next_action_card)
    mcp.tool()(tools_views.start_map_timer)
    mcp.tool()(tools_views.dismiss_view)
    mcp.tool()(tools_views.overlay_status)
    mcp.tool()(tools_views.display_cycle_status)
    mcp.tool()(tools_views.display_classify_alert)
    mcp.tool()(tools_views.display_reconcile_warning)
    mcp.tool()(tools_views.display_cycle_summary)

    return mcp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,  # stdout is the MCP transport; keep logs on stderr
    )

    # Wire the messenger event bus into the transport. The home window (and
    # any future Lua client) subscribes via WebSocket; this is where the
    # publishers (server lifecycle, tools_views) connect to the network layer.
    from integrations import messenger
    messenger.register_transport(transport_ws.emit_event)
    transport_ws.set_snapshot_provider(messenger.snapshot)
    messenger.install_log_handler()

    pid = os.getpid()
    messenger.publish("server.state", {"state": "starting", "pid": pid})

    transport_ws.start_if_enabled()
    if transport_ws.is_enabled():
        messenger.publish(
            "ws.state",
            {"state": "starting", "port": transport_ws.configured_port()},
        )
    else:
        messenger.publish("ws.state", {"state": "unconfigured"})

    messenger.publish("server.state", {"state": "ready", "pid": pid})

    # WS-only mode: the spawning process (Electron overlay) doesn't talk MCP
    # over stdio — it only consumes WebSocket events from `tools_views.display_*`.
    # The FastMCP stdio loop would read EOF immediately (stdio:'ignore' from
    # Electron's `spawn`) and the main thread would return, taking the WS
    # daemon thread with it. Block on a never-set Event instead so the
    # process stays alive until tree-killed on app quit.
    if os.environ.get("POE2_MCP_WS_ONLY") == "1":
        log = logging.getLogger(__name__)
        log.info("WS-only mode: stdio MCP disabled; running until terminated")
        threading.Event().wait()
        return

    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
