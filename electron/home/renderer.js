// Home renderer — subscribes to main-pushed state + WS events, renders the
// control room. No direct WebSocket connection; main process owns the wire.

const $ = (id) => document.getElementById(id);

// ----- shared state ------

const state = {
  main: null,                            // last home:main-state payload
  server: null,                          // last server.state event payload
  ws: null,                              // last ws.state event payload
  views: [],                             // last views.active event payload
  log: [],                               // rolling buffer of log.entry events
  logFilter: 'all',                      // 'all' | 'INFO' | 'WARNING' | 'ERROR'
};

const LOG_BUFFER_MAX = 500;

// ----- rendering ------

function renderHeader() {
  if (state.main && state.main.version) {
    $('version-label').textContent = `v${state.main.version}`;
  }
}

function renderServerPanel() {
  const s = state.server;
  const m = state.main;
  if (s) {
    const stateName = s.state || 'unknown';
    $('server-dot').dataset.state = stateName;
    $('server-state').textContent = stateName;
    $('server-pid').textContent = s.pid ?? '—';
  }
  if (m) {
    $('server-respawn').textContent = `${m.server?.respawn_attempts ?? 0} / ${m.server?.max_respawn ?? 5}`;
    $('server-last-exit').textContent = m.server?.last_exit_code != null
      ? `code ${m.server.last_exit_code}` + (m.server.last_exit_signal ? ` (${m.server.last_exit_signal})` : '')
      : '—';
  }
}

function renderWsPanel() {
  const w = state.ws;
  const m = state.main;
  if (w) {
    const stateName = w.state || 'unknown';
    $('ws-dot').dataset.state = stateName;
    $('ws-state-label').textContent = stateName;
    $('ws-port').textContent = w.port ?? '—';
  }
  if (m) {
    $('ws-clients').textContent = m.ws?.client_count ?? '—';
  }
}

function renderRepoPanel() {
  const m = state.main;
  if (!m) return;
  $('repo-root').textContent = m.repo?.root || '—';
  $('repo-source').textContent = m.repo?.source || '—';
  $('footer-marker').textContent = `marker: ${m.repo?.install_marker || 'n/a'}`;
}

function renderOverlayPanel() {
  const m = state.main;
  if (!m) return;
  const visible = !!m.overlay?.visible;
  $('overlay-dot').dataset.state = visible ? 'visible' : 'hidden';
  $('overlay-state').textContent = visible ? 'visible' : 'hidden';
  $('overlay-hotkey').textContent = m.overlay?.hotkey?.registered
    ? `${m.overlay.hotkey.binding} (registered)`
    : `${m.overlay?.hotkey?.binding || '—'} (conflict — use buttons)`;
}

function renderViewsPanel() {
  const list = $('views-list');
  list.replaceChildren();
  $('views-count').textContent = String(state.views.length);
  if (state.views.length === 0) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'No active views. Trigger one with display_goal_tracker(), start_map_timer(240), …';
    list.appendChild(li);
    return;
  }
  const now = Date.now() / 1000;
  for (const v of state.views) {
    const li = document.createElement('li');
    const vtype = document.createElement('span');
    vtype.className = 'vtype';
    vtype.textContent = v.view_type;
    const vid = document.createElement('span');
    vid.className = 'vid';
    vid.textContent = `#${v.view_id}`;
    const vage = document.createElement('span');
    vage.className = 'vage';
    const age = Math.max(0, Math.floor(now - (v.started_at || now)));
    vage.textContent = `${age}s`;
    const vdismiss = document.createElement('button');
    vdismiss.className = 'vdismiss';
    vdismiss.title = 'Dismiss this view';
    vdismiss.textContent = '×';
    vdismiss.addEventListener('click', () => window.poe2Home.dismissView(v.view_id));
    li.append(vtype, vid, vage, vdismiss);
    list.appendChild(li);
  }
}

function renderLog() {
  const box = $('log-box');
  const filtered = state.logFilter === 'all'
    ? state.log
    : state.log.filter(e => e.level === state.logFilter);
  box.replaceChildren();
  for (const e of filtered) {
    const line = document.createElement('span');
    line.className = 'log-line';
    line.dataset.level = e.level || 'INFO';

    const ts = document.createElement('span');
    ts.className = 'log-ts';
    ts.textContent = formatTs(e.ts) + ' ';

    const lvl = document.createElement('span');
    lvl.className = `log-level ${e.level || 'INFO'}`;
    lvl.textContent = (e.level || 'INFO').padEnd(7, ' ');

    const logger = document.createElement('span');
    logger.className = 'log-logger';
    logger.textContent = (e.logger || '') + ' ';

    const msg = document.createElement('span');
    msg.textContent = e.message || '';

    line.append(ts, lvl, logger, msg, '\n');
    box.appendChild(line);
  }
  // Auto-scroll to bottom unless the user has scrolled up.
  if (box.dataset.userScrolled !== '1') {
    box.scrollTop = box.scrollHeight;
  }
}

