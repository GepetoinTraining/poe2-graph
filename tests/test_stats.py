from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import stats  # noqa: E402


def test_strip_brackets_link_form():
    assert stats.strip_brackets("[Critical|Critical Hit Chance]") == "Critical Hit Chance"


def test_strip_brackets_short_form():
    assert stats.strip_brackets("[Strength]") == "Strength"


def test_parse_extracts_value_and_template():
    s = stats.parse("15% increased [Critical|Critical Hit Chance] for [Spell|Spells]")
    assert s.values == [15.0]
    assert s.template == "#% increased Critical Hit Chance for Spells"


def test_parse_signed_value():
    s = stats.parse("+5 to [Strength]")
    assert s.values == [5.0]
    assert s.template == "+# to Strength"


def test_parse_multivalue():
    s = stats.parse("Adds 4 to 7 Physical Damage")
    assert s.values == [4.0, 7.0]
    assert s.template == "Adds # to # Physical Damage"


def test_aggregate_sums_identical_templates():
    parsed = [
        stats.parse("+5 to [Strength]"),
        stats.parse("+5 to [Strength]"),
        stats.parse("+3 to [Strength]"),
    ]
    agg = stats.aggregate(parsed)
    assert agg == {"+# to Strength": 13.0}
