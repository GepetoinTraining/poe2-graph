// Wizard preload — exposes the installer-action IPC surface to the renderer.
// Mirrors the contextBridge pattern from overlay/preload.js but with a
// wholly separate surface (poe2Wizard, not overlay).

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('poe2Wizard', {
  getDefaults:        ()                    => ipcRenderer.invoke('wizard:get-defaults'),
  detectPrereqs:      ()                    => ipcRenderer.invoke('wizard:detect-prereqs'),
  cloneRepo:          (args)                => ipcRenderer.invoke('wizard:clone-repo', args),
  installPythonDeps:  (args)                => ipcRenderer.invoke('wizard:install-python-deps', args),
  installNodeDeps:    (args)                => ipcRenderer.invoke('wizard:install-node-deps', args),
  packMcpb:           (args)                => ipcRenderer.invoke('wizard:pack-mcpb', args),
  createShortcut:     (args)                => ipcRenderer.invoke('wizard:create-shortcut', args),
  complete:           (args)                => ipcRenderer.invoke('wizard:complete', args),
  openExternal:       (url)                 => ipcRenderer.invoke('wizard:open-external', { url }),
  openPath:           (filepath)            => ipcRenderer.invoke('wizard:open-path', { filepath }),
  resetInstall:       ()                    => ipcRenderer.invoke('wizard:reset-install'),
});
