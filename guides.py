"""Guides — system guides + case studies + character/build intent + GUIDES.xml.

This module covers two distinct surfaces that the original v0.3 spec
collapsed but the goals+guides subspec separates:

  - **Build/character guide intent**: `GuideIntent` + `intent_to_allocation`.
    Used when constructing a character's tree from a build description.
    Per-character, lives in `EXILE/CHARACTER_*.md` once instantiated.

  - **System guides + case studies**: cross-league teaching artifacts that
    transmit "edge" — postures, patterns, timing knowledge that separate
    skilled players from beginners. Per-mechanic / per-topic, lives in
    `data/guides/system/*.yaml` with case studies as siblings.

The two compose at session start via the GUIDES.xml index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape as xml_escape

import networkx as nx
import yaml

from catalog.gem import GemCatalog, load_catalog
from graph.allocation import Allocation
from graph.resolvers import Tree
import goals as goals_module


# ----- paths -----

DATA_GUIDES = Path(__file__).parent / "data" / "guides"
SYSTEM_GUIDES_DIR = DATA_GUIDES / "system"
CASE_STUDIES_DIR = SYSTEM_GUIDES_DIR / "case_studies"
CREATORS_DIR = DATA_GUIDES / "creators"
EDGE_TAXONOMY_PATH = DATA_GUIDES / "edge_taxonomy.yaml"


# ===== build/character guide intent =====

@dataclass
class GuideIntent:
    """Structured extract of a build guide's recommendations."""
    source: str
    character_class: str
    ascendancy: Optional[str] = None

    main_skill: Optional[str] = None
    support_gems: list[str] = field(default_factory=list)
    extra_skills: list[str] = field(default_factory=list)

    key_notables: list[str] = field(default_factory=list)
    key_keystones: list[str] = field(default_factory=list)
    avoid_nodes: list[str] = field(default_factory=list)

    damage_type: Optional[str] = None
    hit_or_dot: Optional[str] = None
    crit_or_not: Optional[str] = None
    defense_layer: list[str] = field(default_factory=list)

    required_uniques: list[str] = field(default_factory=list)
    recommended_uniques: list[str] = field(default_factory=list)

    progression_notes: Optional[str] = None
    author: Optional[str] = None
    license_notes: Optional[str] = None


class GuideValidationError(ValueError):
    pass


def validate_intent(
    intent: GuideIntent, tree: Tree, *, validate_gems: bool = True,
) -> list[str]:
    """Return validation warnings; empty means clean.

    `validate_gems=True` cross-checks main_skill / support_gems / extra_skills
    against the catalog/ gem index. If the catalog can't load (cold cache +
    no network), gem validation is silently skipped rather than producing
    false-positive "unknown gem" warnings for every name.
    """
    warnings: list[str] = []
    class_id = _resolve_class(intent.character_class, tree)
    if class_id is None:
        warnings.append(f"unknown class: {intent.character_class!r}")
        return warnings
    if intent.ascendancy:
        if _resolve_ascendancy(intent.ascendancy, class_id, tree) is None:
            warnings.append(
                f"ascendancy {intent.ascendancy!r} does not belong to class {intent.character_class!r}"
            )
    for name in intent.key_notables + intent.key_keystones:
        if _resolve_node_by_name_or_id(name, tree) is None:
            warnings.append(f"node not found in tree: {name!r}")
    if validate_gems:
        warnings.extend(_validate_intent_gems(intent))
    return warnings


# Back-compat alias for the older API name.
validate = validate_intent


def _try_load_gem_catalog(gem_class: str) -> Optional[GemCatalog]:
    """Best-effort load; returns None on network / parse failure."""
    try:
        return load_catalog(gem_class)
    except Exception:
        return None


