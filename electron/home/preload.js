// Home preload — exposes a minimal, typed surface to the renderer.
//
// Two channel categories:
//   home:*   — main → renderer state pushes (status snapshots, log lines, events)
//   action:* — renderer → main commands (show/hide overlay, restart server, etc.)
//
// nodeIntegration is off + contextIsolation is on; nothing on `window` beyond
// what's listed here.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('poe2Home', {
  // ----- Inbound: subscribe to main-pushed events -----

  // Main-side state (overlay visibility, hotkey, server PID, repo info, etc.).
  onMainState: (handler) =>
    ipcRenderer.on('home:main-state', (_e, payload) => handler(payload)),

  // Raw WS events from the MCP server (server.state, ws.state, view.lifecycle,
  // views.active, log.entry, state.snapshot). Renderer filters by msg.event.
  onWsEvent: (handler) =>
    ipcRenderer.on('home:ws-event', (_e, payload) => handler(payload)),

  // ----- Outbound: actions -----

  showOverlay:        () => ipcRenderer.invoke('home:show-overlay'),
  hideOverlay:        () => ipcRenderer.invoke('home:hide-overlay'),
  restartOverlay:     () => ipcRenderer.invoke('home:restart-overlay'),
  restartServer:      () => ipcRenderer.invoke('home:restart-server'),
  resetInstall:       () => ipcRenderer.invoke('home:reset-install'),
  openInstallFolder:  () => ipcRenderer.invoke('home:open-install-folder'),
  runOnboarding:      () => ipcRenderer.invoke('home:run-onboarding'),
  dismissView:        (viewId) => ipcRenderer.invoke('home:dismiss-view', viewId),
  quit:               () => ipcRenderer.invoke('home:quit'),

  // One-shot pull of current state — used on renderer init before the first push.
  pullSnapshot:       () => ipcRenderer.invoke('home:pull-snapshot'),
});
