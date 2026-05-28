# BUGS — bug-hunter swarm findings (2026-05-27)

Six parallel bug hunters audited the new surfaces introduced by commits
`a9e48b0` (mcp_server + module refactor) and `d4ab5d3` (electron + mcpb).
Each hunter read its scope in full and reported real runtime bugs — not
style nits.

## Triage summary

| Package | Critical | High | Medium | Low | Total |
|---|---:|---:|---:|---:|---:|
| `electron/` | 1 | 4 | 5 | 1 | 11 |
| `catalog/` | 1 | 4 | 5 | 3 | 13 |
| `items/` | 0 | 3 | 4 | 5 | 12 |
| `mcp_server/` | 0 | 2 | 3 | 2 | 7 |
| `mcpb/` | 0 | 0 | 2 | 3 | 5 |
| refactor integrity | 0 | 0 | 0 | 3 | 3 |
| **Total** | **2** | **13** | **19** | **17** | **51** |

## Fix-first list (criticals + the highs that block real users)

These are the bugs that prevent the new surfaces from working at all, or
that silently corrupt parsed data:

1. **[CRITICAL] `electron/overlay/index.html:39`** — `<script src="renderer.js">`
   is missing `type="module"`, but `renderer.js` uses ES `import` statements.
   The overlay's renderer never executes; no WS status, no view rendering,
   no dismiss handlers. The Wizard's `index.html:33` does this correctly —
   just mirror it.
2. **[CRITICAL] `catalog/gem_loader.py:30-33`** — the gem-row regex requires
   a lookahead to a closing `</tbody>`/`</table>`/next row. The LAST gem row
   in the page is skipped if formatting drifts. Add `|\Z` to the lookahead.
3. **[HIGH] `electron/wizard/actions/clone_repo.js:27-30`** —
   `exec(\`git clone ... "${repoUrl}" "${targetDir}"\`)` is shell-evaluated
   with user-controlled strings. **Command injection** via the install
   location page's repo URL field. Switch to `execFile('git', [...])` — no
   shell. Same pattern repeats in `install_python_deps.js`, `install_node_deps.js`,
   `pack_mcpb.js`.
4. **[HIGH] `electron/main.js:343-346`** — `serverChild.kill()` doesn't
   reach descendants on Windows; orphaned `python.exe` keeps the WS port,
   so the next launch can't bind. Use `tree-kill` / `taskkill /T /F` on
   Windows; spawn with `detached: true` + `process.kill(-pid)` on POSIX.
5. **[HIGH] `electron/wizard/pages/done.js:30-40`** — install-marker write is
   fire-and-forget; if the user clicks Finish before the IPC roundtrip
   resolves, the marker isn't written and the next launch re-runs the
   Wizard. Await `complete()` in an `onNext` hook and gate the Finish button.
6. **[HIGH] `items/modifier.py:80, 91` + `items/parser.py:158-189`** — modifier
   value/template parsing doesn't handle en-dash range syntax (`+(110—129)`,
   `(15-20)%`). `extract_values` returns both bounds as a 2-element list;
   `Item.aggregate_stats` then sums min+max. Strip `(min-max)` ranges before
   extracting, or detect and average.
7. **[HIGH] `items/parser.py:262`** — when `Item Level:` is absent,
   `item_level_idx` stays `-1`, so `sections[item_level_idx + 1:]` becomes
   `sections[0:]` — the header section is scanned for mods. Add an explicit
   `if item_level_idx == -1: return [], []` guard.
8. **[HIGH] `catalog/gem.py:101-106, 153-167`** — gem lookups are
   case-sensitive. `is_known_gem("herald of ash")` returns False even when
   the gem exists. Compare on `.casefold()`.
9. **[HIGH] `catalog/hydrate.py:36-43`** — silently drops mods that don't
   match the catalog (data loss with no signal). Also writes to `mod.family`
   without verifying `Modifier` is mutable; will raise `FrozenInstanceError`
   if the dataclass is ever frozen. Return an unhydrated count; fail loudly.
10. **[HIGH] `catalog/poe2db_loader.py:138-140`** — tier extraction from
    trailing digits of the mod name collides: `AddedFireDamageFlat1H` →
    tier 1, identical to real T1 mods. Read poe2db's explicit tier field;
    fall back to a `tier_unknown` sentinel.
