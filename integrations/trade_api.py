"""PoE 2 official Trade API client — rate-limited search + fetch flow.

Two-step pattern:
  1. POST /api/trade2/search/{league}  -> {id, result: [item_ids...], total}
  2. GET  /api/trade2/fetch/{id,id,...}?query={search_id} -> {result: [...]}

Rate limits are enforced server-side via X-Rate-Limit-Ip / X-Rate-Limit-Account
response headers. We parse them and sleep proactively when close to the ceiling.

Search responses are cached on disk for 5 minutes; fetch responses are not
(listings change too fast to cache usefully).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = (
    "poe2-graph/0.1 (https://github.com/GepetoinTraining/poe2-graph; contact via GitHub)"
)
BASE_URL = "https://www.pathofexile.com/api/trade2"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "trade_api"
CACHE_TTL_SECONDS = 5 * 60  # 5 minutes

# Sleep when current usage >= this fraction of the limit.
RATE_LIMIT_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TradeApiError(Exception):
    """Raised for HTTP errors or network failures talking to the trade API."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class TradeApiRateLimited(TradeApiError):
    """Raised on HTTP 429. retry_after_seconds may be None if header absent."""

    def __init__(self, retry_after_seconds: float | None = None):
        msg = "Trade API rate limit exceeded"
        if retry_after_seconds is not None:
            msg += f"; retry after {retry_after_seconds}s"
        super().__init__(msg, status=429)
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Rate-limit state
# ---------------------------------------------------------------------------


class RateLimitState:
    """Tracks parsed rate-limit headers for a session.

    The X-Rate-Limit-Ip and X-Rate-Limit-Account headers look like:
        8:10:60,15:60:120
    meaning "8 requests per 10-second window, 15 per 60-second window."

    The corresponding *-State headers carry current counts:
        5:10:0,12:60:0
    meaning "5 used in current 10s window, 12 used in current 60s window."

    We sleep before a request when any dimension is >= RATE_LIMIT_THRESHOLD of
    its ceiling. The window period (third field) tells us how long to sleep.

    Internal — exposed for tests but not part of the day-to-day public API.
    """

    def __init__(self) -> None:
        # List of (max, period_seconds) tuples from the policy header.
        self._limits: list[tuple[int, int]] = []
        # List of (current_count, period_seconds) tuples from the state header.
        self._state: list[tuple[int, int]] = []

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_header(value: str) -> list[tuple[int, int]]:
        """Parse 'hits:window_seconds:restriction_seconds,...' into [(hits, window), ...].

        The PoE trade API rate-limit header format is three colon-separated
        fields per policy slot, comma-separated across slots:
          hits : window_seconds : restriction_seconds
        e.g. '8:10:60,15:60:120' -> [(8, 10), (15, 60)].

        For limit headers the first field is the max allowed; for state headers
        it is the current count.  We keep (count, window) because the window is
        what we need to sleep for when close to the ceiling.
        """
        result = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            fields = part.split(":")
            if len(fields) < 2:
                continue
            try:
                count = int(fields[0])
                window = int(fields[1])
                result.append((count, window))
            except ValueError:
                continue
        return result

    def update(self, headers: dict[str, str]) -> None:
        """Ingest the response headers dict. Keys are case-insensitive checked."""
        lower = {k.lower(): v for k, v in headers.items()}
        limit_val = lower.get("x-rate-limit-ip") or lower.get("x-rate-limit-account") or ""
        state_val = (
            lower.get("x-rate-limit-ip-state") or lower.get("x-rate-limit-account-state") or ""
        )
        if limit_val:
            self._limits = self._parse_header(limit_val)
        if state_val:
            self._state = self._parse_header(state_val)

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def seconds_to_sleep(self) -> float:
        """Return how many seconds to sleep before the next request.

        Zero means "go ahead immediately."
        """
        if not self._limits or not self._state:
            return 0.0
        max_sleep = 0.0
        for i, (current, period) in enumerate(self._state):
            if i >= len(self._limits):
                break
            limit_max, _ = self._limits[i]
            if limit_max <= 0:
                continue
            if current >= RATE_LIMIT_THRESHOLD * limit_max:
                max_sleep = max(max_sleep, float(period))
        return max_sleep


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_rate_state = RateLimitState()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _query_hash(query: dict) -> str:
    return hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()


def _cache_path(league: str, query_hash: str, cache_dir: Path | None = None) -> Path:
    base = cache_dir if cache_dir is not None else CACHE_DIR
    safe_league = league.replace(" ", "_")
    return base / f"search__{safe_league}__{query_hash[:12]}.json"


def _cache_fresh(path: Path, ttl: int = CACHE_TTL_SECONDS) -> bool:
    if not path.exists():
        return False
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        fetched_at_str = envelope.get("fetched_at", "")
        ttl_seconds = envelope.get("ttl_seconds", ttl)
        fetched_at = datetime.fromisoformat(fetched_at_str)
        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        return age < ttl_seconds
    except Exception:
        return False