def _validate_intent_gems(intent: GuideIntent) -> list[str]:
    """Check main_skill / support_gems / extra_skills against the gem catalogs.

    Active skills can resolve to either the skill catalog (most skills) or
    the spirit catalog (Heralds, Auras, Meta-gems). Supports must resolve
    against the support catalog specifically.

    Missing catalogs (cold cache + no network) cause the corresponding
    checks to be skipped without warning.
    """
    out: list[str] = []
    skill_cat = _try_load_gem_catalog("skill")
    spirit_cat = _try_load_gem_catalog("spirit")
    support_cat = _try_load_gem_catalog("support")

    active_names: Optional[set[str]] = None
    if skill_cat is not None and spirit_cat is not None:
        active_names = skill_cat.names() | spirit_cat.names()

    if active_names is not None:
        if intent.main_skill and intent.main_skill not in active_names:
            out.append(f"unknown main skill: {intent.main_skill!r}")
        for name in intent.extra_skills:
            if name not in active_names:
                out.append(f"unknown extra skill: {name!r}")

    if support_cat is not None:
        support_names = support_cat.names()
        for name in intent.support_gems:
            if name not in support_names:
                out.append(f"unknown support gem: {name!r}")

    return out


def intent_to_allocation(
    intent: GuideIntent,
    tree: Tree,
    g: nx.Graph,
    weapon_set: Optional[int] = None,
) -> Allocation:
    """Construct an Allocation that routes through every key notable/keystone."""
    class_id = _resolve_class(intent.character_class, tree)
    if class_id is None:
        raise GuideValidationError(f"unknown class: {intent.character_class!r}")
    ascendancy_id = 0
    if intent.ascendancy:
        ascendancy_id = _resolve_ascendancy(intent.ascendancy, class_id, tree) or 0
    alloc = Allocation.new(tree, g, character_class=class_id, ascendancy=ascendancy_id)
    targets: list[int] = []
    for name in intent.key_notables + intent.key_keystones:
        h = _resolve_node_by_name_or_id(name, tree)
        if h is not None:
            targets.append(h)
    if targets:
        alloc.route_through(*targets)
        if weapon_set is not None:
            for h in list(alloc.records.keys()):
                alloc.allocate(h, weapon_set=weapon_set)
    return alloc


# ===== edge taxonomy =====

@dataclass
class Edge:
    name: str
    summary: str
    check: str
    category: Optional[str] = None


def load_edge_taxonomy(path: Optional[Path] = None) -> list[Edge]:
    """Read `data/guides/edge_taxonomy.yaml` → list of Edge entries."""
    p = path or EDGE_TAXONOMY_PATH
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return [
        Edge(
            name=e["name"],
            summary=e["summary"],
            check=e["check"],
            category=e.get("category"),
        )
        for e in raw.get("edges", [])
    ]


def edge_names() -> set[str]:
    return {e.name for e in load_edge_taxonomy()}


# ===== system guides =====

@dataclass
class SystemGuide:
    id: str
    topic: str
    summary: str
    game: str                                  # poe1 | poe2 | both
    last_updated: Optional[str] = None
    version_minimum: Optional[str] = None
    difficulty: Optional[str] = None
    transmits: list[str] = field(default_factory=list)        # edge names
    case_studies: list[str] = field(default_factory=list)      # case study ids
    creators: list[dict[str, Any]] = field(default_factory=list)  # {handle, role, note}
    prerequisites: list[dict[str, Any]] = field(default_factory=list)
                                               # {edge, min_confidence}


def load_system_guide(guide_id: str, base_dir: Optional[Path] = None) -> Optional[SystemGuide]:
    base = base_dir or SYSTEM_GUIDES_DIR
    path = base / f"{guide_id}.yaml"
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SystemGuide(
        id=raw.get("id") or path.stem,
        topic=raw.get("topic", ""),
        summary=(raw.get("summary") or "").strip(),
        game=raw.get("game", "both"),
        last_updated=raw.get("last_updated"),
        version_minimum=raw.get("version_minimum"),
        difficulty=raw.get("difficulty"),
        transmits=list(raw.get("transmits") or []),
        case_studies=list(raw.get("case_studies") or []),
        creators=list(raw.get("creators") or []),
        prerequisites=list(raw.get("prerequisites") or []),
    )


def list_system_guides(base_dir: Optional[Path] = None) -> list[SystemGuide]:
    base = base_dir or SYSTEM_GUIDES_DIR
    if not base.exists():
        return []
    out: list[SystemGuide] = []
    for p in sorted(base.glob("*.yaml")):
        sg = load_system_guide(p.stem, base)
        if sg:
            out.append(sg)
    return out