11. **[HIGH] `catalog/poe2db_loader.py:23`** — value-range regex loses the
    sign on `-(min—max)` patterns. `\(?` matches `(`, then `-?` consumes
    the sign inside the group — bounds end up positive. Capture the sign
    outside the paren.
12. **[HIGH] `mcp_server/transport_ws.py:111`** — when the WS broker thread
    crashes (port in use, etc.), `_loop.close()` runs in `finally` but the
    module globals remain `_started=True`, `_loop=<closed>`. Every later
    `display_*` call burns a 2s timeout. Reset both globals in `finally`.
13. **[HIGH] `mcp_server/tools_session.py:34` → `infra.updater.report()`** —
    `welcome()` runs the staleness report synchronously, which fires 4+
    blocking HTTPS calls each with ~15s timeout. First MCP session can hang
    60+s with flaky network. Cache the report (~1h TTL) or run with a hard
    deadline + last-known-good fallback.
14. **[HIGH] `electron/wizard/actions/create_shortcut.js:42-56`** — PowerShell
    quote-escaping is incomplete; `target`/`cwd`/`label` containing `"`
    (rare Windows usernames like `O"Brien` reach this code path via
    `app.getPath('desktop')`) breaks the outer command. Write the PS script
    to a temp file and invoke `powershell -File`, or pass values via
    `-args`.

---

## electron/ — 11 findings

### critical

**`electron/overlay/index.html:39`** — `<script src="renderer.js">` lacks
`type="module"` but `renderer.js` uses ES `import` statements. **Overlay
never runs** — renderer parses with a SyntaxError, no WS status, no view
rendering, no dismiss buttons. Wizard's index.html:33 has it right; mirror.

### high

**`electron/wizard/actions/clone_repo.js:27-30`** —
`exec(\`git clone --recurse-submodules "${repoUrl}" "${targetDir}"\`)` in a
shell with user-controlled strings. `repoUrl` from the install_location
page is unvalidated; `https://x.git" & calc.exe & "` executes arbitrary
commands on Windows. Fix: `execFile('git', ['clone','--recurse-submodules',
repoUrl, targetDir], …)` — no shell.

**`electron/main.js:343-346`** — `serverChild.kill()` sends SIGTERM only to
`python` itself; Windows TerminateProcess doesn't cascade, POSIX SIGTERM
doesn't reach children. Orphaned `python.exe` holds the WS port; next
launch fails to bind. Fix: `tree-kill` / `taskkill /pid <pid> /T /F` on
Windows, `process.kill(-pid)` after `detached: true` spawn on POSIX.

**`electron/wizard/pages/done.js:30-40`** — fire-and-forget IIFE writes the
install marker; Finish button (`wizard/renderer.js:115-118`) calls
`window.close()` on click. User races the IPC roundtrip → marker not
written → next launch re-runs Wizard. Fix: `onNext: async () => { await
complete(...); return true }`, gate Finish on completion.

**`electron/wizard/actions/create_shortcut.js:42-56`** — PowerShell escaping
only handles `'`; `"` in `target`/`cwd`/`label` (rare usernames,
non-standard install dirs) breaks the outer command. Fix: write PS to a
temp file and invoke `powershell -File`, or pass via `-args`.

### medium

**`electron/main.js:83, 226`** — `loadFile(path.join('wizard', 'index.html'))`
uses a relative path, resolved against `process.cwd()`. Desktop shortcut
sets `WorkingDirectory` on Windows but Start Menu / scheduled-task launches
have unpredictable cwd. Fix: `path.join(__dirname, ...)`.

**`electron/main.js:191-194`** — server child's `exit` handler logs and
nulls the reference; no respawn. Overlay shows "connecting…" forever after
any Python crash. Fix: respawn with capped retries; surface a "server died"
status to the renderer.

**`electron/main.js:250-276`** — new WebSocket created without
`removeAllListeners()` on the previous instance. Rapid disconnect→connect
bursts stack listeners; an old `close` handler can fire after a new
connection is open, triggering a second `scheduleReconnect()` and opening
a third ws. Fix: at the top of `connectWebSocket()`: `if (ws) {
ws.removeAllListeners(); try { ws.terminate(); } catch(_){} ws = null; }`.

