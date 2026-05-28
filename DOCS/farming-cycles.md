---
id: farming-cycles
file: DOCS/farming-cycles.md
topic: Farming cycles — declare/open/execute/classify/reconcile/close lifecycle + .farm.graph publishing
priority: action
modules: [farm, store, integrations]
tags: [farming, cycles, roi, div_per_hour, mod_regex, classification, reconcile, farm_graph, exilence, clipboard]
when_to_read: |
  User asks about running a farming cycle, tracking inputs/outputs, publishing
  a 1000-map study, ROI per hour, mod-regex classification, or .farm.graph
  bundles. Also when they mention Exilence CE and want to know the
  differentiation. Also when a content creator (Empyrean, Slipperyjim, ZiggyD)
  asks how to structure a drop study for publication.
mastery_levels: [intermediate, advanced]
---

# Farming cycles

A farming cycle is a declared, bounded experiment: you commit to a set of inputs before you start, record outputs as they land, and close the cycle with a reconciled summary that produces a single comparable ROI number. The unit of analysis is the cycle, not the session and not the week. That distinction determines what you can and cannot conclude from the data, and it is why the farm package exists as a separate layer from your net-worth tracker.

## The cycle as a unit

### Six states

Every cycle moves through exactly these states in order:

```
DECLARE → OPEN → EXECUTE → CLASSIFY → RECONCILE → CLOSE
```

`DECLARE` is the commitment step: you name what you are farming, what inputs you are spending, and what lottery targets (if any) you are chasing. Nothing is time-sensitive here — a declared cycle is just a record with no timestamps yet.

`OPEN` takes a currency snapshot. From this point forward, the clock is running and the exchange rates are locked for this cycle's accounting. Open-time rates anchor the input-cost calculation; close-time rates anchor the output-value calculation. Using two separate snapshots — one at open, one at close — lets you detect rate drift across long cycles.

`EXECUTE` is play. Each item that lands goes into the output log via `record_output` or, more practically, via the clipboard listener running in the background. The cycle stays in EXECUTE until you decide it is done.

`CLASSIFY` is the mod-regex pass. The output log gets matched against patterns derived from the craft graph's `mod_market_value` edges. Each item lands in a bucket: `price_me` (needs a trade-API quote), `gold_pile` (vendor), or a custom bucket you define. Classification happens after the cycle closes, not in real time.

`RECONCILE` cross-checks the declared inputs against what the store can account for. If you declared 200 Chaos Orbs as inputs and the store can only account for 180 as spent, you get a reconcile gap. The gap is not automatically resolved — it is surfaced for your review.

`CLOSE` locks the cycle, runs the ROI summary, and makes the data available for bundle export.

### Why this differs from Exilence CE

Exilence CE tracks your net worth as a time series — every refresh tells you "you're up 1.2 div since last hour." That's useful for the question "am I getting richer?" but doesn't answer the question "was this Sekhemas farm worth running tonight?" The cycle is the unit of comparison: declared inputs, classified outputs, a reconciled close, a single ROI number you can stack against last week's same cycle and against the +flask-charges-mod price change on poe.ninja.

