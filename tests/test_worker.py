"""Worker tests — duration parsing + run_once dispatch (no network)."""

from __future__ import annotations

import io
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import worker  # noqa: E402
import updater  # noqa: E402


# ----- parse_duration -----

def test_parse_duration_seconds():
    assert worker.parse_duration("60s") == timedelta(seconds=60)


def test_parse_duration_minutes():
    assert worker.parse_duration("30m") == timedelta(minutes=30)


def test_parse_duration_hours():
    assert worker.parse_duration("72h") == timedelta(hours=72)


def test_parse_duration_days():
    assert worker.parse_duration("3d") == timedelta(days=3)


def test_parse_duration_handles_whitespace():
    assert worker.parse_duration(" 72 h ") == timedelta(hours=72)


def test_parse_duration_case_insensitive():
    assert worker.parse_duration("72H") == timedelta(hours=72)


def test_parse_duration_rejects_bad_input():
    with pytest.raises(ValueError):
        worker.parse_duration("forever")
    with pytest.raises(ValueError):
        worker.parse_duration("72")  # missing unit
    with pytest.raises(ValueError):
        worker.parse_duration("72x")  # bad unit


# ----- run_once dispatch -----

def test_run_once_calls_sync_and_pull_per_submodule(monkeypatch, tmp_path):
    """run_once should invoke sync_fork_from_upstream + update_tool_submodule for each entry."""
    fake_gitmodules = [
        ("tools/a", "tools/a", "https://github.com/me/a.git"),
        ("tools/b", "tools/b", "https://github.com/me/b.git"),
    ]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/a" if "a.git" in url else "me/b")

    sync_calls = []
    pull_calls = []

    def fake_sync(fork):
        sync_calls.append(fork)
        return (False, "Branch is already up to date")

    def fake_pull(name, path, url):
        pull_calls.append((name, path, url))
        return (False, "no change")

    monkeypatch.setattr(updater, "sync_fork_from_upstream", fake_sync)
    monkeypatch.setattr(updater, "update_tool_submodule", fake_pull)

    # all_tools=True opts out of config's continuous-only default so the
    # synthetic submodules are exercised regardless of what the live config says
    n = worker.run_once(all_tools=True)
    assert sync_calls == ["me/a", "me/b"]
    assert len(pull_calls) == 2
    assert n == 0  # no changes


def test_run_once_skip_sync_when_disabled(monkeypatch):
    """--no-sync-upstream → only pull happens, sync is skipped."""
    fake_gitmodules = [("tools/x", "tools/x", "https://github.com/me/x.git")]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)

    sync_called = []
    monkeypatch.setattr(updater, "sync_fork_from_upstream",
                        lambda f: sync_called.append(f) or (False, ""))
    monkeypatch.setattr(updater, "update_tool_submodule",
                        lambda n, p, u: (False, "no change"))

    worker.run_once(sync_upstream=False, all_tools=True)
    assert sync_called == []


def test_run_once_only_filter(monkeypatch):
    """--only filters out non-matching submodules."""
    fake_gitmodules = [
        ("tools/a", "tools/a", "https://github.com/me/a.git"),
        ("tools/b", "tools/b", "https://github.com/me/b.git"),
    ]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/x")

    pull_targets = []
    monkeypatch.setattr(updater, "sync_fork_from_upstream", lambda f: (False, ""))
    monkeypatch.setattr(updater, "update_tool_submodule",
                        lambda n, p, u: pull_targets.append(n) or (False, "no change"))

    worker.run_once(only=["tools/a"])
    assert pull_targets == ["tools/a"]


def test_run_once_counts_changes(monkeypatch):
    """run_once returns the sum of fork-sync changes + submodule-pull changes."""
    fake_gitmodules = [("tools/x", "tools/x", "https://github.com/me/x.git")]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/x")
    monkeypatch.setattr(updater, "sync_fork_from_upstream", lambda f: (True, "synced"))
    monkeypatch.setattr(updater, "update_tool_submodule", lambda n, p, u: (True, "abcd → efgh"))

    n = worker.run_once(all_tools=True)
    assert n == 2  # one sync change + one pull change