**`electron/overlay/renderer.js:113-120`** — `makeViewCard` interpolates
server-supplied `view` and `id` into `innerHTML` without escaping. A
`view.render` with `id: '<img src=x onerror=alert(1)>'` injects HTML. The
sibling view modules already use `escapeHtml`; do the same here.

**`electron/overlay/views/map_timer.js:42-50`** — MutationObserver is
attached to `container.parentElement`, which IS the node removed by
`onViewDismiss`. The observer never fires on a still-connected ancestor →
`setInterval` and the observer leak per dismissed timer. Fix: observe
`viewsContainer` with `subtree: true`, or expose a per-view `cleanup()`
hook returned from `render()`.

**`electron/wizard/actions/install_python_deps.js:18-21`,
`install_node_deps.js:15-19`, `pack_mcpb.js:16-19`** — same exec +
interpolated path pattern. `repoDir` (user-chosen install location) flows
in unsanitized. Switch all three to `execFile` with arg arrays.

### low

**`electron/main.js:286-292`** — fixed 2s reconnect with no backoff or
jitter. If the server never binds (crash loop, port conflict), the client
hammers indefinitely. Fix: exponential backoff capped ~30s; reset on
successful `open`.

---

## catalog/ — 13 findings

### critical

**`catalog/gem_loader.py:30-33`** — `_GEM_ROW_RE` requires a lookahead to
`<tr data-filters=`, `</tbody>`, or `</table>`. The LAST gem row in a
`<tbody>` is dropped if poe2db ever omits the closing tag, or if EOF
arrives without a sentinel. Add `|\Z` to the lookahead alternation.

### high

**`catalog/gem.py:101-106, 153-167`** — `by_name` and `is_known_gem` are
case-sensitive; clipboard/parsed names won't always match poe2db's casing
(`"herald of ash"` vs `"Herald of Ash"`). Compare on `.casefold()`.

**`catalog/hydrate.py:36-43`** — silently drops un-hydrated mods (data loss
with no signal). Also writes `mod.family = ...` without checking
mutability; will raise `FrozenInstanceError` if `Modifier` is ever made
frozen (consistent with `ModTier`/`BaseType`). Return an `unhydrated`
count; either return a new Modifier or assert mutability upfront.

**`catalog/poe2db_loader.py:138-140`** — tier inferred from trailing digits
of `Name` collides for names ending in non-digit segments
(`AddedFireDamageFlat1H` → tier 1, masking real T1). Use poe2db's explicit
tier field; carry a sentinel for unknowns.

**`catalog/poe2db_loader.py:23`** — value-range regex
`\(?(-?\d+...)\s*[—–-]\s*(-?\d+...)\)?` loses the sign on `-(5—10)%`
patterns: `\(?` matches `(`, then `-?` consumes the inner sign, dropping
the outer negation. Capture the leading `-` outside the paren and apply to
both bounds.

### medium

**`catalog/poe2db_loader.py:159-160`** — `gen_type == 1` is strict; if any
preprocessor returns `1.0` (float), the check fails and the mod is
silently classified as prefix. Coerce: `int(gen_type)` with try/except.

**`catalog/poe2db_loader.py:118-132`** — single-value template fallback
matches any `\d+(?:\.\d+)?`, turning `25% increased Damage with Bows` and
`25% chance to gain 1 charge` into colliding templates. Require unit
context (`%`, `to`) or restrict to specific mod families.

**`catalog/gem_loader.py:36-39`** — `_GEM_LINK_RE` matches `class="gem_red"`
strictly; if poe2db ships multiple classes (`class="gem_red icon"`) the
regex fails. Loosen to `class="[^"]*\b(gem_red|gem_green|gem_blue)\b[^"]*"`.

**`catalog/gem_loader.py:114-115`** — `filters.endswith(name)` strips
substrings without a word boundary; a hypothetical gem literally named
"Herald" could lose a legitimate tag suffix. Require ` ` before name.

**`catalog/poe2db_loader.py:82-85`** — `_strip_html` doesn't `html.unescape`;
custom entities (`&minus;`, numeric refs in attrs) leak through, so
templates carry `&amp;` while clipboard text has `&`. Call
`html.unescape(text)` after stripping.

