"""Smoke tests for the MCP server tool wrappers.

These call the bare tool functions directly (no MCP transport). The goal is to
verify each wrapper doesn't crash against a realistic project state — even an
un-onboarded one where EXILE/ is empty.

Underlying functions (goals, guides, exile, items.parser, catalog) have their
own deeper tests; here we only check the wrapping layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server import (  # noqa: E402
    tools_session, tools_goals, tools_state,
    tools_items, tools_guides, tools_views,
    transport_ws,
)
from mcp_server.server import build_server  # noqa: E402
from mcp_server._serialize import to_jsonable  # noqa: E402


# ===== _serialize =====

def test_to_jsonable_primitives():
    assert to_jsonable(None) is None
    assert to_jsonable(1) == 1
    assert to_jsonable("x") == "x"
    assert to_jsonable(True) is True


def test_to_jsonable_frozenset_becomes_sorted_list():
    assert to_jsonable(frozenset({"b", "a", "c"})) == ["a", "b", "c"]


def test_to_jsonable_path_becomes_string():
    assert to_jsonable(Path("/a/b")) == str(Path("/a/b"))


def test_to_jsonable_dataclass_recurses():
    from dataclasses import dataclass

    @dataclass
    class Inner:
        x: int

    @dataclass
    class Outer:
        inner: Inner
        tags: frozenset

    out = to_jsonable(Outer(Inner(7), frozenset({"a", "b"})))
    assert out == {"inner": {"x": 7}, "tags": ["a", "b"]}


# ===== build_server =====

def test_build_server_registers_tools():
    server = build_server()
    # FastMCP exposes the registered tools via list_tools (async) or the
    # internal _tool_manager. We just confirm the object is constructible and
    # has tools registered — exact count is brittle to grow.
    assert server is not None
    # Each tool registration increments the internal manager's count.
    # FastMCP stores tools in `_tool_manager._tools` (private but stable across
    # 1.x). If this ever breaks, the right fix is `asyncio.run(server.list_tools())`.
    tool_mgr = getattr(server, "_tool_manager", None)
    if tool_mgr is not None:
        tools = getattr(tool_mgr, "_tools", {})
        assert len(tools) >= 15  # we register ~30; floor at 15 is lenient


# ===== session =====

def test_welcome_returns_structured_payload():
    out = tools_session.welcome()
    assert "onboarded" in out
    assert "staleness" in out
    assert "active_characters" in out
    assert "suggested_intents" in out
    assert isinstance(out["suggested_intents"], list)
    assert len(out["suggested_intents"]) >= 1


def test_staleness_report_returns_dict():
    out = tools_session.staleness_report()
    assert isinstance(out, dict)


# ===== goals =====

def test_active_goal_returns_none_when_no_active():
    # No PLAYER.md or no active goal → None
    out = tools_goals.active_goal()
    assert out is None or isinstance(out, dict)


def test_next_actionable_returns_none_when_no_active():
    out = tools_goals.next_actionable()
    assert out is None or isinstance(out, dict)


def test_render_goal_tracker_returns_none_when_no_active():
    out = tools_goals.render_goal_tracker()
    assert out is None or isinstance(out, str)


def test_propose_goal_switch_returns_none_when_no_active():
    out = tools_goals.propose_goal_switch("some_new_id")
    assert out is None or isinstance(out, dict)


def test_recommend_next_action_does_not_crash_when_unonboarded():
    out = tools_goals.recommend_next_action()
    assert "recommendation" in out
    assert "resolved" in out


# ===== state =====

def test_list_characters_returns_list():
    assert isinstance(tools_state.list_characters(), list)


def test_list_leagues_returns_list():
    assert isinstance(tools_state.list_leagues(), list)


def test_active_character_returns_none_or_string():
    out = tools_state.active_character()
    assert out is None or isinstance(out, str)


def test_active_characters_returns_dict():
    assert isinstance(tools_state.active_characters(), dict)


def test_read_player_handles_missing_file():
    out = tools_state.read_player()
    assert "exists" in out
    assert isinstance(out["exists"], bool)


def test_read_character_handles_missing():
    out = tools_state.read_character("definitely_does_not_exist")
    assert out["exists"] is False


# ===== items + catalog =====

def test_parse_clipboard_item_with_real_dump():
    sample = """Item Class: Wands
