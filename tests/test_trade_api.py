"""Trade API client tests — no real network calls.

All HTTP is intercepted with unittest.mock. Cache is redirected to a tmp_path
fixture so tests are hermetic and leave no artifacts.
"""

from __future__ import annotations

import json
import time
import sys
import urllib.error
import urllib.request
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import integrations.trade_api as ta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEAGUE = "Standard"

SEARCH_RESPONSE = {
    "id": "abc123",
    "result": [f"item{i}" for i in range(20)],
    "total": 20,
}

FETCH_RESPONSE = {
    "result": [
        {"listing": {"price": {"amount": 1, "currency": "chaos"}}, "item": {"name": "Waystone"}}
        for _ in range(10)
    ]
}

QUERY = {
    "query": {"status": {"option": "online"}, "type": "Waystone"},
    "sort": {"price": "asc"},
}


def _fake_urlopen_factory(
    response_body: dict,
    status: int = 200,
    headers: dict | None = None,
):
    """Return a context-manager mock that urlopen() can be patched with."""

    def _make_resp():
        raw = json.dumps(response_body).encode()
        resp = MagicMock()
        resp.read.return_value = raw
        resp.status = status
        hdr_dict = headers or {}

        class FakeHeaders:
            def items(self):
                return hdr_dict.items()

            def get(self, key, default=None):
                return hdr_dict.get(key, default)

        resp.headers = FakeHeaders()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    cm = _make_resp()
    return cm


def _http_error(code: int, headers: dict | None = None, body: bytes = b"error"):
    """Build a urllib.error.HTTPError for testing error paths."""
    hdr_dict = headers or {}

    class FakeHeaders:
        def get(self, key, default=None):
            return hdr_dict.get(key, default)

        def items(self):
            return hdr_dict.items()

    exc = urllib.error.HTTPError(
        url="https://example.com",
        code=code,
        msg=f"HTTP {code}",
        hdrs=FakeHeaders(),
        fp=BytesIO(body),
    )
    # Attach a .read() that returns body so our error handler can read it.
    exc.read = lambda: body
    return exc


# ---------------------------------------------------------------------------
# Reset module-level state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_state():
    """Each test starts with a fresh rate-limit state."""
    ta._rate_state = ta.RateLimitState()
    yield
    ta._rate_state = ta.RateLimitState()


# ---------------------------------------------------------------------------
# Test 1: search POSTs to the correct URL with the league in the path
# ---------------------------------------------------------------------------

def test_search_posts_to_correct_url(tmp_path):
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm) as mock_open:
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    mock_open.assert_called_once()
    req_arg = mock_open.call_args[0][0]
    assert f"/search/{LEAGUE}" in req_arg.full_url
    assert req_arg.method == "POST"


# ---------------------------------------------------------------------------
# Test 2: body is correctly JSON-encoded
# ---------------------------------------------------------------------------

def test_search_body_is_json_encoded(tmp_path):
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm) as mock_open:
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    req_arg = mock_open.call_args[0][0]
    sent_body = json.loads(req_arg.data.decode("utf-8"))
    assert sent_body == QUERY


# ---------------------------------------------------------------------------
# Test 3: User-Agent and Content-Type headers are set
# ---------------------------------------------------------------------------

def test_search_headers(tmp_path):
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm) as mock_open:
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    req_arg = mock_open.call_args[0][0]
    assert req_arg.get_header("User-agent") == ta.USER_AGENT
    assert req_arg.get_header("Content-type") == "application/json"


# ---------------------------------------------------------------------------
# Test 4: search response cached on first call, served from cache on second
# ---------------------------------------------------------------------------

def test_search_cached_on_second_call(tmp_path):
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm) as mock_open:
        r1 = ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
        r2 = ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    # urlopen called only once — second call served from cache
    assert mock_open.call_count == 1
    assert r1 == r2 == SEARCH_RESPONSE


# ---------------------------------------------------------------------------
# Test 5: different query hashes -> different cache files
# ---------------------------------------------------------------------------

def test_different_queries_different_cache_files(tmp_path):
    query_a = {"query": {"type": "Waystone"}, "sort": {"price": "asc"}}
    query_b = {"query": {"type": "Map"}, "sort": {"price": "asc"}}
    cm_a = _fake_urlopen_factory({"id": "aaaa", "result": [], "total": 0})
    cm_b = _fake_urlopen_factory({"id": "bbbb", "result": [], "total": 0})
    with patch("urllib.request.urlopen", side_effect=[cm_a, cm_b]):
        ta.search(LEAGUE, query_a, _cache_dir=tmp_path)
        ta.search(LEAGUE, query_b, _cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("search__*.json"))
    assert len(cache_files) == 2


# ---------------------------------------------------------------------------
# Test 6: force_refresh=True bypasses cache
# ---------------------------------------------------------------------------