**`catalog/mod_pool.py:35`** — `possible_mods` doesn't filter out
implicits / corruption-only / unique affix classes; "what can roll on this
rare at ilvl 82" includes mods that can never roll on rares. Default-exclude
`implicit_base`, `implicit_corrupted`, `corruption`, `unique` unless asked.

### low

**`catalog/gem.py:123, 132`; `catalog/mod_pool.py:64, 72`** — module-level
mutable caches without locking; concurrent first-call from two threads
double-fetches and last-write-wins. Wrap with `threading.Lock` or use
`functools.lru_cache`.

**`catalog/poe2db_loader.py:142`** — `int(entry.get("Level") or 1)` — if
`Level` is `0`, falls back to 1 silently. Use
`int(entry["Level"]) if entry.get("Level") is not None else 1`.

---

## items/ — 12 findings

### high

**`items/modifier.py:80, 91` + `items/parser.py:158-189`** — en-dash range
syntax (`+(110—129)`, `(15-20)%`) is not handled. `extract_values` returns
`[110.0, 129.0]` (both bounds); `to_template` produces `"+(#—#) to maximum
Life"`. Downstream `Item.aggregate_stats` (item.py:139) sums min+max. Strip
ranges before extraction, or pick a single rolled value.

**`items/parser.py:262`** — when `Item Level:` is missing, `item_level_idx
== -1`, so `sections[item_level_idx + 1:]` becomes `sections[0:]` — the
header section is scanned for mods. A "+1 Bow" unique name line gets
misclassified as a mod. Add `if item_level_idx == -1: return [], []`.

**`items/parser.py:136`** — defensive double-search on `_ITEM_LEVEL_RE`;
`int(...).group(1)` assumes the second `.search()` matched. Walrus once:
`m = _ITEM_LEVEL_RE.search(full_text); item_level = int(m.group(1)) if m
else 1`.

### medium

**`items/parser.py:71, 143`** — `_REQ_ATTR_RE` is run against `full_text`
not just the requirements section; a future mod template `"Str: 5"` would
match. Locate `Requirements:` explicitly and parse inside it.

**`items/parser.py:147`** — `_CORRUPTED_RE` / `_MIRRORED_RE` run against
`full_text`; a standalone `Corrupted` line in any section flips the flag.
Search only in the footer.

**`items/parser.py:165`** — every explicit mod is dumped into `prefixes`.
Rares with 4+ explicits silently overflow; `is_full` / `open_prefix_slots`
report `max(0, 3-N) = 0`, hiding data corruption. Either validate counts
in `__post_init__` or leave mods in a single `unclassified` list until
hydration.

**`items/parser.py:235-239`** — socket-count fallback counts every alpha
char. `Sockets: Body Rune of Iron` → 5 sockets. Parse PoE 2's actual
space-separated format first.

### low

**`items/parser.py:67`** — `_RARITY_RE = r"^Rarity:\s*(\w+)$"` fails on
Windows CRLF (`Rare\r`). Normalize line endings at entry, or add `\s*`
before each `$`.

**`items/parser.py:194`** — BOM (`﻿`) at start of clipboard text
isn't stripped; `_ITEM_CLASS_RE` fails and `parse_clipboard` raises.
`text = text.lstrip("﻿")` at top.

**`items/item.py:71`** — quality cap at 30 rejects valid catalysed
jewellery (Quality: +50% exists). Raise the ceiling or warn-don't-reject.

**`items/socket.py:34, 41`** — `Rune` and `SoulCore` subclass with `pass`;
dataclass `__eq__` checks `type(self) is type(other)` so equality is
correct, but hashing is identical for same-field-Rune and same-field-SoulCore.
Edge case for dicts keyed by `SocketContent`. Override `__hash__`.

**`items/inventory.py:78`** — `__iter__` returns `dict.items()` while
`__contains__` checks key membership. `for x in inv:` yields tuples but
`x in inv` checks strings. Surprising; document or split into `.entries()`.

---

## mcp_server/ — 7 findings

### high

