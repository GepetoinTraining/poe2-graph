"""EXILE — per-player profile system.

Layout:

  ~/.claude/projects/<project-id>/EXILE.xml    ← generated index, lives in projects
  D:/poe2-graph/EXILE/                          ← player data, lives in the skill
    DONE                                        ← marker file once onboarded
    PLAYER.md                                   ← durable: years_played, knowledge, prefs
    PLAYER.initial.md                           ← first-synth snapshot
    PLAYER.diffs/                               ← timestamped diff log
    LEAGUE_<id>.md                              ← per-league context
    LEAGUE_<id>.initial.md
    LEAGUE_<id>.diffs/
    CHARACTER_<slug>.md                         ← per-character profile
    CHARACTER_<slug>.build                      ← companion .build file
  .env                                          ← account name (gitignored)

Sensitive data (account name, real name) lives in .env, never in PLAYER.md.

Tags carry confidence in [0, 1) where 1.0 is unreachable. Asymptotic Bayesian
bumps: new = old + (1 - old) * delta for positive delta, new = old + old * delta
for negative (delta < 0). One character is active; the rest dormant.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape as xml_escape

import yaml


# ----- paths -----

SKILL_ROOT = Path(__file__).parent
EXILE_DIR = SKILL_ROOT / "EXILE"
DONE_FILE = EXILE_DIR / "DONE"
ENV_FILE = SKILL_ROOT / ".env"


def project_exile_xml_path() -> Path:
    """The EXILE.xml lives in ~/.claude/projects/<project-id>/EXILE.xml.

    The project id is the skill-root path with separators converted (e.g.
    D:/poe2-graph -> D--poe2-graph). This mirrors Claude Code's convention.
    """
    project_id = str(SKILL_ROOT).replace(":", "").replace("\\", "-").replace("/", "-").strip("-")
    # On Windows paths look like "Dpoe2-graph" after stripping ":"; ensure separator
    project_id = re.sub(r"^([A-Za-z])([A-Za-z])", r"\1--\2", project_id)
    return Path.home() / ".claude" / "projects" / project_id / "EXILE.xml"


# ----- templates -----

NOW = lambda: datetime.now(timezone.utc).date().isoformat()


def player_template() -> str:
    return f"""---
schema_version: 1
created: {NOW()}
last_updated: {NOW()}

# Identity (account name goes in .env, NOT here)
joined: null            # iso-date, when you first started PoE
years_played: null
default_game: null      # poe1 | poe2 | both

# Knowledge — what you confidently know vs. don't (tag: confidence, 0-1).
# Confidence asymptotes to 1.0 — never reaches it.
# Game-agnostic tags live at the top; game-specific tags nest under poe1/poe2.
# Edge tags (posture_under_drop, market_timing, ...) go under their game scope.
knows: {{}}             # e.g. trade_engagement: 0.9
                        #      poe1: {{essence_crafting: 0.85, atlas_routing: 0.8}}
                        #      poe2: {{posture_under_drop: 0.4, market_timing: 0.2}}
unknown: {{}}

# Preferences — archetype / playstyle / mode (same shape as knows)
prefers: {{}}           # e.g. hardcore: 0.6
                        #      poe1: {{necromancer: 0.8}}
                        #      poe2: {{caster: 0.7}}
                        # Creator dispositions can nest here too:
                        #      ben_: 0.7  (player likes this creator)

# Hard constraints — these apply per-game; nest if they differ.
mode: null              # hc | sc, or {{poe1: hc, poe2: sc}}
trade: null             # trade | ssf
time_budget: null       # racing | dedicated | standard | casual

# Capacity signals (account-wide, not per-game — your peak wealth is your peak wealth)
grind_capacity: null        # low | medium | high | top
crafting_engagement: null   # none | opportunistic | deliberate
peak_wealth_tier: null      # league_start | mid | divine | mirror
systems_knowledge: null     # basic | intermediate | deep

