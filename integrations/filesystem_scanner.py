"""Detect installed PoE-related tools by canonical path.

Each probe is a fixed (name, game, candidate_paths, tags) tuple. We don't guess
or heuristic-search — every tool has a well-known install location, so the
scanner is just: for each probe, does any candidate path exist?

Cross-platform: probes are Windows-first (this is where most PoE tooling lives)
but the path expansion uses pathlib, so adding mac/linux probes later is mechanical.

The scanner reports findings; it does NOT write to PLAYER.md. Onboarding flow
consumes the results, shows them to the player, and applies tags after review.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Probe:
    name: str
    game: Optional[str]              # "poe1", "poe2", or None for game-agnostic
    candidate_paths: list[str]       # ~ and env vars get expanded
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def expanded_paths(self) -> list[Path]:
        return [Path(os.path.expandvars(os.path.expanduser(p))) for p in self.candidate_paths]


@dataclass
class ProbeResult:
    probe: Probe
    found: bool
    matched_path: Optional[Path] = None
    extra: dict = field(default_factory=dict)  # probe-specific data (file counts etc)


# Canonical install paths — Windows-first.
# Add probes here as tooling evolves; treat this as the source-of-truth registry.
KNOWN_PROBES: list[Probe] = [
    # ----- Build planners -----
    Probe(
        name="pob_poe1",
        game="poe1",
        candidate_paths=[
            "~/Documents/Path of Building Community",
            "C:/ProgramData/Path of Building Community",
        ],
        tags=["pob_user", "pob_poe1_user"],
        notes="PoB Community fork for PoE 1; carries structured patch data we can read.",
    ),
    Probe(
        name="pob_poe2",
        game="poe2",
        candidate_paths=[
            "~/Documents/Path of Building Community (PoE2)",
            "~/Documents/Path of Building Community PoE2",
            "C:/ProgramData/Path of Building Community (PoE2)",
        ],
        tags=["pob_user", "pob_poe2_user"],
        notes="PoB Community fork for PoE 2; same structured-data piggyback strategy as poe1 fork.",
    ),

    # ----- Trade / price-check overlays -----
    Probe(
        name="awakened_poe_trade",
        game="poe1",
        candidate_paths=[
            "~/AppData/Local/Programs/awakened-poe-trade",
            "~/AppData/Roaming/awakened-poe-trade",
        ],
        tags=["trade_overlay_user", "trade_engaged"],
        notes="Awakened PoE Trade — modern price-check overlay; presence => active trader.",
    ),
    Probe(
        name="poe_overlay",
        game="poe1",
        candidate_paths=[
            "~/AppData/Roaming/POE Overlay",
            "~/AppData/Local/POE Overlay",
        ],
        tags=["trade_overlay_user"],
        notes="POE Overlay (multi-purpose overlay).",
    ),
    Probe(
        name="poe_trademacro",
        game="poe1",
        candidate_paths=[
            "~/Documents/POE-TradeMacro",
            "~/Documents/POE-ItemInfo",
        ],
        tags=["trade_overlay_user", "legacy_trader"],
        notes="POE-TradeMacro AHK; veteran trader signal (predates Awakened).",
    ),

    # ----- Wealth tracking -----
    Probe(
        name="exilence_next",
        game="poe1",
        candidate_paths=[
            "~/AppData/Local/Programs/exilence-next",
            "~/AppData/Roaming/Exilence Next",
        ],
        tags=["wealth_tracker_user"],
        notes="Exilence Next — wealth tracking; streamer-adjacent / hyper-tracker signal.",
    ),

    # ----- Convenience tools -----
    Probe(
        name="chaos_recipe_enhancer",
        game="poe1",
        candidate_paths=[
            "~/AppData/Roaming/ChaosRecipeEnhancer",
            "~/AppData/Local/Programs/ChaosRecipeEnhancer",
        ],
        tags=["chaos_recipe_optimizer"],
        notes="ChaosRecipeEnhancer — mid-endgame currency optimizer.",
    ),

    # ----- Game installs -----
    Probe(
        name="poe1_install_standalone",
        game="poe1",
        candidate_paths=[
            "C:/Program Files (x86)/Grinding Gear Games/Path of Exile",
        ],
        tags=["poe1_installed"],
    ),
    Probe(
        name="poe1_install_steam",
        game="poe1",
        candidate_paths=[
            "C:/Program Files (x86)/Steam/steamapps/common/Path of Exile",
            "C:/Program Files/Steam/steamapps/common/Path of Exile",
        ],
        tags=["poe1_installed", "steam_user"],
    ),
    Probe(
        name="poe2_install_standalone",
        game="poe2",
        candidate_paths=[
            "C:/Program Files (x86)/Grinding Gear Games/Path of Exile 2",
        ],
        tags=["poe2_installed"],
    ),
    Probe(
        name="poe2_install_steam",
        game="poe2",
        candidate_paths=[
            "C:/Program Files (x86)/Steam/steamapps/common/Path of Exile 2",
            "C:/Program Files/Steam/steamapps/common/Path of Exile 2",
        ],
        tags=["poe2_installed", "steam_user"],
    ),

    # ----- Game user-data directories (configs, filters, BuildPlanner) -----
    Probe(
        name="poe1_userdata",
        game="poe1",
        candidate_paths=[
            "~/Documents/My Games/Path of Exile",
        ],
        tags=["poe1_user_data"],
        notes="PoE 1 user-data dir; we count .filter files for filter_engagement.",
    ),
    Probe(
        name="poe2_userdata",
        game="poe2",
        candidate_paths=[
            "~/Documents/My Games/Path of Exile 2",
        ],
        tags=["poe2_user_data"],
        notes="PoE 2 user-data dir; contains BuildPlanner/ if the player has used .build files.",
    ),
    Probe(
        name="poe2_buildplanner",
        game="poe2",
        candidate_paths=[
            "~/Documents/My Games/Path of Exile 2/BuildPlanner",
        ],
        tags=["buildplanner_aware"],
        notes="BuildPlanner folder — where .build files render inline in-game. Presence => discovered the format.",
    ),
    Probe(
        name="poe2_online_filters",
        game="poe2",
        candidate_paths=[
            "~/Documents/My Games/Path of Exile 2/OnlineFilters",
        ],
        tags=["filter_synced"],
        notes="OnlineFilters folder — where PoE 2 stores online-synced filters (opaque-ID names). The actual filter delivery surface in PoE 2 (PoE 1 used the user-data root for *.filter files; PoE 2 uses this).",
    ),
]


# ----- scanner -----

def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _count_filter_files(p: Path) -> int:
    try:
        return sum(1 for _ in p.glob("*.filter"))
    except OSError:
        return 0


def _count_build_files(p: Path) -> int:
    try:
        return sum(1 for _ in p.glob("*.build"))
    except OSError:
        return 0


def _count_online_filters(p: Path) -> int:
    """PoE 2 OnlineFilters uses opaque-ID file names, not the .filter extension."""
    try:
        return sum(1 for child in p.iterdir() if child.is_file())
    except OSError:
        return 0


def scan(probes: Optional[list[Probe]] = None) -> list[ProbeResult]:
    """Run all probes (or a custom subset). Returns results in registry order."""
    probes = probes if probes is not None else KNOWN_PROBES
    results: list[ProbeResult] = []
    for probe in probes:
        matched: Optional[Path] = None
        for candidate in probe.expanded_paths():
            if _safe_exists(candidate):
                matched = candidate
                break
        extra: dict = {}
        if matched is not None:
            if probe.name == "poe1_userdata":
                n = _count_filter_files(matched)
                extra["filter_files"] = n
                extra["filter_engagement"] = "custom" if n > 0 else "default"
            elif probe.name == "poe2_buildplanner":
                extra["build_files"] = _count_build_files(matched)
            elif probe.name == "poe2_online_filters":
                extra["online_filters"] = _count_online_filters(matched)
        results.append(ProbeResult(probe=probe, found=matched is not None, matched_path=matched, extra=extra))
    return results


# ----- consumer helpers -----

def found_tags(results: list[ProbeResult]) -> list[str]:
    """Collected tag names from all FOUND probes, deduplicated, sorted."""
    out: set[str] = set()
    for r in results:
        if r.found:
            out.update(r.probe.tags)
    return sorted(out)


def tools_per_game(results: list[ProbeResult]) -> dict[str, list[str]]:
    """{game: [tool_name, ...]} for installed tools, plus 'any' for game-agnostic."""
    per_game: dict[str, list[str]] = {}
    for r in results:
        if not r.found:
            continue
        key = r.probe.game or "any"
        per_game.setdefault(key, []).append(r.probe.name)
    return per_game


def summary(results: list[ProbeResult]) -> str:
    lines = ["Filesystem scan - installed PoE tools:"]
    by_game: dict[str, list[ProbeResult]] = {}
    for r in results:
        by_game.setdefault(r.probe.game or "any", []).append(r)

    for game in ("poe1", "poe2", "any"):
        if game not in by_game:
            continue
        label = {"poe1": "PoE 1", "poe2": "PoE 2", "any": "Generic"}[game]
        lines.append(f"\n  [{label}]")
        for r in by_game[game]:
            marker = "[OK]" if r.found else "[--]"
            base = f"    {marker} {r.probe.name:30s}"
            if r.found:
                base += f" @ {r.matched_path}"
                if r.extra:
                    extras = ", ".join(f"{k}={v}" for k, v in r.extra.items())
                    base += f"  ({extras})"
            lines.append(base)
    found = [r for r in results if r.found]
    tags = found_tags(results)
    lines.append(f"\n  {len(found)} of {len(results)} probes hit")
    lines.append(f"  tags: {tags}")
    return "\n".join(lines)


# ----- CLI -----

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="poe2-graph filesystem scanner")
    p.add_argument("--game", choices=["poe1", "poe2"], default=None,
                   help="filter probes to one game")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    args = p.parse_args()

    probes = [pr for pr in KNOWN_PROBES if args.game is None or pr.game == args.game]
    results = scan(probes)

    if args.json:
        import json
        payload = {
            "found": [
                {
                    "name": r.probe.name,
                    "game": r.probe.game,
                    "path": str(r.matched_path) if r.matched_path else None,
                    "tags": r.probe.tags,
                    "extra": r.extra,
                }
                for r in results if r.found
            ],
            "not_found": [r.probe.name for r in results if not r.found],
            "tags": found_tags(results),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(summary(results))


if __name__ == "__main__":
    main()