**`mcp_server/transport_ws.py:111`** — when the broker thread crashes
(port already in use, etc.), `finally: _loop.close()` runs but
`_started=True` and `_loop=<closed>` remain set. Every later
`display_*` call hits `asyncio.run_coroutine_threadsafe` on a closed loop
and burns a 2s timeout. Reset both globals in `finally`.

**`mcp_server/tools_session.py:34`** — `welcome()` calls
`infra.updater.report()` which fires 4+ blocking HTTPS calls (each
10-15s timeout). First session-start can hang 60+s on flaky network. Cache
the report (~1h TTL) or run with a hard global deadline + last-known-good
fallback.

### medium

**`mcp_server/transport_ws.py:75-89`** — `start_if_enabled()` sets
`_started=True` synchronously; `_run_event_loop` populates `_loop` later.
Calls in that window get `bridge: "disabled"` despite the bridge starting.
Gate `emit_event`'s live check on a `threading.Event` set when the loop
is ready.

**`mcp_server/tools_views.py:111-138` vs `mcp_server/protocol.md:108-111`** —
`start_map_timer` emits `data.started_at_epoch` (float epoch) +
`elapsed_seconds`; `protocol.md` documents `started_at` (ISO 8601). Spec
clients see `undefined` and never render. Either rename + ISO-format the
payload, or update `protocol.md`.

**`mcp_server/tools_views.py:153`** — `overlay_status` reads
`transport_ws._clients` directly (private, lock-free). CPython `len()` on
a `set` is safe today; a future implementation change would break it.
Expose a `transport_ws.client_count()` snapshot.

### low

**`mcp_server/tools_views.py:39-42`** — `_normalize_audience` annotated
`-> str` but type-narrowing only covers in-tuple values; an `Optional[str]`
that's a valid string passes through. Add an explicit `None` guard for
type safety.

**`mcp_server/transport_ws.py:139`** — `await websockets.serve(...)` return
value is discarded; no clean shutdown path. Store on a module global so a
`stop()` can `server.close(); await server.wait_closed()`.

---

## mcpb/ — 5 findings

### medium

**`mcpb/manifest.json:16`** — `"command": "python"` fails on stock
macOS 12.3+ (no `python` symlink) and most modern Linux distros (PEP 394
ships only `python3`). On Windows it can hit the MS Store stub. Ship
`"python3"`, or detect per-platform.

**`mcpb/bootstrap.py:26`** — silent fallback to `POE2_GRAPH_HOME` is
undocumented in `manifest.json`, README, or the error message. A user who
sets `HOME` (e.g. holdover from another tool) gets the server pointed at
the wrong directory with no signal. Drop the fallback or document it.

### low

**`mcpb/bootstrap.py:36`** — `POE2_GRAPH_ROOT` isn't `.strip()`-ed before
`Path(...)`. Trailing whitespace from a UI paste yields
`Path("D:\\poe2-graph ")` which fails `is_dir()` with a confusing error.

**`mcpb/pack.py:67`** — `zf.write` records source-file mtime; bundles
built minutes apart produce different bytes. Hash-based update detection
sees every rebuild as new. Use `ZipInfo` with a fixed `date_time`.

**`mcpb/pack.py:56`** — `sorted(here.rglob("*"))` orders Path objects, so
in-archive order depends on the host OS's path separator. Sort by
`.relative_to(here).as_posix()` for cross-OS reproducibility.

---

## Refactor integrity — 3 findings (all docstring/comment-level)

The refactor (commit `a9e48b0`) that moved files into `graph/`, `infra/`,
`integrations/`, plus the new `catalog/`, `items/`, `mcp_server/`
packages is otherwise clean. No broken Python imports, all tests use the
new paths, the new `__init__.py` files match how callers actually import.

### low

**`infra/config.py:11`** — module docstring example shows
`from config import load`; should be `from infra.config import load`.

**`config.yaml:29`** — comment recommends `python updater.py update-tools`;
should be `python -m infra.updater update-tools`.

**`config.yaml:148`** — comment recommends `python worker.py`; should be
`python -m infra.worker`.

DOCS/*.md still contain stale import paths (`build-construction.md`,
`graph-queries.md`, `updater.md`, `poe2db.md`). Those were excluded from
the integrity audit but should be swept when those chapters are next
touched.
