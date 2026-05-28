---
id: electron
file: DOCS/electron.md
topic: Electron app — Wizard first-run installer + always-on-top Overlay (Ctrl+Alt+Space)
priority: reference
modules: [electron]
tags: [electron, overlay, wizard, installer, ipc, websocket, global_shortcut, in_game, poe2, transparent_window]
when_to_read: |
  User asks about the in-game overlay, the first-run wizard, the desktop
  shortcut, Ctrl+Alt+Space, the Windows portable .exe build, or any
  Electron-side bug ("overlay didn't open", "wizard hangs on step 4",
  "server didn't spawn"). Also when extending overlay views or wiring a
  new wizard step.
---

# electron — Wizard + Overlay (one app, two modes)

## Two modes in one binary

The Electron app is a thin host. On every launch, `main.js` decides between
two modes based on whether an install marker exists at
`<userData>/poe2-graph/installed.json`:

- **Wizard** — first-run installer. Detects prereqs, clones the repo, installs
  Python + Node deps, packs the `.mcpb` bundle, drops a desktop shortcut,
  writes the install marker. After completion, the next launch goes straight
  to Overlay.
- **Overlay** — always-on-top transparent window. Spawns the Python MCP server
  as a child, connects to its localhost WebSocket bridge, renders view
  payloads pushed from `display_*` tools, and binds `Ctrl+Alt+Space` as a
  global toggle.

Both modes are in the same binary because the Wizard's output (a working
checkout + the `.mcpb` bundle + a desktop shortcut) is exactly what the
Overlay needs to start. Single download → working setup → in-game UI.

## Layout

```
electron/
├── package.json        electron + ws + electron-builder + build targets
├── main.js             mode router + WS client + IPC for wizard actions
├── overlay/            steady-state window
│   ├── index.html
│   ├── renderer.js     view router — dispatches to views/*
│   ├── preload.js      contextBridge → window.overlay.*
│   ├── styles.css
│   └── views/
│       ├── item_tooltip.js       (placeholder for poe-item-display swap)
│       ├── goal_tracker.js
│       ├── next_action_card.js
│       └── map_timer.js
└── wizard/             first-run installer
    ├── index.html
    ├── renderer.js     step machine + page navigation
    ├── preload.js      contextBridge → window.poe2Wizard.*
    ├── styles.css
    ├── pages/          one file per step — pure render(container, ctx, api)
    │   ├── welcome.js
    │   ├── prereq_check.js
    │   ├── install_location.js
    │   ├── clone_repo.js
    │   ├── install_deps.js
    │   ├── pack_mcpb.js
    │   ├── create_shortcut.js
    │   └── done.js
    └── actions/        node-side handlers invoked via IPC
        ├── detect_prereqs.js
        ├── clone_repo.js
        ├── install_python_deps.js
        ├── install_node_deps.js
        ├── pack_mcpb.js
        └── create_shortcut.js
```

## Mode router (main.js)

```
app.whenReady ─────► shouldRunWizard()  ───── yes ──► createWizardWindow()
                          │
                          ╰─── no ──► readInstallMarker()
                                       ├──► spawnMcpServer(marker)
                                       ├──► createOverlayWindow()
                                       ├──► register Ctrl+Alt+Space
                                       └──► connectWebSocket(after 1.5s)
```

`shouldRunWizard()` returns:

- `true` if `installed.json` is missing
- `true` if `--force-wizard` is on the command line
- `false` if `--force-overlay` is on the command line (overrides marker check)

Re-running the wizard: `--force-wizard` flag or delete `installed.json`.

## Wizard flow

| Step | Action |
|---|---|
| 1. Welcome | static page |
| 2. Prereqs | `detect_prereqs.js` shells `python --version`, `git --version`, `node --version`; falls back to `py -3` on Windows to dodge the MS Store stub |
| 3. Install location | text inputs for install dir + repo URL |
| 4. Clone repo | `git clone --recurse-submodules` (idempotent — accepts an existing checkout) |
| 5. Install deps | `pip install -r requirements.txt` + `npm install` |
| 6. Pack .mcpb | runs `mcpb/pack.py`; offers "Open in Claude" button |
| 7. Desktop shortcut | platform-specific (`.lnk` / `.command` / `.desktop`) |
| 8. Done | writes install marker; next launch goes to Overlay |

