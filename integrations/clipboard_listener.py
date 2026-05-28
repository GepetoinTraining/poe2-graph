"""clipboard_listener -- continuous clipboard watcher for PoE 2 item drops.

Polls the system clipboard at a fixed interval, detects PoE 2 item text
(heuristic: 'Item Class:' / 'Rarity:' / '--------' blocks), parses it via
`items.parser.parse_clipboard`, and emits a structured event dict for each
new unique item the player copies.

Run as a standalone daemon:

    python -m integrations.clipboard_listener

The daemon writes each event as a JSON file under
D:\\poe2-graph\\.queue\\clipboard\\ (configurable) and logs to stderr.

Clipboard backend: tries `pyperclip` first. Falls back to
`subprocess + PowerShell Get-Clipboard` if pyperclip is not installed.
`pyperclip` is NOT in requirements.txt; add it if you want the fast path
(pip install pyperclip).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from items import parser as item_parser
from mcp_server._serialize import to_jsonable

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root and default queue directory
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QUEUE_DIR = _PROJECT_ROOT / ".queue" / "clipboard"


# ---------------------------------------------------------------------------
# Single exception class for this module
# ---------------------------------------------------------------------------

class ClipboardListenerError(Exception):
    """Raised for unrecoverable clipboard-listener configuration errors."""


# ---------------------------------------------------------------------------
# Clipboard backend -- pyperclip preferred, subprocess fallback
# ---------------------------------------------------------------------------

def _read_clipboard_pyperclip() -> str:
    import pyperclip  # type: ignore[import]
    return pyperclip.paste() or ""


def _read_clipboard_subprocess() -> str:
    """Fallback: call PowerShell Get-Clipboard. Slow but dep-free."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout or ""
    except Exception as exc:
        log.warning("clipboard subprocess failed: %s", exc)
        return ""


def _build_clipboard_reader() -> Callable[[], str]:
    """Return whichever read function is available."""
    try:
        import pyperclip  # type: ignore[import]  # noqa: F401
        log.debug("clipboard backend: pyperclip")
        return _read_clipboard_pyperclip
    except ImportError:
        log.debug("pyperclip not installed; using subprocess fallback")
        return _read_clipboard_subprocess


# Module-level reader so it's resolved once (not on every poll).
_read_clipboard = _build_clipboard_reader()


def read_clipboard() -> str:
    """Read and return the current clipboard contents as a string."""
    return _read_clipboard()


# ---------------------------------------------------------------------------
# Heuristic detection
# ---------------------------------------------------------------------------

def is_poe2_item_text(text: str) -> bool:
    """Return True if `text` looks like a PoE 2 in-game item clipboard dump.

    Checks for any of the three anchor patterns the game always emits:
      - 'Item Class: ...' on a line (canonical first line)
      - 'Rarity: ...' on a line  (always present in item header)
      - A '--------' separator block (at least 8 dashes on its own line)

    False for empty strings, URLs, code, prose paragraphs, etc.
    The test is intentionally cheap -- it must not import the parser.
    """
    if not text or not text.strip():
        return False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Item Class:"):
            return True
        if stripped.startswith("Rarity:") and len(stripped) > len("Rarity:"):
            return True
        if len(stripped) >= 8 and all(c == "-" for c in stripped):
            return True

    return False


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_clipboard_text(text: str) -> Optional[dict[str, Any]]:
    """Parse `text` as a PoE 2 item and return a structured event dict.

    Returns None if the text does not look like a PoE 2 item.

    Returns an event with 'parsed': None and 'parse_error': str if the text
    passed the heuristic but the parser raised.

    Event shape:
        {
          'event_type': 'item_copied',
          'timestamp': '2026-05-27T14:30:00Z',
          'raw_text': str,
          'parsed': dict | None,
          'source': 'clipboard',
          # only present on parse failure:
          'parse_error': str,
        }
    """
    if not is_poe2_item_text(text):
        return None

    event: dict[str, Any] = {
        "event_type": "item_copied",
        "timestamp": _now_iso(),
        "raw_text": text,
        "parsed": None,
        "source": "clipboard",
    }

    try:
        item = item_parser.parse_clipboard(text)
        event["parsed"] = to_jsonable(item)
    except Exception as exc:
        event["parse_error"] = str(exc)

    return event


# ---------------------------------------------------------------------------
# Queue writer (default callback)
# ---------------------------------------------------------------------------

def write_event_to_queue(event: dict[str, Any], queue_dir: Optional[str] = None) -> str:
    """Serialize `event` as JSON and write it to the clipboard queue dir.

    Filename: '{timestamp}_{short_hash}.json'
    Returns the absolute path of the written file.
    """
    target_dir = Path(queue_dir) if queue_dir else _DEFAULT_QUEUE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    ts_tag = event.get("timestamp", _now_iso()).replace(":", "").replace("-", "")
    raw = event.get("raw_text", "")
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    filename = f"{ts_tag}_{short_hash}.json"
    dest = target_dir / filename

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(event, fh, indent=2, ensure_ascii=False)

    log.debug("wrote clipboard event to %s", dest)
    return str(dest)


# ---------------------------------------------------------------------------
# Main watcher loop
# ---------------------------------------------------------------------------

def watch_clipboard(
    callback: Callable[[dict[str, Any]], None],
    *,
    poll_interval_seconds: float = 0.25,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Poll the clipboard; call `callback(event)` for each new PoE 2 item.

    Args:
        callback: Receives the event dict. Exceptions in callback are caught
                  and logged -- one bad call never kills the watcher.
        poll_interval_seconds: How often to read the clipboard.
        stop_event: Set this threading.Event to exit the loop gracefully.
                    Pass None to run forever (e.g. in __main__).

    Change detection: tracks the last seen text by string equality. If the
    player copies the same item twice in a row, the second copy is skipped --
    the intended use case is detecting each new distinct drop.
    """
    last_text: Optional[str] = None

    while stop_event is None or not stop_event.is_set():
        try:
            text = read_clipboard()
        except Exception as exc:
            log.warning("clipboard read error: %s", exc)
            time.sleep(poll_interval_seconds)
            continue

        if text != last_text:
            last_text = text
            event = parse_clipboard_text(text)
            if event is not None:
                try:
                    callback(event)
                except Exception:
                    log.exception("callback raised an exception; continuing")

        time.sleep(poll_interval_seconds)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the clipboard listener until interrupted.

    Logs to stderr. Set a SIGINT (Ctrl+C) or SIGTERM to stop cleanly.
    """
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stop = threading.Event()

    def _handle_signal(sig: int, frame: Any) -> None:
        log.info("received signal %s, stopping", sig)
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    # SIGTERM may not fire on Windows but is harmless to register
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, ValueError):
        pass

    log.info("clipboard listener starting (poll interval %.3fs)", 0.25)
    log.info("queue dir: %s", _DEFAULT_QUEUE_DIR)

    watch_clipboard(write_event_to_queue, poll_interval_seconds=0.25, stop_event=stop)

    log.info("clipboard listener stopped")


if __name__ == "__main__":
    main()
