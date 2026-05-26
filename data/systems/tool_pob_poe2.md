---
schema_version: 1
topic: tool_pob_poe2
game: poe2
last_verified: 2026-05-26
related_topics: [tool_overview, tool_pob_poe1, skill_gems, weapon_sets]
prerequisites: []
mastery_levels:
  not_started: "Hasn't installed PoB-PoE2; uses only the in-game BuildPlanner."
  learning: "Installed PoB-PoE2 but unsure how to read its outputs or import builds."
  competent: "Imports guide-author builds via pobb.in URLs; reads PoB's calculated DPS and EHP; can edit trees and see the impact."
  confident: "Plans builds in PoB-PoE2 before committing currency; uses the configuration panel (boss preset, conditional buffs) to stress-test builds; engages the dual-spec / weapon-set features."
attributed_to: []
---

# Path of Building Community — PoE 2 (tool guide)

The community-maintained build planner for Path of Exile 2. Forked from the original PoB (PoE 1 mainstay since 2016), adapted to PoE 2's systems. **MIT licensed.**

Official: [PathOfBuildingCommunity/PathOfBuilding-PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2)
Our fork: [GepetoinTraining/PathOfBuilding-PoE2](https://github.com/GepetoinTraining/PathOfBuilding-PoE2), bundled at `tools/pob-poe2/` as a git submodule. Patches in flight: headless JSON-RPC snapshot exporter.

## What it does

PoB-PoE2 lets you **construct a build outside the game and see calculated outputs**:

- **Passive tree allocation** with click-to-allocate UI, including weapon-set dual-specialization
- **Calculated DPS** per skill, per support combination, per gear configuration
- **Effective HP (eHP)** broken down by phys / fire / cold / lightning / chaos hits
- **Defense breakdown**: armour mitigation, evasion chance, block %, recovery rate, max-hit estimates
- **Item slot editor** with paste-from-game (Ctrl+C on an in-game item → paste in PoB → it parses)
- **Skill gem + support gem** configuration with reservation costs
- **Configuration panel**: enemy resistances, buff/debuff toggles, charge stacks, boss preset
- **Import/export** via [pobb.in](https://pobb.in) sharing service

## Why a new player would install it

| Scenario | PoB-PoE2 unlocks |
|---|---|
| Following a guide that publishes a PoB code | Import the guide-author's exact build, read the reasoning |
| Considering a costly upgrade | See "if I buy this item, my DPS goes from X to Y" before spending |
| Theorycrafting your own build | Click a node, see the impact; iterate without spending currency in-game |
| Comparing two builds | Side-by-side eDPS / eHP comparison |
| Verifying viability before campaign-end ascension | "Can this build actually kill the pinnacle bosses?" |

## When a new player can skip it

| Scenario | Why skip |
|---|---|
| Acts 1–3 of the campaign | The campaign teaches the build to you; PoB is over-engineering at this stage |
| First time on a new class | Learn the class's identity in-game first, optimize later |
| In-game BuildPlanner is sufficient | If you're not yet hitting friction with PoE 2's built-in planner, you don't need PoB yet |
| Following advice directly from this skill | If we're conversing build choices, you can plan via chat without the GUI |

## Install steps (Windows)

1. Download the **PoB Community PoE 2** installer from [the releases page](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases).
2. Run the installer. Default install location is fine — typically `Documents/Path of Building Community (PoE2)/`.
3. First launch may take a minute to fetch its data files.
4. **Optional**: install [PoBB.in browser integration](https://pobb.in) for the share-link import flow.

## How to use it with poe2-graph

### Today (manual flow)
- You find or build a PoB code → paste it in chat
- I parse the XML, extract the passive tree allocation + gem choices + items
- I emit a `.build` file that PoE 2's BuildPlanner reads inline
- Trade-off: I can read what PoB *configures*, but not what PoB *calculates*. DPS / eHP numbers don't survive the conversion via XML alone.

### Coming (`pob_snapshot.py`)
- PoB-PoE2 exports a JSON snapshot of its calculated stats (eDPS, eHP, defense breakdown, etc.)
- poe2-graph reads the snapshot → attaches to your CHARACTER profile
- Subsequent planning sessions know your build's calculated numbers without re-parsing PoB
- Status: pending upstream PoB-PoE2 headless mode + our snapshot reader

## Common pitfalls (new player)

- **PoB-PoE2 calc engine is younger than PoB-PoE1's**. Some PoE 2 mechanics aren't fully modeled. Don't treat eDPS as a guarantee — treat it as a directional estimate.
- **Config panel matters a lot**. PoB defaults assume nothing — no auras, no flasks, no power charges. If you don't toggle "all your buffs are up" the DPS reads scarily low. Set the boss preset to a realistic encounter (T16 boss / Pinnacle / Trialmaster) before reading the number.
- **Items must include sockets + runes / soul cores** for accurate calc. Paste the full Ctrl+C output, not a summary.
- **Weapon set allocation**. PoB-PoE2 supports the dual-spec system but you must toggle which set is active when reading DPS for that set.
- **Following someone else's PoB doesn't mean you'll play it well**. PoB optimizes raw output; gameplay optimization (positioning, defenses against specific bosses) is separate.

## Cross-reference

- [tool_pob_poe1](tool_pob_poe1.md) — the PoE 1 sibling
- [tool_overview](tool_overview.md) — the umbrella
- [skill_gems](skill_gems.md) — gem mechanics PoB models
- [weapon_sets](weapon_sets.md) — dual-specialization PoB supports
- `pob_snapshot.py` (pending) — the reader that consumes PoB's JSON output

## License & credit

PoB-PoE2 is **MIT-licensed**. Original PoB by Openarl (2016); PoE 2 fork by PathOfBuildingCommunity. We surface its source via our `tools/pob-poe2/` submodule with the upstream LICENSE preserved. We do not redistribute the PoB application binaries — players install via the official release page; our fork is for source-level access we need to patch.
