"""Update worker — keeps tool submodules current with their upstream parents.

Two-phase loop per iteration:

  1. Fork-sync   : `gh repo sync` our forks from their upstream parents
                   (NeverSink-Filter-for-PoE2 etc. update on league launch).
  2. Submodule-pull: `git fetch origin && git reset --hard origin/HEAD` per
                     submodule so the local checkout matches the fork.

Designed to run during league launch windows when NeverSink pushes a
patch-day filter update and we want the new version available locally
without manual `git submodule update --remote`.

Usage:
    python worker.py                            # one-shot — check + update once
    python worker.py --watch                    # loop forever, default interval 600s
    python worker.py --watch --interval 300     # 5-min loop
    python worker.py --watch --duration 72h     # loop for 72 hours then exit
    python worker.py --watch --until 2026-05-30T00:00  # loop until ISO time (UTC)
    python worker.py --only tools/neversink-poe2 # scope to one submodule
    python worker.py --no-sync-upstream          # skip gh repo sync; only pull origin
    python worker.py --log worker.log           # tee output to file

Exits cleanly on Ctrl+C. Network errors during a single iteration log + skip;
they don't crash the loop.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional, TextIO

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import updater  # noqa: E402


_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_DURATION_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def parse_duration(s: str) -> timedelta:
    """Parse '72h', '30m', '1d' etc. → timedelta. Raises ValueError on bad input."""
    m = _DURATION_RE.match(s.strip())
    if not m:
        raise ValueError(f"unrecognized duration: {s!r}; expected like '72h', '30m', '1d'")
    return timedelta(**{_DURATION_UNITS[m.group(2).lower()]: int(m.group(1))})


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(line: str, out: Optional[TextIO] = None) -> None:
    print(line)
    if out is not None:
        out.write(line + "\n")
        out.flush()


def _resolve_only(only: Optional[Iterable[str]], all_tools: bool) -> Optional[set[str]]:
    """Determine which submodules to check.

    - explicit `only` → that set
    - `all_tools` True → None (= check everything in .gitmodules)
    - default → continuous_tools per config (worker scopes to high-velocity polls)
    - no continuous tools configured → fall back to all submodules
    """
    if only is not None:
        return set(only)
    if all_tools:
        return None
    cfg = config.load()
    continuous = config.continuous_tools(cfg)
    if not continuous:
        return None
    return {t.submodule_path for t in continuous if t.submodule_path}


def run_once(
    only: Optional[Iterable[str]] = None,
    sync_upstream: bool = True,
    log_to: Optional[TextIO] = None,
    all_tools: bool = False,
    interval_gate: Optional[dict[str, float]] = None,
) -> int:
    """One iteration of the loop. Returns total count of changes detected
    (fork sync + submodule pull combined).

    `interval_gate`: optional {submodule_path: next_check_epoch} dict used by
    watch() to enforce per-tool intervals from config. When provided, tools
    whose `next_check_epoch > now` are skipped (and the dict is updated for
    fired tools). When None, every matching tool fires.
    """
    only_set = _resolve_only(only, all_tools)
    changes = 0

    # Map submodule path → per-tool interval (only used when interval_gate active)
    per_tool_intervals: dict[str, int] = {}
    if interval_gate is not None:
        cfg = config.load()
        for t in cfg.tools:
            if t.submodule_path:
                per_tool_intervals[t.submodule_path] = t.update_cycle.interval_seconds

    now = time.time()
    submodules = updater._parse_gitmodules()
    for (name, path, url) in submodules:
        if only_set is not None and name not in only_set and path not in only_set:
            continue
        if interval_gate is not None:
            next_at = interval_gate.get(path, 0.0)
            if next_at > now:
                continue

        # Phase 1: sync fork from upstream
        sync_changed = False
        if sync_upstream:
            fork = updater._fork_name_from_url(url)
            if not fork:
                _log(f"[{_now_iso()}] {name}: could not parse fork name from {url}", log_to)
            else:
                sync_changed, sync_msg = updater.sync_fork_from_upstream(fork)
                if sync_changed:
                    _log(f"[{_now_iso()}] {name}: fork synced — {sync_msg}", log_to)
                    changes += 1
                # Skip silent "no change" sync messages to keep the loop quiet.

        # Phase 2: pull local submodule from origin (our fork)
        pull_changed, pull_msg = updater.update_tool_submodule(name, path, url)
        if pull_changed:
            _log(f"[{_now_iso()}] {name}: submodule pulled — {pull_msg}", log_to)
            changes += 1

        # Record fire time so per-tool intervals are respected next iteration.
        if interval_gate is not None:
            tool_interval = per_tool_intervals.get(path, 86400)
            interval_gate[path] = now + tool_interval

    return changes


def watch(
    interval: int,
    stop_at: Optional[datetime],
    only: Optional[Iterable[str]] = None,
    sync_upstream: bool = True,
    log_to: Optional[TextIO] = None,
    all_tools: bool = False,
    respect_per_tool_intervals: bool = True,
) -> None:
    """Loop run_once with `interval` seconds between iterations until interrupted
    or stop_at is reached.

    When `respect_per_tool_intervals=True` (default), each tool fires at its own
    cadence from config (e.g. neversink-poe2 at 300s, pob-poe2 at 604800s); the
    outer loop's `interval` is just the polling tick.
    """
    _log(
        f"[{_now_iso()}] watch start  tick={interval}s  "
        f"stop_at={stop_at.isoformat() if stop_at else 'never (Ctrl+C to stop)'}  "
        f"sync_upstream={sync_upstream}  per_tool_intervals={respect_per_tool_intervals}",
        log_to,
    )
    interval_gate: Optional[dict[str, float]] = {} if respect_per_tool_intervals else None
    try:
        while True:
            if stop_at is not None and datetime.now(timezone.utc) >= stop_at:
                _log(f"[{_now_iso()}] stop time reached, exiting", log_to)
                return
            try:
                n = run_once(
                    only=only, sync_upstream=sync_upstream, log_to=log_to,
                    all_tools=all_tools, interval_gate=interval_gate,
                )
                if n == 0:
                    # quiet "all clear" tick
                    pass
            except Exception as e:  # network errors, gh hiccups — keep going
                _log(f"[{_now_iso()}] iteration error (continuing): {e}", log_to)
            time.sleep(interval)
    except KeyboardInterrupt:
        _log(f"\n[{_now_iso()}] interrupted, exiting", log_to)


def main() -> None:
    # Force UTF-8 stdout so emoji-ish characters in log lines render on Windows.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    p = argparse.ArgumentParser(
        description="poe2-graph update worker — pulls tool submodule updates "
        "(filter / PoB) during league launch windows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1] if __doc__ and "Usage:" in __doc__ else "",
    )
    p.add_argument("--watch", action="store_true", help="loop until interrupted or stop time")
    p.add_argument("--interval", type=int, default=None,
                   help="seconds between watch ticks (default: config.worker.default_interval_seconds)")
    p.add_argument("--until", type=str, help="stop time as ISO 8601 in UTC, e.g. 2026-05-30T00:00")
    p.add_argument("--duration", type=str, help="run for this long, e.g. 72h 30m 1d")
    p.add_argument("--no-sync-upstream", action="store_true",
                   help="skip `gh repo sync`; only pull origin into local submodule")
    p.add_argument("--only", type=str,
                   help="comma-sep submodule paths or names to scope (overrides config-derived default)")
    p.add_argument("--all", action="store_true",
                   help="check all submodules in .gitmodules (override config's continuous-only default)")
    p.add_argument("--no-per-tool-intervals", action="store_true",
                   help="ignore per-tool intervals from config; fire every tool every tick")
    p.add_argument("--log", type=str, help="path to a log file (output is also tee'd to stdout)")
    args = p.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    sync_upstream = not args.no_sync_upstream

    # Default interval from config when not specified
    if args.interval is None:
        cfg = config.load()
        args.interval = cfg.worker.default_interval_seconds

    stop_at: Optional[datetime] = None
    if args.until and args.duration:
        print("error: --until and --duration are mutually exclusive", file=sys.stderr)
        sys.exit(2)
    if args.until:
        stop_at = datetime.fromisoformat(args.until)
        if stop_at.tzinfo is None:
            stop_at = stop_at.replace(tzinfo=timezone.utc)
    elif args.duration:
        stop_at = datetime.now(timezone.utc) + parse_duration(args.duration)

    log_handle: Optional[TextIO] = None
    if args.log:
        log_handle = open(args.log, "a", encoding="utf-8")

    try:
        if not args.watch:
            n = run_once(
                only=only, sync_upstream=sync_upstream, log_to=log_handle,
                all_tools=args.all,
            )
            _log(f"[{_now_iso()}] one-shot complete — {n} change(s) total", log_handle)
        else:
            watch(
                args.interval, stop_at, only=only, sync_upstream=sync_upstream,
                log_to=log_handle, all_tools=args.all,
                respect_per_tool_intervals=not args.no_per_tool_intervals,
            )
    finally:
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    main()
