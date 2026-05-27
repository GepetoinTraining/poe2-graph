# poe2-graph — Electron app

Two modes in one app:

- **Wizard** — first-run installer that detects prereqs, clones the repo,
  installs deps, packs the `.mcpb` bundle for Claude desktop, and drops a
  desktop shortcut. Loaded automatically when no install marker is present.
- **Overlay** — always-on-top transparent window that connects to the
  Python MCP server over a localhost WebSocket bridge, renders view
  payloads from `display_*` tool calls, and binds `Ctrl+Alt+Space` as a
  global toggle. Loaded automatically once setup is complete.

The router lives at the top of [main.js](main.js); it reads/writes an
install marker at `<userData>/poe2-graph/installed.json` (cross-platform
`app.getPath('userData')`).

## Layout

```
electron/
├── package.json        electron, ws, electron-builder + build config
├── main.js             mode router + WS client (overlay) + IPC for wizard actions
├── overlay/            steady-state window
│   ├── index.html
│   ├── renderer.js     view router (view.render → views/*)
│   ├── preload.js      contextBridge → window.overlay.*
│   ├── styles.css
│   └── views/
│       ├── item_tooltip.js       (swap target for poe-item-display)
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

## Mode router (in main.js)

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

## Scripts

```bash
# Dev — picks mode from install state
npm start

# Force wizard (useful for re-running the install flow)
npm run start:wizard

# Force overlay (useful for re-testing overlay without re-installing)
npm run start:overlay

# Build a distributable
npm run dist          # all targets
npm run dist:win      # Windows portable .exe
npm run dist:mac      # macOS .dmg
npm run dist:linux    # Linux .AppImage
```

`npm run dist` writes to `electron/dist/`. The Windows portable target
produces a single `.exe` that, when first run on a fresh machine, launches
the wizard. After the user completes setup, that same `.exe` opens in
overlay mode.

## Wizard flow

| Step | Action | Status |
|---|---|---|
| 1. Welcome | static page | ✓ |
| 2. Prereqs | detect_prereqs.js shells `python --version`, `git --version`, `node --version` | ✓ (working) |
| 3. Install location | text inputs for install dir + repo URL | ✓ |
| 4. Clone repo | `git clone --recurse-submodules` (idempotent — accepts existing checkout) | ✓ |
| 5. Install deps | `pip install -r requirements.txt` + `npm install` | ✓ |
| 6. Pack .mcpb | runs `mcpb/pack.py`, offers "Open in Claude" button | ✓ |
| 7. Desktop shortcut | platform-specific (.lnk / .command / .desktop) | ✓ |
| 8. Done | writes install marker; next launch goes straight to overlay | ✓ |

## Overlay flow

Once installed, every launch:

1. Reads `installed.json` for `repo_dir` and `ws_port`.
2. Spawns `python -m mcp_server.server` as a child with `POE2_GRAPH_ROOT`
   and `POE2_MCP_WS_PORT` in its env. Server's stdout/stderr is piped
   into this process's console.
3. Creates the overlay BrowserWindow (transparent, always-on-top,
   screen-saver level so it floats over PoE 2 windowed-fullscreen).
4. Registers `Ctrl+Alt+Space` as a global toggle.
5. Connects to `ws://localhost:<port>` after a 1.5 s startup delay.
   Reconnects every 2 s on disconnect.

`view.render` / `view.update` / `view.dismiss` messages flow into
[overlay/renderer.js](overlay/renderer.js), which dispatches to the
matching module in [overlay/views/](overlay/views/).

## Known limits

- **Exclusive fullscreen**: PoE 2 in true exclusive fullscreen hides the
  overlay (Windows behavior, not Electron-specific). Run PoE 2 in
  *windowed fullscreen* for the overlay to draw on top.
- **Click-through** isn't enabled yet. The overlay accepts clicks when
  visible. A later phase will toggle `setIgnoreMouseEvents(true, { forward: true })`.
- **Wizard's prereq check assumes** `python`/`git`/`node` are on `PATH`.
  On Windows the Microsoft Store stub for `python` can hijack the name;
  the detector falls back to `py -3` to work around it.
- **Multiple servers**: each Claude surface (Code via .mcp.json, desktop
  via .mcpb, Electron-spawned here) launches its own Python MCP server.
  They share state by reading `EXILE/` from disk, not in memory.
- **Re-running the wizard**: launch with `--force-wizard` or delete
  `<userData>/poe2-graph/installed.json`.
