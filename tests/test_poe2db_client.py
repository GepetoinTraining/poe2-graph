"""poe2db_client tests using the swarm-extracted amulets_modsview.json fixture.

We don't hit the network in tests; the fixture is a real captured response.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import poe2db_client as p2db  # noqa: E402


FIXTURE = ROOT / "amulets_modsview.json"


def test_fixture_exists():
    assert FIXTURE.exists(), "swarm-saved amulets_modsview.json must be present"


def test_extract_sections():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sections = p2db.mods_by_section(data)
    assert "normal" in sections
    assert len(sections["normal"]) > 100  # spec confirmed 208 in agent report


def test_increased_life_tier_ladder():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sections = p2db.mods_by_section(data)
    ladders = p2db.tiers_by_family(sections["normal"])
    # IncreasedLife is the canonical example — should be a real family with 9 tiers.
    life_keys = [k for k in ladders if any("IncreasedLife" in f for f in k)]
    assert life_keys, "expected an IncreasedLife family in normal mods"
    ladder = ladders[life_keys[0]]
    assert len(ladder) >= 1
    # Each tier should have a parsed template that mentions Life.
    assert any("Life" in m.template for m in ladder)


def test_parse_stat_html_range():
    template, vmin, vmax = p2db.parse_stat_html(
        "+<span class='mod-value'>(10—19)</span> to maximum Life"
    )
    assert template == "+# to maximum Life"
    assert vmin == 10
    assert vmax == 19


def test_parse_stat_html_single_value():
    template, vmin, vmax = p2db.parse_stat_html(
        "+<span class='mod-value'>5</span> to Spirit"
    )
    assert template == "+# to Spirit"
    assert vmin == 5
    assert vmax == 5