The two tools occupy different layers. Exilence tells you the slope of your wealth curve; a farming cycle tells you the yield of a specific strategy run under specific conditions. See [When to hand off to Exilence CE](#when-to-hand-off-to-exilence-ce) for the explicit boundary.

### Transactional integrity

Because DECLARE commits the inputs before you start and RECONCILE checks them after, the cycle has a simple integrity guarantee: either the numbers close, or you know by how much they don't. This is what makes cycles stackable. If you run 20 Sekhemas cycles and 3 of them have unresolved reconcile gaps, you know exactly which 17 to trust for the aggregate.

## Quick start: a 50-map Sekhemas cycle

This walks through a minimal but complete cycle. The 50-map scale gives you meaningful signal without demanding a multi-session commitment. Connection setup is assumed — see `DOCS/graph-queries.md` for `get_connection`.

```python
from store import get_connection
from farm import (
    declare_cycle,
    open_cycle,
    classify_outputs,
    reconcile_cycle,
    close_cycle,
    export_cycle_bundle,
)

conn = get_connection()
```

### Step 1: Declare

```python
cycle = declare_cycle(
    conn,
    farm_target='sekhemas_relics',
    lottery_targets=['mirror'],
    inputs=[{'item': 'orb_of_chaos', 'quantity': 200}],
    notes='50-map Sekhemas study, patch 0.2.0f, Stormweaver build',
)
cycle_id = cycle['id']
print(cycle_id)   # e.g. "cyc_20260527_001"
```

`farm_target` is a string identifier for what you are farming. `lottery_targets` are things you are hoping for but not counting on — they affect hit-rate stats at close but not the baseline ROI calculation. `inputs` is a list of `{item, quantity}` dicts. The currency values are priced at open-time rates, not here.

### Step 2: Open (take your pre-run currency snapshot)

```python
cycle = open_cycle(
    conn,
    cycle_id,
    currency_snapshot={
        'chaos':   1240,
        'divine':   18,
        'exalted': 4500,
    },
)
```

The snapshot values are your current stash counts in units of Chaos Orb equivalent. The actual exchange rates (chaos-to-divine, etc.) are fetched from poe.ninja at open time and stored in the cycle record. You do not need to do the conversion manually.

### Step 3: Run and record

Start the clipboard listener in a separate terminal before you go into the game:

```bash
python -m integrations.clipboard_listener
```

Every item you Ctrl+C in-game gets captured and queued. The listener calls `record_output` for you; you do not need to do it manually during play. If you prefer manual logging (for items you don't clipboard-copy), you can call it directly:

```python
from farm import record_output

record_output(conn, cycle_id, item_payload_xml, source='manual')
```

`item_payload_xml` is the raw item text in the game's XML format, the same payload the clipboard listener captures. See [Working with the clipboard listener](#working-with-the-clipboard-listener) for the queue directory and restart behavior.

### Step 4: Classify

After your last map, run the classify pass:

```python
result = classify_outputs(conn, cycle_id, valuable_mod_threshold=0.5)
print(result['price_me_count'])    # items that need a trade quote
print(result['gold_pile_count'])   # items going to vendor
```

`valuable_mod_threshold` is the minimum `mod_market_value` edge weight for a mod to count as valuable. The default of 0.5 is calibrated to exclude single-stat rares that technically have a value but are priced below the cost of listing. Adjust it up if you want a tighter `price_me` list or down if you want to catch more marginal items.

The mod-regex pass does not hit the Trade API. It matches against patterns already in the craft graph. The Trade API queries happen only on the `price_me` bucket, after you have reviewed the list.

### Step 5: Reconcile

```python
recon = reconcile_cycle(conn, cycle_id)
print(recon['gap'])           # 0 means clean; nonzero means investigate
print(recon['gap_items'])     # list of unaccounted items or currency
```

A gap of 0 means the declared inputs match the store's accounting exactly. Any nonzero gap is surfaced as a list so you can decide whether it is data entry error, missed clipboard capture, or a legitimate mystery.

### Step 6: Close

```python
summary = close_cycle(
    conn,
    cycle_id,
    end_currency_snapshot={
        'chaos':   1060,
        'divine':   19,
        'exalted': 4500,
    },
    time_invested_minutes=42.0,
)
print(summary['div_per_hour'])
print(summary['hit_rate'])          # lottery_targets / total_maps
print(summary['total_output_div'])
print(summary['total_input_div'])
print(summary['roi_ratio'])         # output / input, dimensionless
```

`time_invested_minutes` is real elapsed time, not map time. Include your between-map overhead — the number is only useful for div/hour comparison if it is consistent across cycles.

### Step 7: Export

```python
path = export_cycle_bundle(
    conn,
    cycle_id,
    out_path='exports/sekhemas_50map_20260527.farm.graph',
    build_snapshot_path='data/characters/stormweaver_0.2.0f.build',
    author='Empyrean',
    readme='50-map Sekhemas relic study, patch 0.2.0f. Stormweaver, 2.1M DPS, 4.8K EHP.',
)
print(path)   # confirmed write path
```

The bundle contains: the cycle record, all outputs with their classification, the reconcile audit, the close summary, the build snapshot (read-only copy), and the README string you provided. It does not contain your full stash or any data outside this cycle.

## Running a 1000-map study

The lifecycle is identical to the 50-map version. The practical differences are time budget, interruption handling, and what you monitor between sessions.

### Time budget

At roughly 3-4 minutes per Sekhemas map, 1000 maps is 50-65 hours of active play. Most studies of this size run across 3-4 weeks of a league. Plan accordingly — a 1000-map result published in week 8 catches a different economy than the same study published in week 2.

### Interrupting and resuming

A cycle in EXECUTE state can be interrupted freely. The clipboard listener persists its queue to disk; any items captured while the listener was running are preserved. When you resume:

1. Restart the clipboard listener — it will replay any items in the queue directory that haven't been committed yet.
2. Call `open_cycle` again if more than 24 hours have passed, to update the currency snapshot to current rates.

```python
# TODO once farm package finalizes: cycle snapshot refresh API
# For now, open a new sub-cycle or note the rate drift in the README.
```

### What to monitor between sessions

Check `reconcile_cycle` after each session, not only at the end of the study. A gap that appears after session 3 and grows through session 10 is almost always a process error (items not captured, a different character used, currency moved out of the tracked stash). Catching it early is much cheaper than untangling it at cycle 800.

You do not need to classify between sessions. Classification is a batch pass and runs efficiently on the full output set at the end.

### Staging intermediate results

If you want to publish interim results (e.g., "here is the 250-map midpoint"), export a bundle at that point with a note in the README. The cycle stays open; you export a snapshot, not a close. Use a distinct `out_path` so the interim bundle does not overwrite the final one.

```python
# Interim export — cycle remains in EXECUTE state
export_cycle_bundle(
    conn,
    cycle_id,
    out_path='exports/sekhemas_1000map_interim_250.farm.graph',
    author='Empyrean',
    readme='Interim at map 250. Cycle still open. Do not use for final ROI comparison.',
)
```

## Mod-regex classification

### Why classify before pricing

Pricing every drop through the Trade API would dwarf the actual time you spend mapping. The mod-regex pass runs after every cycle: each output's mod text gets matched against patterns from the craft graph's `mod_market_value` edges. Outputs that match valuable patterns become `price_me`; everything else becomes `gold_pile` and gets vendored. In practice, this typically cuts the trade-API workload by an order of magnitude.

### How the craft graph drives it

The craft graph stores `mod_market_value` edges between mods and their approximate chaos-equivalent value per unit. These edges are seeded from poe.ninja data and updated by the `integrations/poe_ninja.py` client. The classification pass matches each output item's mod list against the regex patterns associated with edges above the `valuable_mod_threshold`. Items where at least one mod clears the threshold land in `price_me`.

To refresh the craft graph's mod values before a cycle:

```python
from integrations.poe_ninja import fetch_mod_values
from store import get_connection

conn = get_connection()
fetch_mod_values(conn, league='Standard')   # or your current league slug
```

This is worth doing at league start and again around week 3-4 when the economy stabilizes.

### Worked example: Sekhemas relics

A Sekhemas relic drops with `+increased item rarity (50-80%)`. The craft graph has a `mod_market_value` edge for `+increased_item_rarity` with a weight of 0.72 (above the 0.5 default threshold). This item lands in `price_me`.

A different relic drops with `+2 to level of socketed support gems` at base tier. The edge weight for that mod at base tier is 0.18. This item lands in `gold_pile` and gets vendored without a Trade API call.

The threshold is not a price floor — it is a signal-to-noise filter. You are not asking "is this worth anything?" You are asking "is this worth the overhead of a trade listing?" For most leagues, 0.5 is the right cutoff. If you are farming a strategy where even marginal items sell (e.g., high-volume corruption results), lower it to 0.3.

### Custom buckets

```python
# TODO once farm package finalizes: custom bucket definition API
# Sketch: classify_outputs(conn, cycle_id, extra_buckets=[
#     {'name': 'corruption_check', 'pattern': r'corrupted.*flask_charges'},
# ])
```

## Double-booked reconciliation

### What the reconcile gap means

`reconcile_cycle` cross-references three things: the declared inputs, the items recorded via `record_output`, and the end-currency snapshot. If 200 Chaos Orbs were declared as input but the currency snapshot difference only accounts for 180, the gap is 20 Chaos Orbs. The gap shows up in `recon['gap']` as a numeric value and `recon['gap_items']` as a structured list.

A gap is not automatically treated as loss. It is an audit flag. Common causes:

- Items captured but not matched to this cycle (e.g., you alt-tabbed and Ctrl+C'd something outside the cycle).
- Currency moved between stash tabs that the snapshot doesn't see.
- The clipboard listener missed a capture during a disconnect.
- You actually lost the items to an NPC trade and forgot to log it.

### When to investigate

If the gap is under 5% of declared inputs, it is usually noise — missed clipboard copies or minor stash tab boundary effects. Log a note in the cycle record and close.

If the gap exceeds 5%, investigate before closing. Check the gap_items list against your memory of the session. If you cannot account for it, note it in the README of any bundle you publish. A bundle with an unexplained gap is still publishable; readers can weight it accordingly.

### The audit trail

Every `record_output` call is timestamped and stored in the cycle's output log. If you need to audit a gap manually, you can query the output log directly against the store:

```python
from store import get_connection

conn = get_connection()
rows = conn.execute(
    "SELECT * FROM cycle_outputs WHERE cycle_id = ?", (cycle_id,)
).fetchall()
```

The raw XML payloads are stored alongside the parsed mod list, so you can verify individual items without re-parsing.

## ROI, hit rate, div/hour — what gets computed at close

`close_cycle` computes and stores the following summary edges on the cycle node:

| Field | Definition |
|---|---|
| `total_input_div` | Declared inputs converted to divine at open-time rates |
| `total_output_div` | All `price_me` items priced at close-time rates + vendored gold-pile at chaos vendor rate |
| `roi_ratio` | `total_output_div / total_input_div`, dimensionless |
| `div_per_hour` | `total_output_div / (time_invested_minutes / 60)` |
| `hit_rate` | `lottery_target_drops / total_execution_units` (maps, runs, etc.) |
| `price_me_count` | Items that required a trade quote |
| `gold_pile_count` | Items vendored without a quote |
| `reconcile_gap` | Final gap from the RECONCILE step |

### Comparing two cycles

Two cycles are comparable when they share the same `farm_target` and were run under close enough patch and economy conditions that rate differences don't swamp the signal. The clearest comparisons are same-target, same-league-week, different-build or different-atlas-allocation.

```python
from farm import get_cycle

c1 = get_cycle(conn, 'cyc_20260501_001')
c2 = get_cycle(conn, 'cyc_20260508_002')

delta_dph = c2['div_per_hour'] - c1['div_per_hour']
delta_roi  = c2['roi_ratio']   - c1['roi_ratio']
```

For longitudinal comparison across a league, list all cycles for the same target and plot `div_per_hour` against `open_timestamp`. The slope tells you whether the strategy degrades as the economy matures.

```python
from farm import list_cycles

cycles = list_cycles(conn, farm_target='sekhemas_relics')
# returns list of dicts, sorted by open_timestamp ascending
```

## Publishing as a .farm.graph bundle

### What the bundle contains

`export_cycle_bundle` writes a `.farm.graph` file (a zip archive with a structured manifest). The contents:

- `manifest.json` — cycle metadata: id, farm_target, open/close timestamps, author, patch, league slug
- `cycle.json` — the full cycle record including summary edges
- `outputs/` — one JSON file per recorded output, with parsed mod list and classification bucket
- `reconcile.json` — the full reconcile report including gap detail
- `build_snapshot/` — a read-only copy of the `.build` file you provided
- `README.txt` — the readme string you passed to `export_cycle_bundle`

The build snapshot is included so anyone who imports the bundle can see what build generated the data. It is not validated or re-parsed at import time — it is documentation.

### The manifest

The manifest is the index the import side reads first. It contains enough information to decide whether the bundle is relevant without unpacking the full output set:

```json
{
  "id": "cyc_20260527_001",
  "schema_version": "1.0",
  "farm_target": "sekhemas_relics",
  "author": "Empyrean",
  "patch": "0.2.0f",
  "league": "Settlers",
  "open_timestamp": "2026-05-27T14:00:00Z",
  "close_timestamp": "2026-05-27T15:42:00Z",
  "total_maps": 50,
  "div_per_hour": 4.3,
  "roi_ratio": 1.21,
  "hit_rate": 0.02,
  "reconcile_gap": 0
}
```

### The README convention

The README string is the human-facing context for the bundle. It should answer: what build was this, what patch, what league conditions were notable, what the author thinks the data shows, and any caveats. It does not need to be long. A three-sentence README is better than no README.

Example:

```python
export_cycle_bundle(
    conn,
    cycle_id,
    out_path='exports/sekhemas_1000map_final.farm.graph',
    build_snapshot_path='data/characters/empyrean_stormweaver.build',
    author='Empyrean',
    readme=(
        'Stormweaver with 2.1M pinnacle DPS and 4.8K EHP. '
        'Ran weeks 3-6 of Settlers league, patch 0.2.0f. '
        'MF gear swapped in for Sekhemas (item rarity +180%). '
        'No scarabs used. Lottery target (mirror) hit zero times across 1000 maps.'
    ),
)
```

### How another player imports and re-runs

```python
# TODO once farm package finalizes: import_cycle_bundle API
# Expected shape:
#   from farm import import_cycle_bundle
#   imported = import_cycle_bundle(conn, 'path/to/bundle.farm.graph')
#   # → creates a new read-only cycle record in the local store
#   # → does NOT re-run classification (classification is in the bundle)
#   # → surfaces the build snapshot for reference
```

Until the import API exists, the bundle is a publication artifact. A reader opens the zip, reads `manifest.json` and `README.txt`, and decides whether to replicate the study.

## What the bundle does NOT do

A `.farm.graph` records what did happen across N cycles with one build on one machine. It does NOT analytically predict what would happen with a different build, a different patch, or a different rolling-window of league economy. When you import someone else's bundle, you are asking "is my situation close enough to theirs that their measured outcomes are likely to transfer?" That comparison is qualitative; the bundle gives you the data, not the answer.

Specific limits:

- **No drop-rate simulation.** The hit rates in the bundle are empirical frequencies from observed drops. They are not a model of the underlying probability distribution. With 1000 maps you have enough samples to estimate a mean, but not enough to characterize the tail.
- **No build validation.** The build snapshot in the bundle is a reference copy. The tool does not check whether your current build matches it, whether the passive tree URL is still valid, or whether the gem links are current.
- **No patch-forward extrapolation.** If the bundle was recorded on 0.2.0f and you are on 0.2.1, the tool does not adjust the numbers for balance changes. That adjustment is yours to make.
- **No shared-stash accounting.** The cycle tracks what you declared. If you were simultaneously running another strategy in the same league and currencies moved between shared tabs, the reconcile pass will flag a gap but cannot resolve it automatically.

## Working with the clipboard listener

The listener is a background process that watches the system clipboard for item payloads and feeds them into the cycle's output log.

```bash
python -m integrations.clipboard_listener
```

By default it runs until interrupted (`Ctrl+C`). It writes each captured item to a queue directory before committing it to the store, so a crash or disconnect does not lose data — the next run replays the queue.

### Queue directory

The queue directory is configurable in `config.yaml` under `clipboard_listener.queue_dir`. Default is `data/clipboard_queue/`. Each queued item is a JSON file with the raw XML payload, timestamp, and a commit flag. On startup, the listener processes any uncommitted files in the queue before entering watch mode.

### Binding the listener to a cycle

The listener needs to know which cycle is currently OPEN so it can call `record_output` with the right `cycle_id`. It reads the currently open cycle from the store at startup. If no cycle is open, it still captures items to the queue but defers commit until a cycle is opened.

```python
# To verify the listener is bound to the right cycle:
from farm import get_cycle, list_cycles

open_cycles = [c for c in list_cycles(conn) if c['state'] == 'EXECUTE']
print(open_cycles)   # should be exactly one
```

If you accidentally have two EXECUTE-state cycles open (from a previous session that was not closed), close the stale one before starting the listener.

### Items the listener will not capture

The listener captures items that produce a parseable XML payload when copied. This includes most equipable items. It does NOT capture: currency (no item card), map fragments (no mods to parse), and some league-specific tokens that use a non-standard card layout. For those, use `record_output` directly or note them manually in the cycle's notes field.

## When to hand off to Exilence CE

The farm package is not a replacement for Exilence CE. It is a layer on top of it, or alongside it, depending on how you use it.

If you already run Exilence and it tracks your net worth accurately, keep using it. Wealth-curve tracking and cycle-ROI tracking answer different questions. Exilence CE is the right tool if you want to know whether you are getting richer at the league level. The farm package is the right tool if you want to know whether a specific strategy, with specific inputs, is worth the time.

The handoff is explicit: once a cycle closes and you have the `div_per_hour` number, that result can flow back into your Exilence wealth curve as a manual entry if you want longitudinal wealth tracking. The farm package does not attempt to do this automatically.

If you do not use Exilence, you do not need it to use cycles. The cycle summary gives you enough to compare strategies and make decisions about what to run next.

## See also

- `DOCS/guides.md` — system guides and the transmissible meta-game layer; `time_budget_calibration` and `currency_velocity` edges apply directly to cycle discipline
- `DOCS/goals.md` — `economic` sub-goals can target cycle ROI numbers as their `stat_threshold`
- `DOCS/graph-queries.md` — direct store queries for cycle data and output log
- `DOCS/build-construction.md` — the `.build` snapshot format included in exported bundles
- `contracts.md` — the `.farm.graph` / `.craft.graph` / `.guide.graph` XML schema vocabulary for power users extending the lifecycle
