"""Stat string → structured tuple.

Stats in the tree JSON look like:
  "15% increased [Critical|Critical Hit Chance] for [Spell|Spells]"
  "+5 to [Strength]"
  "Adds 4 to 7 Physical Damage"

The `[link|display]` bracket syntax is GGG's keyword/wiki-link convention.
`[Foo]` is shorthand for `[Foo|Foo]`. Numbers are interpolated literally.

We do NOT compute damage, apply conditionals, or resolve game rules. This is a
text-shape parser that produces enough structure to aggregate identical stat
templates across nodes and overrides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# [link|display] or [link] — capture both forms
BRACKET_RE = re.compile(r"\[([^\]|]+)(?:\|([^\]]+))?\]")
# numeric runs (integers, decimals, signs) for templating
NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")


@dataclass
class Stat:
    """One parsed stat line.

    `template` is the stat with all numbers replaced by `#` and brackets
    stripped to display text — the canonical aggregation key.
    `values` is the numeric runs from the original string, in order.
    `raw` is the original text for debugging / pass-through.
    """
    template: str
    values: list[float]
    raw: str


def strip_brackets(text: str) -> str:
    """Replace [link|display] -> display, [link] -> link."""
    return BRACKET_RE.sub(lambda m: m.group(2) or m.group(1), text)


def parse(text: str) -> Stat:
    plain = strip_brackets(text)
    values: list[float] = []
    def _capture(m: re.Match[str]) -> str:
        raw = m.group(0)
        values.append(float(raw))
        prefix = raw[0] if raw[0] in "+-" else ""
        return f"{prefix}#"
    template = NUMBER_RE.sub(_capture, plain)
    template = re.sub(r"\s+", " ", template).strip()
    return Stat(template=template, values=values, raw=text)


def aggregate(stats: list[Stat]) -> dict[str, float]:
    """Sum values across identical templates.

    Caveat: only stats with a single numeric value aggregate cleanly. Multi-value
    stats (e.g. "Adds # to # damage") need consumer-side handling.
    """
    out: dict[str, float] = {}
    for s in stats:
        if len(s.values) == 1:
            out[s.template] = out.get(s.template, 0.0) + s.values[0]
    return out