function formatTs(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function renderAll() {
  renderHeader();
  renderServerPanel();
  renderWsPanel();
  renderRepoPanel();
  renderOverlayPanel();
  renderViewsPanel();
  renderLog();
}

// ----- WS event dispatch ------

function handleWsEvent(msg) {
  if (!msg || typeof msg !== 'object') return;
  switch (msg.event) {
    case 'state.snapshot': {
      // Bulk restore from the server's latest-of-each cache.
      const snap = msg.payload || {};
      if (snap['server.state'])  state.server = snap['server.state'];
      if (snap['ws.state'])      state.ws     = snap['ws.state'];
      if (snap['views.active'])  state.views  = snap['views.active'].views || [];
      // log.entry snapshot is the most-recent log only; we don't backfill the box from it.
      renderAll();
      break;
    }
    case 'server.state':
      state.server = msg.payload;
      renderServerPanel();
      break;
    case 'ws.state':
      state.ws = msg.payload;
      renderWsPanel();
      break;
    case 'views.active':
      state.views = msg.payload.views || [];
      renderViewsPanel();
      break;
    case 'view.lifecycle':
      // Treat the lifecycle event as a log entry so it shows in the activity stream.
      pushLog({
        level: 'INFO',
        logger: 'view',
        message: `${msg.payload.action} ${msg.payload.view_type || ''} #${msg.payload.view_id}`,
        ts: msg.payload.ts,
      });
      break;
    case 'log.entry':
      pushLog(msg.payload);
      break;
    default:
      // Unknown event — ignore quietly.
      break;
  }
}

function pushLog(entry) {
  state.log.push(entry);
  if (state.log.length > LOG_BUFFER_MAX) {
    state.log.splice(0, state.log.length - LOG_BUFFER_MAX);
  }
  renderLog();
}

// ----- wire actions ------

function bindActions() {
  $('btn-restart-server').addEventListener('click', () => window.poe2Home.restartServer());
  $('btn-show-overlay').addEventListener('click', () => window.poe2Home.showOverlay());
  $('btn-hide-overlay').addEventListener('click', () => window.poe2Home.hideOverlay());
  $('btn-restart-overlay').addEventListener('click', () => window.poe2Home.restartOverlay());
  $('btn-open-folder').addEventListener('click', () => window.poe2Home.openInstallFolder());
  $('btn-reset-install').addEventListener('click', async () => {
    const ok = confirm(
      'Reset install will clear the install marker. Next launch will run the setup wizard again.\n\n' +
      'Player data in EXILE/ is not touched. Continue?'
    );
    if (ok) await window.poe2Home.resetInstall();
  });
  $('btn-run-onboarding').addEventListener('click', async () => {
    const res = await window.poe2Home.runOnboarding();
    if (res && res.message) alert(res.message);
  });
  $('btn-quit').addEventListener('click', async () => {
    const ok = confirm('Quit poe2-graph? The MCP server will stop too.');
    if (ok) await window.poe2Home.quit();
  });
  $('btn-copy-log').addEventListener('click', async () => {
    const text = $('log-box').innerText;
    try {
      await navigator.clipboard.writeText(text);
    } catch { /* ignore — clipboard write requires focus */ }
  });
  for (const chip of document.querySelectorAll('.filter-chips .chip')) {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.logFilter = chip.dataset.filter;
      renderLog();
    });
  }
  // Track user scroll on the log so auto-scroll only fires when at the bottom.
  const box = $('log-box');
  box.addEventListener('scroll', () => {
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 8;
    box.dataset.userScrolled = atBottom ? '0' : '1';
  });
}

// Tick the view-age counter every second so "5s" → "6s" etc.
setInterval(() => {
  if (state.views.length > 0) renderViewsPanel();
}, 1000);

// ----- bootstrap ------

(async () => {
  bindActions();
  window.poe2Home.onMainState((payload) => {
    state.main = payload;
    renderAll();
  });
  window.poe2Home.onWsEvent((msg) => handleWsEvent(msg));
  try {
    const snapshot = await window.poe2Home.pullSnapshot();
    if (snapshot) {
      state.main = snapshot;
      renderAll();
    }
  } catch (err) {
    console.warn('pullSnapshot failed', err);
  }
})();
