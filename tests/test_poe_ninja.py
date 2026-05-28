"""Tests for integrations.poe_ninja -- all HTTP mocked, no real network calls."""

from __future__ import annotations

import io
import json
import sys
import time
import unittest.mock as mock
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import integrations.poe_ninja as ninja  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CURRENCY_FIXTURE = {
    "lines": [
        {
            "currencyTypeName": "Divine Orb",
            "chaosEquivalent": 150.0,
            "pay": {"value": 150.0},
            "receive": {"value": 148.5},
        },
        {
            "currencyTypeName": "Exalted Orb",
            "chaosEquivalent": 7.5,
            "pay": {"value": 7.5},
            "receive": None,
        },
    ],
    "currencyDetails": [
        {"id": 1, "name": "Divine Orb", "icon": "https://example.com/divine.png"},
        {"id": 2, "name": "Exalted Orb", "icon": "https://example.com/exalted.png"},
    ],
}

UNIQUE_FIXTURE = {
    "lines": [
        {"name": "Starforge", "chaosValue": 200.0, "exaltedValue": 1.33},
    ],
}

BUILDS_FIXTURE = {
    "data": [
        {"name": "Build A", "class": "Warrior", "main_skill": "Boneshatter"},
    ],
}


def _make_urlopen_mock(payload: dict, status: int = 200):
    """Return a context-manager mock that yields a response-like object."""
    body = json.dumps(payload).encode("utf-8")
    resp = mock.MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = mock.MagicMock(return_value=False)
    return mock.MagicMock(return_value=resp)


# ---------------------------------------------------------------------------
# Helper: redirect cache dir to tmp_path for each test
# ---------------------------------------------------------------------------

def _redirect_cache(tmp_path: Path) -> None:
    """Point ninja.CACHE_DIR at a per-test temp directory."""
    ninja.CACHE_DIR = tmp_path / "poe_ninja"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fetch_currency_overview_correct_url(tmp_path):
    """fetch_currency_overview must call the PoE 2 currency endpoint."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        result = ninja.fetch_currency_overview("Standard")

    assert result == CURRENCY_FIXTURE
    call_args = urlopen_mock.call_args[0][0]  # the Request object
    assert "poe2" in call_args.full_url
    assert "league=Standard" in call_args.full_url
    assert "type=Currency" in call_args.full_url


def test_user_agent_header_is_set(tmp_path):
    """The User-Agent header must be present on outbound requests."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Standard")

    req = urlopen_mock.call_args[0][0]
    ua = req.get_header("User-agent")
    assert ua is not None
    assert "poe2-graph" in ua


def test_cache_hit_avoids_network(tmp_path):
    """Second call within TTL must not hit the network."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Standard")
        ninja.fetch_currency_overview("Standard")

    assert urlopen_mock.call_count == 1


def test_force_refresh_bypasses_cache(tmp_path):
    """force_refresh=True must hit the network even when cache is fresh."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Standard")
        ninja.fetch_currency_overview("Standard", force_refresh=True)

    assert urlopen_mock.call_count == 2


def test_expired_cache_triggers_refetch(tmp_path):
    """After the TTL expires the client must re-fetch from the network."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)

    # Write a cache envelope with fetched_at set far in the past.
    ninja.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stale_envelope = {
        "fetched_at": time.time() - ninja.CURRENCY_TTL_SECONDS - 1,
        "ttl_seconds": ninja.CURRENCY_TTL_SECONDS,
        "data": CURRENCY_FIXTURE,
    }
    (ninja.CACHE_DIR / "currency__Standard.json").write_text(
        json.dumps(stale_envelope), encoding="utf-8"
    )

    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Standard")

    assert urlopen_mock.call_count == 1


def test_get_chaos_value_known_currency(tmp_path):
    """get_chaos_value returns the correct chaosEquivalent for a listed currency."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        value = ninja.get_chaos_value("Standard", "Divine Orb")

    assert value == 150.0