def system_guides_for_edge(edge: str, base_dir: Optional[Path] = None) -> list[SystemGuide]:
    return [g for g in list_system_guides(base_dir) if edge in g.transmits]


# ===== case studies =====

@dataclass
class ScoringDimension:
    dimension: str
    edge: str
    check: str


@dataclass
class FollowUp:
    delay_hours: int
    prompt: str
    bumps_on_actual_wait: list[dict[str, Any]] = field(default_factory=list)
    bumps_on_actual_sale_at_floor: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CaseStudy:
    id: str
    guide: str
    edge_tags: list[str]
    prerequisites: list[Any]
    estimated_time: str
    setup: dict[str, Any]
    decision_point: str
    scoring_dimensions: list[ScoringDimension]
    claude_response_template: str
    tag_bumps_per_dimension_hit: float
    tag_bumps_per_dimension_miss: float
    follow_up: Optional[FollowUp] = None
    attribution: Optional[dict[str, Any]] = None


def load_case_study(case_id: str, base_dir: Optional[Path] = None) -> Optional[CaseStudy]:
    base = base_dir or CASE_STUDIES_DIR
    path = base / f"{case_id}.yaml"
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    dims = [
        ScoringDimension(
            dimension=d["dimension"], edge=d["edge"], check=d["check"],
        )
        for d in (raw.get("scoring_dimensions") or [])
    ]
    fu_raw = raw.get("follow_up")
    follow_up: Optional[FollowUp] = None
    if fu_raw:
        follow_up = FollowUp(
            delay_hours=int(fu_raw.get("delay_hours", 72)),
            prompt=fu_raw.get("prompt", ""),
            bumps_on_actual_wait=list(fu_raw.get("bumps_on_actual_wait") or []),
            bumps_on_actual_sale_at_floor=list(fu_raw.get("bumps_on_actual_sale_at_floor") or []),
        )
    return CaseStudy(
        id=raw.get("id") or path.stem,
        guide=raw.get("guide", ""),
        edge_tags=list(raw.get("edge_tags") or []),
        prerequisites=list(raw.get("prerequisites") or []),
        estimated_time=raw.get("estimated_time", ""),
        setup=dict(raw.get("setup") or {}),
        decision_point=raw.get("decision_point", "").strip(),
        scoring_dimensions=dims,
        claude_response_template=raw.get("claude_response_template", "").strip(),
        tag_bumps_per_dimension_hit=float(raw.get("tag_bumps_per_dimension_hit", 0.4)),
        tag_bumps_per_dimension_miss=float(raw.get("tag_bumps_per_dimension_miss", 0.0)),
        follow_up=follow_up,
        attribution=raw.get("attribution"),
    )


def list_case_studies(base_dir: Optional[Path] = None) -> list[CaseStudy]:
    base = base_dir or CASE_STUDIES_DIR
    if not base.exists():
        return []
    out: list[CaseStudy] = []
    for p in sorted(base.glob("*.yaml")):
        cs = load_case_study(p.stem, base)
        if cs:
            out.append(cs)
    return out


def case_study_present(cs: CaseStudy, live_data: Optional[dict[str, Any]] = None) -> str:
    """Render the scenario for a player. Live data may be substituted into the
    scenario text by the consumer; this returns the raw text + structure for
    Claude to compose with.
    """
    parts: list[str] = []
    if cs.setup.get("scenario"):
        parts.append(cs.setup["scenario"].strip())
    if live_data and cs.setup.get("live_data"):
        parts.append(f"\nLive data: {live_data}\n")
    parts.append(f"\n**Decision point:** {cs.decision_point}")
    return "\n".join(parts)