def test_force_refresh_bypasses_cache(tmp_path):
    cm1 = _fake_urlopen_factory(SEARCH_RESPONSE)
    cm2 = _fake_urlopen_factory({**SEARCH_RESPONSE, "id": "refreshed"})
    with patch("urllib.request.urlopen", side_effect=[cm1, cm2]) as mock_open:
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
        r2 = ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    assert mock_open.call_count == 2
    assert r2["id"] == "refreshed"


# ---------------------------------------------------------------------------
# Test 7: fetch_listings hits /fetch/<csv-ids>?query=<id>
# ---------------------------------------------------------------------------

def test_fetch_listings_url(tmp_path):
    ids = [f"item{i}" for i in range(5)]
    qid = "abc123"
    cm = _fake_urlopen_factory(FETCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm) as mock_open:
        ta.fetch_listings(ids, query_id=qid)
    req_arg = mock_open.call_args[0][0]
    url = req_arg.full_url
    assert "/fetch/" in url
    assert ",".join(ids) in url
    assert f"query={qid}" in url
    assert req_arg.method == "GET"


# ---------------------------------------------------------------------------
# Test 8: fetch_listings with >10 IDs raises ValueError
# ---------------------------------------------------------------------------

def test_fetch_listings_rejects_more_than_10():
    ids = [f"item{i}" for i in range(11)]
    with pytest.raises(ValueError, match="at most 10"):
        ta.fetch_listings(ids, query_id="abc")


# ---------------------------------------------------------------------------
# Test 9: search_and_fetch chunks >10 into multiple fetch calls
# ---------------------------------------------------------------------------

def test_search_and_fetch_chunks_into_batches(tmp_path):
    # search returns 25 IDs; max_results=25 -> 3 fetch batches (10+10+5)
    search_resp = {"id": "sid", "result": [f"i{n}" for n in range(25)], "total": 25}
    fetch_resp = {"result": [{"listing": {}, "item": {}}] * 10}
    fetch_resp_last = {"result": [{"listing": {}, "item": {}}] * 5}

    search_cm = _fake_urlopen_factory(search_resp)
    fetch_cm1 = _fake_urlopen_factory(fetch_resp)
    fetch_cm2 = _fake_urlopen_factory(fetch_resp)
    fetch_cm3 = _fake_urlopen_factory(fetch_resp_last)

    with patch("urllib.request.urlopen", side_effect=[search_cm, fetch_cm1, fetch_cm2, fetch_cm3]) as mock_open:
        results = ta.search_and_fetch(LEAGUE, QUERY, max_results=25, _cache_dir=tmp_path)

    # 4 HTTP calls total: 1 search + 3 fetches
    assert mock_open.call_count == 4
    assert len(results) == 25


# ---------------------------------------------------------------------------
# Test 10: rate-limit state: parse X-Rate-Limit-Ip and -Ip-State correctly
# ---------------------------------------------------------------------------

def test_rate_limit_state_parsing():
    state = ta.RateLimitState()
    state.update({
        "X-Rate-Limit-Ip": "8:10:60,15:60:120",
        "X-Rate-Limit-Ip-State": "5:10:0,11:60:0",
    })
    # 5/8 = 62.5%, 11/15 = 73.3% — both below 80% threshold, no sleep needed
    assert state.seconds_to_sleep() == 0.0

    # Push first dimension to 80%: 7/8 = 87.5%, keep second below: 11/15 = 73%
    state2 = ta.RateLimitState()
    state2.update({
        "X-Rate-Limit-Ip": "8:10:60,15:60:120",
        "X-Rate-Limit-Ip-State": "7:10:0,11:60:0",
    })
    # Should trigger sleep for 10s (first window = 10s, since 7/8 >= 80%)
    assert state2.seconds_to_sleep() == 10.0


# ---------------------------------------------------------------------------
# Test 11: when state >= 80% of limit, client sleeps
# ---------------------------------------------------------------------------

def test_client_sleeps_when_near_rate_limit(tmp_path):
    # Pre-load rate state to be at 80% of limit.
    # "8:10:60" = 8 hits per 10s window; state "7:10:0" = 7 used -> 87.5% >= 80%.
    ta._rate_state.update({
        "X-Rate-Limit-Ip": "8:10:60",
        "X-Rate-Limit-Ip-State": "7:10:0",
    })
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm):
        with patch("integrations.trade_api.time.sleep") as mock_sleep:
            ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    # Sleep for 10s (the window duration for the triggered slot).
    mock_sleep.assert_called_once_with(10.0)


# ---------------------------------------------------------------------------
# Test 12: HTTP 429 -> TradeApiRateLimited with retry-after if header present
# ---------------------------------------------------------------------------

def test_http_429_raises_rate_limited(tmp_path):
    exc = _http_error(429, headers={"Retry-After": "30"})
    with patch("urllib.request.urlopen", side_effect=exc):
        with pytest.raises(ta.TradeApiRateLimited) as exc_info:
            ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    assert exc_info.value.retry_after_seconds == 30.0
    assert exc_info.value.status == 429