Each step is a pure render function `(container, ctx, api) => void`. The step
machine in `wizard/renderer.js` walks them sequentially; pages can yield
`{ canNext: bool }` to gate the Next button, and `actions/*.js` handle the
Node-side IPC work.

## Overlay flow

Once installed, every launch:

1. Reads `installed.json` for `repo_dir` and `ws_port`.
2. Spawns `python -m mcp_server.server` with `POE2_GRAPH_ROOT` +
   `POE2_MCP_WS_PORT` in env. Child's stdout/stderr is piped to this
   process's console for debugging.
3. Creates the overlay `BrowserWindow` — transparent, frameless, always-on-top,
   `screen-saver` level so it floats over PoE 2 windowed-fullscreen.
4. Registers `Ctrl+Alt+Space` as a global toggle (show/hide).
5. Connects to `ws://localhost:<ws_port>` after a 1.5 s startup delay.
   Reconnects every 2 s on disconnect.

Incoming `view.render` / `view.update` / `view.dismiss` messages flow into
`overlay/renderer.js`, which dispatches by `payload.view` to the matching
module in `overlay/views/`.

## IPC surface

The Wizard renderer can only reach Node code through `contextBridge` channels
declared in the corresponding preload script. The full surface:

`wizard/preload.js` exposes `window.poe2Wizard.*`:

- `detectPrereqs()` — runs all three version checks
- `cloneRepo({ repoUrl, targetDir })`
- `installPythonDeps({ repoDir })`
- `installNodeDeps({ repoDir })`
- `packMcpb({ repoDir })`
- `createShortcut({ repoDir, label })`
- `completeWizard({ repoDir, wsPort })` — writes `installed.json`
- `pickDirectory(default?)` — native dialog wrapper

`overlay/preload.js` exposes `window.overlay.*`:

- `onViewRender(handler)` / `onViewUpdate(handler)` / `onViewDismiss(handler)`
- `onWsState(handler)` — connection status updates
- `dismiss(id)` — user-driven close button (round-trips to server)

`nodeIntegration` is off; `contextIsolation` is on. The renderer cannot
`require` Node or `child_process` directly.

## Build targets

```bash
npm start                # dev — mode picked from install state
npm run start:wizard     # force wizard
npm run start:overlay    # force overlay
npm run dist             # all platforms
npm run dist:win         # Windows portable .exe
npm run dist:mac         # macOS .dmg
npm run dist:linux       # Linux .AppImage
```

`npm run dist` writes to `electron/dist/`. The Windows portable target is the
recommended distribution: a single `.exe` that, when first run on a fresh
machine, launches the Wizard. After setup completes, the same `.exe` opens
in Overlay mode on every subsequent launch.

## Known limits

- **Exclusive fullscreen** hides the overlay (Windows behavior, not
  Electron-specific). Run PoE 2 in **windowed fullscreen** for the overlay
  to draw on top.
- **Click-through** isn't enabled yet. The overlay accepts clicks when
  visible; a later phase will toggle
  `setIgnoreMouseEvents(true, { forward: true })` for hover-only mode.
- **MS Store `python` stub** on Windows can hijack the `python` command.
  The prereq detector falls back to `py -3`; if that also fails the step
  surfaces an actionable error.
- **Each Claude surface spawns its own MCP server.** Claude Code, the
  `.mcpb` bundle in Claude desktop, and this Electron app all launch their
  own Python process. They share state via `EXILE/` on disk, not in memory.

## Cross-references

- `DOCS/mcp-server.md` — server side of the WS bridge + tool registration
- `DOCS/mcpb.md` — the `.mcpb` bundle the Wizard packs in step 6
- `mcp_server/protocol.md` — wire format for `view.render` / `view.dismiss` / `state.snapshot`
- `electron/README.md` — same content, kept alongside the app for repo browsers
