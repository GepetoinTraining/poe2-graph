# Electron ↔ MCP server protocol

JSON messages over localhost WebSocket on `POE2_MCP_WS_PORT` (the Electron
overlay reads the same env var or hard-codes the agreed port).

The server is the source of truth for view state; Electron renders + reports
player actions back. Stateless on the wire — both sides reconcile from the
last `view.render` / `state.snapshot` message they saw.

## Server → client

```jsonc
{
  "event": "view.render",
  "payload": {
    "view": "item_tooltip",     // one of: item_tooltip | build_planner | crafting_planner
                                //          | farming_scenario | goal_tracker | next_action_card
                                //          | map_timer | dump_tab_screenshot
    "id": "vw_8f2c",            // stable id so subsequent updates / dismiss target it
    "audience": "1pct",         // "1pct" (terse) | "30pct" (educational)
    "data": { /* view-specific schema */ }
  }
}
```

```jsonc
{
  "event": "view.update",
  "payload": { "id": "vw_8f2c", "patch": { /* partial of `data` */ } }
}
```

```jsonc
{
  "event": "view.dismiss",
  "payload": { "id": "vw_8f2c" }
}
```

```jsonc
{
  "event": "state.snapshot",
  "payload": { /* full session state — sent on connect + on demand */ }
}
```

## Client → server

```jsonc
{
  "event": "input.event",
  "payload": {
    "view": "build_planner",     // which view produced this event
    "id": "vw_8f2c",
    "kind": "node_clicked",      // view-defined; build_planner emits node_clicked etc.
    "data": { /* event-specific */ }
  }
}
```

```jsonc
{
  "event": "client.hello",
  "payload": { "client": "electron-overlay", "version": "0.1.0" }
}
```

## View `data` schemas (placeholder — align with Path-of-Tools libs)

### `item_tooltip`
Output of `tools_items.parse_clipboard_item`. Will be aligned with
`poe-item-display` / `poe-item-hover-react` prop types when Pedro imports them.

```jsonc
{
  "base": { "name": "Diamond Wand", "category": "Wands", "item_class": "CasterWeapon" },
  "rarity": "rare",
  "name": "Spirit Whisper",
  "item_level": 84,
  "implicits": [ /* Modifier */ ],
  "prefixes":  [ /* Modifier */ ],
  "suffixes":  [ /* Modifier */ ],
  "sockets": [],
  "corrupted": false
}
```

### `goal_tracker`
Output of `tools_goals.render_goal_tracker` — text form right now; will gain a
structured form once the Electron component is in place.

```jsonc
{ "text": "...", "structured": null }
```

### `next_action_card`
Output of `tools_goals.recommend_next_action`.

```jsonc
{
  "rationale": "...",
  "next_subgoal": { /* SubGoal */ },
  "relevant_system_guides": [ /* SystemGuide ids + summary */ ],
  "confidence_gaps": [ ["market_timing", 0.3], ... ]
}
```

### `map_timer`
```jsonc
{ "started_at": "2026-05-27T18:22:00Z", "target_seconds": 240, "elapsed_seconds": 87 }
```

## Lifecycle

- Bridge only starts if `POE2_MCP_WS_PORT` is set in the server's env.
- Without the bridge, `tools_views.display_*` tools return `{"delivered": 0, "bridge": "disabled"}` so the calling Claude can degrade gracefully ("overlay not connected").
- Clients should send `client.hello` on connect. Server replies with `state.snapshot`.
- Disconnect is non-fatal; the server keeps view state in memory so reconnection resyncs via `state.snapshot`.
