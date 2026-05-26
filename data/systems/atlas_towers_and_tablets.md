---
schema_version: 1
topic: atlas_towers_and_tablets
game: poe2
last_verified: 2026-05-26
related_topics: [atlas, mapping, waystones, atlas_passive_tree, league_0_5_return_of_the_ancients]
prerequisites: [waystones]
mastery_levels:
  not_started: "Hasn't done a Precursor Tower map yet."
  learning: "Knows towers exist; doesn't know how to use tablets."
  competent: "Activates towers consistently; matches tablets to atlas-tree specialization."
  confident: "Layers tablets across multiple towers to engineer mechanic-dense maps; balances tablet currency cost against expected return."
attributed_to: [Steelmage, palsteron, Empyrian]
---

# Precursor Towers + Tablets (PoE 2)

The endgame layer that **decides which mechanics appear** in your maps and **how dense they are**. Critical for endgame strategy.

## Precursor Towers

A **Precursor Tower** is a special map node randomly placed across the atlas. The structure:

- **Tower map** — a normal map node, but with an interior tower structure.
- **Clear monsters + rare enemies** to unlock the **Precursor Altar** at the end.
- **At the altar**: you place **Precursor Tablets** that modify all maps within the tower's effective area.

**One tower map = one unlock cycle**. The altar effects persist across multiple subsequent maps in nearby atlas nodes until the tower's tablets are consumed.

## Precursor Tablets

Tablets are items placed at the Precursor Altar to modify content within the tower's reach. Each tablet:

- Specifies an **endgame encounter type** — Expedition, Delirium, Breach, Ritual, Abyssal, Wisps, etc.
- **Increases monster difficulty** and **reward density** within affected maps.
- Can be **crafted with currency** to add up to **two magic modifiers** for further customization (similar to waystone rolling).

## Tablet slot mechanics

The number of tablet slots available at a tower depends on the **waystone** used to enter the tower map:

- **Default**: 1 tablet slot.
- **Waystone with 3+ modifiers**: unlocks the **2nd slot**.
- **Waystone with 6 modifiers** (full rare): unlocks **all 3 slots**.

This couples waystone rolling and tower play: better rolls → more tablet slots → denser mechanic stacking.

## How to engineer a mechanic-dense map

The "tower stacking" play pattern:

1. **Identify your atlas-tree specialization** (Breach, Ritual, etc.).
2. **Roll waystones with 6 modifiers** for max tablet capacity.
3. **Run a tower map** that physically sits near maps you want to farm.
4. **Place tablets matching your atlas tree** (3 Breach tablets if you specialize in Breach).
5. **Run the affected nearby maps** — they now carry layered Breach content stacked with your atlas-tree amplification.

This is the difference between casual mapping (incidental mechanic encounters) and **engineered farming** (every map you run has your specialty mechanic at maximum density).

## The Fortress (0.5+)

In `league_0_5_return_of_the_ancients`, **completing your first Precursor Tower map** unlocks **The Fortress** — the new endgame hub.

Pre-0.5: towers were standalone strategic surfaces.
0.5+: towers are the **gateway to all endgame progression**. The Fortress hub funnels every endgame mechanic, pinnacle access, and crafting surface through it.

## Common mistakes

- **Placing tablets without matching atlas tree** — tablets compound with atlas-tree specialization; mismatched tablets are wasted currency.
- **Running tower maps without rolling the waystone** — entering a 1-mod waystone tower forfeits 2/3 of the tablet slots before you even get to the altar.
- **Skipping tablet rolling** — vanilla tablets give the mechanic but at base density. Magic-rolled tablets significantly amplify the reward.
- **Tower placement neglect** — towers affect nearby maps spatially. If your tower is isolated from your specialized atlas region, the effect doesn't propagate.

## See also

- `waystones` — the map-currency layer that gates tablet capacity
- `atlas_passive_tree` — the layer that *amplifies* what tablets deliver
- `league_0_5_return_of_the_ancients` — Fortress hub mechanics
- `crafting_currency_overview` — currencies used to roll tablets
