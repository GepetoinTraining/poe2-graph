"""Messenger — live two-way bridge between the skill and a passive-tree viewer.

NOT YET IMPLEMENTED. Blocked on a permissive license from
natwarth/poe2-skilltree (currently license-less, see issue
https://github.com/natwarth/poe2-skilltree/issues/2). Until then, the skill
hands off via plain URL: `Allocation.to_url()` → player pastes into the public
hosted viewer.

When the fork lands, this module hosts the localhost WebSocket server that
turns the viewer into a live planning surface — player clicks a node, skill
sees it; skill proposes a route, viewer highlights it.

## Architecture (target)

    [Claude Code skill (Python)]  ←──ws://127.0.0.1:7777──→  [forked viewer (browser)]
            │                                                     │
       Allocation API                                          tree rendering
       EXILE.xml updates                                       node click capture
       build emit                                              overlay drawing
            │                                                     │
            └─────────────── localhost only, no cloud ────────────┘

Both ends fall back to standalone mode when the other isn't running:
  - Viewer alone: works as a public visualizer (URL paste-in only)
  - Skill alone: emits URLs the way it does today

## Protocol (JSON over WS, one message per frame)

Either side can originate any of these:

  → allocate       {node_hash: int, weapon_set?: int, skill_override?: int}
  → deallocate     {node_hash: int}
  → highlight      {nodes: [int], color: str}        # skill paints overlay
  → camera         {focus: int, zoom: float}          # skill steers the view
  → propose_route  {from: int, to: int, path: [int]} # skill suggests
  → ask            {prompt: str, options?: [str]}    # skill surfaces a question
  ← clicked        {node_hash: int, modifiers?: dict}  # viewer reports action
  ← typed          {text: str}                        # chat input from viewer
  ← form_submit    {payload: dict}                    # onboarding form returns

Each message also carries an `id: str` (uuid) and `ts: float` (epoch seconds).

## Default port

7777. Configurable via env var POE2_GRAPH_WS_PORT.

## Implementation notes (for when we unblock)

  - websockets library (asyncio) or a stdlib-only http.server upgrade — TBD
  - The viewer URL signals presence via a query param: ?ws=127.0.0.1:7777
  - The skill keeps a single connection at a time (single-player tool)
  - Messages mutate the active Allocation (allocation.py) which auto-snapshots
    via exile.snapshot() on a debounce
  - When the viewer disconnects, the skill keeps running — next session
    reconnects cleanly

## Why we stub this now instead of building it

The design needs to live somewhere durable while the license is pending.
Putting it as a docstring on a real module means:
  - Future Claude sessions see the intent
  - The protocol survives chat-context decay
  - When the unblock arrives, the implementer reads this file first
"""

from __future__ import annotations

WS_DEFAULT_PORT = 7777


def is_available() -> bool:
    """Return True when the messenger is implemented and connectable.

    Currently always False. Wire this once the implementation lands.
    """
    return False
