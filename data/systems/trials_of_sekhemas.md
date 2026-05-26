---
schema_version: 1
topic: trials_of_sekhemas
game: poe2
last_verified: 2026-05-26
related_topics: [ascension, ascendancy, trials_of_chaos, honour, sanctum]
prerequisites: []
mastery_levels:
  not_started: "Doesn't know how to ascend."
  learning: "Knows Sekhemas exists; doesn't understand Honour or how to manage it."
  competent: "Can complete difficulty 1-2 reliably; understands artifacts + boons + shrines as the Honour-recovery surface."
  confident: "Routes through Sekhemas optimally per build; selects boons that compound with armour/evasion; can clear difficulty 4 for high-tier ascendancy unlocks."
attributed_to: []
---

# Trial of the Sekhemas (PoE 2)

One of two **Ascension Trials** in PoE 2 (the other is `trials_of_chaos`). Sanctum-derived roguelike. Completing earns Ascendancy Skill Points.

## Honour — the load-bearing mechanic

The Trial introduces a **new health bar called Honour**:

- Honour pool = combined total Life + Energy Shield, **as a separate bar**.
- Whenever you take damage to Life or ES, you **also lose Honour**.
- If you lose **all** Honour, the Trial fails. Permanently. Restart the difficulty.
- **Honour cannot be recovered through normal means** — no life flask, no regen, no leech. Only via specific **artifacts**, **boons**, or **room reward shrines**.

This is the *strategic point* of Sekhemas: you can't tank through it. Avoiding damage is the game.

## Damage mitigation against Honour

- **Armour** reduces the **amount of Honour lost from hits** (same way it reduces physical damage).
- **Evasion** gives you a **chance to lose zero Honour** on a hit.
- **Honour Resistance** scales like other resistances, **capping at 75%** by default. At cap, a 100-damage hit takes only 25 from Honour.

Builds that already stack armour + evasion + cap-flat-resists translate well into Sekhemas. Pure ES builds without evasion struggle.

## Roguelike structure

- Series of **rooms**. Each cleared room offers a reward choice.
- **Boons** = run-only passive buffs you select at room transitions.
- **Afflictions** = run-only debuffs sometimes accepted in trade for higher reward.
- Boss encounters punctuate the run.

Monsters in Sekhemas are designed for the Honour mechanic: **slower, well-signaled attacks** and **traps** that can be avoided by careful play. The trial rewards positioning + pattern reading over twitch reflex.

## Ascension points earned

- **4 difficulty levels** of the Sekhemas Trial exist.
- Each cleared difficulty grants **2 Ascendancy Points**.
- Combined with Trial of Chaos: up to **8 total ascendancy points** earnable across both Trials.

The standard early-character pattern:
- Difficulty 1 of either Trial → 2 points (first ascendancy choice)
- Difficulty 1 of the *other* Trial → 2 more points
- Difficulty 3 of either → ascendancy points 5-6
- Difficulty 4 of either → ascendancy points 7-8

## Common mistakes

- **Tanking the trial like a regular map** — Honour ignores life-pool size. Pure ES / pure life builds without evasion get punished.
- **Skipping boon selection** — boons are run-mandatory, not optional. Compounding boons across the run is the difference between completion and failure at difficulty 3+.
- **Picking afflictions on a fragile build** — afflictions look like minor debuffs but compound dangerously with the Honour mechanic. Read carefully before accepting.

## See also

- `trials_of_chaos` — the other ascension path
- `ascendancies` — how ascendancy points are spent
- `league_0_1_early_access` — Sekhemas shipped at 0.1 and is structurally unchanged