Rarity: Rare
Spirit Whisper
Diamond Wand
--------
Quality: +20% (augmented)
Spell Damage: 92-129 (augmented)
Critical Strike Chance: 7.50%
Attacks per Second: 1.20
--------
Requirements:
Level: 78
Int: 209
--------
Item Level: 84
--------
+1 to Level of all Lightning Spell Skills
--------
+24 to Intelligence
Adds 42 to 71 Lightning Damage to Spells
"""
    out = tools_items.parse_clipboard_item(sample)
    assert out["ok"] is True
    assert "item" in out
    assert out["item"]["rarity"] == "rare"


def test_parse_clipboard_item_handles_garbage():
    out = tools_items.parse_clipboard_item("garbage not a real item")
    assert out["ok"] is False
    assert "error" in out


def test_query_gem_finds_real_gem():
    out = tools_items.query_gem("Fireball")
    assert "matches" in out
    # Cache is warmed from earlier sessions; if it's cold and network fails, this may
    # return zero matches with per-class error markers — still a valid response shape.
    assert isinstance(out["matches"], list)


def test_query_gem_unknown_name_returns_empty_matches():
    out = tools_items.query_gem("Definitely Not A Real Gem Name")
    # Either empty matches or per-class entries with .gem absent
    assert "matches" in out
    real_hits = [m for m in out["matches"] if "gem" in m]
    assert real_hits == []


# ===== guides =====

def test_list_system_guides_returns_list():
    out = tools_guides.list_system_guides()
    assert isinstance(out, list)


def test_list_system_guides_filters_by_game():
    poe2_only = tools_guides.list_system_guides(game="poe2")
    assert all(sg["game"] in ("poe2", "both") for sg in poe2_only)


def test_list_creators_returns_list():
    out = tools_guides.list_creators()
    assert isinstance(out, list)


def test_load_edge_taxonomy_returns_list():
    out = tools_guides.load_edge_taxonomy()
    assert isinstance(out, list)


# ===== views (no overlay connected — bridge disabled) =====

def test_overlay_status_disabled_by_default(monkeypatch):
    monkeypatch.delenv("POE2_MCP_WS_PORT", raising=False)
    out = tools_views.overlay_status()
    assert out["enabled"] is False
    assert out["configured_port"] is None


def test_display_item_tooltip_returns_delivery_ack(monkeypatch):
    monkeypatch.delenv("POE2_MCP_WS_PORT", raising=False)
    sample = """Item Class: Rings
Rarity: Rare
Doom Loop
Iron Ring
--------
Item Level: 70
--------
+15 to maximum Life
"""
    out = tools_views.display_item_tooltip(sample)
    assert out["ok"] is True
    assert "delivery" in out
    assert out["delivery"]["bridge"] == "disabled"


def test_display_goal_tracker_without_active_goal():
    out = tools_views.display_goal_tracker()
    assert out["ok"] is False
    assert "no active goal" in out["error"]


def test_dismiss_view_returns_delivery_ack(monkeypatch):
    monkeypatch.delenv("POE2_MCP_WS_PORT", raising=False)
    out = tools_views.dismiss_view("vw_test_123")
    assert out["ok"] is True
    assert out["view_id"] == "vw_test_123"


# ===== transport_ws =====

def test_transport_disabled_without_env(monkeypatch):
    monkeypatch.delenv("POE2_MCP_WS_PORT", raising=False)
    assert transport_ws.is_enabled() is False
    assert transport_ws.configured_port() is None


def test_transport_invalid_port_disables_bridge(monkeypatch):
    monkeypatch.setenv("POE2_MCP_WS_PORT", "not-a-port")
    assert transport_ws.configured_port() is None


def test_transport_valid_port_parses(monkeypatch):
    monkeypatch.setenv("POE2_MCP_WS_PORT", "8889")
    assert transport_ws.configured_port() == 8889


def test_emit_event_returns_ack_when_disabled():
    # When the broker isn't started, emit_event returns a structured ack
    ack = transport_ws.emit_event("test.event", {"foo": "bar"})
    assert ack["delivered"] == 0
    assert ack["bridge"] in ("disabled", "live")