def case_study_apply_bumps(
    cs: CaseStudy,
    scoring: dict[str, bool],
    fm: dict[str, Any],
    game: str = "poe2",
) -> dict[str, float]:
    """Apply tag bumps for a scored case-study response.

    `scoring` is a dict {dimension_name: bool_hit}. Returns the new confidence
    per affected edge. Mutates `fm` in place (caller writes the file).

    Also appends the case-study completion to EXILE/HISTORY.md (best-effort —
    history I/O failures don't block the bump return).
    """
    import exile
    bumps: dict[str, float] = {}
    for dim in cs.scoring_dimensions:
        hit = scoring.get(dim.dimension, False)
        delta = cs.tag_bumps_per_dimension_hit if hit else cs.tag_bumps_per_dimension_miss
        if delta:
            new = exile.update_tag(fm, "knows", dim.edge, delta, game=game)
            bumps[dim.edge] = new
    try:
        import history
        history.append_case_study(case_id=cs.id, scoring=scoring, bumps=bumps)
    except Exception:
        pass
    return bumps


# ===== creators =====

@dataclass
class Creator:
    handle: str
    display_name: str
    channels: dict[str, str] = field(default_factory=dict)
    home_url: Optional[str] = None
    build_hub: Optional[str] = None
    live_status_url: Optional[str] = None
    disposition: str = "public"                # public | opted_out
    games: list[str] = field(default_factory=list)
    primary_language: Optional[str] = None
    specialties: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)
    style_notes: Optional[str] = None
    transmits: list[dict[str, Any]] = field(default_factory=list)
                                               # [{edge, confidence, note?}]


def load_creator(handle: str, base_dir: Optional[Path] = None) -> Optional[Creator]:
    base = base_dir or CREATORS_DIR
    path = base / f"{handle}.yaml"
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Creator(
        handle=raw.get("handle") or path.stem,
        display_name=raw.get("display_name", handle),
        channels=dict(raw.get("channels") or {}),
        home_url=raw.get("home_url"),
        build_hub=raw.get("build_hub"),
        live_status_url=raw.get("live_status_url"),
        disposition=raw.get("disposition", "public"),
        games=list(raw.get("games") or []),
        primary_language=raw.get("primary_language"),
        specialties=list(raw.get("specialties") or []),
        style_tags=list(raw.get("style_tags") or []),
        style_notes=(raw.get("style_notes") or "").strip() or None,
        transmits=list(raw.get("transmits") or []),
    )


def list_creators(base_dir: Optional[Path] = None) -> list[Creator]:
    base = base_dir or CREATORS_DIR
    if not base.exists():
        return []
    out: list[Creator] = []
    for p in sorted(base.glob("*.yaml")):
        c = load_creator(p.stem, base)
        if c and c.disposition != "opted_out":
            out.append(c)
    return out


def creators_who_transmit(edge: str, min_confidence: float = 0.5, base_dir: Optional[Path] = None) -> list[Creator]:
    out: list[Creator] = []
    for c in list_creators(base_dir):
        for t in c.transmits:
            if t.get("edge") == edge and float(t.get("confidence", 0)) >= min_confidence:
                out.append(c)
                break
    return out


# ===== keystone: recommend_next_action =====
#
# The composer that ties EXILE (player + league + character) into a single
# action surface for "what should I do tonight." Reads from frontmatter dicts
# (testable without disk); returns a structured `ActionRecommendation` that
# Claude composes into a conversational response.

@dataclass
class ActionRecommendation:
    """Composed recommendation surface returned by `recommend_next_action`.

    Carries the active major goal + next actionable sub-goal, the league
    learning focus, the cheapest character-goal step (if alloc supplied),
    and the system guides / creators / case studies whose edges intersect
    with the active sub-goal's `related_edges`. Confidence gaps name the
    edges the active goal pulls in that the player has < 0.5 confidence on.

    The `rationale` is a one-line summary suitable for surfacing directly;
    the structured fields let Claude compose a longer response.
    """
    active_player_goal: Optional[Any] = None        # goals.PlayerGoal | None
    next_subgoal: Optional[Any] = None              # goals.SubGoal | None
    next_learning_goal: Optional[Any] = None        # goals.LearningGoal | None
    next_character_target: Optional[Any] = None     # (goals.Goal, path:list[int]) | None
    relevant_system_guides: list[SystemGuide] = field(default_factory=list)
    relevant_creators: list[Creator] = field(default_factory=list)
    relevant_case_studies: list[CaseStudy] = field(default_factory=list)
    confidence_gaps: list[tuple[str, float]] = field(default_factory=list)
    edges_of_interest: list[str] = field(default_factory=list)
    rationale: str = ""


