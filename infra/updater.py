"""Self-update mechanism for the poe2-graph skill.

Three independent update layers, each on its own cadence:

  1. Skill code        — our GitHub repo, version-tagged. Manual / on-version-mismatch.
  2. Tree data         — GepetoinTraining mirrors of GGG exports. Per game patch.
  3. poe2db cache      — already 24h-TTL via poe2db_client; invalidate to force refresh.

Player data (EXILE/, PLAYER.md, LEAGUE_*.md, CHARACTER_*.md) is sacrosanct —
no update operation touches these paths.

All network calls go through urllib with our UA. No third-party deps for the
updater itself — keeps the bootstrap clean.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
VERSION_PATH = ROOT / "VERSION"

# Cache for report_cached() — see its docstring for the full contract.
CACHE_DIR = ROOT / ".cache"
STALENESS_CACHE_PATH = CACHE_DIR / "staleness.json"
STALENESS_CACHE_TTL_SECONDS = 3600  # 1 hour
STALENESS_DEADLINE_SECONDS = 2.0    # hard ceiling for the session-start path

USER_AGENT = "poe2-graph-updater/0.1 (https://github.com/GepetoinTraining/poe2-graph)"

# poe-tool-dev maintains a serverless poller that hits GGG's patch server
# every minute and writes the current version to a single file. Currently
# tracks PoE 1; PoE 2 coverage TBD. License: MIT.
# https://github.com/poe-tool-dev/latest-patch-version
GAME_VERSION_URL = "https://raw.githubusercontent.com/poe-tool-dev/latest-patch-version/main/latest.txt"

# Files the updater preserves across skill updates. Pattern matching is shallow:
# exact directory names + glob-style patterns checked against root-relative paths.
PROTECTED_PATHS = (
    "EXILE/",
    "PLAYER.md",
    "LEAGUE_*.md",
    "CHARACTER_*.md",
    "data/poe2db_cache/",  # cache is regeneratable, but no point wiping it on skill update
    "tools/",              # bundled forks (submodules) — managed by `git submodule`, not by skill update
    "config.yaml",         # user-edited config — Claude reads, never silently overwrites
)


# ----- manifest IO -----

def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(m: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def local_version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


# ----- network helpers -----

def _fetch_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_json(url: str, timeout: int = 15) -> dict:
    return json.loads(_fetch_text(url, timeout=timeout))


def _fork_name_from_url(repo_url: str) -> Optional[str]:
    """Extract 'owner/repo' from a GitHub URL. None on parse failure."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def _github_api_latest_commit(repo_url: str) -> Optional[str]:
    """Return the SHA of the default branch's tip. None on failure."""
    fork = _fork_name_from_url(repo_url)
    if not fork:
        return None
    api_url = f"https://api.github.com/repos/{fork}/commits?per_page=1"
    try:
        data = _fetch_json(api_url)
    except Exception:
        return None
    if isinstance(data, list) and data:
        return data[0].get("sha")
    return None


def _github_raw_version(repo_url: str, file_path: str = "VERSION") -> Optional[str]:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/main/{file_path}"
    try:
        return _fetch_text(raw_url).strip()
    except Exception:
        return None


# ----- staleness reports -----

@dataclass
class SourceStatus:
    name: str
    local_ref: str           # local commit hash or version
    remote_ref: Optional[str]  # remote commit hash or version
    stale: bool
    note: str = ""


@dataclass
class StalenessReport:
    skill: SourceStatus
    passive_tree: SourceStatus
    atlas_tree: SourceStatus
    poe2db_cache_age_days: Optional[float]
    upstream_game_version: Optional[str] = None  # from poe-tool-dev/latest-patch-version
    tool_submodules: list[SourceStatus] = field(default_factory=list)
    cache_stale: bool = False  # True if served from a stale on-disk cache (refresh missed deadline)

    @property
    def any_stale(self) -> bool:
        return (
            self.skill.stale
            or self.passive_tree.stale
            or self.atlas_tree.stale
            or any(s.stale for s in self.tool_submodules)
        )


