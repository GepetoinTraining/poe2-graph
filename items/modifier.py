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
    """
    family: str
    tier: int = 0                        # 0 = unknown / un-hydrated
    values: list[float] = field(default_factory=list)
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
        # Replace each '#' with the corresponding value in order
        result = tmpl
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
#   "+(10—15)% increased Lightning Damage" → range syntax, used by poe2db raw text
#
# This is the inverse of Modifier.render(); useful when ingesting in-game text
# without yet knowing which catalog tier it matches.

_VALUE_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")
# Tighter pattern that doesn't consume the sign — preserves literal `+`/`-`
# prefixes in templates ("+# to maximum Life" vs "# to maximum Life").
_VALUE_PATTERN_NO_SIGN = re.compile(r"(?<![+-])-?\d+(?:\.\d+)?|(?<=[+-])\d+(?:\.\d+)?")


def extract_values(rendered: str) -> list[float]:
    """Extract numeric values from a rendered mod string.

    Includes signed values (the sign IS part of the numeric value, e.g.
    "-5% Cold Resistance" → [-5.0]).
    """
    return [float(m.group()) for m in _VALUE_PATTERN.finditer(rendered)]


def to_template(rendered: str) -> str:
    """Replace numeric values in a rendered string with '#' placeholders.

    Preserves literal signs ('+' / '-') as part of the template:
        "+12 to maximum Life"  →  "+# to maximum Life"
        "-5% Cold Resistance"  →  "-#% Cold Resistance"
    Inverse of Modifier.render() — the result is suitable as a ModTier.template.
    """
    return _VALUE_PATTERN_NO_SIGN.sub("#", rendered)