def recommend_next_action(
    player_fm: dict[str, Any],
    league_fm: Optional[dict[str, Any]] = None,
    character_fm: Optional[dict[str, Any]] = None,
    alloc: Optional[Allocation] = None,
    game: str = "poe2",
) -> ActionRecommendation:
    """The keystone composer. Inputs are frontmatter dicts; output is a
    structured action surface.

    Active player goal → next actionable sub-goal → edges of interest →
    matching system guides + creators + case studies. League learning goal
    contributes via topic → system-guide → transmits. Optional Allocation
    surfaces the cheapest character-goal node-step.
    """
    league_fm = league_fm or {}
    character_fm = character_fm or {}

    # 1. Active player goal + next actionable sub-goal
    active_pg = _active_player_goal_from_fm(player_fm)
    next_sub = active_pg.next_actionable() if active_pg else None

    # 2. Build edges of interest (sub-goal first, then PlayerGoal-wide)
    edges_of_interest: set[str] = set()
    if next_sub:
        edges_of_interest.update(next_sub.related_edges or [])
    if active_pg:
        edges_of_interest.update(active_pg.related_edges or [])

    # 3. Next learning goal — and its topic-linked system guide's transmits
    next_lg = _next_learning_goal_from_fm(league_fm)
    if next_lg and next_lg.topic:
        for sg in list_system_guides():
            if sg.id == next_lg.topic or sg.topic.lower() == next_lg.topic.lower():
                edges_of_interest.update(sg.transmits)

    # 4. Next character-goal target (only if alloc supplied)
    next_char_target = None
    if alloc is not None and character_fm.get("goals_for_character"):
        next_char_target = _next_actionable_char_from_fm(character_fm, alloc)

    # 5. System guides — score by edge overlap, prefer matching game
    guide_scores: list[tuple[int, SystemGuide]] = []
    for sg in list_system_guides():
        if sg.game not in (game, "both"):
            continue
        overlap = len(set(sg.transmits) & edges_of_interest)
        if overlap > 0:
            guide_scores.append((overlap, sg))
    guide_scores.sort(key=lambda x: (-x[0], x[1].id))
    relevant_guides = [g for _, g in guide_scores]

    # 6. Creators — score by edge overlap at min_confidence 0.5
    creator_scores: list[tuple[int, Creator]] = []
    for c in list_creators():
        if game not in c.games:
            continue
        overlap = sum(
            1 for t in c.transmits
            if t.get("edge") in edges_of_interest and float(t.get("confidence", 0) or 0) >= 0.5
        )
        if overlap > 0:
            creator_scores.append((overlap, c))
    creator_scores.sort(key=lambda x: (-x[0], x[1].handle))
    relevant_creators = [c for _, c in creator_scores][:5]

    # 7. Case studies — by edge_tags overlap
    case_scores: list[tuple[int, CaseStudy]] = []
    for cs in list_case_studies():
        overlap = len(set(cs.edge_tags) & edges_of_interest)
        if overlap > 0:
            case_scores.append((overlap, cs))
    case_scores.sort(key=lambda x: (-x[0], x[1].id))
    relevant_cases = [c for _, c in case_scores][:3]

    # 8. Confidence gaps in knows.<game>.<edge>
    knows_section = player_fm.get("knows") or {}
    if isinstance(knows_section, dict):
        knows = knows_section.get(game) or {}
        if not isinstance(knows, dict):
            knows = {}
    else:
        knows = {}
    gaps: list[tuple[str, float]] = []
    for edge in sorted(edges_of_interest):
        raw = knows.get(edge, 0.0)
        conf = float(raw) if isinstance(raw, (int, float)) else 0.0
        if conf < 0.5:
            gaps.append((edge, conf))
    gaps.sort(key=lambda x: x[1])

    # 9. Rationale string
    rationale = _compose_rationale(
        active_pg, next_sub, next_lg, next_char_target,
        relevant_guides, relevant_creators, relevant_cases, gaps,
    )

    return ActionRecommendation(
        active_player_goal=active_pg,
        next_subgoal=next_sub,
        next_learning_goal=next_lg,
        next_character_target=next_char_target,
        relevant_system_guides=relevant_guides,
        relevant_creators=relevant_creators,
        relevant_case_studies=relevant_cases,
        confidence_gaps=gaps,
        edges_of_interest=sorted(edges_of_interest),
        rationale=rationale,
    )


