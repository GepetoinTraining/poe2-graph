"""Modifier — a mod actually rolled on a specific Item.

The schema-side template (ModTier, with value ranges + iLvl gates) lives
in `catalog.mod_tier`. This module is just the per-item instance: the
rolled values, the crafting-state flags (fractured / crafted / implicit /
corrupted-implicit), plus small helpers used by the clipboard parser.

`family` + `tier` on a Modifier join back to the ModTier catalog. Hydrating
those join keys from the rendered text is `catalog.hydrate`'s job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Modifier:
    """A modifier actually rolled on a specific Item.

    `family` + `tier` join back to the ModTier catalog. `values` are the
    rolled numbers (positional — matches the order of `#` in the template).

    `value_ranges` is populated INSTEAD of `values` when the input is an
    unidentified mod, where the game prints the possible roll range like
    "+(110-129) to maximum Life" instead of a single rolled scalar. When
    `value_ranges` is non-empty, the owning Item is unidentified and
    `values` is empty.
    """
    family: str
    tier: int = 0                        # 0 = unknown / un-hydrated
    values: list[float] = field(default_factory=list)
    value_ranges: list[tuple[float, float]] = field(default_factory=list)
    template: Optional[str] = None       # may be set when un-hydrated (parser knows the rendered text but not the catalog yet)
    is_fractured: bool = False           # locked by FracturingOrb
    is_crafted: bool = False             # bench-crafted (well-of-souls etc.)
    is_implicit: bool = False            # implicit (base or corrupted)
    is_corrupted_implicit: bool = False  # added/changed by Vaal Orb

    def render(self, tier_template: Optional[str] = None) -> str:
        """Apply self.values into the template, returning the display text.

        Uses self.template if provided; otherwise the caller passes a tier
        template (looked up from the ModPool catalog).
        """
        tmpl = tier_template or self.template
        if tmpl is None:
            # Last-ditch: render values inline without template
            return " ".join(_fmt_value(v) for v in self.values)
        result = tmpl
        # If this is an unidentified mod, render ranges into the template's
        # `#` slots; otherwise render the rolled scalars.
        if self.value_ranges and not self.values:
            for lo, hi in self.value_ranges:
                result = result.replace("#", f"({_fmt_value(lo)}-{_fmt_value(hi)})", 1)
        else:
            for v in self.values:
                result = result.replace("#", _fmt_value(v), 1)
        return result


def _fmt_value(v: float) -> str:
    """Format a rolled value for display: integer values as int, floats with 1 decimal."""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


# Convenience: parse a rendered template back into (template_with_hashes, values).
#
# Example:
#   "+12 to maximum Life" + template "+# to maximum Life" → values [12.0]
#   "+(110-129) to maximum Life" → unidentified range, value_ranges [(110, 129)]
#
# This is the inverse of Modifier.render(); useful when ingesting in-game text
# without yet knowing which catalog tier it matches.

_VALUE_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")
# Tighter pattern that doesn't consume the sign — preserves literal `+`/`-`
# prefixes in templates ("+# to maximum Life" vs "# to maximum Life").
_VALUE_PATTERN_NO_SIGN = re.compile(r"(?<![+-])-?\d+(?:\.\d+)?|(?<=[+-])\d+(?:\.\d+)?")

# Unidentified-item range syntax: `(low-high)` with hyphen, en-dash (–), or
# em-dash (—) as the separator. Either bound may carry a leading sign, and an
# outer `-`/`+` before the open-paren applies to the whole range (poe2db
# prints reduction mods as `-(5-10)%`).
_RANGE_PATTERN = re.compile(
    r"(?P<outer>[-+]?)\(\s*"
    r"(?P<lo>[-+]?\d+(?:\.\d+)?)\s*"
    r"[-–—]\s*"
    r"(?P<hi>[-+]?\d+(?:\.\d+)?)"
    r"\s*\)"
)


def extract_value_ranges(rendered: str) -> list[tuple[float, float]]:
    """Extract `(min, max)` range bounds from an unidentified mod line.

    Returns one tuple per `(min-max)` group in the line. Multi-stat mods
    (e.g. "Adds (5-10) to (15-25) Physical Damage") return two tuples.
    An outer `-` immediately before the open-paren is absorbed into both
    bounds so the stored numbers carry the full sign — `-(5-10)%` yields
    `(-5.0, -10.0)`. A `+` is kept on the template side by `to_template`.
    Returns `[]` if no range syntax is present — the mod is identified.
    """
    out: list[tuple[float, float]] = []
    for m in _RANGE_PATTERN.finditer(rendered):
        lo = float(m.group("lo"))
        hi = float(m.group("hi"))
        if m.group("outer") == "-":
            lo, hi = -lo, -hi
        out.append((lo, hi))
    return out


def extract_values(rendered: str) -> list[float]:
    """Extract numeric values from a rendered mod string.

    Includes signed values (the sign IS part of the numeric value, e.g.
    "-5% Cold Resistance" → [-5.0]). Range syntax like `(110-129)` is
    treated as a single template slot — its bounds belong on
    `value_ranges` instead, so they're stripped before scalar extraction.
    """
    text = _strip_ranges_for_template(rendered)
    return [float(m.group()) for m in _VALUE_PATTERN.finditer(text)]


def to_template(rendered: str) -> str:
    """Replace numeric values in a rendered string with '#' placeholders.

    Preserves a leading `+` (and renders the absorbed `-` as part of the
    value, not the template) so `+#` and `#` templates round-trip with
    the loader's output:
        "+12 to maximum Life"      →  "+# to maximum Life"
        "-5% Cold Resistance"      →  "#% Cold Resistance"   (sign on values)
        "+(110-129) to max Life"   →  "+# to max Life"        (range → one slot)
        "-(5-10)% reduced ..."     →  "#% reduced ..."        (sign on ranges)
    Inverse of Modifier.render() — the result is suitable as a ModTier.template.
    """
    text = _strip_ranges_for_template(rendered)
    return _VALUE_PATTERN_NO_SIGN.sub("#", text)


def _strip_ranges_for_template(text: str) -> str:
    """Replace `(low-high)` ranges with `#`, absorbing a leading `-` into
    the conceptual value and preserving a leading `+` on the template side.

    Used by both `extract_values` (to avoid re-counting range bounds) and
    `to_template` (to produce the same shape the catalog loader emits).
    """
    def replace(m: re.Match) -> str:
        return "+#" if m.group("outer") == "+" else "#"
    return _RANGE_PATTERN.sub(replace, text)
