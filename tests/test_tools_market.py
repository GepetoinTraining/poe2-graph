"""Tests for mcp_server.tools_market — dict-in / dict-out contract.

HTTP is fully mocked — no real network calls.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server import tools_market
from integrations.trade_api import TradeApiRateLimited, TradeApiError
from integrations.poe_ninja import PoeNinjaError


# Shared fixture for a fake currency overview response.
FAKE_CURRENCY_OVERVIEW = {
    "lines": [
        {"currencyTypeName": "Chaos Orb", "chaosEquivalent": 1.0, "pay": None, "receive": None},
        {"currencyTypeName": "Divine Orb", "chaosEquivalent": 200.0, "pay": None, "receive": None},
    ],
    "currencyDetails": [
        {"id": 1, "icon": "", "name": "Chaos Orb", "tradeId": "chaos"},
    ],
}

FAKE_UNIQUE_OVERVIEW = {
    "lines": [
        {"name": "Headhunter", "chaosValue": 25000.0},
    ],
}

FAKE_BUILDS_META = {"builds": []}

FAKE_TRADE_SEARCH = {"id": "search123", "result": ["a1", "a2", "a3"], "total": 3}
FAKE_TRADE_FETCH = {"result": [{"listing": {"price": {"amount": 5}}, "item": {"name": "Ring"}}]}


# ---- market_currency_overview ----

def test_currency_overview_returns_lines(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", return_value=FAKE_CURRENCY_OVERVIEW):
        result = tools_market.market_currency_overview("Standard", force_refresh=True)
    assert result["ok"] is True
    assert len(result["lines"]) == 2
    assert "currencyDetails" in result


def test_currency_overview_poe_ninja_error(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", side_effect=PoeNinjaError("network down")):
        result = tools_market.market_currency_overview("Standard", force_refresh=True)
    assert result["ok"] is False
    assert result["error_type"] == "PoeNinjaError"
    assert result["retry_after_seconds"] is None


# ---- market_get_chaos_value ----

def test_get_chaos_value_found(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", return_value=FAKE_CURRENCY_OVERVIEW):
        result = tools_market.market_get_chaos_value("Standard", "Divine Orb")
    assert result["ok"] is True
    assert result["chaos_value"] == 200.0


def test_get_chaos_value_not_found(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", return_value=FAKE_CURRENCY_OVERVIEW):
        result = tools_market.market_get_chaos_value("Standard", "Mirror of Kalandra")
    assert result["ok"] is True
    assert result["chaos_value"] is None


# ---- market_unique_overview ----

def test_unique_overview_returns_lines(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", return_value=FAKE_UNIQUE_OVERVIEW):
        result = tools_market.market_unique_overview("Standard", "UniqueWeapon", force_refresh=True)
    assert result["ok"] is True
    assert len(result["lines"]) == 1


def test_unique_overview_bad_category_returns_error(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    result = tools_market.market_unique_overview("Standard", "NotARealCategory")
    assert result["ok"] is False
    assert result["error_type"] == "PoeNinjaError"


# ---- market_builds_meta ----

def test_builds_meta_returns_data(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    with patch("integrations.poe_ninja._fetch_json", return_value=FAKE_BUILDS_META):
        result = tools_market.market_builds_meta("Standard", force_refresh=True)
    assert result["ok"] is True
    assert "data" in result


# ---- trade_search ----

def test_trade_search_returns_structured_result():
    with patch("integrations.trade_api._do_post", return_value=FAKE_TRADE_SEARCH):
        with patch("integrations.trade_api._cache_fresh", return_value=False):
            result = tools_market.trade_search("Standard", {"query": {}})
    assert result["ok"] is True
    assert result["search_id"] == "search123"
    assert result["total"] == 3
    assert "result_ids" in result


def test_trade_search_rate_limited_returns_error():
    exc = TradeApiRateLimited(retry_after_seconds=30.0)
    with patch("integrations.trade_api._do_post", side_effect=exc):
        with patch("integrations.trade_api._cache_fresh", return_value=False):
            result = tools_market.trade_search("Standard", {"query": {}})
    assert result["ok"] is False
    assert result["error_type"] == "TradeApiRateLimited"
    assert result["retry_after_seconds"] == 30.0


def test_trade_search_generic_error_returns_error():
    exc = TradeApiError("HTTP 500 from trade API", status=500)
    with patch("integrations.trade_api._do_post", side_effect=exc):
        with patch("integrations.trade_api._cache_fresh", return_value=False):
            result = tools_market.trade_search("Standard", {"query": {}})
    assert result["ok"] is False
    assert result["error_type"] == "TradeApiError"
    assert result["retry_after_seconds"] is None


# ---- trade_fetch_listings ----

def test_trade_fetch_listings_returns_listings():
    with patch("integrations.trade_api._do_get", return_value=FAKE_TRADE_FETCH):
        result = tools_market.trade_fetch_listings(["a1"], query_id="search123")
    assert result["ok"] is True
    assert len(result["listings"]) == 1


def test_trade_fetch_listings_rate_limited():
    exc = TradeApiRateLimited(retry_after_seconds=60.0)
    with patch("integrations.trade_api._do_get", side_effect=exc):
        result = tools_market.trade_fetch_listings(["a1"], query_id="search123")
    assert result["ok"] is False
    assert result["retry_after_seconds"] == 60.0


# ---- trade_search_and_fetch ----

def test_trade_search_and_fetch_combines_steps():
    with patch("integrations.trade_api._do_post", return_value=FAKE_TRADE_SEARCH):
        with patch("integrations.trade_api._cache_fresh", return_value=False):
            with patch("integrations.trade_api._do_get", return_value=FAKE_TRADE_FETCH):
                result = tools_market.trade_search_and_fetch("Standard", {"query": {}}, max_results=3)
    assert result["ok"] is True
    assert "listings" in result


# ---- market_clear_cache ----

def test_market_clear_cache_returns_ok(tmp_path, monkeypatch):
    import integrations.poe_ninja as pn
    import integrations.trade_api as ta
    monkeypatch.setattr(pn, "CACHE_DIR", tmp_path / "poe_ninja")
    monkeypatch.setattr(ta, "CACHE_DIR", tmp_path / "trade_api")
    result = tools_market.market_clear_cache()
    assert result["ok"] is True