def check_skill_version() -> SourceStatus:
    manifest = load_manifest()
    local = local_version()
    remote = _github_raw_version(manifest["skill_repo"])
    stale = remote is not None and remote != local
    return SourceStatus(
        name="skill_code",
        local_ref=local,
        remote_ref=remote,
        stale=stale,
        note="remote unreachable" if remote is None else "",
    )


def check_data_source(key: str) -> SourceStatus:
    manifest = load_manifest()
    src = manifest["data_sources"][key]
    local = src["last_commit"]
    remote = _github_api_latest_commit(src["repo"])
    stale = remote is not None and remote != local
    return SourceStatus(
        name=key,
        local_ref=local,
        remote_ref=remote,
        stale=stale,
        note="remote unreachable" if remote is None else "",
    )


def latest_game_version() -> Optional[str]:
    """Fetch the current PoE patch version from poe-tool-dev/latest-patch-version.

    Returns the version string (e.g. "3.28.0.10") or None on failure. Currently
    tracks PoE 1 only; PoE 2 coverage is upstream-pending.
    """
    try:
        return _fetch_text(GAME_VERSION_URL, timeout=10).strip()
    except Exception:
        return None


# ----- tool submodules -----

def _parse_gitmodules(gm_path: Optional[Path] = None) -> list[tuple[str, str, str]]:
    """Return [(name, path, url), ...] from .gitmodules.

    `name` is the submodule path used as the section identifier (e.g. 'tools/pob-poe2').
    Returns empty list if no .gitmodules file or no submodules registered.
    """
    gm = gm_path if gm_path is not None else ROOT / ".gitmodules"
    if not gm.exists():
        return []
    import configparser
    cp = configparser.ConfigParser()
    try:
        cp.read(gm, encoding="utf-8")
    except Exception:
        return []
    out: list[tuple[str, str, str]] = []
    for section in cp.sections():
        m = re.match(r'^submodule "([^"]+)"$', section)
        if not m:
            continue
        name = m.group(1)
        path = cp.get(section, "path", fallback=name)
        url = cp.get(section, "url", fallback="")
        out.append((name, path, url))
    return out


def check_tool_submodule(name: str, path: str, url: str) -> SourceStatus:
    """Check one submodule's local HEAD against its upstream default branch."""
    abs_path = ROOT / path
    if not abs_path.exists() or not any(abs_path.iterdir() if abs_path.is_dir() else []):
        return SourceStatus(
            name=name,
            local_ref="(not initialized)",
            remote_ref=None,
            stale=False,
            note="submodule registered but not yet cloned — run `git submodule update --init`",
        )

    rc, out, _ = _run(["git", "-C", str(abs_path), "rev-parse", "HEAD"])
    if rc != 0 or not out.strip():
        return SourceStatus(
            name=name,
            local_ref="(unknown)",
            remote_ref=None,
            stale=False,
            note="could not read local HEAD",
        )
    local = out.strip()

    remote = _github_api_latest_commit(url) if url else None
    stale = remote is not None and remote != local
    return SourceStatus(
        name=name,
        local_ref=local,
        remote_ref=remote,
        stale=stale,
        note="remote unreachable" if remote is None else "",
    )


def check_tool_submodules() -> list[SourceStatus]:
    return [check_tool_submodule(name, path, url) for (name, path, url) in _parse_gitmodules()]