def _active_player_goal_from_fm(fm: dict[str, Any]):
    """Return the single active PlayerGoal in `fm['player_goals']`, or None.
    Malformed entries (missing required fields) are skipped silently.
    """
    for raw in (fm.get("player_goals") or []):
        if not isinstance(raw, dict) or raw.get("status") != "active":
            continue
        try:
            return goals_module.PlayerGoal.from_dict(raw)
        except (KeyError, ValueError):
            continue
    return None


def _next_learning_goal_from_fm(fm: dict[str, Any]):
    """Pick the lowest-mastery non-confident LearningGoal from `fm['learning_goals']`.
    Malformed entries are skipped silently.
    """
    items: list = []
    for g in (fm.get("learning_goals") or []):
        if not isinstance(g, dict):
            continue
        try:
            items.append(goals_module.LearningGoal.from_dict(g))
        except (KeyError, ValueError):
            continue
    items = [g for g in items if g.mastery != "confident"]
    if not items:
        return None
    order = {"learning": 0, "not_started": 1, "competent": 2}
    items.sort(key=lambda g: order.get(g.mastery, 99))
    return items[0]


def _next_actionable_char_from_fm(character_fm: dict[str, Any], alloc: Allocation):
    """FM-driven analog of `goals.next_actionable`: pick cheapest unallocated
    node-based character goal reachable from the current Allocation.

    Returns (goal, path) tuple or None. Goal is a `goals.Goal` instance.
    """
    candidates: list[tuple[int, Any, list[int]]] = []
    for raw in (character_fm.get("goals_for_character") or []):
        if not isinstance(raw, dict):
            continue
        try:
            g = goals_module.Goal.from_dict(raw)
        except (KeyError, ValueError):
            continue
        if g.status not in ("planned", "in_progress"):
            continue
        if g.kind not in ("reach_keystone", "reach_notable"):
            continue
        target = g.target
        if target is None:
            continue
        target_hash: Optional[int] = None
        if isinstance(target, int):
            if alloc.tree.node_by_hash(target):
                target_hash = target
        else:
            node = alloc.tree.node_by_id(str(target))
            target_hash = node.get("skill") if node else None
        if target_hash is None or target_hash in alloc.records:
            continue
        try:
            path = alloc.shortest_path_to(target_hash)
        except Exception:
            continue
        seed = alloc._connected_seed()
        cost = sum(1 for h in path if h not in seed)
        candidates.append((cost, g, path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, goal, path = candidates[0]
    return (goal, path)


def _compose_rationale(
    pg, sub, lg, char_target,
    guides: list[SystemGuide],
    creators: list[Creator],
    cases: list[CaseStudy],
    gaps: list[tuple[str, float]],
) -> str:
    """Single-line summary for direct surfacing. Structured fields carry depth."""
    parts: list[str] = []
    if pg:
        parts.append(f'Active major: "{pg.statement}"')
        if sub:
            parts.append(f"Next sub-goal: {sub.statement}")
        else:
            parts.append("(no actionable sub-goal — all blocked or done)")
    else:
        parts.append("No active major player goal — propose one or activate a dormant goal.")
    if lg:
        parts.append(f"League focus: \"{lg.description}\" ({lg.mastery})")
    if char_target:
        goal, path = char_target
        parts.append(f"Cheapest character next-step: {goal.description} (~{max(0, len(path) - 1)} hops)")
    if gaps:
        gap_str = ", ".join(f"{e}({c:.2f})" for e, c in gaps[:3])
        parts.append(f"Confidence gaps: {gap_str}")
    if guides:
        parts.append(f"Guides: {', '.join(g.id for g in guides[:3])}")
    if creators:
        parts.append(f"Creators: {', '.join(c.handle for c in creators[:3])}")
    if cases:
        parts.append(f"Case studies: {', '.join(cs.id for cs in cases[:2])}")
    return " · ".join(parts) if parts else "No actionable signal — onboarding may be incomplete."


# ===== GUIDES.xml composer =====

def compose_guides_xml() -> str:
    """Build the GUIDES.xml composing system guides + case studies + creators."""
    parts: list[str] = ['<?xml version="1.0" encoding="utf-8"?>', "<guides>"]
    parts.append(f'  <generated_at>{_now_iso()}</generated_at>')

    # Edges
    parts.append("  <edge_taxonomy>")
    for e in load_edge_taxonomy():
        cat = f' category="{xml_escape(e.category)}"' if e.category else ""
        parts.append(f'    <edge name="{xml_escape(e.name)}"{cat}/>')
    parts.append("  </edge_taxonomy>")

    # System guides
    for g in list_system_guides():
        parts.append(
            f'  <system_guide id="{xml_escape(g.id)}" game="{xml_escape(g.game)}"'
            f' difficulty="{xml_escape(g.difficulty or "")}">'
        )
        parts.append(f'    <topic>{xml_escape(g.topic)}</topic>')
        if g.summary:
            parts.append(f'    <summary>{xml_escape(g.summary)}</summary>')
        for edge in g.transmits:
            parts.append(f'    <transmits edge="{xml_escape(edge)}"/>')
        for cs_id in g.case_studies:
            parts.append(f'    <case_study id="{xml_escape(cs_id)}"/>')
        for c in g.creators:
            handle = c.get("handle", "")
            role = c.get("role", "")
            parts.append(f'    <creator handle="{xml_escape(handle)}" role="{xml_escape(role)}"/>')
        for p in g.prerequisites:
            edge = p.get("edge", "")
            mc = p.get("min_confidence", 0)
            parts.append(f'    <prerequisite edge="{xml_escape(edge)}" min_confidence="{float(mc):.2f}"/>')
        parts.append("  </system_guide>")

    # Creators
    for c in list_creators():
        parts.append(f'  <creator handle="{xml_escape(c.handle)}" disposition="{xml_escape(c.disposition)}">')
        parts.append(f'    <display_name>{xml_escape(c.display_name)}</display_name>')
        for kind, url in c.channels.items():
            parts.append(f'    <channel kind="{xml_escape(kind)}" url="{xml_escape(url)}"/>')
        if c.live_status_url:
            parts.append(f'    <live_status_url>{xml_escape(c.live_status_url)}</live_status_url>')
        for tag in c.style_tags:
            parts.append(f'    <style_tag name="{xml_escape(tag)}"/>')
        for t in c.transmits:
            edge = t.get("edge", "")
            conf = float(t.get("confidence", 0))
            parts.append(f'    <transmits edge="{xml_escape(edge)}" confidence="{conf:.2f}"/>')
        parts.append("  </creator>")

    parts.append("</guides>\n")
    return "\n".join(parts)


def write_guides_xml(out_path: Optional[Path] = None) -> Path:
    """Write GUIDES.xml. Defaults to the project-level claude path next to EXILE.xml."""
    import exile
    if out_path is None:
        out_path = exile.project_exile_xml_path().with_name("GUIDES.xml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(compose_guides_xml(), encoding="utf-8")
    return out_path


# ===== module-private helpers =====

def _resolve_class(name: str, tree: Tree) -> Optional[int]:
    for i, cls in enumerate(tree.classes):
        if cls.get("name", "").lower() == name.lower():
            return i
    return None


def _resolve_ascendancy(name: str, class_id: int, tree: Tree) -> Optional[int]:
    if not (0 <= class_id < len(tree.classes)):
        return None
    cls = tree.classes[class_id]
    for i, asc in enumerate(cls.get("ascendancies", []), start=1):
        if asc is None:
            continue
        asc_name = asc.get("name") if isinstance(asc, dict) else asc
        if asc_name and asc_name.lower() == name.lower():
            return i
    return None


def _resolve_node_by_name_or_id(token: str, tree: Tree) -> Optional[int]:
    node = tree.node_by_id(token)
    if node and "skill" in node:
        return node["skill"]
    low = token.lower()
    for n in tree.raw["nodes"].values():
        if (n.get("name") or "").lower() == low:
            return n.get("skill")
    return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
