"""Clipboard queue tools — inspect and drain the clipboard-listener queue.

The clipboard listener daemon (integrations.clipboard_listener) writes one
JSON file per detected item copy into a queue directory. These tools let
Claude inspect the queue and ingest queued events into a farming cycle
without needing to interact with the daemon process directly.

Default queue dir: <repo_root>/.queue/clipboard/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import farm
from store import get_connection

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QUEUE = _REPO_ROOT / ".queue" / "clipboard"


def _resolve_queue(queue_dir: Optional[str]) -> Path:
    return Path(queue_dir) if queue_dir else _DEFAULT_QUEUE


def _queue_files(queue_path: Path) -> list[Path]:
    """Return .json files in queue_path sorted by filename (which encodes timestamp)."""
    if not queue_path.exists():
        return []
    return sorted(queue_path.glob("*.json"))


def clipboard_queue_status(queue_dir: Optional[str] = None) -> dict[str, Any]:
    """Report the current state of the clipboard event queue.

    Returns {ok: True, pending_count: int, oldest_timestamp: str | None,
    newest_timestamp: str | None, queue_dir: str}. pending_count is the number
    of .json files waiting to be ingested into a cycle.
    """
    queue_path = _resolve_queue(queue_dir)
    files = _queue_files(queue_path)

    oldest: Optional[str] = None
    newest: Optional[str] = None

    if files:
        try:
            first = json.loads(files[0].read_text(encoding="utf-8"))
            oldest = first.get("timestamp")
        except (json.JSONDecodeError, OSError):
            pass
        try:
            last = json.loads(files[-1].read_text(encoding="utf-8"))
            newest = last.get("timestamp")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "ok": True,
        "pending_count": len(files),
        "oldest_timestamp": oldest,
        "newest_timestamp": newest,
        "queue_dir": str(queue_path),
    }


def clipboard_drain_into_cycle(
    cycle_id: str,
    queue_dir: Optional[str] = None,
    max_items: int = 100,
) -> dict[str, Any]:
    """Read queued clipboard events and ingest them into the given ACTIVE cycle.

    Loads each .json event file, extracts the raw item text from
    event['raw_text'], calls farm.record_output for each, then deletes the
    consumed file. Returns {ok: True, ingested_count: int, errors: list[dict]}.
    A bad file never aborts the drain — errors are collected and returned.
    max_items caps how many files are processed in a single call.
    """
    queue_path = _resolve_queue(queue_dir)
    files = _queue_files(queue_path)[:max_items]

    ingested = 0
    errors: list[dict] = []

    conn = get_connection()
    try:
        for fpath in files:
            try:
                event = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                errors.append({"file": str(fpath), "error": f"read failed: {exc}"})
                continue

            raw_text = event.get("raw_text", "")

            # record_output wraps item_payload in <item><![CDATA[...]></item> itself,
            # so we pass the raw text directly — no extra XML envelope here.
            try:
                farm.record_output(conn, cycle_id, raw_text, source="clipboard")
                ingested += 1
                fpath.unlink(missing_ok=True)
            except ValueError as exc:
                errors.append({"file": str(fpath), "error": str(exc)})
            except OSError as exc:
                errors.append({"file": str(fpath), "error": f"delete failed: {exc}"})
    finally:
        conn.close()

    return {"ok": True, "ingested_count": ingested, "errors": errors}


def clipboard_peek_queue(
    queue_dir: Optional[str] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Peek at the head of the clipboard queue without consuming any files.

    Returns {ok: True, items: list[dict]} — up to `limit` event dicts from
    the oldest queued files. Files are not deleted. Useful for previewing what
    would be ingested before committing to a drain.
    """
    queue_path = _resolve_queue(queue_dir)
    files = _queue_files(queue_path)[:limit]

    items: list[dict] = []
    for fpath in files:
        try:
            event = json.loads(fpath.read_text(encoding="utf-8"))
            items.append(event)
        except (json.JSONDecodeError, OSError):
            items.append({"file": str(fpath), "error": "unreadable"})

    return {"ok": True, "items": items}


def clipboard_clear_queue(queue_dir: Optional[str] = None) -> dict[str, Any]:
    """Delete all queued clipboard events.

    Removes every .json file from the queue directory without ingesting them.
    Returns {ok: True, deleted_count: int}. Use with care — this permanently
    drops un-ingested item data.
    """
    queue_path = _resolve_queue(queue_dir)
    files = _queue_files(queue_path)

    deleted = 0
    for fpath in files:
        try:
            fpath.unlink(missing_ok=True)
            deleted += 1
        except OSError:
            pass

    return {"ok": True, "deleted_count": deleted}
