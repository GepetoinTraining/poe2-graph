"""poe.ninja client -- fetch currency rates and build meta for PoE 2.

poe.ninja is the community's public price/meta oracle. It exposes JSON
endpoints for currency exchange rates, unique item pricing, and build meta.
Polite usage is mandatory: cache aggressively, identify via User-Agent, never
hammer the endpoint.

PoE 2 endpoints live under /poe2/api/data/ (not the root /api/data/).

Currency endpoint shape: {'lines': [...], 'currencyDetails': [...]}
  Each line: {
    'currencyTypeName': str,
    'pay': {...} | None,
    'receive': {...} | None,
    'chaosEquivalent': float,
    ...
  }
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

USER_AGENT = "poe2-graph/0.1 (https://github.com/GepetoinTraining/poe2-graph)"
BASE_URL = "https://poe.ninja/poe2/api/data"

# Cache directory: under the project root, not in data/ like poe2db uses,
# since this is runtime-fetched external data rather than scraped game data.
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "poe_ninja"

CURRENCY_TTL_SECONDS = 6 * 60 * 60    # 6 hours
BUILDS_TTL_SECONDS = 24 * 60 * 60     # 24 hours

UNIQUE_CATEGORIES = {
    "UniqueWeapon",
    "UniqueArmour",
    "UniqueAccessory",
    "UniqueFlask",
    "UniqueJewel",
    "UniqueMap",
    "UniqueRelic",
}


class PoeNinjaError(Exception):
    """Raised on network errors or non-2xx HTTP responses from poe.ninja."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(name: str) -> Path:
    return CACHE_DIR / name


def _read_cache(path: Path, ttl_seconds: int) -> Optional[dict]:
    """Return cached data if it exists and is still fresh, else None."""
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = envelope.get("fetched_at", 0.0)
    age = time.time() - fetched_at
    if age < ttl_seconds:
        return envelope.get("data")
    return None


def _write_cache(path: Path, ttl_seconds: int, data: dict) -> None:
    envelope = {
        "fetched_at": time.time(),
        "ttl_seconds": ttl_seconds,
        "data": data,
    }
    path.write_text(json.dumps(envelope), encoding="utf-8")


def _fetch_json(url: str) -> dict:
    """Perform a GET request and return parsed JSON. Raises PoeNinjaError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        snippet = exc.read().decode("utf-8", errors="replace")[:200]
        raise PoeNinjaError(
            f"HTTP {exc.code} from poe.ninja: {exc.reason} -- {snippet}"
        ) from exc
    except urllib.error.URLError as exc:
        raise PoeNinjaError(f"Network error fetching poe.ninja: {exc.reason}") from exc

    if status < 200 or status >= 300:
        raise PoeNinjaError(f"HTTP {status} from poe.ninja: {body[:200]}")

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise PoeNinjaError(f"poe.ninja returned non-JSON: {body[:200]}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_currency_overview(league: str, *, force_refresh: bool = False) -> dict:
    """Return parsed currency-overview JSON from poe.ninja.

    Shape: {'lines': [...], 'currencyDetails': [...]}
    Each line contains 'currencyTypeName', 'chaosEquivalent', 'pay', 'receive'.

    Cached with a 6h TTL under .cache/poe_ninja/. Pass force_refresh=True to
    bypass the cache and hit the network unconditionally.
    """
    _ensure_cache_dir()
    filename = f"currency__{league}.json"
    path = _cache_path(filename)

    if not force_refresh:
        cached = _read_cache(path, CURRENCY_TTL_SECONDS)
        if cached is not None:
            return cached

    url = f"{BASE_URL}/currencyoverview?league={league}&type=Currency"
    data = _fetch_json(url)
    _write_cache(path, CURRENCY_TTL_SECONDS, data)
    return data


def fetch_unique_overview(
    league: str,
    category: str = "UniqueWeapon",
    *,
    force_refresh: bool = False,
) -> dict:
    """Return parsed unique-item pricing JSON from poe.ninja.

    category must be one of: UniqueWeapon, UniqueArmour, UniqueAccessory,
    UniqueFlask, UniqueJewel, UniqueMap, UniqueRelic.

    Cached with a 6h TTL. Each (league, category) pair gets its own cache file.
    """
    if category not in UNIQUE_CATEGORIES:
        raise PoeNinjaError(
            f"Unknown unique category '{category}'. "
            f"Valid values: {sorted(UNIQUE_CATEGORIES)}"
        )

    _ensure_cache_dir()
    filename = f"unique__{league}__{category}.json"
    path = _cache_path(filename)

    if not force_refresh:
        cached = _read_cache(path, CURRENCY_TTL_SECONDS)
        if cached is not None:
            return cached

    url = f"{BASE_URL}/itemoverview?league={league}&type={category}"
    data = _fetch_json(url)
    _write_cache(path, CURRENCY_TTL_SECONDS, data)
    return data


def fetch_builds_meta(league: str, *, force_refresh: bool = False) -> dict:
    """Return parsed build-meta JSON from poe.ninja.

    Endpoint: https://poe.ninja/poe2/api/data/builds?league={league}
    Returns the raw response; processing is deferred to the caller.
    Cached with a 24h TTL.
    """
    _ensure_cache_dir()
    filename = f"builds__{league}.json"
    path = _cache_path(filename)

    if not force_refresh:
        cached = _read_cache(path, BUILDS_TTL_SECONDS)
        if cached is not None:
            return cached

    url = f"{BASE_URL}/builds?league={league}"
    data = _fetch_json(url)
    _write_cache(path, BUILDS_TTL_SECONDS, data)
    return data


def get_chaos_value(league: str, currency_name: str) -> Optional[float]:
    """Return the chaosEquivalent for a named currency, or None if not listed.

    Calls fetch_currency_overview internally; benefits from the cache.
    'Chaos Orb' itself typically appears with chaosEquivalent == 1.0.
    """
    overview = fetch_currency_overview(league)
    for line in overview.get("lines", []):
        if line.get("currencyTypeName") == currency_name:
            return float(line["chaosEquivalent"])
    return None


def clear_cache() -> None:
    """Remove all files under .cache/poe_ninja/. Safe to call from tests."""
    if not CACHE_DIR.exists():
        return
    for f in CACHE_DIR.iterdir():
        if f.is_file():
            f.unlink()
