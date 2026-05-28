---
id: contracts
file: DOCS/contracts.md
topic: XML schema vocabulary for .farm.graph / .craft.graph / .guide.graph bundles + manifest schema + cross-graph references
priority: reference
modules: [store, graphfmt, farm]
tags: [contracts, schema, xml, farm_graph, craft_graph, guide_graph, manifest, cross_refs, format_spec]
when_to_read: |
  User asks about the XML payload shape for any .X.graph file, what fields a
  manifest.xml must contain, how to write or validate a bundle, how to
  reference one graph from another, or what attribute names are reserved.
  Also when a power user is extending the format vocabulary, or a developer
  is writing a reader/writer for one of the bundle types. Pairs with
  DOCS/farming-cycles.md for the user-facing workflow side of the same
  artifacts.
mastery_levels: [advanced]
---

# poe2-graph contracts

XML schema vocabulary for the `.X.graph` format family. Companion to the design doc
(§2.1, §2.2). Implementation references: `store`, `graphfmt`, `farm` packages.

---

## 0. Reading order

| Question | Go to |
|---|---|
| What is a `.X.graph` file physically? | §1, §3 |
| What fields must manifest.xml contain? | §3 |
| What is in a `.farm.graph` bundle? | §4 |
| What is in a `.craft.graph` bundle? | §5 |
| What is in a `.guide.graph` bundle? | §6 |
| How do graphs reference each other? | §7 |
| What attribute names are reserved? | §8 |
| How are unknowns handled by readers? | §9 |
| What should I validate before trusting a payload? | §10 |

---

## 1. Conventions

### 1.1 Physical format

A `.X.graph` file is one of three physical forms, detected by `graphfmt.detect_format()`:

- **zip bundle** — a ZIP archive (`PK\x03\x04` magic), containing `manifest.xml` plus
  any number of content files. Use this when the graph travels with media, a
  `.build` snapshot, or a nested sub-graph.
- **gzip single-doc** — a gzip-compressed XML document (`\x1f\x8b` magic). Use this
  for passing a single XML graph without packaging siblings.
- **plain XML** — uncompressed XML starting with `<`. Accepted in dev/test contexts only.

The reader auto-dispatches in `graphfmt.read_graph(path)`. Writers call
`graphfmt.write_bundle(...)` or `graphfmt.write_single(...)` directly.

### 1.2 Element vs attribute discipline

Apply this consistently across all schemas in this document:

- **Attributes** carry identity and metadata: `id`, `timestamp`, `status`,
  `classification`, `weight`, `kind`, `type`, `progress`, `mastery`, `market_value`.
- **Elements** carry content: `<title>`, `<statement>`, `<description>`,
  `<notes>`, `<mods>`, `<item>`, `<target>`, `<farm_target>`.

When in doubt: if the value fits in a token (a word, a float, an ISO date), put it in
an attribute. If it is free text that may contain angle brackets or line breaks, use an
element with CDATA or escaped text.

### 1.3 Identifier convention