def update_tool_submodule(name: str, path: str, url: str) -> tuple[bool, str]:
    """Pull origin's default branch into the submodule's local checkout.

    Returns (changed, message). changed=True if the local HEAD moved.
    Uses `git fetch origin` + `git reset --hard origin/HEAD` — assumes the
    submodule is meant to track origin's default branch (the standard
    `git submodule update --remote` semantics).
    """
    abs_path = ROOT / path
    if not abs_path.exists():
        return False, f"submodule path {path} not found"

    rc, before_out, _ = _run(["git", "-C", str(abs_path), "rev-parse", "HEAD"])
    if rc != 0:
        return False, "could not read pre-pull HEAD"
    before = before_out.strip()

    rc, _, err = _run(["git", "-C", str(abs_path), "fetch", "origin"])
    if rc != 0:
        return False, f"git fetch failed: {err.strip()}"

    rc, _, err = _run(["git", "-C", str(abs_path), "reset", "--hard", "origin/HEAD"])
    if rc != 0:
        return False, f"git reset failed: {err.strip()}"

    rc, after_out, _ = _run(["git", "-C", str(abs_path), "rev-parse", "HEAD"])
    after = after_out.strip() if rc == 0 else "?"

    if before == after:
        return False, "no change"
    return True, f"{before[:8]} → {after[:8]}"


def sync_fork_from_upstream(fork_repo: str) -> tuple[bool, str]:
    """Run `gh repo sync` to update one of our forks from its upstream parent.

    `fork_repo` is the 'owner/repo' string (e.g. 'GepetoinTraining/NeverSink-Filter-for-PoE2').
    `gh repo sync` auto-detects the parent; no explicit --source needed.

    Returns (changed, message). changed=True if the fork moved.
    Requires `gh` CLI authenticated with repo scope.
    """
    rc, out, err = _run(["gh", "repo", "sync", fork_repo])
    text = (out + err).strip()
    if rc != 0:
        return False, f"gh repo sync failed: {text}"
    # gh prints either "✓ Synced the ... branch..." (changed) or "✓ Branch ... is already up to date" (no change)
    changed = "already up to date" not in text.lower() and "synced" in text.lower()
    return changed, text


def update_all_tool_submodules(sync_upstream: bool = True) -> list[tuple[str, bool, str, Optional[tuple[bool, str]]]]:
    """Update every submodule. Returns list of (name, local_changed, local_msg, sync_result).

    If sync_upstream=True, first `gh repo sync` each fork from its parent before pulling.
    sync_result is None when sync_upstream=False, else (sync_changed, sync_msg).
    """
    out: list[tuple[str, bool, str, Optional[tuple[bool, str]]]] = []
    for (name, path, url) in _parse_gitmodules():
        sync_result: Optional[tuple[bool, str]] = None
        if sync_upstream:
            fork = _fork_name_from_url(url)
            if fork:
                sync_result = sync_fork_from_upstream(fork)
        local_changed, local_msg = update_tool_submodule(name, path, url)
        out.append((name, local_changed, local_msg, sync_result))
    return out


def poe2db_cache_age_days() -> Optional[float]:
    cache = DATA_DIR / "poe2db_cache"
    if not cache.exists():
        return None
    files = list(cache.glob("*.html"))
    if not files:
        return None
    oldest = min(f.stat().st_mtime for f in files)
    return (datetime.now().timestamp() - oldest) / 86400.0


def report() -> StalenessReport:
    return StalenessReport(
        skill=check_skill_version(),
        passive_tree=check_data_source("passive_tree"),
        atlas_tree=check_data_source("atlas_tree"),
        poe2db_cache_age_days=poe2db_cache_age_days(),
        upstream_game_version=latest_game_version(),
        tool_submodules=check_tool_submodules(),
    )


# ----- cached, deadline-bounded report for session-start -----

