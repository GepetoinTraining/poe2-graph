"""Tests for integrations.clipboard_listener."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.clipboard_listener import (  # noqa: E402
    is_poe2_item_text,
    parse_clipboard_text,
    watch_clipboard,
    write_event_to_queue,
    read_clipboard,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WAND_ITEM = """\
Item Class: Wands
Rarity: Rare
Doom Glow
Diamond Wand
--------
Quality: +5% (augmented)
[Spirit] [12]
--------
Requirements:
Level: 32
Int: 53
--------
Item Level: 33
--------
+1 to Level of all Spell Skills (rune)
--------
Adds 11 to 18 Cold Damage to Spells
24% increased Spell Damage
+25 to maximum Mana
+22 to Intelligence
--------
{ rune: 'iron-rune' }
"""

RING_ITEM = """\
Item Class: Rings
Rarity: Magic
Glowing Band of Fortune
--------
Item Level: 45
--------
+15 to maximum Life
"""

PLAIN_TEXT = "Hello, this is a normal paragraph.\nIt does not have any item structure."

CODE_SNIPPET = "def foo(x):\n    return x + 1\n"

URL_TEXT = "https://www.pathofexile.com/trade/search/poe2/abc123"


# ---------------------------------------------------------------------------
# is_poe2_item_text
# ---------------------------------------------------------------------------

def test_is_poe2_item_text_true_for_wand():
    assert is_poe2_item_text(WAND_ITEM) is True


def test_is_poe2_item_text_true_for_ring():
    assert is_poe2_item_text(RING_ITEM) is True


def test_is_poe2_item_text_true_only_rarity_line():
    # Minimal: just a Rarity line should be enough.
    assert is_poe2_item_text("Rarity: Normal\nFoo Bar\n--------\n") is True


def test_is_poe2_item_text_true_separator_block():
    # A separator block alone is a positive signal.
    assert is_poe2_item_text("--------\nsome stat\n--------") is True


def test_is_poe2_item_text_false_plain():
    assert is_poe2_item_text(PLAIN_TEXT) is False


def test_is_poe2_item_text_false_code():
    assert is_poe2_item_text(CODE_SNIPPET) is False


def test_is_poe2_item_text_false_url():
    assert is_poe2_item_text(URL_TEXT) is False


def test_is_poe2_item_text_false_empty():
    assert is_poe2_item_text("") is False


def test_is_poe2_item_text_false_whitespace_only():
    assert is_poe2_item_text("   \n\t\n  ") is False


# ---------------------------------------------------------------------------
# parse_clipboard_text
# ---------------------------------------------------------------------------

def test_parse_clipboard_text_returns_none_for_plain():
    result = parse_clipboard_text(PLAIN_TEXT)
    assert result is None


def test_parse_clipboard_text_returns_none_for_empty():
    result = parse_clipboard_text("")
    assert result is None


def test_parse_clipboard_text_valid_item_returns_event():
    result = parse_clipboard_text(WAND_ITEM)
    assert result is not None
    assert result["event_type"] == "item_copied"
    assert result["source"] == "clipboard"
    assert result["raw_text"] == WAND_ITEM
    assert "timestamp" in result
    # parsed should be a non-None dict
    assert result["parsed"] is not None
    assert isinstance(result["parsed"], dict)
    assert "parse_error" not in result


def test_parse_clipboard_text_event_shape_complete():
    result = parse_clipboard_text(WAND_ITEM)
    required_keys = {"event_type", "timestamp", "raw_text", "parsed", "source"}
    assert required_keys.issubset(result.keys())


def test_parse_clipboard_text_item_shaped_but_broken_returns_parse_error():
    # Looks like an item (has Item Class header) but body is malformed enough
    # to not produce a valid parse (no Rarity line present).
    broken_text = "Item Class: Wands\n--------\nsome garbage\n"
    result = parse_clipboard_text(broken_text)
    # Should match the heuristic (has "Item Class:")
    assert result is not None
    # Parser will raise ValueError for missing Rarity
    assert result["parsed"] is None
    assert "parse_error" in result
    assert isinstance(result["parse_error"], str)


# ---------------------------------------------------------------------------
# watch_clipboard
# ---------------------------------------------------------------------------

def _make_stop(after: float = 0.0) -> threading.Event:
    """Return a stop event that fires after `after` seconds."""
    evt = threading.Event()
    if after > 0:
        threading.Timer(after, evt.set).start()
    else:
        evt.set()
    return evt


def test_watch_clipboard_calls_callback_for_new_item(tmp_path):
    """Callback is invoked once when a new item appears on the clipboard."""
    calls = []

    def cb(event):
        calls.append(event)

    stop = threading.Event()
    paste_values = [WAND_ITEM]
    call_count = [0]

    def fake_paste():
        idx = min(call_count[0], len(paste_values) - 1)
        call_count[0] += 1
        return paste_values[idx]

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        # Run enough polls to process the item, then stop.
        def stopper():
            time.sleep(0.2)
            stop.set()

        t = threading.Thread(target=stopper, daemon=True)
        t.start()
        watch_clipboard(cb, poll_interval_seconds=0.05, stop_event=stop)

    assert len(calls) == 1
    assert calls[0]["event_type"] == "item_copied"


def test_watch_clipboard_no_duplicate_for_same_text():
    """Same item text appearing twice (no change) triggers callback only once."""
    calls = []

    def cb(event):
        calls.append(event)

    stop = threading.Event()
    # Every poll returns the same wand item.
    poll_count = [0]

    def fake_paste():
        poll_count[0] += 1
        if poll_count[0] > 4:
            stop.set()
        return WAND_ITEM

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(cb, poll_interval_seconds=0.01, stop_event=stop)

    assert len(calls) == 1


def test_watch_clipboard_no_callback_for_plain_text():
    """Clipboard changes with plain text do not fire the callback."""
    calls = []

    def cb(event):
        calls.append(event)

    stop = threading.Event()
    texts = [PLAIN_TEXT, CODE_SNIPPET, URL_TEXT, ""]
    idx = [0]

    def fake_paste():
        val = texts[idx[0] % len(texts)]
        idx[0] += 1
        if idx[0] >= len(texts) + 2:
            stop.set()
        return val

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(cb, poll_interval_seconds=0.01, stop_event=stop)

    assert calls == []


def test_watch_clipboard_exits_on_stop_event():
    """Loop exits promptly when stop_event is set."""
    stop = threading.Event()
    stop.set()  # already stopped before the loop runs

    called = []

    def fake_paste():
        called.append(1)
        return PLAIN_TEXT

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(lambda e: None, poll_interval_seconds=0.01, stop_event=stop)

    # With stop already set, the loop body should not execute at all.
    assert called == []


def test_watch_clipboard_callback_exception_does_not_kill_loop():
    """An exception in callback is caught; subsequent items still processed."""
    results = []
    call_count = [0]

    def cb(event):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("simulated callback error")
        results.append(event)

    stop = threading.Event()
    texts = [WAND_ITEM, RING_ITEM]
    idx = [0]

    def fake_paste():
        if idx[0] >= len(texts):
            stop.set()
            return ""
        val = texts[idx[0]]
        idx[0] += 1
        return val

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(cb, poll_interval_seconds=0.01, stop_event=stop)

    # First call raised, second should still be processed.
    assert len(results) == 1


def test_watch_clipboard_two_different_items_trigger_twice():
    """Two distinct item pastes each fire the callback exactly once."""
    calls = []

    def cb(event):
        calls.append(event["raw_text"])

    stop = threading.Event()
    texts = [WAND_ITEM, RING_ITEM]
    idx = [0]

    def fake_paste():
        if idx[0] >= len(texts):
            stop.set()
            return ""
        val = texts[idx[0]]
        idx[0] += 1
        return val

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(cb, poll_interval_seconds=0.01, stop_event=stop)

    assert len(calls) == 2
    assert WAND_ITEM in calls
    assert RING_ITEM in calls


# ---------------------------------------------------------------------------
# write_event_to_queue
# ---------------------------------------------------------------------------

def test_write_event_to_queue_creates_json_file(tmp_path):
    event = {
        "event_type": "item_copied",
        "timestamp": "20260527T143000Z",
        "raw_text": WAND_ITEM,
        "parsed": {"rarity": "rare"},
        "source": "clipboard",
    }
    path = write_event_to_queue(event, queue_dir=str(tmp_path))
    assert Path(path).exists()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["event_type"] == "item_copied"
    assert data["parsed"]["rarity"] == "rare"


def test_write_event_to_queue_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    event = {
        "event_type": "item_copied",
        "timestamp": "20260527T143000Z",
        "raw_text": "x",
        "parsed": None,
        "source": "clipboard",
    }
    path = write_event_to_queue(event, queue_dir=str(nested))
    assert Path(path).exists()


def test_write_event_to_queue_filenames_are_unique(tmp_path):
    """Rapid sequential writes produce distinct filenames."""
    event_a = {
        "event_type": "item_copied",
        "timestamp": "20260527T143000Z",
        "raw_text": WAND_ITEM,
        "parsed": None,
        "source": "clipboard",
    }
    event_b = {
        "event_type": "item_copied",
        "timestamp": "20260527T143001Z",
        "raw_text": RING_ITEM,
        "parsed": None,
        "source": "clipboard",
    }
    path_a = write_event_to_queue(event_a, queue_dir=str(tmp_path))
    path_b = write_event_to_queue(event_b, queue_dir=str(tmp_path))
    assert path_a != path_b


# ---------------------------------------------------------------------------
# Integration: two distinct items via mocked clipboard -> two callbacks
# ---------------------------------------------------------------------------

def test_integration_two_items_two_callbacks():
    """Full integration: mock clipboard returns two items; callback fires twice."""
    received = []

    def cb(event):
        received.append(event)

    stop = threading.Event()
    items = [WAND_ITEM, RING_ITEM]
    idx = [0]

    def fake_paste():
        if idx[0] >= len(items):
            stop.set()
            return ""
        val = items[idx[0]]
        idx[0] += 1
        return val

    with patch("integrations.clipboard_listener.read_clipboard", side_effect=fake_paste):
        watch_clipboard(cb, poll_interval_seconds=0.01, stop_event=stop)

    assert len(received) == 2
    event_types = {e["event_type"] for e in received}
    assert event_types == {"item_copied"}
    raw_texts = {e["raw_text"] for e in received}
    assert WAND_ITEM in raw_texts
    assert RING_ITEM in raw_texts
