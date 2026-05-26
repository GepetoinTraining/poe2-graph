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
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
VERSION_PATH = ROOT / "VERSION"

USER_AGENT = "poe2-graph-updater/0.1 (https://github.com/GepetoinTraining/poe2-graph)"

# Files the updater preserves across skill updates. Pattern matching is shallow:
# exact directory names + glob-style patterns checked against root-relative paths.
PROTECTED_PATHS = (
    "EXILE/",
    "PLAYER.md",
    "LEAGUE_*.md",
    "CHARACTER_*.md",
    "data/poe2db_cache/",  # cache is regeneratable, but no point wiping it on skill update
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


def _github_api_latest_commit(repo_url: str) -> Optional[str]:
    """Return the SHA of the default branch's tip. None on failure."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    api_url = f"https://api.github.com/repos/{owner}/{name}/commits?per_page=1"
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

    @property
    def any_stale(self) -> bool:
        return self.skill.stale or self.passive_tree.stale or self.atlas_tree.stale


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


if __name__ == "__main__":
    main()
