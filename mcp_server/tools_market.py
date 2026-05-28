"""Market tools — poe.ninja price oracle and official Trade API wrappers.

Read-mostly. Errors from rate limiting are returned as structured envelopes
so the calling Claude can decide whether to retry or surface the message.
"""

from __future__ import annotations

from typing import Any, Optional

from integrations import poe_ninja
from integrations.poe_ninja import PoeNinjaError
from integrations import trade_api
from integrations.trade_api import TradeApiError, TradeApiRateLimited


def market_currency_overview(
    league: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return currency pricing from poe.ninja for the given league.

    Cached with a 6-hour TTL. Pass force_refresh=True to bypass the cache.
    Returns {ok: True, lines: list[dict], currencyDetails: list[dict]}.
    Each line contains currencyTypeName, chaosEquivalent, pay, receive.
    """
    try:
        data = poe_ninja.fetch_currency_overview(league, force_refresh=force_refresh)
        return {
            "ok": True,
            "lines": data.get("lines", []),
            "currencyDetails": data.get("currencyDetails", []),
        }
    except PoeNinjaError as exc:
        return {"ok": False, "error_type": "PoeNinjaError", "error": str(exc), "retry_after_seconds": None}


def market_get_chaos_value(league: str, currency_name: str) -> dict[str, Any]:
    """Return the chaos equivalent for a named currency from poe.ninja.

    Uses the cached currency overview. Returns {ok: True, currency_name: str,
    chaos_value: float | None}. chaos_value is None if the currency is not
    listed in poe.ninja for this league.
    """
    try:
        value = poe_ninja.get_chaos_value(league, currency_name)
        return {"ok": True, "currency_name": currency_name, "chaos_value": value}
    except PoeNinjaError as exc:
        return {"ok": False, "error_type": "PoeNinjaError", "error": str(exc), "retry_after_seconds": None}


def market_unique_overview(
    league: str,
    category: str = "UniqueWeapon",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return unique item pricing from poe.ninja for the given league and category.

    category must be one of: UniqueWeapon, UniqueArmour, UniqueAccessory,
    UniqueFlask, UniqueJewel, UniqueMap, UniqueRelic.
    Cached with a 6-hour TTL per (league, category) pair.
    Returns {ok: True, lines: list[dict]}.
    """
    try:
        data = poe_ninja.fetch_unique_overview(league, category, force_refresh=force_refresh)
        return {"ok": True, "lines": data.get("lines", [])}
    except PoeNinjaError as exc:
        return {"ok": False, "error_type": "PoeNinjaError", "error": str(exc), "retry_after_seconds": None}


def market_builds_meta(league: str, force_refresh: bool = False) -> dict[str, Any]:
    """Return raw build-meta JSON from poe.ninja for the given league.

    Cached with a 24-hour TTL. Returns {ok: True, data: dict} — the raw
    poe.ninja builds endpoint response, passed through without transformation.
    """
    try:
        data = poe_ninja.fetch_builds_meta(league, force_refresh=force_refresh)
        return {"ok": True, "data": data}
    except PoeNinjaError as exc:
        return {"ok": False, "error_type": "PoeNinjaError", "error": str(exc), "retry_after_seconds": None}


def trade_search(
    league: str,
    query: dict,
    realm: str = "poe2",
) -> dict[str, Any]:
    """Execute a search on the official PoE 2 Trade API.

    query is the standard Trade API JSON body (same structure as the website uses).
    realm is always 'poe2' for PoE 2 searches.
    Returns {ok: True, search_id: str, result_ids: list[str], total: int} on
    success, or an error envelope on network/rate-limit failure. Search results
    are cached for 5 minutes by (league, query hash).
    """
    try:
        data = trade_api.search(league, query, realm=realm)
        return {
            "ok": True,
            "search_id": data.get("id", ""),
            "result_ids": data.get("result", []),
            "total": data.get("total", 0),
        }
    except TradeApiRateLimited as exc:
        return {
            "ok": False,
            "error_type": "TradeApiRateLimited",
            "error": str(exc),
            "retry_after_seconds": exc.retry_after_seconds,
        }
    except TradeApiError as exc:
        return {
            "ok": False,
            "error_type": "TradeApiError",
            "error": str(exc),
            "retry_after_seconds": None,
        }


def trade_fetch_listings(
    item_ids: list[str],
    query_id: str,
    realm: str = "poe2",
) -> dict[str, Any]:
    """Fetch up to 10 listing details from the Trade API.

    item_ids: list of item IDs from a previous trade_search result (max 10).
    query_id: the search_id returned by trade_search — required by the API.
    Returns {ok: True, listings: list[dict]} where each listing contains
    both the 'listing' (price, seller) and 'item' (stats, mods) sub-dicts.
    """
    try:
        data = trade_api.fetch_listings(item_ids, query_id=query_id, realm=realm)
        return {"ok": True, "listings": data.get("result", [])}
    except TradeApiRateLimited as exc:
        return {
            "ok": False,
            "error_type": "TradeApiRateLimited",
            "error": str(exc),
            "retry_after_seconds": exc.retry_after_seconds,
        }
    except TradeApiError as exc:
        return {
            "ok": False,
            "error_type": "TradeApiError",
            "error": str(exc),
            "retry_after_seconds": None,
        }


def trade_search_and_fetch(
    league: str,
    query: dict,
    max_results: int = 10,
    realm: str = "poe2",
) -> dict[str, Any]:
    """Convenience: run a trade search then fetch the first N listings.

    Automatically chunks fetch calls into batches of 10 as required by the API.
    Returns {ok: True, listings: list[dict]} — the flat listing+item list from
    all fetched batches, up to max_results entries.
    """
    try:
        listings = trade_api.search_and_fetch(league, query, max_results=max_results, realm=realm)
        return {"ok": True, "listings": listings}
    except TradeApiRateLimited as exc:
        return {
            "ok": False,
            "error_type": "TradeApiRateLimited",
            "error": str(exc),
            "retry_after_seconds": exc.retry_after_seconds,
        }
    except TradeApiError as exc:
        return {
            "ok": False,
            "error_type": "TradeApiError",
            "error": str(exc),
            "retry_after_seconds": None,
        }


def market_clear_cache() -> dict[str, Any]:
    """Wipe both poe.ninja and trade_api disk caches.

    Removes all files under .cache/poe_ninja/ and .cache/trade_api/. Safe to
    call at any time — the next request will re-fetch from the network.
    Returns {ok: True}.
    """
    poe_ninja.clear_cache()
    trade_api.clear_cache()
    return {"ok": True}
