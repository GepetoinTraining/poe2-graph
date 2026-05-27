"""Round-trip the v7 URL codec against Pedro's verified test build."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph import parser  # noqa: E402


PEDRO_URL = (ROOT / "examples" / "pedro-stormweaver.txt").read_text().strip()


def test_pedro_url_header():
    build = parser.parse(PEDRO_URL)
    assert build.version == 7
    assert build.character_class == 7  # Sorceress
    assert build.ascendancy == 1       # Stormweaver (1-indexed)
    assert len(build.records) == 142


def test_pedro_url_flag_distribution():
    """Spec §3 verified parse table."""
    build = parser.parse(PEDRO_URL)
    counts = parser.flag_summary(build)
    assert counts == {0: 75, 1: 28, 2: 34, 3: 5}


def test_pedro_url_byte_size():
    build = parser.parse(PEDRO_URL)
    assert build.encoded_size() == 687


def test_roundtrip_bytes():
    build = parser.parse(PEDRO_URL)
    raw_in = parser._decode_b64url(parser._strip_url_prefix(PEDRO_URL))
    raw_out = parser.encode(build)
    assert raw_in == raw_out


def test_roundtrip_url():
    build = parser.parse(PEDRO_URL)
    assert parser.encode_url(build) == PEDRO_URL


def test_truncated_payload_raises():
    """A payload chopped before its last record should fail loud."""
    raw = parser._decode_b64url(parser._strip_url_prefix(PEDRO_URL))
    truncated = parser._encode_b64url(raw[:-3])
    try:
        parser.parse(truncated)
    except ValueError:
        return
    raise AssertionError("expected ValueError on truncated payload")