# Detected toolchain (from filesystem scanner). Per-game where it matters.
tools_installed: []         # e.g. [pob_poe1, pob_poe2, awakened_poe_trade]

# Player goals — cross-league, durable identity-level objectives.
# Distinct from league_goals (in-league tactical) and character milestones.
# See goals.PlayerGoal for the structure.
player_goals: []            # [{{id, statement, type, horizon, measurable, measure, related_edges, progress}}]
---

# Notes

Free-form context tags can't capture.
"""


def league_template(league_id: str, game: str = "poe2") -> str:
    return f"""---
schema_version: 1
created: {NOW()}
last_updated: {NOW()}

league_id: {league_id}
game: {game}              # poe2 | poe1
started: null
goal: null                # one-sentence statement
goal_tags: []

challenges_target: null

active_mechanics: []      # league-specific mechanics engaged with

# League goals — in-league tactical objectives. Each goal has:
#   type: economic | mechanical | knowledge | identity
#   measurable: bool;  measure: str (how progress is checked)
#   related_edges: [edge_name, ...] from data/guides/edge_taxonomy.yaml
#   deadline: optional "league_week_N" or iso-date
#   progress: 0..1
# See goals.LeagueGoal for the dataclass.
league_goals: []

# Learning goals (legacy v0.3) — mechanic-mastery objectives.
# Will gradually merge into knows.<game>.<edge_name> confidence tracking on
# PLAYER.md as the case-study system matures.
learning_goals: []

session_log: []           # quick session-by-session notes
---

# Notes
"""


def character_template(character_id: str, league_id: str = "", game: str = "poe2") -> str:
    return f"""---
schema_version: 1
created: {NOW()}
last_updated: {NOW()}

character_id: {character_id}
character_name: null
game: {game}              # poe1 | poe2 (explicit; not inferred from league)
class: null
ascendancy: null
status: dormant           # active | dormant — exclusivity is per-game
build_file: {character_id}.build
build_url: null
current_level: null
league: {league_id}

archetype_tags: []        # caster, attacker, minion, totem, dot, hit, crit, ...
defense_tags: []          # armour, evasion, es, block, dodge, parry
offense_tags: []          # phys, fire, cold, lightning, chaos, ele, ...

milestones: []
goals_for_character: []
---

# Build notes
"""


ENV_EXAMPLE = """# Your PoE account name + discriminator. Used for OAuth/trade API calls.
# This file is gitignored. Never written into PLAYER.md.
POE_ACCOUNT_NAME=AccountName#1234

# Optional: a current character name to scope OAuth requests
POE_CHARACTER_NAME=