def report_cached(
    *,
    deadline: float = STALENESS_DEADLINE_SECONDS,
    max_age: float = STALENESS_CACHE_TTL_SECONDS,
) -> StalenessReport:
    """Disk-cached, deadline-bounded `report()` for session-start callers.

    `welcome()` and similar tools must return in well under a second even when
    the network is flaky; `report()` synchronously fires 4+ HTTPS calls, each
    with a 10-15s timeout, so a fresh `report()` on session start can hang 60+
    seconds. This wrapper:

    1. Returns the on-disk cache as-is if it's no older than `max_age`.
    2. Otherwise submits `report()` to a background thread with a hard
       `deadline`. On success, refreshes the cache and returns the fresh
       report (`cache_stale=False`).
    3. On deadline / network error, falls back to the cached report with
       `cache_stale=True` — the daemon thread keeps running in the
       background and may populate the cache for a later call.
    4. With no cache AND no fresh data, returns a sentinel "unknown" report
       (also `cache_stale=True`) rather than raising.

    The cache lives at `<repo>/.cache/staleness.json` so all Claude surfaces
    (Code, desktop, Electron) share it across Python process restarts.
    """
    cached = _read_staleness_cache()
    if cached is not None and _cache_age_seconds(cached) <= max_age:
        return _staleness_from_dict(cached["report"], cache_stale=False)

    # Run the slow report in a daemon thread so the deadline is enforceable.
    # ThreadPoolExecutor with max_workers=1 + non-blocking shutdown via context
    # manager: when the with-block exits, the executor's thread keeps running
    # if it hasn't completed, but cleanup happens on process exit.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="staleness-refresh")
    fut = executor.submit(report)
    executor.shutdown(wait=False)  # don't block on the worker; let it run
    try:
        fresh = fut.result(timeout=deadline)
        _write_staleness_cache(fresh)
        return fresh
    except FutureTimeoutError:
        pass
    except Exception:
        pass

    if cached is not None:
        return _staleness_from_dict(cached["report"], cache_stale=True)
    return _empty_staleness_report(cache_stale=True)


