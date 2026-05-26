---
id: guides
file: DOCS/guides.md
topic: System guides + case studies + edge taxonomy + creator catalog + dual-purpose framing
priority: action
modules: [guides, systems, creators]
tags: [guides, case_studies, edges, taxonomy, creators, transmissible_knowledge]
when_to_read: |
  User asks about a game mechanic that needs teaching (essence crafting, atlas
  routing, mirror handling, market timing, playstyle calibration), references
  a content creator and wants Claude's read, expresses an attitude that maps
  to an edge (efficiency-vs-fun, optimize-the-fun-out, post-drop fire-sale
  instinct), or hits a moment where a case-study-shaped lesson would land.
  Also when Claude needs to apply tag bumps after a teaching exchange.
---

# Guides — the transmissible meta-game layer

## Two surfaces

`guides.py` covers two surfaces the v0.3 spec collapsed but the goals+guides subspec separates:

- **Build/character guide intent** — `GuideIntent` + `intent_to_allocation`. Per-character. Used when constructing a build from a guide description.
- **System guides + case studies** — cross-league teaching artifacts that transmit *edges* (postures, patterns, timing). The transmissible meta-game.

This doc covers the second surface. For build intent, see `DOCS/build-construction.md`.

## The four-cell composition (from the subspec)

| | Cross-league (durable) | In-league (situational) |
|---|---|---|
| **GOALS** | `PlayerGoal` in PLAYER.md | `LeagueGoal` in LEAGUE_*.md |
| **GUIDES** | System guides in `data/guides/system/` | Character guides in CHARACTER_*.md |

## Edge taxonomy

`data/guides/edge_taxonomy.yaml` is the curated list of meta-knowledge tags the skill teaches. **Edges are distinct from mechanic tags.** Mechanic tags describe knowledge of game systems; edges describe postures, patterns, and timing knowledge that separate skilled from beginner play.

Currently 18 edges across 5 categories:

- **economic** (7): market_timing, volume_reading, league_phase_awareness, currency_velocity, option_value_vs_face_value, patient_pricing, flow_anticipation
- **crafting** (3): downside_discipline, miss_economy, investing_vs_gambling
- **discipline** (2): posture_under_drop, marginal_capability_thinking (the 80/100 rule)
- **trade** (1): negotiation_posture
- **psychological** (3): time_budget_calibration, aspirational_calibration, playstyle_authenticity

Each edge becomes a key in `knows.poe2.<edge_name>` in PLAYER.md, with confidence in `[0, 1)` per the asymptotic bump rule.

```python
guides.load_edge_taxonomy()    # → [Edge] from yaml
guides.edge_names()             # → set[str]
```

The taxonomy grows. When the skill recognises an edge during play that isn't in the list, it proposes adding it via review.

## System guides

A system guide is metadata + a reference to one or more case studies that exercise the edges it transmits.

```python
sg = guides.load_system_guide("mirror_handling_v1")
sg.topic, sg.summary, sg.game, sg.difficulty
sg.transmits      # ["posture_under_drop", "option_value_vs_face_value", ...]
sg.case_studies   # ["mirror_drop_day_1", ...]
sg.creators       # [{handle, role, note}, ...]
sg.prerequisites  # [{edge, min_confidence}, ...]

guides.list_system_guides()
guides.system_guides_for_edge("posture_under_drop")
```

Seed corpus shipped (each with one fully-authored case study, ~3 TODO slots):

- `mirror_handling_v1` (advanced, economic) — posture_under_drop + market_timing
- `playstyle_calibration_v1` (foundational, psychological) — time_budget + aspirational + authenticity
- `upgrade_pacing_v1` (intermediate, discipline) — marginal_capability_thinking + downside_discipline

## Case studies — dual-purpose primitive

**The frame:** case studies are dual-purpose. The seed corpus teaches Claude the shape; once internalised, Claude improvises case-study-flavoured moments from real player situations using the same schema. Authored cases are exemplars; improvised cases handle the long tail; high-value improvisations curate back into the catalog.

A case study is a scenario where the player makes a decision and Claude responds with multi-dimensional scoring + conservative tag bumps + follow-up scheduling.

```python
cs = guides.load_case_study("mirror_drop_day_1")
cs.setup.scenario           # the situation
cs.decision_point           # "What do you tell them?"
cs.scoring_dimensions       # 4-6 dimensions, each with an edge + check
cs.claude_response_template # the rubric for Claude's response
cs.tag_bumps_per_dimension_hit  # default 0.4
cs.follow_up                # {delay_hours, prompt, bumps_on_*}

text = guides.case_study_present(cs)         # render scenario for player
bumps = guides.case_study_apply_bumps(cs, scoring_dict, fm, game="poe2")
# scoring_dict: {dimension_name: bool_hit} — Claude scores via natural-language
# assessment of the player's response, not a quiz answer
```

### Follow-up cadences

Different edges resolve on different clocks:

- 24h (upgrade pacing) — concrete sustain check
- 72h (mirror handling) — economic discipline holds
- 504h / 3-week (playstyle calibration) — psychological calibration lands

The follow-up schema includes both `bumps_on_actual_<positive>` and `bumps_on_actual_<negative_but_self_aware>` — catching a burnout AND pivoting can be a larger bump than avoiding the trap altogether, because the player demonstrated meta-awareness.

## Creators catalog

Per-handle YAMLs in `data/guides/creators/<handle>.yaml`. Each carries channels, build hub, live status URL (so Claude can `WebFetch` to check live state), specialties, style tags, and `transmits` — edge-confidence pairs scored by how well they teach that edge.

```python
c = guides.load_creator("ghazzy")
c.display_name, c.channels, c.live_status_url, c.disposition
c.transmits   # [{edge, confidence, note}, ...]

guides.list_creators()                         # excludes opted_out
guides.creators_who_transmit("posture_under_drop", min_confidence=0.5)
```

`disposition: opted_out` removes a creator from the catalog without deleting the file (audit trail preserved).

## GUIDES.xml

`guides.compose_guides_xml()` / `write_guides_xml()` produce the composable index — same pattern as EXILE.xml and DOCS.xml. Loaded into Claude's context at session start.

## See also

- `DOCS/goals.md` — `related_edges` on goals link to taxonomy entries
- `DOCS/exile.md` — `knows.poe2.<edge>` tags + the asymptotic bump math
- `ATTRIBUTIONS.md` — creators referenced in the catalog
