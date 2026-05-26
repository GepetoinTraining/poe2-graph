---
id: goals
file: DOCS/goals.md
topic: Five goal types + decomposition DAG + single-active rule + switch intervention + WoW tracker
priority: action
modules: [goals, exile]
tags: [goals, decomposition, sub_goals, switch_intervention, wow_tracker, single_active]
when_to_read: |
  User mentions a goal (theirs or anyone's), asks what to do tonight, asks to
  break down a big goal into sub-goals, tries to switch their active major
  goal, wants to track progress, or asks for the "what's next" recommendation.
  Also when Claude needs to surface goal state at session start as a
  WoW-tracker-style block.
---

# Goals — five types + decomposition + switch discipline

## The five goal types

| Type | Lives in | Scope | Progress shape |
|---|---|---|---|
| `PlayerGoal` | `PLAYER.md` `player_goals:` | Cross-league, identity / durable | Aggregated from sub_goals, or asymptotic float |
| `LeagueGoal` | `LEAGUE_<id>.md` `league_goals:` | In-league, tactical | Asymptotic float with optional `deadline` |
| `SubGoal` | Nested under `PlayerGoal.sub_goals` | Tactical decomposition of a PlayerGoal | DAG via `depends_on`, status open/in_progress/done/blocked |
| `Goal` (character) | `CHARACTER_<slug>.md` `goals_for_character:` | Per-playthrough milestones | kind = reach_keystone / level_milestone / etc. |
| `LearningGoal` | `LEAGUE_<id>.md` `learning_goals:` | Mastery of a mechanic | Mastery scale: not_started → learning → competent → confident |

PlayerGoal + SubGoal is the load-bearing pair for the "what should I do tonight" loop. The others are supplementary.

## Decomposition — the WoW-quest-tracker model

A PlayerGoal carries a list of `SubGoal`s with `depends_on` edges. The result is a DAG. SubGoal kinds:

- `stat_threshold` — target: `{stat: name, value: number}` (e.g. 10M DPS)
- `composite` — depends_on others; rolls up when prerequisites done
- `atlas_progression` — atlas-tree advancement
- `economic` — target: `{resource: name, count: int}` or currency
- `knowledge` — links to a `LearningGoal` via `learning_goal_id`
- `milestone` — boolean status, no target
- `acquire` — WoW "collect N of X" — target: `{item, count}`
- `travel` — WoW "go to / unlock" — target: `{place_or_unlock}`
- `kill` — WoW "kill N" — target: `{enemy, count}`
- `interact` — WoW "talk to / use" — target: `{object_or_system}`
- `freeform` — narrative-only

`PlayerGoal.next_actionable()` walks the DAG, finds the leaf-most available (no unmet deps) sub-goal, ranks by progress descending + preference for measurable kinds. Returns the one Claude should surface as tonight's concrete next step.

## Single-active major rule

Hard rule: at most ONE `PlayerGoal` is `status="active"` per league. The rest are `dormant`, `completed`, or `abandoned`. The single-active rule forces the player to commit, which forces decomposition — the only way past a hard sub-goal is through it.

```python
goals.set_active_player_goal("beat_ubers")    # exclusive — others demoted to dormant
goals.active_player_goal()                     # → PlayerGoal | None
goals.complete_player_goal("beat_ubers")
goals.abandon_player_goal("beat_ubers")
```

## The switch intervention

When the player tries to switch their active major goal while the current one still has open sub-goals, Claude surfaces an intervention instead of silently swapping:

```python
intervention = goals.propose_goal_switch("new_goal")
if intervention:
    # Don't switch yet. Engage the player on the current sub-goal first.
    print(intervention.explanation())
    # → "You're proposing to switch from 'Beat ubers'. Before we make that
    #    switch, let's name what's actually stuck on the current goal — a
    #    major-goal switch often means a sub-goal feels invisible..."
```

Claude can still proceed with the switch after the conversation, but the discipline is to surface the sub-goal state first. Often the player isn't stuck on the major; they're stuck on a sub-goal that feels invisible.

## WoW-tracker rendering

`goals.render_goal_tracker(player_goal)` produces:

```
[ACTIVE GOAL] Beat all PoE 2 pinnacle bosses this league
  (All pinnacle bosses defeated on the active character)

  ◯ 10M+ effective DPS against pinnacle archetype  — at 4.0M/10.0M (40%)
  ● 8000+ effective health pool  — at 8.0K/8.0K (100%)
  ◌ Build composite — stats cleared, ascendancy allocated  [blocked]
  ◯ Atlas tree allocated for pinnacle access  — 47%
  ◯ Stockpile 3 sets of pinnacle fragments  — 0/3 fragments (0%)

[NEXT ACTION] Atlas tree allocated for pinnacle access
  12 points from gateway node; 3 are on your existing map-tier branch
```

Markers: `●` done, `◯` open/available, `◌` blocked (deps unmet).

## Sub-goal lifecycle

```python
goals.mark_subgoal_done("beat_ubers", "ehp_threshold")           # status=done, progress=1.0
goals.update_subgoal_progress("beat_ubers", "dps_threshold", 0.6) # auto-flips to in_progress
# Parent PlayerGoal.progress auto-recomputes as mean of sub-progresses
```

## Goal-friction detection

`goals.goal_friction(player_goals, league_goals)` detects laddering vs conflict:

- "Main HC for three leagues" (identity) + "Push deepest Sanctum delve" (mechanical) → flagged friction
- "Hit Mirror tier" (economic) + "Speedfarm T15s by week 2" (economic) → ladders cleanly

Heuristic-driven for v1; the signal is "Claude raises the tension, player decides."

## Cross-references

- `DOCS/guides.md` — `related_edges` on goals cross-reference edges in the taxonomy
- `DOCS/exile.md` — confidence math (`exile.bump_confidence`) is what powers progress
- `DOCS/build-construction.md` — sub-goals of `stat_threshold` kind drive Allocation extension