def _write_cache(path: Path, data: dict, ttl: int = CACHE_TTL_SECONDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl,
        "data": data,
    }
    path.write_text(json.dumps(envelope), encoding="utf-8")


def _read_cache(path: Path) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    return envelope["data"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _make_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


def _handle_response_headers(resp) -> None:
    """Update global rate-limit state from response headers."""
    headers = {k: v for k, v in resp.headers.items()}
    _rate_state.update(headers)


def _check_rate_limit() -> None:
    """Sleep if needed before issuing a request."""
    delay = _rate_state.seconds_to_sleep()
    if delay > 0:
        time.sleep(delay)


def _do_post(url: str, body: dict) -> dict:
    """POST JSON body to url, return parsed response dict."""
    _check_rate_limit()
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_make_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            _handle_response_headers(resp)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry_after = None
            try:
                retry_after = float(exc.headers.get("Retry-After") or 0) or None
            except (TypeError, ValueError):
                pass
            raise TradeApiRateLimited(retry_after) from exc
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise TradeApiError(
            f"HTTP {exc.code} from trade API: {body_text[:200]}", status=exc.code
        ) from exc
    except urllib.error.URLError as exc:
        raise TradeApiError(f"Network error: {exc.reason}") from exc


def _do_get(url: str) -> dict:
    """GET url, return parsed response dict."""
    _check_rate_limit()
    req = urllib.request.Request(url, headers=_make_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            _handle_response_headers(resp)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry_after = None
            try:
                retry_after = float(exc.headers.get("Retry-After") or 0) or None
            except (TypeError, ValueError):
                pass
            raise TradeApiRateLimited(retry_after) from exc
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise TradeApiError(
            f"HTTP {exc.code} from trade API: {body_text[:200]}", status=exc.code
        ) from exc
    except urllib.error.URLError as exc:
        raise TradeApiError(f"Network error: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search(
    league: str,
    query: dict,
    *,
    realm: str = "poe2",
    force_refresh: bool = False,
    _cache_dir: Path | None = None,
) -> dict:
    """Execute a trade search.

    league   -- league name, e.g. 'Standard', 'Settlers'.
    query    -- trade-API query JSON body.
    realm    -- always 'poe2' for PoE 2 (reserved for future use).
    force_refresh -- bypass disk cache and re-issue the request.

    Returns parsed response: {'id': str, 'result': list[str], 'total': int, ...}.
    Cached for 5 min by (league, query_hash).
    """
    qhash = _query_hash(query)
    cpath = _cache_path(league, qhash, _cache_dir)

    if not force_refresh and _cache_fresh(cpath):
        return _read_cache(cpath)

    url = f"{BASE_URL}/search/{urllib.parse.quote(league, safe='')}"
    data = _do_post(url, query)
    _write_cache(cpath, data)
    return data


def fetch_listings(
    item_ids: list[str],
    *,
    query_id: str,
    realm: str = "poe2",
) -> dict:
    """Fetch up to 10 listings per call.

    item_ids -- list of item IDs from a search result (max 10).
    query_id -- the search ID returned by search(), required by the API.

    Returns parsed response: {'result': [{'listing': {...}, 'item': {...}}, ...]}.
    Not cached.
    """
    if len(item_ids) > 10:
        raise ValueError(
            f"fetch_listings accepts at most 10 IDs per call; got {len(item_ids)}. "
            "Use search_and_fetch for larger batches."
        )
    ids_csv = ",".join(item_ids)
    qs = urllib.parse.urlencode({"query": query_id})
    url = f"{BASE_URL}/fetch/{ids_csv}?{qs}"
    return _do_get(url)


def search_and_fetch(
    league: str,
    query: dict,
    *,
    max_results: int = 10,
    realm: str = "poe2",
    _cache_dir: Path | None = None,
) -> list[dict]:
    """Convenience: search then fetch the first max_results listings.

    Chunks automatically when max_results > 10 (API limit per fetch call).
    Returns the flat list of listing+item dicts from all fetched batches.
    """
    search_resp = search(league, query, realm=realm, _cache_dir=_cache_dir)
    query_id = search_resp.get("id", "")
    all_ids: list[str] = search_resp.get("result", [])
    ids_to_fetch = all_ids[:max_results]

    results: list[dict] = []
    # Chunk into batches of 10.
    batch_size = 10
    for start in range(0, len(ids_to_fetch), batch_size):
        batch = ids_to_fetch[start : start + batch_size]
        resp = fetch_listings(batch, query_id=query_id, realm=realm)
        results.extend(resp.get("result", []))

    return results


def clear_cache(_cache_dir: Path | None = None) -> None:
    """Wipe .cache/trade_api/ — for tests and manual invalidation."""
    base = _cache_dir if _cache_dir is not None else CACHE_DIR
    if not base.exists():
        return
    for p in base.iterdir():
        if p.is_file():
            p.unlink()
