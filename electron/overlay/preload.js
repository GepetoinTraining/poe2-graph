// Bridge between the Electron main process (which owns the WS connection +
// hotkey) and the sandboxed renderer (which owns the DOM). Exposes a small
// surface — no `require` in the renderer, no node access.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('overlay', {
  // ---- inbound (main → renderer) ----
  onWsStatus: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on('ws-status', listener);
    return () => ipcRenderer.removeListener('ws-status', listener);
  },

  onWsMessage: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on('ws-message', listener);
    return () => ipcRenderer.removeListener('ws-message', listener);
  },

  // ---- outbound (renderer → main → server) ----
  send: (message) => ipcRenderer.invoke('ws-send', message),

  hide: () => ipcRenderer.invoke('overlay-hide'),
});