def test_get_chaos_value_unknown_currency(tmp_path):
    """get_chaos_value returns None for a currency not in the overview."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        value = ninja.get_chaos_value("Standard", "Phantom Orb That Does Not Exist")

    assert value is None


def test_unique_overview_different_categories_produce_different_cache_files(tmp_path):
    """Each category gets its own cache file."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(UNIQUE_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_unique_overview("Standard", "UniqueWeapon")
        ninja.fetch_unique_overview("Standard", "UniqueArmour")

    cache_files = list(ninja.CACHE_DIR.iterdir())
    names = {f.name for f in cache_files}
    assert "unique__Standard__UniqueWeapon.json" in names
    assert "unique__Standard__UniqueArmour.json" in names
    assert urlopen_mock.call_count == 2


def test_http_error_raises_poe_ninja_error(tmp_path):
    """HTTP 500 must raise PoeNinjaError containing the status code."""
    _redirect_cache(tmp_path)
    http_err = urllib.error.HTTPError(
        url="https://poe.ninja/poe2/api/data/currencyoverview",
        code=500,
        msg="Internal Server Error",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b"Something went wrong"),
    )
    with mock.patch("urllib.request.urlopen", side_effect=http_err):
        try:
            ninja.fetch_currency_overview("Standard")
            assert False, "Expected PoeNinjaError"
        except ninja.PoeNinjaError as exc:
            assert "500" in str(exc)


def test_network_error_raises_poe_ninja_error(tmp_path):
    """URLError (connection refused, DNS failure, etc.) must raise PoeNinjaError."""
    _redirect_cache(tmp_path)
    url_err = urllib.error.URLError(reason="Connection refused")
    with mock.patch("urllib.request.urlopen", side_effect=url_err):
        try:
            ninja.fetch_currency_overview("Standard")
            assert False, "Expected PoeNinjaError"
        except ninja.PoeNinjaError as exc:
            assert "Network error" in str(exc)


def test_clear_cache_removes_files(tmp_path):
    """clear_cache() must delete all files from the cache directory."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Standard")

    assert any(ninja.CACHE_DIR.iterdir())  # at least one file written

    ninja.clear_cache()

    assert not any(ninja.CACHE_DIR.iterdir())  # directory now empty


def test_fetch_builds_meta_round_trip(tmp_path):
    """fetch_builds_meta must return the raw fixture payload."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(BUILDS_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        result = ninja.fetch_builds_meta("Standard")

    assert result == BUILDS_FIXTURE


def test_fetch_builds_meta_correct_url(tmp_path):
    """fetch_builds_meta must call the PoE 2 builds endpoint."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(BUILDS_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_builds_meta("Settlers")

    req = urlopen_mock.call_args[0][0]
    assert "poe2" in req.full_url
    assert "builds" in req.full_url
    assert "league=Settlers" in req.full_url


def test_builds_meta_uses_24h_ttl(tmp_path):
    """Build meta cache should not expire within 23 hours."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(BUILDS_FIXTURE)

    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_builds_meta("Standard")

    # Write a cache envelope aged 23h (still fresh under 24h TTL).
    cache_file = ninja.CACHE_DIR / "builds__Standard.json"
    envelope = json.loads(cache_file.read_text(encoding="utf-8"))
    envelope["fetched_at"] = time.time() - 23 * 60 * 60
    cache_file.write_text(json.dumps(envelope), encoding="utf-8")

    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_builds_meta("Standard")

    # Second call should read from cache, no extra network call.
    assert urlopen_mock.call_count == 1


def test_unique_overview_invalid_category_raises(tmp_path):
    """fetch_unique_overview with an unrecognized category must raise PoeNinjaError."""
    _redirect_cache(tmp_path)
    try:
        ninja.fetch_unique_overview("Standard", "NotARealCategory")
        assert False, "Expected PoeNinjaError"
    except ninja.PoeNinjaError as exc:
        assert "NotARealCategory" in str(exc)


def test_first_call_writes_cache_file(tmp_path):
    """After a successful fetch, a cache file must exist on disk."""
    _redirect_cache(tmp_path)
    urlopen_mock = _make_urlopen_mock(CURRENCY_FIXTURE)
    with mock.patch("urllib.request.urlopen", urlopen_mock):
        ninja.fetch_currency_overview("Hardcore")

    expected = ninja.CACHE_DIR / "currency__Hardcore.json"
    assert expected.exists()
    envelope = json.loads(expected.read_text(encoding="utf-8"))
    assert envelope["data"] == CURRENCY_FIXTURE
    assert "fetched_at" in envelope
    assert "ttl_seconds" in envelope
