// Electron main process — three windows + tray + single-instance.
//
// Window topology:
//   Wizard   (first-run installer; only when no install marker, opaque chrome)
//   Home     (always-visible control room; in taskbar; close-to-tray)
//   Overlay  (transparent in-game HUD; summoned via hotkey or home button)
//
// Lifecycle:
//   app.whenReady
//     ├─ single-instance lock                                  (exits if 2nd instance)
//     ├─ shouldRunWizard? ──yes──► createWizardWindow
//     └─ no
//           ├─ cleanupOrphans()                                (kill stale python on our ports)
//           ├─ spawnMcpServer(marker)                          (port-probed, dev-aware)
//           ├─ createHomeWindow()                              (auto-shown)
//           ├─ createOverlayWindow()                           (hidden by default)
//           ├─ createTray()
//           ├─ registerHotkeys()                               (with fallback chains)
//           └─ connectWebSocket()
//
// Force-flags for dev/testing:
//   --force-wizard      load wizard regardless of install marker
//   --force-overlay     load home + overlay regardless of install marker; also
//                       auto-shows the overlay window on launch

const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage,
        screen, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const net = require('net');
const { spawn } = require('child_process');

const WebSocket = require('ws');
const treeKill = require('tree-kill');

// ============================================================================
// Single-instance lock
// ============================================================================

// If another instance is already running, give the OS our argv so the first
// instance can focus its home window, then exit immediately. This MUST happen
// before any window creation or server spawning.
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[main] another instance is already running — exiting');
  app.quit();
  process.exit(0);
}

// ============================================================================
// install state
// ============================================================================

const INSTALL_DIR = path.join(app.getPath('userData'), 'poe2-graph');
const INSTALL_MARKER = path.join(INSTALL_DIR, 'installed.json');
// PID of the most recently spawned MCP server. Used by cleanupOrphans on
// next launch to kill ONLY our own orphan — sibling processes (Claude
// desktop's .mcpb bundle, IDE-launched servers, anything else on the same
// port range) are explicitly left alone.
const SERVER_PID_FILE    = path.join(INSTALL_DIR, 'server.pid');
const CLIPBOARD_PID_FILE = path.join(INSTALL_DIR, 'clipboard.pid');

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

function writeServerPidFile(pid) {
  try {
    fs.mkdirSync(INSTALL_DIR, { recursive: true });
    fs.writeFileSync(SERVER_PID_FILE, String(pid), 'utf8');
  } catch (err) {
    console.warn('[cleanup] writeServerPidFile failed:', err.message);
  }
}