def test_run_once_logs_to_file(monkeypatch, tmp_path):
    """When log_to is provided, change lines are written to the file handle."""
    fake_gitmodules = [("tools/x", "tools/x", "https://github.com/me/x.git")]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/x")
    monkeypatch.setattr(updater, "sync_fork_from_upstream", lambda f: (True, "synced"))
    monkeypatch.setattr(updater, "update_tool_submodule", lambda n, p, u: (False, "no change"))

    buf = io.StringIO()
    worker.run_once(log_to=buf, all_tools=True)
    out = buf.getvalue()
    assert "tools/x" in out
    assert "fork synced" in out


def test_run_once_default_scopes_to_continuous_tools(monkeypatch):
    """Without --only or --all, worker only fires for tools whose update_cycle.mode
    is 'continuous' per config."""
    import config

    # Synthetic config with one continuous tool, one scheduled
    fake_cfg = config.Config(tools=[
        config.ToolEntry(name="cont", type="bundled_fork", submodule_path="tools/cont",
                         update_cycle=config.UpdateCycle(mode="continuous", interval_seconds=300)),
        config.ToolEntry(name="sched", type="bundled_fork", submodule_path="tools/sched",
                         update_cycle=config.UpdateCycle(mode="scheduled", interval_seconds=86400)),
    ])
    monkeypatch.setattr(config, "load", lambda force=False: fake_cfg)

    fake_gitmodules = [
        ("tools/cont", "tools/cont", "https://github.com/me/cont.git"),
        ("tools/sched", "tools/sched", "https://github.com/me/sched.git"),
    ]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/x")

    pulled = []
    monkeypatch.setattr(updater, "sync_fork_from_upstream", lambda f: (False, ""))
    monkeypatch.setattr(updater, "update_tool_submodule",
                        lambda n, p, u: pulled.append(p) or (False, "no change"))

    worker.run_once()
    # Only the continuous tool's path should have been pulled
    assert pulled == ["tools/cont"]


def test_run_once_interval_gate_respects_per_tool_intervals(monkeypatch):
    """When interval_gate dict is provided, tools whose next-check is in the
    future are skipped; tools that fire have their next-check updated."""
    import config

    fake_cfg = config.Config(tools=[
        config.ToolEntry(name="fast", type="bundled_fork", submodule_path="tools/fast",
                         update_cycle=config.UpdateCycle(mode="continuous", interval_seconds=60)),
        config.ToolEntry(name="slow", type="bundled_fork", submodule_path="tools/slow",
                         update_cycle=config.UpdateCycle(mode="continuous", interval_seconds=3600)),
    ])
    monkeypatch.setattr(config, "load", lambda force=False: fake_cfg)

    fake_gitmodules = [
        ("tools/fast", "tools/fast", "https://github.com/me/fast.git"),
        ("tools/slow", "tools/slow", "https://github.com/me/slow.git"),
    ]
    monkeypatch.setattr(updater, "_parse_gitmodules", lambda: fake_gitmodules)
    monkeypatch.setattr(updater, "_fork_name_from_url", lambda url: "me/x")
    monkeypatch.setattr(updater, "sync_fork_from_upstream", lambda f: (False, ""))

    pulled = []
    monkeypatch.setattr(updater, "update_tool_submodule",
                        lambda n, p, u: pulled.append(p) or (False, "no change"))

    import time as time_module
    now = time_module.time()
    gate: dict[str, float] = {"tools/slow": now + 1800}  # not due for 30 min
    worker.run_once(interval_gate=gate)

    # 'fast' fired; 'slow' was gated
    assert "tools/fast" in pulled
    assert "tools/slow" not in pulled
    # After firing, 'fast' should have a future next-check
    assert gate["tools/fast"] > now


# ----- updater helpers added for worker -----

def test_fork_name_from_url_parses_canonical():
    assert updater._fork_name_from_url("https://github.com/Owner/Repo") == "Owner/Repo"
    assert updater._fork_name_from_url("https://github.com/Owner/Repo.git") == "Owner/Repo"
    assert updater._fork_name_from_url("https://github.com/Owner/Repo/") == "Owner/Repo"


def test_fork_name_from_url_returns_none_on_garbage():
    assert updater._fork_name_from_url("not-a-url") is None
    assert updater._fork_name_from_url("https://gitlab.com/x/y") is None
