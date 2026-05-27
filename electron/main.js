// Electron main process — routes between two modes based on install state.
//
//   - WIZARD mode: no `installed.json` at app.getPath('userData')/poe2-graph.
//     Loads electron/wizard/index.html, exposes installer IPC (prereq detect,
//     clone, deps, pack, shortcut, complete).
//
//   - OVERLAY mode: install marker present. Loads electron/overlay/index.html,
//     spawns the Python MCP server as a child process, opens the WebSocket
//     bridge to it.
//
// Force-flags for dev/testing:
//   --force-wizard      load wizard regardless of install marker
//   --force-overlay     load overlay regardless of install marker

const { app, BrowserWindow, globalShortcut, ipcMain, screen, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

const WebSocket = require('ws');

// ============================================================================
// install state
// ============================================================================

const INSTALL_DIR = path.join(app.getPath('userData'), 'poe2-graph');
const INSTALL_MARKER = path.join(INSTALL_DIR, 'installed.json');

function readInstallMarker() {
  try {
    const raw = fs.readFileSync(INSTALL_MARKER, 'utf8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeInstallMarker(data) {
  fs.mkdirSync(INSTALL_DIR, { recursive: true });
  fs.writeFileSync(INSTALL_MARKER, JSON.stringify(data, null, 2), 'utf8');
}

function clearInstallMarker() {
  try { fs.unlinkSync(INSTALL_MARKER); } catch { /* ignore */ }
}

function shouldRunWizard() {
  if (process.argv.includes('--force-wizard')) return true;
  if (process.argv.includes('--force-overlay')) return false;
  return readInstallMarker() === null;
}

// ============================================================================
// shared window state
// ============================================================================

let mainWindow = null;
let mode = null;            // 'wizard' | 'overlay'

// ============================================================================
// WIZARD mode
// ============================================================================

function createWizardWindow() {
  mode = 'wizard';
  mainWindow = new BrowserWindow({
    width: 720,
    height: 560,
    resizable: false,
    minimizable: true,
    maximizable: false,
    fullscreenable: false,
    title: 'poe2-graph — setup',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'wizard', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  mainWindow.loadFile(path.join('wizard', 'index.html'));
  mainWindow.on('closed', () => { mainWindow = null; });
}

// Wizard IPC — registered once at app-ready regardless of mode, so the
// wizard can call these via window.poe2Wizard.*.

ipcMain.handle('wizard:get-defaults', () => {
  return {
    home: os.homedir(),
    defaultInstallDir: path.join(os.homedir(), 'poe2-graph'),
    platform: process.platform,
    installMarkerPath: INSTALL_MARKER,
  };
});

ipcMain.handle('wizard:detect-prereqs', async () => {
  const detect = require('./wizard/actions/detect_prereqs.js');
  return detect();
});

ipcMain.handle('wizard:clone-repo', async (_event, { repoUrl, targetDir }) => {
  const cloneRepo = require('./wizard/actions/clone_repo.js');
  return cloneRepo({ repoUrl, targetDir });
});

ipcMain.handle('wizard:install-python-deps', async (_event, { repoDir }) => {
  const fn = require('./wizard/actions/install_python_deps.js');
  return fn({ repoDir });
});

ipcMain.handle('wizard:install-node-deps', async (_event, { repoDir }) => {
  const fn = require('./wizard/actions/install_node_deps.js');
  return fn({ repoDir });
});

ipcMain.handle('wizard:pack-mcpb', async (_event, { repoDir }) => {
  const fn = require('./wizard/actions/pack_mcpb.js');
  return fn({ repoDir });
});

ipcMain.handle('wizard:create-shortcut', async (_event, { targetCommand, label }) => {
  const fn = require('./wizard/actions/create_shortcut.js');
  return fn({ targetCommand, label });
});

ipcMain.handle('wizard:complete', async (_event, { repoDir, wsPort }) => {
  const marker = {
    installed_at: new Date().toISOString(),
    repo_dir: repoDir,
    ws_port: wsPort || null,
    schema_version: 1,
  };
  writeInstallMarker(marker);
  return { ok: true, marker, markerPath: INSTALL_MARKER };
});

ipcMain.handle('wizard:open-external', async (_event, { url }) => {
  await shell.openExternal(url);
  return { ok: true };
});

ipcMain.handle('wizard:open-path', async (_event, { filepath }) => {
  await shell.openPath(filepath);
  return { ok: true };
});

ipcMain.handle('wizard:reset-install', async () => {
  clearInstallMarker();
  return { ok: true };
});

// ============================================================================
// OVERLAY mode
// ============================================================================

const HOTKEY_TOGGLE = 'Control+Alt+Space';
const RECONNECT_DELAY_MS = 2000;
const CLIENT_NAME = 'electron-overlay';
const CLIENT_VERSION = '0.1.0';

let serverChild = null;
let ws = null;
let reconnectTimer = null;
let isShuttingDown = false;
let wsPort = null;

function spawnMcpServer(marker) {
  if (!marker || !marker.repo_dir) return;
  const port = marker.ws_port || 8889;
  wsPort = port;
  // The bundled .mcpb's bootstrap.py already does this. For the Electron-spawned
  // case we replicate it: launch `python -m mcp_server.server` from the
  // configured repo root, with POE2_MCP_WS_PORT set so the bridge binds.
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    POE2_MCP_WS_PORT: String(port),
    POE2_GRAPH_ROOT: marker.repo_dir,
  };
  console.log(`[server] spawning python -m mcp_server.server (cwd=${marker.repo_dir}, ws=${port})`);
  serverChild = spawn('python', ['-m', 'mcp_server.server'], {
    cwd: marker.repo_dir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  serverChild.stdout.on('data', (buf) => process.stdout.write(`[server] ${buf}`));
  serverChild.stderr.on('data', (buf) => process.stderr.write(`[server] ${buf}`));
  serverChild.on('exit', (code, signal) => {
    console.log(`[server] exited code=${code} signal=${signal}`);
    serverChild = null;
  });
}

function createOverlayWindow() {
  mode = 'overlay';
  const { workArea } = screen.getPrimaryDisplay();
  const width = 420;
  const height = 640;
  const x = workArea.x + workArea.width - width - 24;
  const y = workArea.y + 24;

  mainWindow = new BrowserWindow({
    x, y, width, height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'overlay', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.loadFile(path.join('overlay', 'index.html'));
  mainWindow.on('closed', () => { mainWindow = null; });
}

function toggleOverlay() {
  if (!mainWindow) {
    createOverlayWindow();
    mainWindow.once('ready-to-show', () => mainWindow.show());
    return;
  }
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

function sendToRenderer(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function connectWebSocket() {
  if (isShuttingDown || mode !== 'overlay') return;
  const url = `ws://localhost:${wsPort}`;
  console.log(`[ws] connecting to ${url}`);
  sendToRenderer('ws-status', { status: 'connecting', url });
  try {
    ws = new WebSocket(url);
  } catch (err) {
    console.error('[ws] construct failed', err);
    scheduleReconnect();
    return;
  }
  ws.on('open', () => {
    sendToRenderer('ws-status', { status: 'open', url });
    safeSend({ event: 'client.hello', payload: { client: CLIENT_NAME, version: CLIENT_VERSION } });
  });
  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return; }
    sendToRenderer('ws-message', msg);
  });
  ws.on('close', () => {
    sendToRenderer('ws-status', { status: 'closed', url });
    scheduleReconnect();
  });
  ws.on('error', (err) => console.warn('[ws] error', err.message));
}

function safeSend(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
    return true;
  }
  return false;
}

function scheduleReconnect() {
  if (isShuttingDown || reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, RECONNECT_DELAY_MS);
}

// Overlay IPC
ipcMain.handle('ws-send', (_event, message) => safeSend(message));
ipcMain.handle('overlay-hide', () => {
  if (mainWindow && mainWindow.isVisible()) mainWindow.hide();
  return true;
});

// ============================================================================
// app lifecycle
// ============================================================================

app.whenReady().then(() => {
  if (shouldRunWizard()) {
    createWizardWindow();
    return;
  }
  const marker = readInstallMarker();
  spawnMcpServer(marker);
  createOverlayWindow();

  const registered = globalShortcut.register(HOTKEY_TOGGLE, toggleOverlay);
  if (!registered) console.warn(`[hotkey] ${HOTKEY_TOGGLE} unavailable`);
  else console.log(`[hotkey] ${HOTKEY_TOGGLE} → toggle overlay`);

  // Give the server a beat to bind the WS port before we connect.
  setTimeout(connectWebSocket, 1500);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (shouldRunWizard()) createWizardWindow();
      else createOverlayWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (mode === 'wizard') {
    // After wizard completes the user is expected to relaunch from the icon;
    // exiting the process here is correct.
    app.quit();
  }
  // Overlay mode: keep alive so the hotkey + WS stay live with the window hidden.
});

app.on('will-quit', () => {
  isShuttingDown = true;
  globalShortcut.unregisterAll();
  if (ws) { try { ws.close(); } catch (_) {} }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  if (serverChild) {
    try { serverChild.kill(); } catch (_) {}
    serverChild = null;
  }
});