All `id` values use the form `<prefix>_<slug>`, where `slug` is lower-case ASCII with
underscores. No spaces, no UUIDs at the first level (UUIDs are reserved for
system-generated events in the store's `edges` table).

Examples of well-formed ids:
```
cycle_sekhemas_relics_001
output_headhunter_drop_1
goal_become_self_sufficient_crafter
subgoal_hit_80pct_chaos_res
```

The prefix identifies the element type:
- `cycle_` — farm cycle root
- `input_` — farm input node
- `output_` — farm output node
- `state_` — craft item state node
- `goal_` — player goal node in a guide graph
- `subgoal_` — sub-goal node in a guide graph

### 1.4 Timestamp convention

All timestamps in payload XML use ISO 8601 with UTC timezone: `2026-05-27T14:30:00Z`.
Elements that have not yet occurred carry an empty tag: `<closed_at/>`.
Store rows use `appended_at` (ISO string, from `history.append_*` signatures) as the
`ts` column when syncing to Turso.

### 1.5 Namespace policy

No XML namespaces in v1. All elements are in the default (empty) namespace.

### 1.6 Versioning approach

`format_version` is an integer, starting at 1. It lives in `manifest.xml` for bundles
and as an attribute on the root element for single-doc graphs. Readers must check this
field before interpreting a payload. Unknown versions must be rejected with a clear
error — not silently processed with assumptions.

### 1.7 Edge representation

Edges in the `.X.graph` schemas are represented in two places:

1. **In the store** — rows in the `edges` table with `source_id`, `target_id`,
   `graph_id`, `edge_type`, `weight`, and `payload` (XML string). The `payload` field
   is the canonical schema contract (see §4.4, §5.2, etc.).
2. **In XML documents** — when the full document is serialised (e.g. `cycle.xml`), edges
   are rendered as child elements of the graph root with `source` and `target`
   attributes referencing node ids.

### 1.8 Cross-graph references

When a node in one graph refers to a node in another graph, the reference lives in
the `graph_refs` table (`store.insert_graph_ref`). In XML serialisations, a `<ref>`
element with `graph` and `node` attributes carries the pointer. See §7 for the full
cross-graph reference taxonomy.

---

## 2. Common building blocks

These types recur across all `.X.graph` schemas. Define them once here.

### 2.1 node_id

A text string in the form `<prefix>_<slug>`. Unique within a `graph_id`. In the
`nodes` table, `node_id` is the PRIMARY KEY across all graphs — if the same logical
item appears in two graphs, each occurrence gets a distinct, prefixed `node_id`.

### 2.2 Timestamps

```xml
<opened_at>2026-05-27T14:32:00Z</opened_at>
<closed_at/>
```

Empty self-closing tag means "not yet set". ISO 8601 with `Z` suffix means UTC.

### 2.3 Currency amount

```xml
<cost currency="chaos" amount="40"/>
<cost currency="divine" amount="1"/>
<cost currency="exalted" amount="3"/>
```

`currency` is a lower-case slug matching GGG's internal currency item name
(e.g. `chaos`, `divine`, `exalted`, `vaal`, `annulment`, `augmentation`,
`alteration`, `transmutation`, `regal`). `amount` is a positive integer.

### 2.4 Item text encoding

When a full clipboard paste is embedded in a payload, wrap it in CDATA:

```xml
<item><![CDATA[Item Class: Waystones
Rarity: Rare
Crumbling Morale
Waystone
--------
Item Level: 83
--------
+12% increased Rarity of Items found in this Area (implicit)
--------
+25% increased Pack Size
+18% increased Monster Movement Speed]]></item>
```

Do not XML-escape the paste text; use CDATA so line breaks and special characters
are preserved exactly.

### 2.5 Mod pattern type

A mod pattern is a Python regex that matches any numeric substitution with `\d+` or
`\d+\.\d+`. The pattern represents the structural shape of a mod across all item
rolls.

```xml
<mod pattern="\+\d+% increased Rarity of Items" market_value="0.6">
  <last_seen>2026-05-27T12:00:00Z</last_seen>
  <source>poe.ninja_mod_meta</source>
</mod>
```

`market_value` is a float in [0, 1] representing relative market desirability
(1.0 = maximum, 0.0 = worthless). The scale is project-internal — it is not a price
in any currency.

### 2.6 Item classification vocabulary

The set of valid `classification` values for output nodes (see §4.3):

| Value | Meaning |
|---|---|
| `price_me` | Item requires manual price check before selling |
| `vendor` | Vendor trash — sell without checking |
| `keep` | Upgrade candidate — do not sell |
| `chaos_recipe` | Part of a chaos recipe set |
| `unknown` | Not yet classified |

---

## 3. Manifest schema (`.X.graph` bundles)

Manifest is always `manifest.xml` at the root of the zip archive. It describes the
bundle's identity, contents, and cross-references between those contents.
`graphfmt.dict_to_manifest_xml(d)` serialises the dict form; `graphfmt.manifest_to_dict(xml)`
parses it back.

### 3.1 Full example

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest>
  <bundle_id>sekhemas_relics_1000_emp</bundle_id>
  <graph_type>farm</graph_type>
  <format_version>1</format_version>
  <created_at>2026-05-27T14:30:00Z</created_at>
  <author>Empyrean</author>
  <contents>
    <file path="cycle.xml" role="primary"/>
    <file path="character.build" role="build_snapshot"/>
    <file path="atlas.guide.graph" role="nested_graph"/>
    <file path="empirical.xml" role="measurements"/>
    <file path="README.md" role="readme"/>
  </contents>
  <cross_refs>
    <ref from="cycle.xml" to="character.build" relation="ran_by"/>
    <ref from="cycle.xml" to="atlas.guide.graph" relation="atlas_strategy"/>
  </cross_refs>
</manifest>
```

### 3.2 Required fields

| Element | Type | Constraint |
|---|---|---|
| `bundle_id` | slug | Unique within author's collection; used as `graph_id` in the store |
| `graph_type` | enum | `farm` \| `craft` \| `guide` |
| `format_version` | integer | Must be `1` for this contract version |
| `created_at` | ISO timestamp | UTC |

### 3.3 Optional fields

| Element | Notes |
|---|---|
| `author` | Creator slug or display name |
| `contents` | If absent, reader treats zip members as all content with no roles |
| `cross_refs` | May be empty or absent |

Any extra scalar-string elements the author adds (e.g. `<league_id>`) are preserved
through round-trips by `manifest_to_dict` / `dict_to_manifest_xml` (they fall through
to the "extra scalar keys" branch in `graphfmt/manifest.py` lines 30-33).

### 3.4 Contents roles

| `role` | Meaning |
|---|---|
| `primary` | The graph's root document (e.g. `cycle.xml` for farm) |
| `build_snapshot` | A `.build` file captured at bundle creation time |
| `nested_graph` | A fully valid `.X.graph` nested inside this bundle |
| `measurements` | Supporting data (empirical runs, price snapshots) |
| `readme` | Human-readable description (also surfaced as `readme` key by `read_bundle`) |

### 3.5 Cross-ref relations

| `relation` | Meaning |
|---|---|
| `ran_by` | The primary cycle/craft was executed with this build |
| `atlas_strategy` | The farm cycle follows this atlas guide |
| `upgrade_path` | The craft graph follows this upgrade-pacing guide |
| `teaches` | This guide was the learning source for this cycle |

---

## 4. `.farm.graph` schema

A farm graph captures one farming cycle: what was targeted, what dropped, how much
time was spent, and the economic outcome. The primary file is `cycle.xml`.

### 4.1 Cycle root node

The root of `cycle.xml` is a `<cycle>` element. Its `node_id` (stored in the `nodes`
table as `graph_type = "farm"`) is the `id` attribute value.

```xml
<cycle id="cycle_sekhemas_relics_001" status="ACTIVE">
  <farm_target>sekhemas_relics</farm_target>
  <lottery_targets>
    <target>mirror_of_kalandra</target>
    <target>temporalis</target>
  </lottery_targets>
  <declared_at>2026-05-27T14:30:00Z</declared_at>
  <opened_at>2026-05-27T14:32:00Z</opened_at>
  <closed_at/>
  <notes>T16 honour run, 4-key spec. Targeting relic drops and flipping
waystones on the side.</notes>
</cycle>
```

`status` values: `ACTIVE` (in-progress), `CLOSED` (complete), `ABANDONED`.

`farm_target` is a short slug naming the farming method or content type. Established
slugs for Sekhemas and Breaches:

| `farm_target` | Description |
|---|---|
| `sekhemas_relics` | Sekhemas relic farming via honour run |
| `sekhemas_honour` | Sekhemas honour-only run (no relic focus) |
| `breach_chaos` | Breach ring crafting via chaos spam |
| `breach_splinters` | Breach splinter accumulation |
| `citadel_rotation` | Citadel boss rotation for keystones |
| `waystone_flip` | Waystone identification and resale |
| `map_sustain` | General T16 sustain without specific target |

`lottery_targets` are the rare jackpot items that would qualify as a lottery win for
this cycle. List them so `farm.classify` can flag a drop as a lottery hit.

### 4.2 Input nodes

Each input to the cycle is a node with `graph_type = "farm"` and an `input_` prefix
id. Inputs represent consumables spent per run.

```xml
<input id="input_waystone_t16" status="active">
  <description>T16 waystone with 60%+ rarity</description>
  <cost currency="chaos" amount="8"/>
  <quantity_per_run>1</quantity_per_run>
</input>
```

```xml
<input id="input_sekhemas_key" status="active">
  <description>Inscribed Ultimatum key (4-key tier)</description>
  <cost currency="chaos" amount="12"/>
  <quantity_per_run>4</quantity_per_run>
</input>
```

The edge from `input_*` to `cycle_*` has `edge_type = "consumed_by"` and `weight`
equal to the chaos-equivalent cost per run.

### 4.3 Output nodes

Each distinct item type that dropped gets an output node. A single notable drop (a
rare belt, a unique flask) is its own node.

```xml
<output id="output_sekhemas_relic_ring_01"
        classification="price_me"
        timestamp="2026-05-27T14:55:00Z">
  <item><![CDATA[Item Class: Rings
Rarity: Rare
Obsidian Ring
--------
Item Level: 80
--------
+28% to Chaos Resistance (implicit)
--------
+62 to Maximum Life
+41% to Cold Resistance
+38% to Lightning Resistance]]></item>
  <mods>+62 max life / +41% cold res / +38% lightning res</mods>
</output>
```

```xml
<output id="output_chaos_drop_batch_01"
        classification="vendor"
        timestamp="2026-05-27T14:57:00Z">
  <description>Bulk currency from 3 runs</description>
  <quantity currency="chaos" amount="60"/>
</output>
```

`classification` is one of the values from §2.6. Reader implementations should call
`store.xml_extract(payload, '/output/@classification')` to read classification without
parsing the full item text.

`mods` is a short human-readable summary of the notable mods (for quick scanning).
It is not the source of truth — `<item>` CDATA is.

The edge from `cycle_*` to `output_*` has `edge_type = "produced"` and `weight = 0.0`
(outputs are unweighted until priced; pricing happens in the ROI summary edge).

### 4.4 Currency snapshot edges

When a cycle is closed, one or more price-snapshot edges record the market value
at close time. These are stored in the `edges` table with `edge_type = "price_snapshot"`.

The payload:
```xml
<price_snapshot currency="divine" rate_in_chaos="210"
                timestamp="2026-05-27T16:00:00Z">
  <source>poe.ninja</source>
</price_snapshot>
```

`rate_in_chaos` is the chaos-equivalent value of one unit of `currency` at snapshot
time. This is the denominator used when computing ROI.

### 4.5 Classification metadata

After a cycle closes, `farm.classify` assigns classifications to output nodes and
emits classification edges from the `cycle_*` node to each `output_*` node.

```xml
<classification verdict="price_me" confidence="0.85"
                classified_at="2026-05-27T16:02:00Z">
  <reason>Rare ring with life + two T1 resists; market value unknown</reason>
</classification>
```

`confidence` is a float in [0, 1]. If `confidence` is below 0.5, the classification
is advisory — the player should confirm manually.

The edge storing this payload has `edge_type = "classified_as"`, `source_id =
"cycle_*"`, `target_id = "output_*"`.

### 4.6 Summary edges (ROI / hit_rate / div_per_hour)

When a cycle closes and enough data exists, summary edges record aggregate performance.
These travel from `cycle_*` to itself (self-loops are valid in the store) or to a
synthetic `summary_*` node.

ROI summary:
```xml
<roi chaos_in="480" chaos_out="1250" runs="10"
     div_per_hour="2.4" hit_rate="0.15"
     computed_at="2026-05-27T16:05:00Z">
  <notes>One nice ring sold for 300c. Rest is vendor trash.</notes>
</roi>
```

`chaos_in` is total input cost across all runs. `chaos_out` is total gross revenue.
`div_per_hour` assumes 6 runs per hour for this farm target (configurable per target).
`hit_rate` is the fraction of runs that produced at least one `price_me` or `keep` output.

These edges have `edge_type = "summary"` and `weight = div_per_hour`.

### 4.7 Cross-refs to canonical inventory nodes

When an output node corresponds to a known item in the canonical inventory (see
`items/inventory.py`), a `graph_refs` row links the output node to the canonical node:

```python
store.insert_graph_ref(
    conn,
    referencing_node_id="output_headhunter_drop_1",
    referenced_node_id="inv_headhunter_001",
    ref_type="output_of",
)
```

The `ref_type` values for farm outputs:

| `ref_type` | Meaning |
|---|---|
| `output_of` | This output node is a specific drop instance of the canonical item |
| `lottery_win` | The output qualifies as a declared lottery target |
| `cost_ref` | This input node's cost references a canonical currency node |

### 4.8 Bundle layout

A `.farm.graph` bundle contains:

```
sekhemas_relics_1000_emp.farm.graph   (zip)
  manifest.xml
  cycle.xml                           primary
  empirical.xml                       measurements (per-run timing, map mods seen)
  character.build                     build_snapshot
  atlas.guide.graph                   nested_graph (the atlas strategy used)
  README.md                           readme
```

`empirical.xml` is the run-log companion. Its root is `<runs>` containing one
`<run>` per map cleared:

```xml
<runs cycle_id="cycle_sekhemas_relics_001">
  <run seq="1" started_at="2026-05-27T14:32:00Z"
       ended_at="2026-05-27T14:41:00Z" outcome="clear">
    <map_mods>+25% pack size / +18% monster speed</map_mods>
    <loot_notes>Two rings, one flask, vendor trash</loot_notes>
  </run>
  <run seq="2" started_at="2026-05-27T14:42:00Z"
       ended_at="2026-05-27T14:50:00Z" outcome="death">
    <map_mods>+35% pack size / ele reflect</map_mods>
    <loot_notes/>
  </run>
</runs>
```

`outcome` values: `clear`, `death`, `abandoned`.

---

## 5. `.craft.graph` schema

A craft graph captures a crafting decision tree: the sequence of item states and
currency applications that transforms a base into a target. Nodes are item states;
edges are currency applications with probability weights.

### 5.1 Item state nodes

Each distinct state the item can be in is a node with `graph_type = "craft"`.

```xml
<state id="state_ilvl85_armour_base" phase="start">
  <item><![CDATA[Item Class: Body Armours
Rarity: Normal
Glorious Plate
--------
Armour: 891
--------
Item Level: 85
--------
[Unidentified]]]></item>
  <mods/>
  <notes>Fresh base, item level 85, six-linked manually.</notes>
</state>
```

```xml
<state id="state_after_essence_woe_1" phase="mid">
  <item><![CDATA[Item Class: Body Armours
Rarity: Rare
...]]></item>
  <mods>+85 to maximum Life / +2 to Level of all Strength Skill Gems</mods>
  <notes>Essence of Woe hit the life mod. Now need res and another suffix.</notes>
</state>
```

```xml
<state id="state_final_target" phase="target">
  <description>6L armour with 80+ life, level gems, two capped res</description>
  <mods>+80 to maximum Life / +2 gem levels / two resistance suffixes</mods>
</state>
```

`phase` values: `start` (base item), `mid` (intermediate state), `target` (desired
end state), `dead_end` (unrecoverable state).

The `target` phase node has no `<item>` CDATA — it is a specification, not an actual
item. It carries `<description>` and `<mods>` as the success criterion.

### 5.2 Currency-application edges

Each edge in a craft graph represents one currency application or craft action.

```xml
<currency_apply currency="essence_of_woe" expected_cost="1">
  <probability>1.0</probability>
  <outcome_notes>Forces +# to maximum Life as a prefix.
Guarantees at least T3 but can hit T1.</outcome_notes>
</currency_apply>
```

```xml
<currency_apply currency="chaos" expected_cost="3">
  <probability>0.08</probability>
  <outcome_notes>Chaos spam until life + two res.
Typical: 15-40 chaos per attempt.</outcome_notes>
</currency_apply>
```

Edges have `edge_type = "currency_apply"` in the store. `weight` is the chaos-equivalent
expected cost of this application (single application, not total). `probability` is the
estimated probability that this transition produces the target state.

Multi-edge semantics: multiple edges between the same source and target state are valid.
They represent alternative currency approaches to the same transition.

### 5.3 Probability weights

`<probability>` is a float in (0, 1]. A value of 1.0 means deterministic (e.g.
applying an Essence). A value below 0.05 is a "long-shot" craft and should be flagged
in the UI.

For complex mod combinations, use conditional probability: the probability given that
all prerequisites are already present. Document the conditioning assumptions in
`<outcome_notes>`.

### 5.4 mod_market_value edges

The craft graph interacts with the farm's `farm.classify` system. When a crafted item
carries mods with known market values, `mod_market_value` edges flow from the
`state_*` node to the `output_*` node in the farm graph (via `graph_refs`).

The edge payload, stored in the `edges` table with `edge_type = "mod_market_value"`:

```xml
<mod pattern="\+\d+% increased Rarity of Items" market_value="0.6">
  <last_seen>2026-05-27T12:00:00Z</last_seen>
  <source>poe.ninja_mod_meta</source>
</mod>
```

Reader implementations should use `store.xml_extract(payload, '/mod/@market_value')`
and `store.xml_extract(payload, '/mod/@pattern')` to project these without full parse.

`market_value` is on the same [0, 1] scale as §2.5. `source` is the data provider
slug. Established sources:

| `source` | Meaning |
|---|---|
| `poe.ninja_mod_meta` | poe.ninja mod popularity data |
| `manual` | Hand-coded by the skill author |
| `inferred` | Derived from price ratios across recent cycles |

### 5.5 Bundle layout

A `.craft.graph` bundle contains:

```
armour_6l_life_gems.craft.graph   (zip)
  manifest.xml
  craft.xml                       primary (the state DAG)
  README.md                       readme
```

Optional additions when the craft is tied to a character or a guide:
```
  character.build                 build_snapshot (the target build that needs the item)
  upgrade_pacing.guide.graph      nested_graph (the upgrade-pacing guide)
```

The manifest for a craft bundle:

```xml
<manifest>
  <bundle_id>armour_6l_life_gems_pedro_001</bundle_id>
  <graph_type>craft</graph_type>
  <format_version>1</format_version>
  <created_at>2026-05-27T10:00:00Z</created_at>
  <author>pedro</author>
  <contents>
    <file path="craft.xml" role="primary"/>
    <file path="character.build" role="build_snapshot"/>
    <file path="README.md" role="readme"/>
  </contents>
  <cross_refs>
    <ref from="craft.xml" to="character.build" relation="ran_by"/>
  </cross_refs>
</manifest>
```

---

## 6. `.guide.graph` schema

See also: validation report §goals.py and §guides.py+systems.py for the confirmed and
partial reuse status.

A guide graph captures player knowledge structure: goals, sub-goals, dependencies, and
links to the guide corpus. The primary file is `guide.xml`.

The v1 source of truth for goal data is YAML frontmatter in `EXILE/*.md`. A
`.guide.graph` is a serialised view of that data, either for sharing or for offline
planning. The round-trip path is: `goals.PlayerGoal.to_dict()` → XML serialisation
→ `goals.PlayerGoal.from_dict()`.

See validation report §goals.py for the full gap analysis: goals are currently stored
as YAML, not graph format. The schema below is what the v2 serialisation MUST produce.

### 6.1 Goal nodes (the four types from goals.py)

The four `PlayerGoal.type` values from `goals.py` line 355 (`GOAL_TYPES`) are the
canonical classification:

| `type` | Meaning |
|---|---|
| `economic` | Wealth, currency, trading objectives |
| `mechanical` | Build performance, survivability, damage |
| `knowledge` | Learning a system, mastery of a mechanic |
| `identity` | Playstyle commitments (HC, SSF, trade-league main) |

A goal node serialised from `PlayerGoal.to_dict()`:

```xml
<goal id="goal_become_self_sufficient_crafter"
      type="knowledge"
      horizon="leagues"
      status="active"
      measurable="true"
      progress="0.25">
  <statement>Craft all my own gear without relying on trade for upgrades</statement>
  <measure>Self-crafted item in every slot at league end</measure>
  <related_edges>
    <edge name="crafting_deliberate"/>
    <edge name="market_timing"/>
  </related_edges>
  <created>2026-04-01</created>
  <activated_at>2026-05-10</activated_at>
</goal>
```

`horizon` values (from `goals.GOAL_HORIZONS`): `leagues`, `months`, `years`.

`status` values (from `goals.PLAYER_GOAL_STATUS`): `active`, `dormant`, `completed`,
`abandoned`. At most one `<goal>` in a guide graph has `status="active"` at any moment —
this is the single-active rule from `goals.set_active_player_goal()`.

`related_edges` are edge names from `data/guides/edge_taxonomy.yaml`. They link the
goal to the guide corpus scoring in `guides.recommend_next_action()`.

### 6.2 SubGoal nodes

Sub-goals are nested inside their parent `<goal>` element in `guide.xml`. They map
directly to `SubGoal.to_dict()`.

The eleven `kind` values from `goals.SUB_GOAL_KINDS` (line 362):

| `kind` | Progress shape |
|---|---|
| `stat_threshold` | `target.stat` + `target.value`; progress = current/target |
| `composite` | Progress = mean of sub-steps |
| `atlas_progression` | `target.nodes_allocated` + optional `target.gateway` |
| `economic` | `target.resource` + `target.count` |
| `knowledge` | Links to a `LearningGoal` via `learning_goal_id` |
| `milestone` | Binary; status flips on event |
| `acquire` | `target.item` + `target.count` |
| `travel` | `target.place_or_unlock` |
| `kill` | `target.enemy` + `target.count` |
| `interact` | `target.object_or_system` |
| `freeform` | Narrative only |

Status values (from `goals.SUB_GOAL_STATUS`): `open`, `in_progress`, `done`, `blocked`.

```xml
<subgoal id="subgoal_hit_80pct_chaos_res"
         kind="stat_threshold"
         status="in_progress"
         progress="0.62">
  <statement>Hit 80% chaos resistance on the active character</statement>
  <target>
    <stat>chaos_resistance</stat>
    <value>80</value>
  </target>
  <depends_on/>
  <related_edges>
    <edge name="defence_layering"/>
  </related_edges>
</subgoal>
```

```xml
<subgoal id="subgoal_acquire_chaos_res_belt"
         kind="acquire"
         status="open"
         progress="0.0">
  <statement>Find or craft a belt with 30%+ chaos resistance</statement>
  <target>
    <item>Belt with chaos resistance</item>
    <count>1</count>
  </target>
  <depends_on>
    <dep ref="subgoal_hit_80pct_chaos_res"/>
  </depends_on>
  <learning_goal_id>essence_crafting</learning_goal_id>
</subgoal>
```

`<depends_on>` contains zero or more `<dep ref="..."/>` elements, where `ref` is the
`id` of another `<subgoal>` within the same goal. This is the DAG structure; a
sub-goal is "available" when all its `depends_on` refs have `status="done"`. This
matches `PlayerGoal.next_actionable()` in `goals.py` lines 515-535.

`learning_goal_id` (when present) cross-references a `LearningGoal` stored in
`EXILE/LEAGUE_*.md` frontmatter.

### 6.3 depends_on edges

In the `edges` table, each `<dep>` from §6.2 becomes a row:

```python
store.insert_edge(
    conn,
    source_id="subgoal_acquire_chaos_res_belt",
    target_id="subgoal_hit_80pct_chaos_res",
    graph_id="guide_pedro_season3",
    edge_type="depends_on",
    weight=1.0,
    payload="<dep/>",
)
```

`weight = 1.0` for hard dependencies. Future: `weight < 1.0` for soft/advisory
dependencies (not in v1).

### 6.4 Goal-to-creator/case-study references

Goals optionally reference creators and case studies from the guide corpus. In
`guide.xml`:

```xml
<goal id="goal_become_self_sufficient_crafter" ...>
  ...
  <related_creators>
    <creator slug="ben_"/>
    <creator slug="subtractem"/>
  </related_creators>
  <related_case_studies>
    <case_study id="essence_crafting_body_armor_t16"/>
  </related_case_studies>
</goal>
```

`slug` values match `Creator.name` in `guides.py` (loaded from
`data/guides/creators/*.yaml`). `id` values match `CaseStudy.id`.

In the `graph_refs` table, each reference becomes a row with:

| `ref_type` | Meaning |
|---|---|
| `creator_ref` | Goal references this creator as a learning source |
| `case_study_ref` | Goal references this case study as a concrete example |

### 6.5 Bundle layout

A `.guide.graph` bundle contains:

```
pedro_season3_goals.guide.graph   (zip)
  manifest.xml
  guide.xml                       primary (player goals + sub-goal DAG)
  README.md                       readme
```

The manifest for a guide bundle:

```xml
<manifest>
  <bundle_id>pedro_season3_goals</bundle_id>
  <graph_type>guide</graph_type>
  <format_version>1</format_version>
  <created_at>2026-05-27T09:00:00Z</created_at>
  <author>pedro</author>
  <contents>
    <file path="guide.xml" role="primary"/>
    <file path="README.md" role="readme"/>
  </contents>
  <cross_refs/>
</manifest>
```

The root of `guide.xml` is a `<guide>` element:

```xml
<?xml version="1.0" encoding="utf-8"?>
<guide id="pedro_season3_goals" format_version="1"
       player="pedro" league="Settlers3">
  <goal id="goal_become_self_sufficient_crafter" ...>
    <subgoal .../>
    <subgoal .../>
  </goal>
  <goal id="goal_reach_citadel_farming" type="mechanical"
        status="dormant" ...>
    ...
  </goal>
</guide>
```

`league` is the `league_id` this guide was authored in. It is informational — goals
are player-level, not league-scoped (see validation report §goals.py: `PlayerGoal`
lives in `PLAYER.md`, not `LEAGUE_*.md`).

---

## 7. Cross-graph references

All cross-graph references go through the `graph_refs` table in the store. The XML
serialisation uses `<ref>` elements. This section defines the complete set of valid
cross-graph reference combinations for v1.

### 7.1 Farm graph referencing a build

A `.farm.graph` cycle ran with a specific character build. The reference links the
cycle node to the build file included in the bundle.

Store row:
```python
store.insert_graph_ref(
    conn,
    referencing_node_id="cycle_sekhemas_relics_001",
    referenced_node_id="build_empyrean_stormweaver_01",
    ref_type="ran_by",
)
```

In `cycle.xml`:
```xml
<cycle id="cycle_sekhemas_relics_001" ...>
  ...
  <ref graph="character.build" node="build_empyrean_stormweaver_01"
       relation="ran_by"/>
</cycle>
```

### 7.2 Farm graph referencing a guide graph

A `.farm.graph` cycle followed an atlas strategy captured in a `.guide.graph`.

Store row:
```python
store.insert_graph_ref(
    conn,
    referencing_node_id="cycle_sekhemas_relics_001",
    referenced_node_id="guide_pedro_season3_goals",
    ref_type="atlas_strategy",
)
```

In `cycle.xml`:
```xml
<ref graph="atlas.guide.graph" node="guide_pedro_season3_goals"
     relation="atlas_strategy"/>
```

### 7.3 Craft graph referencing a guide graph

A `.craft.graph` implements an upgrade-pacing principle described in a `.guide.graph`.

```python
store.insert_graph_ref(
    conn,
    referencing_node_id="state_ilvl85_armour_base",
    referenced_node_id="subgoal_acquire_chaos_res_belt",
    ref_type="upgrade_path",
)
```

In `craft.xml`:
```xml
<state id="state_ilvl85_armour_base" ...>
  ...
  <ref graph="upgrade_pacing.guide.graph"
       node="subgoal_acquire_chaos_res_belt"
       relation="upgrade_path"/>
</state>
```

### 7.4 Reference resolution at read time

When a reader encounters a `<ref>` inside a bundle, it resolves in this order:

1. Check if `graph` names a file in the bundle's `contents` dict.
2. If yes, parse that file to find `node`.
3. If no, query `store.query_graph_refs(conn, referenced_node_id=node)` to locate
   the node in the shared store.

Step 3 allows bundles to reference nodes in other bundles that are not packaged
together. The reference is advisory — if resolution fails, the reader should warn but
not crash.

---

## 8. Reserved attributes and elements

These names carry fixed semantics across all `.X.graph` schemas. Do not repurpose them.

### 8.1 Reserved attributes

| Attribute | Type | Semantics |
|---|---|---|
| `id` | slug | Node or element identity. Unique within the graph. |
| `timestamp` | ISO datetime (UTC) | When the event or measurement occurred. |
| `status` | enum | Lifecycle state of the containing element (graph-specific values). |
| `classification` | enum | Output classification (see §2.6). |
| `weight` | float | Edge weight in the store `edges` table. Semantics per edge_type. |
| `kind` | enum | Sub-goal kind (see §6.2 table). |
| `type` | enum | Goal type (see §6.1 table). |
| `progress` | float [0,1] | Completion fraction. 1.0 = done. |
| `mastery` | enum | LearningGoal mastery level: `not_started` / `learning` / `competent` / `confident`. |
| `market_value` | float [0,1] | Relative market desirability (see §2.5). |
| `format_version` | integer | Schema version (currently 1). |
| `confidence` | float [0,1] | Classification or tagging confidence. |

### 8.2 Reserved elements

| Element | Semantics |
|---|---|
| `<item>` | Full GGG clipboard text in CDATA. |
| `<mods>` | Short human-readable mod summary. |
| `<description>` | Free-text description of a node. |
| `<statement>` | One-sentence goal statement (PlayerGoal / SubGoal). |
| `<notes>` | Free-form session notes. |
| `<depends_on>` | Container for `<dep>` references (sub-goal DAG). |
| `<related_edges>` | Container for `<edge name="..."/>` edge taxonomy references. |
| `<related_creators>` | Container for `<creator slug="..."/>` references. |
| `<related_case_studies>` | Container for `<case_study id="..."/>` references. |
| `<ref>` | Cross-graph reference: `graph` + `node` + `relation` attributes. |
| `<cost>` | Currency cost: `currency` + `amount` attributes (see §2.3). |
| `<target>` | Structured sub-goal target (content varies by `kind`). |
| `<measure>` | Human-readable measure of completion for a goal. |

---

## 9. Forward-compatibility rules

### 9.1 Unknown elements are preserved

When a reader encounters an element name it does not recognise inside a known parent,
it must preserve that element through any round-trip. The reader must not discard
unknown elements silently. This applies to:

- Unknown child elements inside `<cycle>`, `<input>`, `<output>`, `<state>`, `<goal>`,
  `<subgoal>`.
- Unknown attributes on any known element.
- Unknown top-level elements inside `<guide>`, `<craft>`, `<runs>`.

Implementation guidance: when round-tripping via `ET.fromstring` / `ET.tostring`,
ElementTree preserves unknown elements by default. Verify that any string-builder
paths (like those in `docs.py` and `exile.py`) do not strip elements they do not
produce.

### 9.2 format_version policy

A reader encountering `format_version > 1` (the current contract version) must:
1. Log a warning naming the version.
2. Attempt to parse the document with the v1 rules.
3. If parsing fails, raise a clear error identifying the unknown version — not a
   generic XML parse error.

A reader encountering `format_version < 1` must reject the document immediately.

### 9.3 New edge_type values

The store allows any string in `edge_type`. If a reader queries edges and sees an
`edge_type` it does not recognise, it must pass through the row without interpretation.
It must not discard the row or raise an error.

### 9.4 New classification values

If `farm.classify` emits a `classification` value not in §2.6, the display layer
must render it as-is and not substitute a default. The §2.6 table is a closed set for
v1 but will grow in v2.

---

## 10. Validation cookbook

Before trusting any `.X.graph` payload, a reader should verify:

### 10.1 Bundle validation (zip format)

1. `manifest.xml` is present. If absent: raise, do not proceed.
2. `manifest["graph_type"]` is one of `farm`, `craft`, `guide`. If unknown: warn,
   continue with pass-through.
3. `manifest["format_version"]` is `"1"` (string, after `manifest_to_dict` coercion).
   If higher: warn. If absent or lower: raise.
4. The file named in the `role="primary"` content entry exists in the bundle's
   `contents` dict. If absent: raise.

### 10.2 Node payload validation

Before inserting a node into the store via `store.insert_node`, verify:
1. `node_id` is non-empty and matches the `<prefix>_<slug>` pattern.
2. `graph_type` is `farm`, `craft`, or `guide`.
3. `payload` is valid XML (parseable by `ET.fromstring` without error).
4. The root element tag of `payload` matches the expected tag for `graph_type`
   (e.g. `farm` nodes have roots `cycle`, `input`, or `output`).

### 10.3 Edge payload validation

Before inserting an edge via `store.insert_edge`, verify:
1. `source_id` and `target_id` exist in the `nodes` table (or are being inserted
   in the same transaction).
2. `weight` is a finite float (not NaN or Inf).
3. `payload` is valid XML if non-empty.

### 10.4 Goal DAG validation (guide graphs)

Before writing a `guide.xml` to disk:
1. All `<dep ref="..."/>` values in any `<subgoal>` resolve to another `<subgoal>`
   id in the same `<goal>`.
2. The dependency graph is acyclic. Use `PlayerGoal.next_actionable()` as a smoke
   test — it will not terminate on a cycle.
3. At most one `<goal>` has `status="active"`. This enforces the single-active rule
   from `goals.set_active_player_goal()`.

### 10.5 Quick-check via store.xml_extract

```python
from store import xml_extract

# Read classification without full parse
cls = xml_extract(output_payload, "/output/@classification")
assert cls in ("price_me", "vendor", "keep", "chaos_recipe", "unknown", None)

# Read cycle status
status = xml_extract(cycle_payload, "/cycle/@status")
assert status in ("ACTIVE", "CLOSED", "ABANDONED", None)

# Read goal progress
progress_str = xml_extract(goal_payload, "/goal/@progress")
progress = float(progress_str) if progress_str else 0.0
assert 0.0 <= progress <= 1.0
```

`xml_extract` is the preferred projection path — it avoids full document parses for
hot-path queries.