# Optional: poe2db language (defaults to us)
POE2DB_LANG=us
"""


# ----- frontmatter IO -----

_FM_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body)."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def write_frontmatter(fm: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"---\n{yaml_text}---\n{body if body.startswith(chr(10)) else chr(10) + body}"


def read_file(path: Path) -> tuple[dict[str, Any], str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def write_file(path: Path, fm: dict[str, Any], body: str) -> None:
    fm = dict(fm)
    fm["last_updated"] = NOW()
    path.write_text(write_frontmatter(fm, body), encoding="utf-8")


# ----- confidence math -----

def bump_confidence(current: float, delta: float) -> float:
    """Asymptotic update toward (but never reaching) 1.0.

    Positive delta moves toward 1: new = old + (1 - old) * delta.
    Negative delta moves toward 0: new = old + old * delta  (delta < 0).

    Examples:
      bump_confidence(0.0, 0.5)  == 0.5
      bump_confidence(0.5, 0.5)  == 0.75
      bump_confidence(0.75, 0.5) == 0.875
      bump_confidence(0.5, -0.3) == 0.35
    """
    if not (-1.0 <= delta <= 1.0):
        raise ValueError(f"delta must be in [-1, 1], got {delta}")
    if delta >= 0:
        # Asymptotic toward 1.0; with delta < 1, the result is strictly < 1 if current < 1.
        return current + (1.0 - current) * delta
    return max(0.0, current + current * delta)


def update_tag(
    fm: dict[str, Any],
    section: str,
    tag: str,
    delta: float,
    game: Optional[str] = None,
) -> float:
    """Bump a tag's confidence in `fm[section]` (or `fm[section][game]` if scoped).

    Game-agnostic: tag lives at fm[section][tag].
    Game-scoped:   tag lives at fm[section][game][tag] (game in {'poe1', 'poe2'}).

    Returns the new value.
    """
    section_data = fm.setdefault(section, {})
    if section_data is None:
        section_data = {}
        fm[section] = section_data

    if game:
        target = section_data.setdefault(game, {})
        if not isinstance(target, dict):
            target = {}
            section_data[game] = target
    else:
        target = section_data

    raw = target.get(tag, 0.0)
    current = float(raw) if isinstance(raw, (int, float)) else 0.0
    new = bump_confidence(current, delta)
    target[tag] = round(new, 4)
    return new


def get_tag(
    fm: dict[str, Any],
    section: str,
    tag: str,
    game: Optional[str] = None,
) -> float:
    """Read a tag's confidence. Returns 0.0 if absent."""
    section_data = fm.get(section) or {}
    if game:
        target = section_data.get(game) or {}
    else:
        target = section_data
    if not isinstance(target, dict):
        return 0.0
    raw = target.get(tag, 0.0)
    return float(raw) if isinstance(raw, (int, float)) else 0.0


# ----- diff log -----

def _diffs_dir(path: Path) -> Path:
    return path.parent / f"{path.stem}.diffs"


