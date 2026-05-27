"""Goals — two-sided system.

CHARACTER GOALS (`Goal`, lives in CHARACTER_*.md frontmatter):
  Per-character progression objectives. "Reach Ancestral Bond." "Hit level 90."
  "Obtain Headhunter." Measurable against build state.

LEAGUE LEARNING GOALS (`LearningGoal`, lives in LEAGUE_*.md frontmatter):
  Player development objectives at the league level. "Learn how to craft high
  tier rares." "Learn how to boss." "Become a competent hideout warrior."
  Measured against a mastery scale (not_started / learning / competent /
  confident), not against the build.

The two are intentionally distinct shapes because they have different progress
semantics: a character goal completes ("done"); a learning goal advances
through mastery levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import networkx as nx

from graph.allocation import Allocation
from graph.resolvers import Tree
import exile


# ----- types -----

# Allowed goal kinds. Each has a different `target` shape.
GOAL_KINDS = (
    "reach_keystone",      # target = keystone node id (string) or skill hash (int)
    "reach_notable",       # target = notable node id or skill hash
    "level_milestone",     # target = int level (e.g. 60, 90)
    "stat_threshold",      # target = {stat_template: str, value: float}
    "obtain_item",         # target = item name or Metadata path
    "freeform",            # target = None; description is the source of truth
)


@dataclass
class Goal:
    id: str                                # short stable slug, e.g. "ancestral_bond"
    kind: str                              # one of GOAL_KINDS
    description: str                       # natural-language statement
    target: Any = None                     # depends on kind; see above
    status: str = "planned"                # planned | in_progress | done | abandoned
    created: Optional[str] = None
    achieved_at: Optional[str] = None
    notes: Optional[str] = None
    progress: Optional[float] = None       # 0..1 if measurable

    def __post_init__(self) -> None:
        if self.kind not in GOAL_KINDS:
            raise ValueError(f"unknown goal kind: {self.kind!r}; expected one of {GOAL_KINDS}")
        if self.created is None:
            self.created = datetime.now(timezone.utc).date().isoformat()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Goal":
        return cls(
            id=d["id"],
            kind=d["kind"],
            description=d["description"],
            target=d.get("target"),
            status=d.get("status", "planned"),
            created=d.get("created"),
            achieved_at=d.get("achieved_at"),
            notes=d.get("notes"),
            progress=d.get("progress"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "description": self.description,
            "status": self.status,
            "created": self.created,
        }
        if self.target is not None:
            d["target"] = self.target
        if self.achieved_at is not None:
            d["achieved_at"] = self.achieved_at
        if self.notes is not None:
            d["notes"] = self.notes
        if self.progress is not None:
            d["progress"] = self.progress
        return d


# ----- CHARACTER_*.md frontmatter IO -----

def _character_path(character_id: str) -> Path:
    return exile.EXILE_DIR / f"CHARACTER_{character_id}.md"


def list_goals(character_id: str) -> list[Goal]:
    fm, _ = exile.read_file(_character_path(character_id))
    raw_goals = fm.get("goals_for_character") or []
    return [Goal.from_dict(g) for g in raw_goals if isinstance(g, dict)]


def save_goals(character_id: str, goals: list[Goal]) -> None:
    path = _character_path(character_id)
    fm, body = exile.read_file(path)
    fm["goals_for_character"] = [g.to_dict() for g in goals]
    exile.write_file(path, fm, body)


def add_goal(character_id: str, goal: Goal) -> None:
    goals = list_goals(character_id)
    if any(g.id == goal.id for g in goals):
        raise ValueError(f"goal id {goal.id!r} already exists on character {character_id!r}")
    goals.append(goal)
    save_goals(character_id, goals)


def update_goal(character_id: str, goal_id: str, **changes: Any) -> Goal:
    goals = list_goals(character_id)
    for g in goals:
        if g.id == goal_id:
            for key, value in changes.items():
                setattr(g, key, value)
            save_goals(character_id, goals)
            return g
    raise KeyError(f"no goal {goal_id!r} on character {character_id!r}")


def mark_done(character_id: str, goal_id: str) -> Goal:
    return update_goal(
        character_id, goal_id,
        status="done",
        achieved_at=datetime.now(timezone.utc).date().isoformat(),
        progress=1.0,
    )


def active_goals(character_id: str) -> list[Goal]:
    return [g for g in list_goals(character_id) if g.status in ("planned", "in_progress")]


# ----- progress / actionability -----

def goal_progress(goal: Goal, alloc: Allocation) -> float:
    """Return progress fraction in [0, 1] for goals that can be measured.

    Unmeasurable goals (freeform, obtain_item) return the stored value or 0.0.
    """
    if goal.status == "done":
        return 1.0

    if goal.kind in ("reach_keystone", "reach_notable"):
        target_hash = _resolve_node_target(goal.target, alloc.tree)
        if target_hash is None:
            return 0.0
        if target_hash in alloc.records:
            return 1.0
        # measure as 1 - (cost_to_target / initial_cost) — but initial_cost is unknown
        # so just report 0 until allocated. A finer measure could be added later.
        return 0.0

    if goal.kind == "level_milestone":
        # level info isn't carried in Allocation; the character's current_level lives in
        # CHARACTER_*.md and is the source. Return stored progress if present.
        return float(goal.progress or 0.0)

    if goal.kind in ("stat_threshold", "obtain_item", "freeform"):
        return float(goal.progress or 0.0)

    return 0.0


def next_actionable(
    character_id: str,
    alloc: Allocation,
) -> Optional[tuple[Goal, list[int]]]:
    """Return the (goal, path) for the cheapest next allocation step toward any
    active node-based goal. Returns None if no node-based goal is reachable.
    """
    candidates: list[tuple[int, Goal, list[int]]] = []
    for goal in active_goals(character_id):
        if goal.kind not in ("reach_keystone", "reach_notable"):
            continue
        target_hash = _resolve_node_target(goal.target, alloc.tree)
        if target_hash is None or target_hash in alloc.records:
            continue
        try:
            path = alloc.shortest_path_to(target_hash)
        except nx.NetworkXNoPath:
            continue
        # Cost = path length minus what's already allocated/implicit
        seed = alloc._connected_seed()
        cost = sum(1 for h in path if h not in seed)
        candidates.append((cost, goal, path))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, goal, path = candidates[0]
    return (goal, path)


def _resolve_node_target(target: Union[str, int, None], tree: Tree) -> Optional[int]:
    """Accept a string node id or a skill-hash int; return the skill hash."""
    if target is None:
        return None
    if isinstance(target, int):
        return target if tree.node_by_hash(target) else None
    # string id
    node = tree.node_by_id(str(target))
    return node.get("skill") if node else None


# ===== LEAGUE LEARNING GOALS =====

# Mastery scale — distinct from character-goal status (planned/in_progress/done)
MASTERY_LEVELS = ("not_started", "learning", "competent", "confident")


@dataclass
class LearningGoal:
    """A learning objective at the league level, measured against mastery levels.

    `topic` should align with a `data/systems/<topic>.md` entry when one exists,
    so the mastery_levels vocabulary is shared between the goal and the
    teaching artifact.
    """
    id: str                                  # short stable slug, e.g. "essence_crafting"
    description: str                         # natural-language statement
    topic: Optional[str] = None              # link to systems/<topic>.md
    mastery: str = "not_started"             # one of MASTERY_LEVELS
    related_creators: list[str] = field(default_factory=list)  # creators.json names
    progress_notes: list[str] = field(default_factory=list)    # session-by-session
    created: Optional[str] = None
    last_advanced: Optional[str] = None      # date of last mastery bump

    def __post_init__(self) -> None:
        if self.mastery not in MASTERY_LEVELS:
            raise ValueError(f"unknown mastery {self.mastery!r}; expected one of {MASTERY_LEVELS}")
        if self.created is None:
            self.created = datetime.now(timezone.utc).date().isoformat()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LearningGoal":
        return cls(
            id=d["id"],
            description=d["description"],
            topic=d.get("topic"),
            mastery=d.get("mastery", "not_started"),
            related_creators=list(d.get("related_creators") or []),
            progress_notes=list(d.get("progress_notes") or []),
            created=d.get("created"),
            last_advanced=d.get("last_advanced"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "mastery": self.mastery,
            "created": self.created,
        }
        if self.topic:
            d["topic"] = self.topic
        if self.related_creators:
            d["related_creators"] = self.related_creators
        if self.progress_notes:
            d["progress_notes"] = self.progress_notes
        if self.last_advanced:
            d["last_advanced"] = self.last_advanced
        return d


def _league_path(league_id: str) -> Path:
    return exile.EXILE_DIR / f"LEAGUE_{league_id}.md"


def list_learning_goals(league_id: str) -> list[LearningGoal]:
    fm, _ = exile.read_file(_league_path(league_id))
    raw = fm.get("learning_goals") or []
    return [LearningGoal.from_dict(g) for g in raw if isinstance(g, dict)]


def save_learning_goals(league_id: str, goals: list[LearningGoal]) -> None:
    path = _league_path(league_id)
    fm, body = exile.read_file(path)
    fm["learning_goals"] = [g.to_dict() for g in goals]
    exile.write_file(path, fm, body)


def add_learning_goal(league_id: str, goal: LearningGoal) -> None:
    existing = list_learning_goals(league_id)
    if any(g.id == goal.id for g in existing):
        raise ValueError(f"learning goal {goal.id!r} already exists on league {league_id!r}")
    existing.append(goal)
    save_learning_goals(league_id, existing)


def advance_mastery(league_id: str, goal_id: str) -> LearningGoal:
    """Bump a learning goal one step up the mastery scale, or stay at confident."""
    goals_ = list_learning_goals(league_id)
    for g in goals_:
        if g.id == goal_id:
            idx = MASTERY_LEVELS.index(g.mastery)
            new_idx = min(idx + 1, len(MASTERY_LEVELS) - 1)
            g.mastery = MASTERY_LEVELS[new_idx]
            g.last_advanced = datetime.now(timezone.utc).date().isoformat()
            save_learning_goals(league_id, goals_)
            try:
                import history
                history.append_learning_progress(
                    learning_goal_id=g.id, league_id=league_id, mastery=g.mastery,
                )
            except Exception:
                pass
            return g
    raise KeyError(f"no learning goal {goal_id!r} on league {league_id!r}")


def set_mastery(league_id: str, goal_id: str, mastery: str) -> LearningGoal:
    if mastery not in MASTERY_LEVELS:
        raise ValueError(f"unknown mastery {mastery!r}")
    return _update_learning_goal(league_id, goal_id, mastery=mastery,
                                  last_advanced=datetime.now(timezone.utc).date().isoformat())


def add_progress_note(league_id: str, goal_id: str, note: str) -> LearningGoal:
    goals_ = list_learning_goals(league_id)
    for g in goals_:
        if g.id == goal_id:
            g.progress_notes.append(f"{datetime.now(timezone.utc).date().isoformat()}: {note}")
            save_learning_goals(league_id, goals_)
            return g
    raise KeyError(f"no learning goal {goal_id!r} on league {league_id!r}")


def _update_learning_goal(league_id: str, goal_id: str, **changes: Any) -> LearningGoal:
    goals_ = list_learning_goals(league_id)
    for g in goals_:
        if g.id == goal_id:
            for k, v in changes.items():
                setattr(g, k, v)
            save_learning_goals(league_id, goals_)
            return g
    raise KeyError(f"no learning goal {goal_id!r} on league {league_id!r}")


# ===== PLAYER GOALS (cross-league, durable identity) =====

GOAL_TYPES = ("economic", "mechanical", "knowledge", "identity")
GOAL_HORIZONS = ("leagues", "months", "years")
PLAYER_GOAL_STATUS = ("active", "dormant", "completed", "abandoned")

# Sub-goal kinds. The first set is measurable / quantifiable. The "WoW-tracker"
# kinds (acquire/travel/kill/interact) are concrete-action verbs the player
# can tick off without measurement.
SUB_GOAL_KINDS = (
    "stat_threshold",     # target: {stat: name, value: number}
    "composite",          # target: depends on shape; usually unifies sub-objectives
    "atlas_progression",  # target: {nodes_allocated: int, gateway: optional}
    "economic",           # target: {resource: name, count: int}  or {currency_div: int}
    "knowledge",          # target: {learning_goal_id} — cross-ref to LearningGoal
    "milestone",          # target: null; status flips on event
    "acquire",            # target: {item: name, count: int}        — WoW "collect"
    "travel",             # target: {place_or_unlock: str}           — WoW "go to"
    "kill",               # target: {enemy: name, count: int}        — WoW "kill N"
    "interact",           # target: {object_or_system: str}          — WoW "talk to / use"
    "freeform",           # target: null; narrative-only
)

SUB_GOAL_STATUS = ("open", "in_progress", "done", "blocked")


@dataclass
class SubGoal:
    """A WoW-tracker-style sub-goal: concrete, scoped, sometimes measurable,
    with a dependency on prior sub-goals via `depends_on`.

    A sub-goal is "available" when all its `depends_on` are `done`. The
    `next_actionable_subgoal()` traversal finds the leaf-most available
    sub-goals and ranks them by closeness-to-completion + edge-alignment +
    cost-fit.
    """
    id: str
    statement: str
    kind: str
    target: Optional[dict[str, Any]] = None
    depends_on: list[str] = field(default_factory=list)
    progress: float = 0.0                                # 0..1
    status: str = "open"                                 # open | in_progress | done | blocked
    related_edges: list[str] = field(default_factory=list)
    learning_goal_id: Optional[str] = None               # link to LearningGoal
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in SUB_GOAL_KINDS:
            raise ValueError(f"unknown sub-goal kind {self.kind!r}; expected {SUB_GOAL_KINDS}")
        if self.status not in SUB_GOAL_STATUS:
            raise ValueError(f"unknown sub-goal status {self.status!r}; expected {SUB_GOAL_STATUS}")
        if not (0.0 <= self.progress <= 1.0):
            raise ValueError(f"progress out of [0,1]: {self.progress}")

    @classmethod
    def from_dict(cls, d: dict) -> "SubGoal":
        return cls(
            id=d["id"],
            statement=d["statement"],
            kind=d["kind"],
            target=d.get("target"),
            depends_on=list(d.get("depends_on") or []),
            progress=float(d.get("progress", 0.0)),
            status=d.get("status", "open"),
            related_edges=list(d.get("related_edges") or []),
            learning_goal_id=d.get("learning_goal_id"),
            notes=d.get("notes"),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "statement": self.statement,
            "kind": self.kind,
            "status": self.status,
            "progress": round(self.progress, 4),
        }
        if self.target is not None:
            d["target"] = self.target
        if self.depends_on:
            d["depends_on"] = self.depends_on
        if self.related_edges:
            d["related_edges"] = self.related_edges
        if self.learning_goal_id:
            d["learning_goal_id"] = self.learning_goal_id
        if self.notes:
            d["notes"] = self.notes
        return d


@dataclass
class PlayerGoal:
    """A cross-league durable goal in PLAYER.md.

    Hard rule: at most ONE PlayerGoal is `status="active"` at any time. The
    rest are `dormant`, `completed`, or `abandoned`. The single-active rule
    forces the player to commit, which forces decomposition into `sub_goals`
    because the only way past a hard sub-goal is through it, not around it
    by switching majors.
    """
    id: str                              # short stable slug
    statement: str                       # one-sentence statement of intent
    type: str                            # economic | mechanical | knowledge | identity
    horizon: str = "leagues"             # leagues | months | years
    measurable: bool = False
    measure: Optional[str] = None
    related_edges: list[str] = field(default_factory=list)
    progress: float = 0.0                # aggregated from sub_goals if present, else manual
    status: str = "dormant"              # active | dormant | completed | abandoned
    sub_goals: list[SubGoal] = field(default_factory=list)
    created: Optional[str] = None
    activated_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.type not in GOAL_TYPES:
            raise ValueError(f"unknown player goal type {self.type!r}; expected {GOAL_TYPES}")
        if self.horizon not in GOAL_HORIZONS:
            raise ValueError(f"unknown horizon {self.horizon!r}; expected {GOAL_HORIZONS}")
        if self.status not in PLAYER_GOAL_STATUS:
            raise ValueError(f"unknown status {self.status!r}; expected {PLAYER_GOAL_STATUS}")
        if not (0.0 <= self.progress <= 1.0):
            raise ValueError(f"progress out of [0,1]: {self.progress}")
        if self.created is None:
            self.created = datetime.now(timezone.utc).date().isoformat()

    @classmethod
    def from_dict(cls, d: dict) -> "PlayerGoal":
        return cls(
            id=d["id"],
            statement=d["statement"],
            type=d["type"],
            horizon=d.get("horizon", "leagues"),
            measurable=bool(d.get("measurable", False)),
            measure=d.get("measure"),
            related_edges=list(d.get("related_edges") or []),
            progress=float(d.get("progress", 0.0)),
            status=d.get("status", "dormant"),
            sub_goals=[SubGoal.from_dict(s) for s in d.get("sub_goals") or [] if isinstance(s, dict)],
            created=d.get("created"),
            activated_at=d.get("activated_at"),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "statement": self.statement,
            "type": self.type,
            "horizon": self.horizon,
            "measurable": self.measurable,
            "measure": self.measure,
            "related_edges": self.related_edges,
            "progress": round(self.progress, 4),
            "status": self.status,
            "created": self.created,
        }
        if self.activated_at:
            d["activated_at"] = self.activated_at
        if self.sub_goals:
            d["sub_goals"] = [sg.to_dict() for sg in self.sub_goals]
        return d

    def next_actionable(self) -> Optional[SubGoal]:
        """The leaf-most sub-goal that's `open` with all `depends_on` done.

        Ranks candidates by progress (closer to completion first), then by
        whether they have measurable progress (preferring concrete over
        abstract). Returns None if no candidate is available.
        """
        done_ids = {sg.id for sg in self.sub_goals if sg.status == "done"}
        candidates: list[SubGoal] = [
            sg for sg in self.sub_goals
            if sg.status in ("open", "in_progress")
            and all(dep in done_ids for dep in sg.depends_on)
        ]
        if not candidates:
            return None
        # Prefer higher progress; break ties by preferring measurable kinds
        measurable_kinds = {"stat_threshold", "economic", "atlas_progression", "acquire", "kill"}
        candidates.sort(
            key=lambda sg: (-sg.progress, 0 if sg.kind in measurable_kinds else 1)
        )
        return candidates[0]

    def open_subgoals(self) -> list[SubGoal]:
        return [sg for sg in self.sub_goals if sg.status in ("open", "in_progress")]


def list_player_goals() -> list[PlayerGoal]:
    fm, _ = exile.read_file(exile.EXILE_DIR / "PLAYER.md")
    raw = fm.get("player_goals") or []
    return [PlayerGoal.from_dict(g) for g in raw if isinstance(g, dict)]


def save_player_goals(goals_: list[PlayerGoal]) -> None:
    path = exile.EXILE_DIR / "PLAYER.md"
    fm, body = exile.read_file(path)
    fm["player_goals"] = [g.to_dict() for g in goals_]
    exile.write_file(path, fm, body)


def add_player_goal(goal: PlayerGoal) -> None:
    existing = list_player_goals()
    if any(g.id == goal.id for g in existing):
        raise ValueError(f"player goal {goal.id!r} already exists")
    existing.append(goal)
    save_player_goals(existing)


def update_player_progress(goal_id: str, delta: float) -> PlayerGoal:
    """Asymptotically bump player-goal progress toward 1.0 (never reaches it)."""
    goals_ = list_player_goals()
    for g in goals_:
        if g.id == goal_id:
            g.progress = exile.bump_confidence(g.progress, delta)
            save_player_goals(goals_)
            return g
    raise KeyError(f"no player goal {goal_id!r}")


# ----- single-active player goal enforcement -----

def set_active_player_goal(goal_id: str) -> PlayerGoal:
    """Mark exactly one PlayerGoal `active`. Any previously-active goal
    becomes `dormant`. Single-active rule per league.
    """
    goals_ = list_player_goals()
    found = None
    for g in goals_:
        if g.id == goal_id:
            g.status = "active"
            g.activated_at = datetime.now(timezone.utc).date().isoformat()
            found = g
        elif g.status == "active":
            g.status = "dormant"
    if not found:
        raise KeyError(f"no player goal {goal_id!r}")
    save_player_goals(goals_)
    return found


def active_player_goal() -> Optional[PlayerGoal]:
    for g in list_player_goals():
        if g.status == "active":
            return g
    return None


def complete_player_goal(goal_id: str) -> PlayerGoal:
    goals_ = list_player_goals()
    for g in goals_:
        if g.id == goal_id:
            g.status = "completed"
            g.progress = 1.0
            save_player_goals(goals_)
            # Append to the long-horizon journal. Best-effort — never block goal
            # completion if history I/O fails.
            try:
                import history
                done_subs = sum(1 for sg in g.sub_goals if sg.status == "done")
                history.append_goal_completed(
                    goal_id=g.id,
                    activated_at=g.activated_at or g.created or "",
                    sub_goals_completed=done_subs,
                )
            except Exception:
                pass
            return g
    raise KeyError(f"no player goal {goal_id!r}")


def abandon_player_goal(goal_id: str) -> PlayerGoal:
    goals_ = list_player_goals()
    for g in goals_:
        if g.id == goal_id:
            g.status = "abandoned"
            save_player_goals(goals_)
            return g
    raise KeyError(f"no player goal {goal_id!r}")


# ----- sub-goal lifecycle -----

def mark_subgoal_done(goal_id: str, sub_id: str) -> SubGoal:
    goals_ = list_player_goals()
    for g in goals_:
        if g.id == goal_id:
            for sg in g.sub_goals:
                if sg.id == sub_id:
                    sg.status = "done"
                    sg.progress = 1.0
                    _recompute_player_progress(g)
                    save_player_goals(goals_)
                    return sg
            raise KeyError(f"no sub-goal {sub_id!r} in player goal {goal_id!r}")
    raise KeyError(f"no player goal {goal_id!r}")


def update_subgoal_progress(goal_id: str, sub_id: str, progress: float) -> SubGoal:
    if not (0.0 <= progress <= 1.0):
        raise ValueError(f"progress out of [0,1]: {progress}")
    goals_ = list_player_goals()
    for g in goals_:
        if g.id == goal_id:
            for sg in g.sub_goals:
                if sg.id == sub_id:
                    sg.progress = progress
                    if progress >= 1.0:
                        sg.status = "done"
                    elif progress > 0:
                        sg.status = "in_progress"
                    _recompute_player_progress(g)
                    save_player_goals(goals_)
                    return sg
            raise KeyError(f"no sub-goal {sub_id!r}")
    raise KeyError(f"no player goal {goal_id!r}")


def _recompute_player_progress(goal: PlayerGoal) -> None:
    """If a goal has sub_goals, the player progress is the mean of sub-progress."""
    if not goal.sub_goals:
        return
    goal.progress = round(
        sum(sg.progress for sg in goal.sub_goals) / len(goal.sub_goals), 4
    )


# ----- the switch intervention -----

@dataclass
class GoalSwitchIntervention:
    """Surfaced when the player tries to switch their active major goal while
    the current major has open sub-goals. Claude uses the `prompt` to engage
    the player on smaller goals first instead of silently accepting the switch.
    """
    current_goal: PlayerGoal
    proposed_goal_id: str
    current_actionable: Optional[SubGoal]
    open_subgoals: list[SubGoal]
    prompt: str

    def explanation(self) -> str:
        """Render the intervention as a player-facing message."""
        lines = [self.prompt, ""]
        lines.append(f"Currently active: {self.current_goal.statement!r}")
        lines.append(f"  Progress: {self.current_goal.progress:.0%}")
        lines.append(f"  Open sub-goals: {len(self.open_subgoals)}")
        if self.current_actionable:
            lines.append(f"  Next actionable: {self.current_actionable.statement}")
            if self.current_actionable.progress > 0:
                lines.append(f"    (currently at {self.current_actionable.progress:.0%})")
        return "\n".join(lines)


def propose_goal_switch(new_goal_id: str) -> Optional[GoalSwitchIntervention]:
    """Surface an intervention if the player tries to activate a new major
    while the current major still has open sub-goals.

    Returns None (no intervention needed) when:
      - there's no active goal currently
      - the proposed goal is already active
      - the current goal has zero open sub-goals (completion / abandonment OK)

    Returns a GoalSwitchIntervention otherwise. Caller (Claude in
    conversation) decides whether to engage the player on the current
    sub-goal first, or proceed with the switch anyway.
    """
    active = active_player_goal()
    if active is None:
        return None
    if active.id == new_goal_id:
        return None
    open_subs = active.open_subgoals()
    if not open_subs:
        return None  # current goal is effectively finished; switch is clean

    actionable = active.next_actionable()
    prompt = (
        f"You're proposing to switch from {active.statement!r} to a new "
        f"major goal. Before we make that switch, let's name what's "
        f"actually stuck on the current goal — a major-goal switch often "
        f"means a sub-goal feels invisible. Walk me through where you are."
    )
    return GoalSwitchIntervention(
        current_goal=active,
        proposed_goal_id=new_goal_id,
        current_actionable=actionable,
        open_subgoals=open_subs,
        prompt=prompt,
    )


# ----- WoW-tracker rendering -----

def render_goal_tracker(goal: PlayerGoal) -> str:
    """Format a PlayerGoal as a WoW-quest-tracker-style block for the player.

    [ACTIVE GOAL] <statement>
      ◯ <open sub-goal> — at 4M/10M (40%)
      ● <done sub-goal>
      ◯ <blocked sub-goal>  [blocked]

    [NEXT ACTION] <statement of next_actionable>
    """
    lines = [f"[ACTIVE GOAL] {goal.statement}"]
    if goal.measure:
        lines.append(f"  ({goal.measure})")
    lines.append("")

    if not goal.sub_goals:
        lines.append("  (no sub-goals yet — decompose this goal before activating)")
        return "\n".join(lines)

    done_ids = {sg.id for sg in goal.sub_goals if sg.status == "done"}
    for sg in goal.sub_goals:
        if sg.status == "done":
            marker = "●"
        elif any(dep not in done_ids for dep in sg.depends_on):
            marker = "◌"  # blocked
        else:
            marker = "◯"  # open / available

        progress_str = ""
        if sg.kind == "stat_threshold" and sg.target:
            stat = sg.target.get("stat", "")
            value = sg.target.get("value", 0)
            cur = sg.progress * value if value else 0
            progress_str = f"  — at {_human(cur)}/{_human(value)} ({sg.progress:.0%})"
        elif sg.kind in ("economic", "acquire", "kill") and sg.target:
            count = sg.target.get("count", 0)
            cur = sg.progress * count if count else 0
            unit = sg.target.get("resource") or sg.target.get("item") or sg.target.get("enemy") or ""
            progress_str = f"  — {int(cur)}/{int(count)} {unit} ({sg.progress:.0%})"
        elif sg.progress > 0 and sg.status != "done":
            progress_str = f"  — {sg.progress:.0%}"

        suffix = ""
        if marker == "◌":
            suffix = "  [blocked]"
        lines.append(f"  {marker} {sg.statement}{progress_str}{suffix}")

    actionable = goal.next_actionable()
    if actionable:
        lines.append("")
        lines.append(f"[NEXT ACTION] {actionable.statement}")
        if actionable.notes:
            lines.append(f"  {actionable.notes}")

    return "\n".join(lines)


def _human(n: float) -> str:
    """Compact number formatting for the tracker."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


