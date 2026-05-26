"""NeverSink filter recommender.

Phase-2 community handoff: we do NOT generate item filters. NeverSink owns
that surface (MIT, https://github.com/NeverSinkDev/NeverSink-Filter-for-PoE2).
What we do is pair the player's build + league phase + edges-of-interest
with a recommended strictness level and a list of post-download
customizations they can apply manually.

The output is a `.filter.md` companion file written alongside the `.build`
the player imports — not a `.filter` file. The .filter itself comes from
NeverSink's release page.

API:
  recommend_filter(character_fm, league_fm?, player_fm?, edges_of_interest?)
  render_recommendation(rec) -> str
  write_recommendation(rec, path) -> Path
  fetch_latest_release_url() -> Optional[str]
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


NEVERSINK_REPO = "NeverSinkDev/NeverSink-Filter-for-PoE2"
NEVERSINK_REPO_URL = f"https://github.com/{NEVERSINK_REPO}"
NEVERSINK_RELEASES_LATEST = f"{NEVERSINK_REPO_URL}/releases/latest"
NEVERSINK_RELEASES_API = f"https://api.github.com/repos/{NEVERSINK_REPO}/releases/latest"

# Local bundled fork — when this directory exists, the recommender can hand the
# player the actual filter file path on disk instead of pointing them at the
# release page. Filenames follow NeverSink's convention:
#   "NeverSink's filter 2 - {N}-{STRICTNESS}.filter"
# where N is 0..6 and STRICTNESS matches STRICTNESS_LEVELS (uppercased + hyphenated).
LOCAL_FORK_PATH = Path(__file__).parent / "tools" / "neversink-poe2"

# NeverSink's PoE2 strictness ladder. Adjust if the upstream taxonomy shifts;
# this list is canonical as of NeverSink-Filter-for-PoE2 0.5-era releases.
STRICTNESS_LEVELS = (
    "regular",
    "semi-strict",
    "strict",
    "very-strict",
    "uber-strict",
    "uber-plus-strict",
)


@dataclass
class FilterRecommendation:
    """A FilterRecommendation pairs a strictness level with a list of
    customization notes the player applies after downloading the base
    filter. We never modify or redistribute NeverSink's .filter file.
    """
    strictness: str
    rationale: str
    customizations: list[str] = field(default_factory=list)
    base_download_url: str = NEVERSINK_RELEASES_LATEST
    attribution: str = (
        "Filter authored by NeverSinkDev (MIT) — "
        f"{NEVERSINK_REPO_URL}. "
        "poe2-graph does not modify or redistribute the filter; "
        "we surface strictness + customization recommendations only."
    )


def recommend_filter(
    character_fm: dict[str, Any],
    league_fm: Optional[dict[str, Any]] = None,
    player_fm: Optional[dict[str, Any]] = None,
    edges_of_interest: Optional[list[str]] = None,
) -> FilterRecommendation:
    """Recommend a NeverSink strictness level + customizations.

    Strictness derives from `current_level`, `peak_wealth_tier`, `time_budget`,
    `grind_capacity`. Customizations derive from `class`/`ascendancy`/
    `archetype_tags` and the active goal's `edges_of_interest`.
    """
    league_fm = league_fm or {}
    player_fm = player_fm or {}
    edges = set(edges_of_interest or [])

    strictness, rationale = _choose_strictness(character_fm, player_fm)
    customizations = _compose_customizations(character_fm, player_fm, edges)

    return FilterRecommendation(
        strictness=strictness,
        rationale=rationale,
        customizations=customizations,
    )


def _choose_strictness(
    character_fm: dict[str, Any], player_fm: dict[str, Any]
) -> tuple[str, str]:
    """Pick strictness by level + wealth + grind, then adjust by time budget."""
    level = character_fm.get("current_level") or 0
    if not isinstance(level, int):
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = 0
    peak_wealth = (player_fm.get("peak_wealth_tier") or "").lower()
    time_budget = (player_fm.get("time_budget") or "").lower()
    grind = (player_fm.get("grind_capacity") or "").lower()

    high_wealth = peak_wealth in ("divine", "mirror")
    veteran_grind = grind in ("high", "top")

    if level < 30:
        strictness = "regular"
        rationale = f"Early levelling (lvl {level}) — see drops to learn the loot table"
    elif level < 60:
        strictness = "semi-strict"
        rationale = f"Mid-campaign (lvl {level}) — filter early bases, keep mid-tier visible"
    elif level < 80:
        if high_wealth or veteran_grind:
            strictness = "strict"
            rationale = (
                f"Endgame entry (lvl {level}) + veteran wealth/grind — strict cuts the noise"
            )
        else:
            strictness = "semi-strict"
            rationale = f"Endgame entry (lvl {level}) — semi-strict balances signal and floor"
    elif level < 95:
        if high_wealth:
            strictness = "very-strict"
            rationale = (
                f"Late endgame (lvl {level}) + high wealth tier — "
                "very-strict to surface chase items only"
            )
        else:
            strictness = "strict"
            rationale = f"Late endgame (lvl {level}) — strict cuts T1-T7 mapping noise"
    else:
        if high_wealth and veteran_grind:
            strictness = "uber-strict"
            rationale = f"95+ endgame mapper, high wealth + grind — uber-strict for divine+ farms"
        else:
            strictness = "very-strict"
            rationale = f"95+ endgame (lvl {level}) — very-strict for endgame mapping"

    # Racing time budget loosens strictness by one step (you need to see more).
    if time_budget == "racing":
        idx = STRICTNESS_LEVELS.index(strictness)
        if idx > 0:
            strictness = STRICTNESS_LEVELS[idx - 1]
            rationale += " · loosened one step for racing time budget"

    return strictness, rationale


def _compose_customizations(
    character_fm: dict[str, Any],
    player_fm: dict[str, Any],
    edges: set[str],
) -> list[str]:
    """Build the human-readable customization list. Order: class-driven →
    ascendancy-driven → edge-driven → wealth-tier-driven."""
    customizations: list[str] = []

    cls = (character_fm.get("class") or "").lower()
    asc = (character_fm.get("ascendancy") or "").lower()
    archetype_tags = {t.lower() for t in (character_fm.get("archetype_tags") or [])}

    # ----- class-driven base highlights -----
    if cls == "sorceress" or "caster" in archetype_tags:
        customizations.append(
            "Highlight Spirit-modifier item bases (Body Armours, Helmets, Boots) — caster spirit scaling"
        )
        customizations.append(
            "Highlight wand and sceptre bases at iLvl 75+ — caster weapon upgrades"
        )
    if cls == "huntress":
        customizations.append(
            "Highlight spear and bow bases at iLvl 75+ — Huntress weapon options"
        )
    if cls == "mercenary":
        customizations.append(
            "Highlight crossbow and quiver bases at iLvl 75+ — Mercenary weapon scaling"
        )
    if cls == "warrior":
        customizations.append(
            "Highlight 2H weapon bases (maces, axes, staves) at iLvl 75+ — Warrior scaling"
        )
        customizations.append(
            "Highlight Strength-tagged armour bases — Warrior gear"
        )
    if cls == "witch":
        customizations.append(
            "Highlight wand and sceptre bases at iLvl 75+ — Witch caster weapons"
        )
        if "minion" in archetype_tags or asc == "infernalist":
            customizations.append(
                "Highlight Spirit + minion-tagged gear bases — minion scaling"
            )
    if cls == "monk":
        customizations.append(
            "Highlight quarterstaff bases at iLvl 75+ — Monk scaling"
        )
    if cls == "ranger":
        customizations.append(
            "Highlight bow and quiver bases at iLvl 75+ — Ranger scaling"
        )
    if cls == "druid":
        customizations.append(
            "Highlight stave and warstaff bases at iLvl 75+ — Druid scaling"
        )

    # ----- ascendancy-specific -----
    if asc == "stormweaver":
        customizations.append(
            "Show jewels with %lightning damage / %elemental damage modifiers — Stormweaver scaling"
        )
    if asc == "titan":
        customizations.append(
            "Show jewels with armour / max-life modifiers — Titan scaling"
        )
    if asc == "warbringer":
        customizations.append(
            "Show totem-tagged supports and gear — Warbringer scaling"
        )
    if asc == "deadeye":
        customizations.append(
            "Show jewels with %projectile damage / %attack speed — Deadeye scaling"
        )
    if asc == "infernalist":
        customizations.append(
            "Show fire-resist gear bases unconditionally — Infernalist self-damage discipline"
        )
    if asc == "gemling legionnaire" or asc == "gemling":
        customizations.append(
            "Show all int-stacking jewels (cluster + standard) — Gemling Archmage scaling"
        )

    # ----- edge-driven -----
    if "marginal_capability_thinking" in edges:
        customizations.append(
            "Keep upgrade-tier items visible at iLvl 75+ even at strict — "
            "you're at the upgrade-pacing fork"
        )
    if "option_value_vs_face_value" in edges:
        customizations.append(
            "Show all uniques unconditionally — option-value items often look unimpressive at face"
        )
    if "currency_velocity" in edges or "flow_anticipation" in edges:
        customizations.append(
            "Annotate currency tiers (Regals, Exalts, Divines) with sound cues — flow tracking"
        )
    if "posture_under_drop" in edges:
        customizations.append(
            "Add distinct alert sound for Divine Orb and rarer — "
            "discrete signal for big-drop posture practice"
        )

    # ----- wealth-tier driven -----
    peak_wealth = (player_fm.get("peak_wealth_tier") or "").lower()
    if peak_wealth in ("divine", "mirror"):
        customizations.append(
            "Add Mirror + Exalted Orb tier highlights (high-end currency sounds)"
        )

    return customizations


def render_recommendation(rec: FilterRecommendation) -> str:
    """Format a FilterRecommendation as a player-readable markdown block.

    If a local bundled filter file exists for the chosen strictness, surface
    its path so the player can copy from disk instead of downloading.
    """
    lines = [
        "## Filter recommendation",
        "",
        f"**Strictness**: `{rec.strictness}`",
        f"**Why**: {rec.rationale}",
        "",
    ]
    local = local_filter_path(rec.strictness)
    if local is not None:
        lines.append(f"**Local file** (bundled NeverSink, MIT): `{local}`")
    lines.append(f"**Download** (NeverSink, MIT): {rec.base_download_url}")
    lines.append("")
    if rec.customizations:
        lines.append("**Customizations to apply after download:**")
        for c in rec.customizations:
            lines.append(f"- {c}")
        lines.append("")
    lines.append(f"_{rec.attribution}_")
    return "\n".join(lines)


def write_recommendation(rec: FilterRecommendation, path: Path) -> Path:
    """Write the recommendation as a `<character_id>.filter.md` companion.

    Does NOT write a `.filter` file — that comes from NeverSink's release.
    We emit the markdown so the player can keep it open alongside the build.
    """
    path.write_text(render_recommendation(rec), encoding="utf-8")
    return path


def local_filter_files_dir() -> Optional[Path]:
    """Return the bundled NeverSink-PoE2 filter directory if present, else None.

    The fork at `tools/neversink-poe2/` carries all 7 strictness `.filter` files
    + 5 style packs locally. When this returns a path, callers can read filter
    contents directly from disk without a network round-trip.
    """
    if LOCAL_FORK_PATH.exists() and LOCAL_FORK_PATH.is_dir():
        return LOCAL_FORK_PATH
    return None


# Map of STRICTNESS_LEVELS values → NeverSink's filename suffix conventions.
_LOCAL_FILTER_SUFFIX = {
    "regular":          "1-REGULAR",
    "semi-strict":      "2-SEMI-STRICT",
    "strict":           "3-STRICT",
    "very-strict":      "4-VERY-STRICT",
    "uber-strict":      "5-UBER-STRICT",
    "uber-plus-strict": "6-UBER-PLUS-STRICT",
}


def local_filter_path(strictness: str) -> Optional[Path]:
    """Return the path to the bundled filter file for the given strictness,
    or None if the fork isn't checked out / the file isn't present.

    Filename pattern: "NeverSink's filter 2 - {N}-{STRICTNESS}.filter"
    """
    base = local_filter_files_dir()
    if base is None:
        return None
    suffix = _LOCAL_FILTER_SUFFIX.get(strictness)
    if suffix is None:
        # 'regular' fallback for the 0-SOFT level if upstream ever ships it
        if strictness == "soft":
            suffix = "0-SOFT"
        else:
            return None
    candidate = base / f"NeverSink's filter 2 - {suffix}.filter"
    if candidate.exists():
        return candidate
    return None


def fetch_latest_release_url(timeout: float = 5.0) -> Optional[str]:
    """Query GitHub for the latest NeverSink-Filter-for-PoE2 release URL.

    Returns the release's html_url, or None if the API call fails (offline,
    rate-limited, etc.). Callers should fall back to `NEVERSINK_RELEASES_LATEST`
    which is the always-current release-page URL.
    """
    try:
        req = urllib.request.Request(
            NEVERSINK_RELEASES_API,
            headers={"User-Agent": "poe2-graph/0.x"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("html_url")
    except Exception:
        return None