def snapshot(path: Path, label: str = "") -> Path:
    """Save current file state to a timestamped diff log entry.

    The first call also creates `<stem>.initial.<ext>` if not present.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    initial = path.with_name(f"{path.stem}.initial{path.suffix}")
    if not initial.exists():
        shutil.copyfile(path, initial)

    diffs = _diffs_dir(path)
    diffs.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-") if label else "snap"
    out = diffs / f"{ts}_{safe_label}.md"
    out.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return out


def diff_against_initial(path: Path) -> str:
    """Unified diff between current file and its .initial snapshot."""
    initial = path.with_name(f"{path.stem}.initial{path.suffix}")
    if not initial.exists():
        return ""
    a = initial.read_text(encoding="utf-8").splitlines(keepends=True)
    b = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile=initial.name, tofile=path.name))


def diff_history(path: Path) -> list[Path]:
    """List of snapshot files in chronological order."""
    d = _diffs_dir(path)
    if not d.exists():
        return []
    return sorted(d.glob("*.md"))


# ----- onboarding state -----

def is_onboarded() -> bool:
    return DONE_FILE.exists()


def mark_done(notes: str = "") -> Path:
    EXILE_DIR.mkdir(exist_ok=True)
    DONE_FILE.write_text(
        f"onboarding completed: {datetime.now(timezone.utc).isoformat()}\n{notes}",
        encoding="utf-8",
    )
    return DONE_FILE


def init_skeleton() -> dict[str, Path]:
    """Create EXILE/ with empty templates if not already present. Idempotent."""
    EXILE_DIR.mkdir(exist_ok=True)
    created: dict[str, Path] = {}

    player = EXILE_DIR / "PLAYER.md"
    if not player.exists():
        player.write_text(player_template(), encoding="utf-8")
        created["PLAYER.md"] = player

    if not ENV_FILE.exists():
        env_example = SKILL_ROOT / ".env.example"
        if not env_example.exists():
            env_example.write_text(ENV_EXAMPLE, encoding="utf-8")
            created[".env.example"] = env_example

    return created


# ----- character management -----

CHARACTER_FILENAME_RE = re.compile(r"^CHARACTER_([A-Za-z0-9_-]+)\.md$")


def list_characters(game: Optional[str] = None) -> list[str]:
    """Return all character ids, optionally filtered by game (poe1|poe2)."""
    if not EXILE_DIR.exists():
        return []
    ids: list[str] = []
    for p in EXILE_DIR.iterdir():
        m = CHARACTER_FILENAME_RE.match(p.name)
        if not m:
            continue
        if game is not None:
            fm, _ = read_file(p)
            if fm.get("game") != game:
                continue
        ids.append(m.group(1))
    return sorted(ids)


def create_character(character_id: str, league_id: str = "", game: str = "poe2") -> Path:
    EXILE_DIR.mkdir(exist_ok=True)
    path = EXILE_DIR / f"CHARACTER_{character_id}.md"
    if path.exists():
        return path
    path.write_text(character_template(character_id, league_id, game), encoding="utf-8")
    return path


def set_active_character(character_id: str) -> None:
    """Mark one character active. Exclusivity is per-game: other characters in
    the same game become dormant; characters in other games are untouched.

    This lets you main a PoE 2 character while keeping a PoE 1 character active
    in parallel.
    """
    target_path = EXILE_DIR / f"CHARACTER_{character_id}.md"
    if not target_path.exists():
        raise FileNotFoundError(target_path)
    target_fm, _ = read_file(target_path)
    target_game = target_fm.get("game")

    for cid in list_characters():
        path = EXILE_DIR / f"CHARACTER_{cid}.md"
        fm, body = read_file(path)
        if cid == character_id:
            fm["status"] = "active"
        elif fm.get("game") == target_game:
            fm["status"] = "dormant"
        # else: different game — don't touch its status
        write_file(path, fm, body)


def active_character(game: Optional[str] = None) -> Optional[str]:
    """Return the active character id, optionally scoped to a game."""
    for cid in list_characters(game=game):
        fm, _ = read_file(EXILE_DIR / f"CHARACTER_{cid}.md")
        if fm.get("status") == "active":
            return cid
    return None


def active_characters() -> dict[str, str]:
    """{game: character_id} for each game with an active character."""
    out: dict[str, str] = {}
    for cid in list_characters():
        fm, _ = read_file(EXILE_DIR / f"CHARACTER_{cid}.md")
        if fm.get("status") == "active":
            game = fm.get("game") or "unknown"
            out[game] = cid
    return out


# ----- league management -----

LEAGUE_FILENAME_RE = re.compile(r"^LEAGUE_([A-Za-z0-9_.-]+)\.md$")


def list_leagues() -> list[str]:
    if not EXILE_DIR.exists():
        return []
    return sorted(
        m.group(1)
        for p in EXILE_DIR.iterdir()
        if (m := LEAGUE_FILENAME_RE.match(p.name))
    )


def create_league(league_id: str, game: str = "poe2") -> Path:
    EXILE_DIR.mkdir(exist_ok=True)
    path = EXILE_DIR / f"LEAGUE_{league_id}.md"
    if path.exists():
        return path
    path.write_text(league_template(league_id, game), encoding="utf-8")
    return path


# ----- EXILE.xml composer -----

def compose_exile_xml() -> str:
    """Build the EXILE.xml from the current state of EXILE/.

    Tags are extracted from each file's frontmatter — sections we know about
    (knows, unknown, prefers, archetype_tags, defense_tags, offense_tags,
    goal_tags) become <tag> elements with confidence attributes when applicable.
    """
    parts: list[str] = ['<?xml version="1.0" encoding="utf-8"?>']
    parts.append("<exile>")
    parts.append(f'  <skill_root>{xml_escape(str(SKILL_ROOT))}</skill_root>')
    parts.append(f'  <onboarded>{str(is_onboarded()).lower()}</onboarded>')

    player_path = EXILE_DIR / "PLAYER.md"
    if player_path.exists():
        fm, _ = read_file(player_path)
        parts.append(f'  <player src="{xml_escape(str(player_path))}">')
        parts.extend(_render_tag_dict("knows", fm.get("knows") or {}, indent=4))
        parts.extend(_render_tag_dict("prefers", fm.get("prefers") or {}, indent=4))
        parts.extend(_render_tag_dict("unknown", fm.get("unknown") or {}, indent=4))
        for key in ("mode", "trade", "time_budget", "grind_capacity",
                    "crafting_engagement", "peak_wealth_tier", "systems_knowledge"):
            v = fm.get(key)
            if v is not None:
                parts.append(f'    <attr name="{key}" value="{xml_escape(str(v))}"/>')
        for tool in (fm.get("tools_installed") or []):
            parts.append(f'    <tool name="{xml_escape(str(tool))}"/>')
        parts.append("  </player>")

    for league_id in list_leagues():
        lpath = EXILE_DIR / f"LEAGUE_{league_id}.md"
        fm, _ = read_file(lpath)
        parts.append(
            f'  <league id="{xml_escape(league_id)}" game="{xml_escape(str(fm.get("game", "")))}" '
            f'src="{xml_escape(str(lpath))}">'
        )
        if fm.get("goal"):
            parts.append(f'    <goal>{xml_escape(str(fm["goal"]))}</goal>')
        parts.extend(_render_tag_list("goal_tags", fm.get("goal_tags") or [], indent=4))
        parts.extend(_render_tag_list("active_mechanics", fm.get("active_mechanics") or [], indent=4))
        parts.append("  </league>")

    for cid in list_characters():
        cpath = EXILE_DIR / f"CHARACTER_{cid}.md"
        fm, _ = read_file(cpath)
        status = fm.get("status", "dormant")
        game = fm.get("game", "")
        parts.append(
            f'  <character id="{xml_escape(cid)}" game="{xml_escape(str(game))}" '
            f'status="{xml_escape(status)}" src="{xml_escape(str(cpath))}">'
        )
        for key in ("class", "ascendancy", "current_level", "league", "build_url"):
            v = fm.get(key)
            if v is not None:
                parts.append(f'    <attr name="{key}" value="{xml_escape(str(v))}"/>')
        parts.extend(_render_tag_list("archetype_tags", fm.get("archetype_tags") or [], indent=4))
        parts.extend(_render_tag_list("defense_tags", fm.get("defense_tags") or [], indent=4))
        parts.extend(_render_tag_list("offense_tags", fm.get("offense_tags") or [], indent=4))
        parts.append("  </character>")

    parts.append("</exile>\n")
    return "\n".join(parts)


def _render_tag_dict(section: str, d: dict, indent: int) -> list[str]:
    """Render a section's tags. Supports two shapes:

      flat:    {tag: confidence}            → <tag section name confidence/>
      nested:  {game: {tag: confidence}}    → <tag section game name confidence/>

    Mixed is fine (some keys at top, some game-scoped sub-dicts).
    """
    pad = " " * indent
    out: list[str] = []
    for key, value in (d or {}).items():
        if isinstance(value, dict):
            # game-scoped sub-dict
            for tag, conf in value.items():
                if not isinstance(conf, (int, float)):
                    continue
                out.append(
                    f'{pad}<tag section="{xml_escape(section)}" game="{xml_escape(str(key))}" '
                    f'name="{xml_escape(str(tag))}" confidence="{float(conf):.3f}"/>'
                )
        elif isinstance(value, (int, float)):
            out.append(
                f'{pad}<tag section="{xml_escape(section)}" name="{xml_escape(str(key))}" '
                f'confidence="{float(value):.3f}"/>'
            )
    return out


def _render_tag_list(section: str, lst: list, indent: int) -> list[str]:
    """Tag list (no confidences) → <tag section="X" name="Y"/>."""
    pad = " " * indent
    return [
        f'{pad}<tag section="{xml_escape(section)}" name="{xml_escape(str(t))}"/>'
        for t in (lst or [])
    ]


def write_exile_xml() -> Path:
    out = project_exile_xml_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(compose_exile_xml(), encoding="utf-8")
    return out