function readServerPidFile() {
  try {
    const raw = fs.readFileSync(SERVER_PID_FILE, 'utf8').trim();
    const pid = parseInt(raw, 10);
    return Number.isInteger(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

function clearServerPidFile() {
  try { fs.unlinkSync(SERVER_PID_FILE); } catch { /* ignore */ }
}

function writeClipboardPidFile(pid) {
  try {
    fs.mkdirSync(INSTALL_DIR, { recursive: true });
    fs.writeFileSync(CLIPBOARD_PID_FILE, String(pid), 'utf8');
  } catch (err) {
    console.warn('[clipboard] writeClipboardPidFile failed:', err.message);
  }
}

function readClipboardPidFile() {
  try {
    const raw = fs.readFileSync(CLIPBOARD_PID_FILE, 'utf8').trim();
    const pid = parseInt(raw, 10);
    return Number.isInteger(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

function clearClipboardPidFile() {
  try { fs.unlinkSync(CLIPBOARD_PID_FILE); } catch { /* ignore */ }
}

// ----------------------------------------------------------------------------
// Repo-root resolution
//
// Priority: POE2_GRAPH_ROOT env var → dev-checkout detection → install marker.
// See spawnMcpServer for usage.
// ----------------------------------------------------------------------------

function detectDevRepoRoot() {
  const candidate = path.resolve(__dirname, '..');
  try {
    if (fs.existsSync(path.join(candidate, 'mcp_server', 'server.py'))) {
      return candidate;
    }
  } catch { /* ignore */ }
  return null;
}

function resolveRepoRoot(marker) {
  const envRoot = (process.env.POE2_GRAPH_ROOT || '').trim();
  if (envRoot) return { repoDir: envRoot, source: 'env' };
  const dev = detectDevRepoRoot();
  if (dev) return { repoDir: dev, source: 'dev' };
  if (marker && marker.repo_dir) return { repoDir: marker.repo_dir, source: 'marker' };
  return { repoDir: null, source: null };
}

function shouldRunWizard() {
  if (process.argv.includes('--force-wizard')) return true;
  if (process.argv.includes('--force-overlay')) return false;
  if (detectDevRepoRoot()) return false;
  return readInstallMarker() === null;
}

function readVersion() {
  // Best-effort: walk up from the resolved repo root looking for VERSION.
  // Falls back to the package.json version if VERSION isn't found (packaged
  // installs may not ship the file).
  try {
    const dev = detectDevRepoRoot();
    if (dev) {
      const v = fs.readFileSync(path.join(dev, 'VERSION'), 'utf8').trim();
      if (v) return v;
    }
  } catch { /* ignore */ }
  try {
    return require('./package.json').version;
  } catch {
    return 'unknown';
  }
}

// ============================================================================
// Windows + tray globals
// ============================================================================

let wizardWindow = null;
let homeWindow = null;
let overlayWindow = null;
let tray = null;
let mode = null;            // 'wizard' | 'overlay'  (overlay = home + overlay coexist)
let isQuitting = false;     // set true on user-driven quit so close-to-tray no-ops

// ============================================================================
// Shared main-side state (mirrored to the home renderer)
// ============================================================================

const HOTKEY_OVERLAY_CANDIDATES = [
  'Control+Alt+Space',
  'Control+Alt+P',
  'Control+Shift+Space',
  'Alt+Shift+G',
];
const HOTKEY_HOME_CANDIDATES = [
  'Control+Alt+H',
  'Control+Shift+H',
  'Alt+Shift+H',
];

const RECONNECT_DELAY_MIN_MS = 1000;
const RECONNECT_DELAY_MAX_MS = 30000;
const MAX_SERVER_RESPAWN = 5;
const CLIENT_NAME = 'electron-overlay';
const CLIENT_VERSION = '0.1.0';

const MAX_CLIPBOARD_RESPAWN = 5;

const mainState = {
  version: readVersion(),
  server: {
    pid: null,
    state: 'starting',          // 'starting' | 'ready' | 'dying' | 'dead' | 'gave_up'
    respawn_attempts: 0,
    max_respawn: MAX_SERVER_RESPAWN,
    last_exit_code: null,
    last_exit_signal: null,
  },
  ws: {
    state: 'connecting',        // 'connecting' | 'open' | 'closed'
    port: null,
    client_count: 0,
  },
  overlay: {
    visible: false,
    hotkey: { binding: null, registered: false },
  },
  home: {
    hotkey: { binding: null, registered: false },
  },
  repo: {
    root: null,
    source: null,
    install_marker: INSTALL_MARKER,
  },
  clipboard: {
    pid: null,
    state: 'starting',          // 'starting' | 'ready' | 'dying' | 'dead' | 'gave_up'
    respawn_attempts: 0,
    max_respawn: MAX_CLIPBOARD_RESPAWN,
    last_exit_code: null,
    last_exit_signal: null,
  },
};

function patchMainState(patch) {
  // Shallow-merge per top-level key. Renderer takes the whole state on each push.
  for (const k of Object.keys(patch)) {
    mainState[k] = { ...(mainState[k] || {}), ...patch[k] };
  }
  pushMainState();
  rebuildTrayMenu();
}

function pushMainState() {
  sendToHome('home:main-state', mainState);
}

// ============================================================================
// Server child + WebSocket state
// ============================================================================

let serverChild = null;
let serverRespawnAttempts = 0;
let clipboardChild = null;
let clipboardRespawnAttempts = 0;
let ws = null;
let reconnectAttempt = 0;
let reconnectTimer = null;
let isShuttingDown = false;
let wsPort = null;

// ============================================================================
// Orphan cleanup — PID-file based, never touches sibling MCP servers
//
// On clean shutdown we tree-kill the server child and clear the PID file.
// On a crash/force-quit, the file survives with a stale PID — next launch
// reads it, verifies the PID is still alive AND still a python process,
// then kills it. Sibling python processes (Claude desktop's .mcpb bundle,
// IDE-launched servers) are NEVER touched: we don't know their PIDs, so
// the cleanup is structurally incapable of going after them.
// ============================================================================

function getProcessImage(pid) {
  return new Promise((resolve) => {
    if (process.platform !== 'win32') {
      const proc = spawn('ps', ['-p', String(pid), '-o', 'comm='], {
        stdio: ['ignore', 'pipe', 'ignore'],
      });
      let out = '';
      proc.stdout.on('data', (d) => { out += d.toString(); });
      proc.on('exit', () => resolve(out.trim() || null));
      proc.on('error', () => resolve(null));
      return;
    }
    const proc = spawn('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'], {
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    let out = '';
    proc.stdout.on('data', (d) => { out += d.toString(); });
    proc.on('exit', () => {
      const m = out.match(/^"([^"]+)"/);
      resolve(m ? m[1] : null);
    });
    proc.on('error', () => resolve(null));
  });
}

async function cleanupOrphanPid(pid, label, clearFn) {
  if (!pid) return null;
  const image = await getProcessImage(pid);
  if (!image) {
    clearFn();
    return null;
  }
  if (!/^python(w)?(\.exe)?$/i.test(image)) {
    console.warn(`[cleanup] previous ${label} pid ${pid} is now ${image}; stale, skipping`);
    clearFn();
    return null;
  }
  console.log(`[cleanup] killing previous Electron-spawned ${label} pid=${pid}`);
  await new Promise((resolve) => {
    try {
      treeKill(pid, 'SIGTERM', (err) => {
        if (err) console.warn(`[cleanup] tree-kill(${pid}) failed:`, err.message);
        resolve();
      });
    } catch (err) {
      console.warn(`[cleanup] tree-kill(${pid}) threw:`, err && err.message);
      resolve();
    }
  });
  clearFn();
  return { pid, image };
}

async function cleanupOrphans() {
  const results = await Promise.all([
    cleanupOrphanPid(readServerPidFile(),    'server',    clearServerPidFile),
    cleanupOrphanPid(readClipboardPidFile(), 'clipboard', clearClipboardPidFile),
  ]);
  return results.filter(Boolean);
}

// ============================================================================
// WIZARD mode
// ============================================================================

function createWizardWindow() {
  mode = 'wizard';
  wizardWindow = new BrowserWindow({
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
  wizardWindow.loadFile(path.join(__dirname, 'wizard', 'index.html'));
  wizardWindow.on('closed', () => { wizardWindow = null; });
}

// Wizard IPC — registered once at module load so the wizard can call these
// regardless of which mode the app started in.
ipcMain.handle('wizard:get-defaults', () => ({
  home: os.homedir(),
  defaultInstallDir: path.join(os.homedir(), 'poe2-graph'),
  platform: process.platform,
  installMarkerPath: INSTALL_MARKER,
}));

ipcMain.handle('wizard:detect-prereqs', async () => {
  const detect = require('./wizard/actions/detect_prereqs.js');
  return detect();
});

ipcMain.handle('wizard:clone-repo', async (_e, { repoUrl, targetDir }) => {
  const cloneRepo = require('./wizard/actions/clone_repo.js');
  return cloneRepo({ repoUrl, targetDir });
});

ipcMain.handle('wizard:install-python-deps', async (_e, { repoDir }) => {
  return require('./wizard/actions/install_python_deps.js')({ repoDir });
});

ipcMain.handle('wizard:install-node-deps', async (_e, { repoDir }) => {
  return require('./wizard/actions/install_node_deps.js')({ repoDir });
});

ipcMain.handle('wizard:pack-mcpb', async (_e, { repoDir }) => {
  return require('./wizard/actions/pack_mcpb.js')({ repoDir });
});

ipcMain.handle('wizard:create-shortcut', async (_e, { targetCommand, label }) => {
  return require('./wizard/actions/create_shortcut.js')({ targetCommand, label });
});

ipcMain.handle('wizard:complete', async (_e, { repoDir, wsPort }) => {
  const marker = {
    installed_at: new Date().toISOString(),
    repo_dir: repoDir,
    ws_port: wsPort || null,
    schema_version: 1,
  };
  writeInstallMarker(marker);
  return { ok: true, marker, markerPath: INSTALL_MARKER };
});

ipcMain.handle('wizard:open-external', async (_e, { url }) => {
  await shell.openExternal(url);
  return { ok: true };
});

ipcMain.handle('wizard:open-path', async (_e, { filepath }) => {
  await shell.openPath(filepath);
  return { ok: true };
});

ipcMain.handle('wizard:reset-install', async () => {
  clearInstallMarker();
  return { ok: true };
});

// ============================================================================
// MCP server — port probe + spawn + respawn
// ============================================================================

function isPortFree(port) {
  return new Promise((resolve) => {
    const probe = net.createServer();
    probe.once('error', () => resolve(false));
    probe.once('listening', () => probe.close(() => resolve(true)));
    probe.listen(port, '127.0.0.1');
  });
}

async function findFreePort(start, maxAttempts = 10) {
  for (let i = 0; i < maxAttempts; i++) {
    if (await isPortFree(start + i)) return start + i;
  }
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const ephemeral = probe.address().port;
      probe.close(() => resolve(ephemeral));
    });
  });
}

async function spawnMcpServer(marker) {
  const { repoDir, source } = resolveRepoRoot(marker);
  if (!repoDir) {
    console.warn('[server] no repo root resolved — set POE2_GRAPH_ROOT or run from a source checkout');
    patchMainState({ server: { state: 'dead', pid: null } });
    return;
  }
  patchMainState({
    repo: { root: repoDir, source },
    server: { state: 'starting' },
  });

  const desiredPort = Number(
    process.env.POE2_MCP_WS_PORT
    || (marker && marker.ws_port)
    || 8889
  );
  const port = await findFreePort(desiredPort);
  if (port !== desiredPort) {
    console.log(`[server] port ${desiredPort} in use; falling back to ${port}`);
  }
  wsPort = port;
  patchMainState({ ws: { port } });

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    POE2_MCP_WS_PORT: String(port),
    POE2_GRAPH_ROOT: repoDir,
    POE2_MCP_WS_ONLY: '1',
  };
  console.log(`[server] spawning python -m mcp_server.server (source=${source}, cwd=${repoDir}, ws=${port})`);
  serverChild = spawn('python', ['-m', 'mcp_server.server'], {
    cwd: repoDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  // Stash our PID so the next launch's cleanupOrphans can target only us,
  // never sibling processes (Claude desktop bundle, etc.).
  writeServerPidFile(serverChild.pid);
  patchMainState({ server: { pid: serverChild.pid, state: 'starting' } });

  serverChild.stdout.on('data', (buf) => process.stdout.write(`[server] ${buf}`));
  serverChild.stderr.on('data', (buf) => process.stderr.write(`[server] ${buf}`));
  serverChild.on('exit', (code, signal) => {
    console.log(`[server] exited code=${code} signal=${signal}`);
    serverChild = null;
    clearServerPidFile();
    patchMainState({
      server: { state: 'dying', pid: null, last_exit_code: code, last_exit_signal: signal },
    });
    sendToOverlay('server-status', { status: 'died', code, signal });

    if (isShuttingDown || mode !== 'overlay') return;
    if (serverRespawnAttempts >= MAX_SERVER_RESPAWN) {
      console.warn(`[server] giving up after ${serverRespawnAttempts} respawn attempts`);
      patchMainState({ server: { state: 'gave_up' } });
      sendToOverlay('server-status', { status: 'gave_up', attempts: serverRespawnAttempts });
      return;
    }
    serverRespawnAttempts += 1;
    patchMainState({ server: { respawn_attempts: serverRespawnAttempts } });
    const delay = 2000 * serverRespawnAttempts;
    console.log(`[server] respawning in ${delay}ms (attempt ${serverRespawnAttempts}/${MAX_SERVER_RESPAWN})`);
    setTimeout(() => {
      if (isShuttingDown || mode !== 'overlay') return;
      spawnMcpServer(readInstallMarker());
    }, delay);
  });
}

function restartServer() {
  if (serverChild) {
    const pid = serverChild.pid;
    try { treeKill(pid, 'SIGTERM'); } catch { /* ignore */ }
    // exit handler will respawn (subject to the cap)
  } else {
    serverRespawnAttempts = 0;
    spawnMcpServer(readInstallMarker());
  }
}

// ============================================================================
// Clipboard listener — watches system clipboard, writes events to .queue/
// ============================================================================

function spawnClipboardListener(repoDir) {
  if (process.argv.includes('--no-clipboard')) {
    console.log('[clipboard] skipping spawn (--no-clipboard flag set)');
    patchMainState({ clipboard: { state: 'dead', pid: null } });
    return;
  }
  if (!repoDir) {
    console.warn('[clipboard] no repo root resolved — cannot spawn clipboard listener');
    patchMainState({ clipboard: { state: 'dead', pid: null } });
    return;
  }

  patchMainState({ clipboard: { state: 'starting' } });

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    POE2_GRAPH_ROOT: repoDir,
  };
  console.log(`[clipboard] spawning python -m integrations.clipboard_listener (cwd=${repoDir})`);
  clipboardChild = spawn('python', ['-m', 'integrations.clipboard_listener'], {
    cwd: repoDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  writeClipboardPidFile(clipboardChild.pid);
  patchMainState({ clipboard: { pid: clipboardChild.pid, state: 'starting' } });

  clipboardChild.stdout.on('data', (buf) => process.stdout.write(`[clipboard] ${buf}`));
  clipboardChild.stderr.on('data', (buf) => process.stderr.write(`[clipboard] ${buf}`));
  clipboardChild.on('exit', (code, signal) => {
    console.log(`[clipboard] exited code=${code} signal=${signal}`);
    clipboardChild = null;
    clearClipboardPidFile();
    patchMainState({
      clipboard: { state: 'dying', pid: null, last_exit_code: code, last_exit_signal: signal },
    });

    if (isShuttingDown || mode !== 'overlay') return;
    if (clipboardRespawnAttempts >= MAX_CLIPBOARD_RESPAWN) {
      console.warn(`[clipboard] giving up after ${clipboardRespawnAttempts} respawn attempts`);
      patchMainState({ clipboard: { state: 'gave_up' } });
      return;
    }
    clipboardRespawnAttempts += 1;
    patchMainState({ clipboard: { respawn_attempts: clipboardRespawnAttempts } });
    const delay = 2000 * clipboardRespawnAttempts;
    console.log(`[clipboard] respawning in ${delay}ms (attempt ${clipboardRespawnAttempts}/${MAX_CLIPBOARD_RESPAWN})`);
    setTimeout(() => {
      if (isShuttingDown || mode !== 'overlay') return;
      const m = readInstallMarker();
      const { repoDir: rd } = resolveRepoRoot(m);
      spawnClipboardListener(rd || repoDir);
    }, delay);
  });
}

function restartClipboardListener() {
  if (clipboardChild) {
    const pid = clipboardChild.pid;
    try { treeKill(pid, 'SIGTERM'); } catch { /* ignore */ }
    // exit handler will respawn (subject to the cap)
  } else {
    clipboardRespawnAttempts = 0;
    const m = readInstallMarker();
    const { repoDir } = resolveRepoRoot(m);
    spawnClipboardListener(repoDir);
  }
}

// ============================================================================
// HOME window — always-visible control room
// ============================================================================

function createHomeWindow() {
  homeWindow = new BrowserWindow({
    width: 760,
    height: 820,
    minWidth: 640,
    minHeight: 560,
    title: 'poe2-graph',
    autoHideMenuBar: true,
    backgroundColor: '#0e1016',
    webPreferences: {
      preload: path.join(__dirname, 'home', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  homeWindow.loadFile(path.join(__dirname, 'home', 'index.html'));

  homeWindow.on('close', (e) => {
    if (!isQuitting) {
      // Close-to-tray: hide instead of destroy. Tray menu has Quit.
      e.preventDefault();
      homeWindow.hide();
      rebuildTrayMenu();
    }
  });
  homeWindow.on('closed', () => { homeWindow = null; });
  homeWindow.on('show', rebuildTrayMenu);
  homeWindow.on('hide', rebuildTrayMenu);

  // Push the initial state once the renderer is ready.
  homeWindow.webContents.once('did-finish-load', () => pushMainState());
}

function showHome() {
  if (!homeWindow) {
    createHomeWindow();
    return;
  }
  homeWindow.show();
  homeWindow.focus();
}

function toggleHome() {
  if (!homeWindow || homeWindow.isDestroyed()) {
    createHomeWindow();
    return;
  }
  if (homeWindow.isVisible()) homeWindow.hide();
  else { homeWindow.show(); homeWindow.focus(); }
}

// ============================================================================
// OVERLAY window — transparent in-game HUD
// ============================================================================

function createOverlayWindow() {
  mode = 'overlay';
  const { workArea } = screen.getPrimaryDisplay();
  const width = 420;
  const height = 640;
  const x = workArea.x + workArea.width - width - 24;
  const y = workArea.y + 24;

  overlayWindow = new BrowserWindow({
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

  overlayWindow.setAlwaysOnTop(true, 'screen-saver');
  overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlayWindow.loadFile(path.join(__dirname, 'overlay', 'index.html'));

  overlayWindow.on('show', () => {
    patchMainState({ overlay: { visible: true } });
  });
  overlayWindow.on('hide', () => {
    patchMainState({ overlay: { visible: false } });
  });
  overlayWindow.on('closed', () => {
    overlayWindow = null;
    patchMainState({ overlay: { visible: false } });
  });

  // Auto-show only when --force-overlay was passed explicitly. The new
  // primary surface is the home window — the overlay is summoned on demand.
  if (process.argv.includes('--force-overlay')) {
    overlayWindow.once('ready-to-show', () => {
      overlayWindow.show();
      console.log('[overlay] auto-shown (--force-overlay)');
    });
  }
}

function showOverlay() {
  if (!overlayWindow || overlayWindow.isDestroyed()) {
    createOverlayWindow();
    overlayWindow.once('ready-to-show', () => { overlayWindow.show(); overlayWindow.focus(); });
    return;
  }
  overlayWindow.show();
  overlayWindow.focus();
}

function hideOverlay() {
  if (overlayWindow && overlayWindow.isVisible()) overlayWindow.hide();
}

function toggleOverlay() {
  if (!overlayWindow || overlayWindow.isDestroyed()) {
    showOverlay();
    return;
  }
  if (overlayWindow.isVisible()) overlayWindow.hide();
  else { overlayWindow.show(); overlayWindow.focus(); }
}

function restartOverlay() {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.destroy();
    overlayWindow = null;
  }
  createOverlayWindow();
}

// ============================================================================
// IPC helpers — push to windows
// ============================================================================

function sendToOverlay(channel, payload) {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.webContents.send(channel, payload);
  }
}

function sendToHome(channel, payload) {
  if (homeWindow && !homeWindow.isDestroyed()) {
    homeWindow.webContents.send(channel, payload);
  }
}

// ============================================================================
// WebSocket client (main → server)
// ============================================================================

function connectWebSocket() {
  if (isShuttingDown || mode !== 'overlay') return;
  if (ws) {
    try { ws.removeAllListeners(); } catch (_) {}
    try { ws.terminate(); } catch (_) {}
    ws = null;
  }
  const url = `ws://localhost:${wsPort}`;
  console.log(`[ws] connecting to ${url}`);
  patchMainState({ ws: { state: 'connecting' } });
  sendToOverlay('ws-status', { status: 'connecting', url });

  try {
    ws = new WebSocket(url);
  } catch (err) {
    console.error('[ws] construct failed', err);
    scheduleReconnect();
    return;
  }
  ws.on('open', () => {
    reconnectAttempt = 0;
    serverRespawnAttempts = 0;
    patchMainState({
      ws: { state: 'open' },
      server: { state: 'ready', respawn_attempts: 0 },
    });
    sendToOverlay('ws-status', { status: 'open', url });
    safeSend({ event: 'client.hello', payload: { client: CLIENT_NAME, version: CLIENT_VERSION } });
  });
  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return; }
    // Forward to both windows; each filters by msg.event.
    sendToOverlay('ws-message', msg);
    sendToHome('home:ws-event', msg);
    // Mirror a few high-signal events onto main-side state so the tray
    // menu + home state can react without each window doing its own bookkeeping.
    if (msg.event === 'server.state') {
      patchMainState({ server: { state: msg.payload.state, pid: msg.payload.pid || mainState.server.pid } });
    } else if (msg.event === 'ws.state') {
      // server-reported bridge state (separate from main's WS-client state).
      // We don't overwrite mainState.ws.state here — that field tracks the
      // main→server connection.
    } else if (msg.event === 'views.active') {
      // Tray dot for overlay activity could use this; for now, no-op.
    }
  });
  ws.on('close', () => {
    patchMainState({ ws: { state: 'closed' } });
    sendToOverlay('ws-status', { status: 'closed', url });
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
  const base = Math.min(
    RECONNECT_DELAY_MAX_MS,
    RECONNECT_DELAY_MIN_MS * Math.pow(2, reconnectAttempt)
  );
  const jitter = Math.random() * 0.3 * base;
  const delay = Math.floor(base + jitter);
  reconnectAttempt += 1;
  console.log(`[ws] reconnect in ${delay}ms (attempt ${reconnectAttempt})`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

// ============================================================================
// Hotkeys — register with a fallback chain, surface what won
// ============================================================================

function registerHotkeyWithFallback(candidates, handler) {
  for (const combo of candidates) {
    let registered = false;
    try { registered = globalShortcut.register(combo, handler); }
    catch { /* invalid accelerator; try next */ }
    if (registered) return { binding: combo, registered: true };
  }
  // None registered — return the first candidate as the "intended" binding so
  // the home can display "Ctrl+Alt+Space (conflict)" instead of "—".
  return { binding: candidates[0], registered: false };
}

function registerHotkeys() {
  const overlay = registerHotkeyWithFallback(HOTKEY_OVERLAY_CANDIDATES, toggleOverlay);
  const home = registerHotkeyWithFallback(HOTKEY_HOME_CANDIDATES, toggleHome);
  if (overlay.registered) console.log(`[hotkey] overlay toggle = ${overlay.binding}`);
  else console.warn(`[hotkey] no overlay hotkey could be registered (tried ${HOTKEY_OVERLAY_CANDIDATES.join(', ')})`);
  if (home.registered) console.log(`[hotkey] home toggle = ${home.binding}`);
  else console.warn(`[hotkey] no home hotkey could be registered (tried ${HOTKEY_HOME_CANDIDATES.join(', ')})`);
  patchMainState({
    overlay: { hotkey: overlay },
    home: { hotkey: home },
  });
}

// ============================================================================
// System tray
// ============================================================================

function trayIconImage() {
  const p = path.join(__dirname, 'shared', 'assets', 'tray.png');
  try {
    const img = nativeImage.createFromPath(p);
    if (img.isEmpty()) {
      console.warn(`[tray] icon at ${p} loaded empty; using fallback`);
      return nativeImage.createEmpty();
    }
    return img;
  } catch (err) {
    console.warn(`[tray] failed to load icon at ${p}:`, err.message);
    return nativeImage.createEmpty();
  }
}

function createTray() {
  if (tray) return;
  tray = new Tray(trayIconImage());
  tray.setToolTip('poe2-graph');
  // Single-click toggles home window visibility (Windows convention).
  tray.on('click', () => toggleHome());
  rebuildTrayMenu();
}

function rebuildTrayMenu() {
  if (!tray) return;
  const homeVisible = homeWindow && !homeWindow.isDestroyed() && homeWindow.isVisible();
  const overlayVisible = overlayWindow && !overlayWindow.isDestroyed() && overlayWindow.isVisible();
  const clipboardLabel = `Clipboard: ${mainState.clipboard.state}`
    + (mainState.clipboard.pid ? ` (pid ${mainState.clipboard.pid})` : '');

  const menu = Menu.buildFromTemplate([
    {
      label: `Server: ${mainState.server.state}` + (mainState.server.pid ? ` (pid ${mainState.server.pid})` : ''),
      enabled: false,
    },
    {
      label: `WS bridge: ${mainState.ws.state}` + (mainState.ws.port ? ` (port ${mainState.ws.port})` : ''),
      enabled: false,
    },
    {
      label: clipboardLabel,
      enabled: false,
    },
    {
      label: `Overlay: ${overlayVisible ? 'visible' : 'hidden'}`,
      enabled: false,
    },
    { type: 'separator' },
    {
      label: homeVisible ? 'Hide home' : 'Show home',
      accelerator: mainState.home.hotkey.binding || undefined,
      click: () => toggleHome(),
    },
    {
      label: overlayVisible ? 'Hide overlay' : 'Show overlay',
      accelerator: mainState.overlay.hotkey.binding || undefined,
      click: () => toggleOverlay(),
    },
    { type: 'separator' },
    { label: 'Restart server', click: () => restartServer() },
    { label: 'Restart clipboard', click: () => restartClipboardListener() },
    { label: 'Restart overlay', click: () => restartOverlay() },
    { type: 'separator' },
    {
      label: 'Quit poe2-graph',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
}

// ============================================================================
// Home IPC handlers
// ============================================================================

ipcMain.handle('home:pull-snapshot', () => mainState);
ipcMain.handle('home:show-overlay', () => { showOverlay(); return { ok: true }; });
ipcMain.handle('home:hide-overlay', () => { hideOverlay(); return { ok: true }; });
ipcMain.handle('home:restart-overlay', () => { restartOverlay(); return { ok: true }; });
ipcMain.handle('home:restart-server', () => { restartServer(); return { ok: true }; });
ipcMain.handle('home:restart-clipboard', () => { restartClipboardListener(); return { ok: true }; });
ipcMain.handle('home:reset-install', () => {
  clearInstallMarker();
  patchMainState({ repo: { ...mainState.repo, source: 'reset' } });
  return { ok: true };
});
ipcMain.handle('home:open-install-folder', () => {
  if (mainState.repo.root) shell.openPath(mainState.repo.root);
  return { ok: true };
});
ipcMain.handle('home:run-onboarding', () => {
  // v1 placeholder. Real implementation is the next round: a guided UI flow
  // (filesystem scan → questionnaire → write EXILE/PLAYER.md + LEAGUE_*.md +
  // CHARACTER_*.md). Until then, point at the Claude-driven path.
  return {
    ok: false,
    message:
      'Onboarding UI is coming next round. For now, open a Claude conversation ' +
      'with this skill attached and ask: "Walk me through onboarding."',
  };
});
ipcMain.handle('home:dismiss-view', (_e, viewId) => {
  // Round-trip through the WS as a user-driven view.dismiss; same path the
  // overlay's × button takes. Server unregisters it and broadcasts views.active.
  safeSend({ event: 'input.event', payload: { id: viewId, kind: 'view_dismissed', data: {} } });
  return { ok: true };
});
ipcMain.handle('home:quit', () => {
  isQuitting = true;
  app.quit();
  return { ok: true };
});

// Overlay IPC (existing surface)
ipcMain.handle('ws-send', (_e, message) => safeSend(message));
ipcMain.handle('overlay-hide', () => { hideOverlay(); return true; });

// ============================================================================
// App lifecycle
// ============================================================================

app.on('second-instance', () => {
  // Another instance was launched; bring the first instance's home forward.
  showHome();
});

app.whenReady().then(async () => {
  if (shouldRunWizard()) {
    createWizardWindow();
    return;
  }

  // 1. Kill any stale python.exe holding our candidate ports
  await cleanupOrphans();

  // 2. Spawn the MCP server (port-probed) and clipboard listener
  const marker = readInstallMarker();
  await spawnMcpServer(marker);
  spawnClipboardListener(marker?.repo_dir || resolveRepoRoot(marker).repoDir);

  // 3. Create home (auto-shown) and overlay (hidden unless --force-overlay)
  createHomeWindow();
  createOverlayWindow();

  // 4. Tray + hotkeys
  createTray();
  registerHotkeys();

  // 5. Connect the WS client (server needs a beat to bind)
  setTimeout(connectWebSocket, 1500);

  app.on('activate', () => {
    // macOS: re-open from Dock click
    if (BrowserWindow.getAllWindows().length === 0) {
      if (shouldRunWizard()) createWizardWindow();
      else { createHomeWindow(); createOverlayWindow(); }
    } else if (homeWindow && !homeWindow.isVisible()) {
      homeWindow.show();
    }
  });
});

app.on('window-all-closed', () => {
  // Wizard mode: exit when the window closes.
  if (mode === 'wizard') {
    app.quit();
    return;
  }
  // Overlay mode: do nothing. Closing the home hides to tray (close handler
  // calls preventDefault), so window-all-closed normally doesn't fire. If
  // both windows are genuinely destroyed (e.g. user force-killed them), keep
  // the tray running — quit only via Tray → Quit.
});

app.on('before-quit', () => { isQuitting = true; });

app.on('will-quit', () => {
  isShuttingDown = true;
  globalShortcut.unregisterAll();
  if (ws) { try { ws.close(); } catch (_) {} }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  if (tray) { try { tray.destroy(); } catch (_) {} tray = null; }
  if (serverChild) {
    const pid = serverChild.pid;
    try {
      treeKill(pid, 'SIGTERM', (err) => {
        if (err) console.warn(`[server] tree-kill(pid=${pid}) failed:`, err.message);
      });
    } catch (err) {
      console.warn(`[server] tree-kill threw:`, err && err.message);
    }
    serverChild = null;
  }
  if (clipboardChild) {
    const pid = clipboardChild.pid;
    try {
      treeKill(pid, 'SIGTERM', (err) => {
        if (err) console.warn(`[clipboard] tree-kill(pid=${pid}) failed:`, err.message);
      });
    } catch (err) {
      console.warn(`[clipboard] tree-kill threw:`, err && err.message);
    }
    clipboardChild = null;
  }
  // Clean shutdown: drop PID files so the next launch doesn't waste
  // time looking for already-dead processes.
  clearServerPidFile();
  clearClipboardPidFile();
});