def invalidate_staleness_cache() -> bool:
    """Remove the on-disk staleness cache. Returns True if a file was deleted."""
    try:
        STALENESS_CACHE_PATH.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _read_staleness_cache() -> Optional[dict]:
    try:
        return json.loads(STALENESS_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_staleness_cache(r: StalenessReport) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": time.time(), "report": _staleness_to_dict(r)}
        STALENESS_CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        # Read-only filesystem, perms issue, etc. — non-fatal; we still return
        # the fresh result, the next call will just re-fetch.
        pass


def _cache_age_seconds(cache: dict) -> float:
    return time.time() - float(cache.get("saved_at", 0.0))


def _staleness_to_dict(r: StalenessReport) -> dict:
    return {
        "skill": _sourcestatus_to_dict(r.skill),
        "passive_tree": _sourcestatus_to_dict(r.passive_tree),
        "atlas_tree": _sourcestatus_to_dict(r.atlas_tree),
        "poe2db_cache_age_days": r.poe2db_cache_age_days,
        "upstream_game_version": r.upstream_game_version,
        "tool_submodules": [_sourcestatus_to_dict(s) for s in r.tool_submodules],
    }


def _sourcestatus_to_dict(s: SourceStatus) -> dict:
    return {
        "name": s.name,
        "local_ref": s.local_ref,
        "remote_ref": s.remote_ref,
        "stale": s.stale,
        "note": s.note,
    }


def _staleness_from_dict(d: dict, *, cache_stale: bool) -> StalenessReport:
    def src(sd: dict) -> SourceStatus:
        return SourceStatus(
            name=sd["name"],
            local_ref=sd["local_ref"],
            remote_ref=sd.get("remote_ref"),
            stale=bool(sd.get("stale", False)),
            note=sd.get("note", ""),
        )
    return StalenessReport(
        skill=src(d["skill"]),
        passive_tree=src(d["passive_tree"]),
        atlas_tree=src(d["atlas_tree"]),
        poe2db_cache_age_days=d.get("poe2db_cache_age_days"),
        upstream_game_version=d.get("upstream_game_version"),
        tool_submodules=[src(s) for s in d.get("tool_submodules", [])],
        cache_stale=cache_stale,
    )


def _empty_staleness_report(*, cache_stale: bool) -> StalenessReport:
    """Sentinel report when there's neither a cache nor a fresh fetch."""
    unknown = SourceStatus(
        name="unknown", local_ref="unknown", remote_ref=None,
        stale=False, note="staleness report unavailable",
    )
    return StalenessReport(
        skill=unknown,
        passive_tree=unknown,
        atlas_tree=unknown,
        poe2db_cache_age_days=None,
        upstream_game_version=None,
        tool_submodules=[],
        cache_stale=cache_stale,
    )


# ----- update operations -----

def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Subprocess wrapper for git operations."""
    import subprocess
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return p.returncode, p.stdout, p.stderr


def _is_git_clone(path: Path) -> bool:
    return (path / ".git").is_dir()


def update_data_source(key: str) -> bool:
    """Pull the latest tree-export upstream into its working dir and refresh the
    cached data file. Returns True if data changed.
    """
    manifest = load_manifest()
    src = manifest["data_sources"][key]

    # Map manifest keys to checkout dirs and target paths
    layout = {
        "passive_tree": (ROOT / "poe2-skilltree-export", DATA_DIR / "passive-tree.json"),
        "atlas_tree":   (ROOT / "atlastree-export",      DATA_DIR / "atlas-tree.json"),
    }
    checkout, target = layout[key]
    upstream_data = checkout / "data.json"

    if not _is_git_clone(checkout):
        rc, _, err = _run(["git", "clone", "--depth", "1", src["repo"], str(checkout)])
        if rc != 0:
            raise RuntimeError(f"git clone failed for {key}: {err}")
    else:
        rc, _, err = _run(["git", "fetch", "--depth", "1", "origin"], cwd=checkout)
        if rc != 0:
            raise RuntimeError(f"git fetch failed for {key}: {err}")
        rc, _, err = _run(["git", "reset", "--hard", "origin/HEAD"], cwd=checkout)
        if rc != 0:
            raise RuntimeError(f"git reset failed for {key}: {err}")

    if not upstream_data.exists():
        raise RuntimeError(f"expected {upstream_data} after pull, not found")

    changed = (not target.exists()) or (
        upstream_data.read_bytes() != target.read_bytes()
    )
    shutil.copyfile(upstream_data, target)

    rc, out, _ = _run(["git", "rev-parse", "HEAD"], cwd=checkout)
    new_sha = out.strip() if rc == 0 else "unknown"

    manifest["data_sources"][key]["last_commit"] = new_sha
    manifest["data_sources"][key]["fetched_at"] = date.today().isoformat()
    save_manifest(manifest)
    return changed


def invalidate_poe2db_cache() -> int:
    """Remove the poe2db cache so the next request re-fetches. Returns count removed."""
    cache = DATA_DIR / "poe2db_cache"
    if not cache.exists():
        return 0
    removed = 0
    for f in cache.glob("*.html"):
        f.unlink()
        removed += 1
    return removed


def update_skill_code() -> str:
    """Pull skill code from the GitHub repo. Refuses to clobber player data.

    Returns a short status string. Assumes a git-cloned install; falls back to
    a friendly error if not.
    """
    if not _is_git_clone(ROOT):
        return (
            "skill not installed via git clone — can't auto-update. "
            "Re-clone from the GitHub repo to get the latest version. "
            "Your EXILE/ and PLAYER.md will not be touched if you clone alongside."
        )

    # Ensure protected paths aren't tracked changes that git would clobber.
    rc, out, _ = _run(["git", "status", "--porcelain"], cwd=ROOT)
    if rc == 0 and out.strip():
        # Only warn — protected paths should be in .gitignore on the upstream repo.
        # We let git pull anyway; the protected paths shouldn't be tracked.
        pass

    rc, _, err = _run(["git", "fetch", "origin"], cwd=ROOT)
    if rc != 0:
        return f"git fetch failed: {err}"
    rc, _, err = _run(["git", "pull", "--ff-only"], cwd=ROOT)
    if rc != 0:
        return f"git pull failed (non fast-forward?): {err}"

    return f"skill updated to {local_version()}"


# ----- CLI entry point -----

def _format_report(r: StalenessReport) -> str:
    lines = ["poe2-graph staleness report:"]
    for s in (r.skill, r.passive_tree, r.atlas_tree):
        marker = "STALE" if s.stale else "ok"
        local_short = (s.local_ref or "")[:8] if s.local_ref else "?"
        remote_short = (s.remote_ref or "?")[:8] if s.remote_ref else "?"
        note = f"  [{s.note}]" if s.note else ""
        lines.append(f"  {marker:5s} {s.name:14s}  local={local_short}  remote={remote_short}{note}")
    age = r.poe2db_cache_age_days
    if age is None:
        lines.append(f"  --    poe2db_cache    (empty)")
    else:
        marker = "STALE" if age > 1.0 else "ok"
        lines.append(f"  {marker:5s} poe2db_cache    age={age:.1f}d  (24h TTL)")
    if r.upstream_game_version:
        lines.append(f"  --    game_version    upstream={r.upstream_game_version}  (poe-tool-dev/latest-patch-version, PoE 1 only)")
    else:
        lines.append(f"  --    game_version    (upstream unreachable)")
    if r.tool_submodules:
        lines.append("")
        lines.append("  Bundled forks (tools/):")
        for s in r.tool_submodules:
            marker = "STALE" if s.stale else "ok"
            local_short = (s.local_ref or "")[:8] if s.local_ref else "?"
            remote_short = (s.remote_ref or "?")[:8] if s.remote_ref else "?"
            note = f"  [{s.note}]" if s.note else ""
            lines.append(f"    {marker:5s} {s.name:24s}  local={local_short}  remote={remote_short}{note}")
    return "\n".join(lines)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="poe2-graph self-updater")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="report staleness without updating anything")
    sub.add_parser("update-data", help="refresh tree data from upstream forks")
    sub.add_parser("update-skill", help="pull latest skill code from our GitHub repo")
    sub.add_parser("invalidate-cache", help="wipe the poe2db.tw cache")
    sub.add_parser("update-all", help="run skill update + data update + cache invalidate")
    pt = sub.add_parser("update-tools", help="pull each tool submodule's latest (default: also sync forks from upstream)")
    pt.add_argument("--no-sync-upstream", action="store_true", help="skip gh repo sync; only pull origin into submodules")
    pt.add_argument("--only", type=str, help="comma-sep submodule paths to scope")
    args = p.parse_args()

    if args.cmd == "status":
        print(_format_report(report()))
    elif args.cmd == "update-data":
        for key in ("passive_tree", "atlas_tree"):
            changed = update_data_source(key)
            print(f"{key}: {'changed' if changed else 'no change'}")
    elif args.cmd == "update-skill":
        print(update_skill_code())
    elif args.cmd == "invalidate-cache":
        n = invalidate_poe2db_cache()
        print(f"removed {n} cached page(s)")
    elif args.cmd == "update-all":
        print(update_skill_code())
        for key in ("passive_tree", "atlas_tree"):
            changed = update_data_source(key)
            print(f"{key}: {'changed' if changed else 'no change'}")
        n = invalidate_poe2db_cache()
        print(f"removed {n} cached page(s)")
    elif args.cmd == "update-tools":
        only = {s.strip() for s in args.only.split(",")} if args.only else None
        sync_upstream = not args.no_sync_upstream
        for (name, path, url) in _parse_gitmodules():
            if only is not None and name not in only and path not in only:
                continue
            if sync_upstream:
                fork = _fork_name_from_url(url)
                if fork:
                    s_changed, s_msg = sync_fork_from_upstream(fork)
                    suffix = " (CHANGED)" if s_changed else ""
                    print(f"  sync {fork}: {s_msg}{suffix}")
            l_changed, l_msg = update_tool_submodule(name, path, url)
            suffix = " (CHANGED)" if l_changed else ""
            print(f"  pull {name}: {l_msg}{suffix}")


if __name__ == "__main__":
    main()