def test_http_429_no_retry_after(tmp_path):
    exc = _http_error(429)
    with patch("urllib.request.urlopen", side_effect=exc):
        with pytest.raises(ta.TradeApiRateLimited) as exc_info:
            ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    assert exc_info.value.retry_after_seconds is None


# ---------------------------------------------------------------------------
# Test 13: HTTP 500 -> TradeApiError with status in message
# ---------------------------------------------------------------------------

def test_http_500_raises_trade_api_error(tmp_path):
    exc = _http_error(500, body=b"Internal Server Error")
    with patch("urllib.request.urlopen", side_effect=exc):
        with pytest.raises(ta.TradeApiError) as exc_info:
            ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    err = exc_info.value
    assert err.status == 500
    assert "500" in str(err)
    # TradeApiError is not TradeApiRateLimited
    assert not isinstance(err, ta.TradeApiRateLimited)


# ---------------------------------------------------------------------------
# Test 14: Network error -> TradeApiError
# ---------------------------------------------------------------------------

def test_network_error_raises_trade_api_error(tmp_path):
    net_exc = urllib.error.URLError(reason="Connection refused")
    with patch("urllib.request.urlopen", side_effect=net_exc):
        with pytest.raises(ta.TradeApiError) as exc_info:
            ta.search(LEAGUE, QUERY, force_refresh=True, _cache_dir=tmp_path)
    assert "Network error" in str(exc_info.value)
    assert exc_info.value.status is None


# ---------------------------------------------------------------------------
# Test 15: clear_cache removes files from cache dir
# ---------------------------------------------------------------------------

def test_clear_cache(tmp_path):
    cm = _fake_urlopen_factory(SEARCH_RESPONSE)
    with patch("urllib.request.urlopen", return_value=cm):
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    assert any(tmp_path.glob("search__*.json"))
    ta.clear_cache(tmp_path)
    assert not any(tmp_path.glob("search__*.json"))


# ---------------------------------------------------------------------------
# Test 16: TradeApiRateLimited is subclass of TradeApiError
# ---------------------------------------------------------------------------

def test_rate_limited_is_subclass():
    err = ta.TradeApiRateLimited(15.0)
    assert isinstance(err, ta.TradeApiError)
    assert err.status == 429
    assert err.retry_after_seconds == 15.0


# ---------------------------------------------------------------------------
# Test 17: search_and_fetch respects max_results <= 10 (no chunking needed)
# ---------------------------------------------------------------------------

def test_search_and_fetch_single_batch(tmp_path):
    search_resp = {"id": "sid", "result": [f"i{n}" for n in range(20)], "total": 20}
    fetch_resp = {"result": [{"listing": {}, "item": {}}] * 5}
    search_cm = _fake_urlopen_factory(search_resp)
    fetch_cm = _fake_urlopen_factory(fetch_resp)
    with patch("urllib.request.urlopen", side_effect=[search_cm, fetch_cm]) as mock_open:
        results = ta.search_and_fetch(LEAGUE, QUERY, max_results=5, _cache_dir=tmp_path)
    # 1 search + 1 fetch
    assert mock_open.call_count == 2
    assert len(results) == 5


# ---------------------------------------------------------------------------
# Test 18: rate-limit state with account headers (fallback)
# ---------------------------------------------------------------------------

def test_rate_limit_state_account_headers():
    state = ta.RateLimitState()
    state.update({
        "X-Rate-Limit-Account": "10:10:60",
        "X-Rate-Limit-Account-State": "9:10:0",
    })
    # 9/10 = 90% >= 80% -> should sleep 10s (the 10s window)
    assert state.seconds_to_sleep() == 10.0


# ---------------------------------------------------------------------------
# Test 19: cache respects TTL (expired cache triggers re-fetch)
# ---------------------------------------------------------------------------

def test_expired_cache_triggers_refetch(tmp_path):
    cm1 = _fake_urlopen_factory(SEARCH_RESPONSE)
    cm2 = _fake_urlopen_factory({**SEARCH_RESPONSE, "id": "new_id"})
    with patch("urllib.request.urlopen", side_effect=[cm1, cm2]) as mock_open:
        ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
        # Manually expire the cache by rewriting it with fetched_at far in the past.
        qhash = ta._query_hash(QUERY)
        cpath = ta._cache_path(LEAGUE, qhash, tmp_path)
        envelope = json.loads(cpath.read_text())
        from datetime import timedelta
        old_time = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            - timedelta(seconds=400)
        ).isoformat()
        envelope["fetched_at"] = old_time
        cpath.write_text(json.dumps(envelope))
        # Second call should re-fetch because TTL=300 has passed.
        result = ta.search(LEAGUE, QUERY, _cache_dir=tmp_path)
    assert mock_open.call_count == 2
    assert result["id"] == "new_id"