# ===== LEAGUE GOALS (in-league tactical) =====

@dataclass
class LeagueGoal:
    """In-league tactical objective in LEAGUE_*.md."""
    id: str
    statement: str
    type: str                              # economic | mechanical | knowledge | identity
    measurable: bool = False
    measure: Optional[str] = None
    deadline: Optional[str] = None         # "league_week_3" | iso-date | null
    related_edges: list[str] = field(default_factory=list)
    progress: float = 0.0
    created: Optional[str] = None

    def __post_init__(self) -> None:
        if self.type not in GOAL_TYPES:
            raise ValueError(f"unknown league goal type {self.type!r}")
        if not (0.0 <= self.progress <= 1.0):
            raise ValueError(f"progress out of [0,1]: {self.progress}")
        if self.created is None:
            self.created = datetime.now(timezone.utc).date().isoformat()

    @classmethod
    def from_dict(cls, d: dict) -> "LeagueGoal":
        return cls(
            id=d["id"],
            statement=d["statement"],
            type=d["type"],
            measurable=bool(d.get("measurable", False)),
            measure=d.get("measure"),
            deadline=d.get("deadline"),
            related_edges=list(d.get("related_edges") or []),
            progress=float(d.get("progress", 0.0)),
            created=d.get("created"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "type": self.type,
            "measurable": self.measurable,
            "measure": self.measure,
            "deadline": self.deadline,
            "related_edges": self.related_edges,
            "progress": round(self.progress, 4),
            "created": self.created,
        }


def list_league_goals(league_id: str) -> list[LeagueGoal]:
    fm, _ = exile.read_file(_league_path(league_id))
    raw = fm.get("league_goals") or []
    return [LeagueGoal.from_dict(g) for g in raw if isinstance(g, dict)]


def save_league_goals(league_id: str, goals_: list[LeagueGoal]) -> None:
    path = _league_path(league_id)
    fm, body = exile.read_file(path)
    fm["league_goals"] = [g.to_dict() for g in goals_]
    exile.write_file(path, fm, body)


def add_league_goal(league_id: str, goal: LeagueGoal) -> None:
    existing = list_league_goals(league_id)
    if any(g.id == goal.id for g in existing):
        raise ValueError(f"league goal {goal.id!r} already exists on league {league_id!r}")
    existing.append(goal)
    save_league_goals(league_id, existing)


def update_league_progress(league_id: str, goal_id: str, delta: float) -> LeagueGoal:
    goals_ = list_league_goals(league_id)
    for g in goals_:
        if g.id == goal_id:
            g.progress = exile.bump_confidence(g.progress, delta)
            save_league_goals(league_id, goals_)
            return g
    raise KeyError(f"no league goal {goal_id!r} on league {league_id!r}")


# ===== goal-goal composition =====

@dataclass
class Friction:
    """A tension between a player goal and a league goal."""
    player_goal_id: str
    league_goal_id: str
    reason: str


def goal_friction(player_goals: list[PlayerGoal], league_goals: list[LeagueGoal]) -> list[Friction]:
    """Detect tensions between identity-level and tactical goals.

    A simple heuristic: an `identity` player goal (e.g. "main HC for three
    leagues") clashes with high-risk league goals. This v1 hand-wires a couple
    of patterns; richer detection is later work.
    """
    out: list[Friction] = []
    hc_identity = [
        pg for pg in player_goals
        if pg.type == "identity"
        and ("hardcore" in pg.statement.lower() or " hc " in f" {pg.statement.lower()} ")
    ]
    if hc_identity:
        risky_keywords = ["deepest", "sanctum", "all-in", "speedrun", "race"]
        for pg in hc_identity:
            for lg in league_goals:
                if any(k in lg.statement.lower() for k in risky_keywords):
                    out.append(Friction(
                        player_goal_id=pg.id,
                        league_goal_id=lg.id,
                        reason=(
                            f"{pg.statement!r} is an HC identity goal; "
                            f"{lg.statement!r} reads as high-risk and clashes with HC discipline."
                        ),
                    ))
    return out


def related_edges_for_goal(goal: Union[PlayerGoal, LeagueGoal, "Goal", "LearningGoal"]) -> list[str]:
    """Return the edge names this goal pulls in."""
    edges = getattr(goal, "related_edges", None)
    if edges:
        return list(edges)
    return []
