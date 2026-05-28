// Renderer — runs inside the BrowserWindow. Receives WS messages from main
// (via preload's contextBridge) and routes them to view modules.
//
// View modules are intentionally small placeholders right now. When
// poe-item-display / poe-item-hover-react / poe-item-parser get imported,
// each module's `render` function gets swapped for a React mount call.

import { renderItemTooltip } from './views/item_tooltip.js';
import { renderGoalTracker } from './views/goal_tracker.js';
import { renderNextActionCard } from './views/next_action_card.js';
import { renderMapTimer } from './views/map_timer.js';
import { renderCycleStatus } from './views/cycle_status.js';
import { renderClassifyAlert } from './views/classify_alert.js';
import { renderReconcileWarning } from './views/reconcile_warning.js';
import { renderCycleSummary } from './views/cycle_summary.js';

const RENDERERS = {
  item_tooltip: renderItemTooltip,
  goal_tracker: renderGoalTracker,
  next_action_card: renderNextActionCard,
  map_timer: renderMapTimer,
  cycle_status: renderCycleStatus,
  classify_alert: renderClassifyAlert,
  reconcile_warning: renderReconcileWarning,
  cycle_summary: renderCycleSummary,
};

// Views whose visual treatment changes with audience. The audience-1pct /
// audience-30pct left-border marker is applied only to these; map_timer and
// item_tooltip render the same payload either way and shouldn't carry the
// chip-color hint.
const AUDIENCE_AWARE_VIEWS = new Set([
  'goal_tracker', 'next_action_card',
  'cycle_status', 'classify_alert', 'reconcile_warning', 'cycle_summary',
]);

// ---- DOM refs ----
const wsIndicator = document.getElementById('ws-indicator');
const viewsContainer = document.getElementById('views-container');
const placeholder = document.getElementById('placeholder');
const activeViewCount = document.getElementById('active-view-count');
const eventLogLink = document.getElementById('event-log-link');
const hideButton = document.getElementById('hide-button');

// ---- view registry ----
// id → { element, view, lastUpdate }
const activeViews = new Map();
let eventCount = 0;

function setWsStatus(payload) {
  wsIndicator.className = `status status-${payload.status}`;
  wsIndicator.textContent = payload.status === 'open' ? 'live' : payload.status;
}

function bumpEventCount(eventName) {
  eventCount += 1;
  eventLogLink.textContent = `${eventCount} events (last: ${eventName})`;
}

function updateActiveViewCount() {
  const n = activeViews.size;
  activeViewCount.textContent = n === 1 ? '1 active view' : `${n} active views`;
  placeholder.style.display = n === 0 ? '' : 'none';
}

// ---- message routing ----

function handleMessage(msg) {
  if (!msg || typeof msg !== 'object') return;
  bumpEventCount(msg.event || 'unknown');
  switch (msg.event) {
    case 'view.render':  return onViewRender(msg.payload || {});
    case 'view.update':  return onViewUpdate(msg.payload || {});
    case 'view.dismiss': return onViewDismiss(msg.payload || {});
    case 'state.snapshot': /* TODO: bulk view reconciliation */ return;
    default:
      console.debug('unhandled event:', msg.event);
  }
}

function onViewRender(payload) {
  const { view, id, audience, data } = payload;
  if (!view || !id) return;
  const renderer = RENDERERS[view];
  if (!renderer) {
    console.warn(`unknown view type: ${view}`);
    return;
  }
  let entry = activeViews.get(id);
  if (!entry) {
    const element = makeViewCard(view, id, audience);
    viewsContainer.appendChild(element);
    entry = { element, view, audience, data, cleanup: null };
    activeViews.set(id, entry);
  } else {
    entry.data = data;
    entry.audience = audience;
    entry.element.classList.remove('audience-1pct', 'audience-30pct');
    if (audience) entry.element.classList.add(`audience-${audience}`);
  }
  const bodyEl = entry.element.querySelector('.view-card-body');
  // Re-render replaces the body; run the previous cleanup so timers /
  // observers from the prior render don't outlive their DOM.
  runCleanup(entry);
  const result = renderer(bodyEl, data, { audience });
  entry.cleanup = (result && typeof result.cleanup === 'function') ? result.cleanup : null;
  updateActiveViewCount();
}

function onViewUpdate(payload) {
  const { id, patch } = payload;
  const entry = activeViews.get(id);
  if (!entry) return;
  entry.data = { ...(entry.data || {}), ...(patch || {}) };
  const renderer = RENDERERS[entry.view];
  if (renderer) {
    const bodyEl = entry.element.querySelector('.view-card-body');
    runCleanup(entry);
    const result = renderer(bodyEl, entry.data, { audience: entry.audience });
    entry.cleanup = (result && typeof result.cleanup === 'function') ? result.cleanup : null;
  }
}

function onViewDismiss(payload) {
  // Server-driven dismiss (e.g. Claude-side `dismiss_view` MCP tool, voice
  // command in a future iteration). Mirrors the user-click path below — the
  // single dismissView() funnel ensures cleanup runs either way.
  dismissView(payload.id, { notifyServer: false });
}

function dismissView(id, { notifyServer }) {
  const entry = activeViews.get(id);
  if (!entry) return;
  runCleanup(entry);
  entry.element.remove();
  activeViews.delete(id);
  updateActiveViewCount();
  if (notifyServer) {
    window.overlay.send({
      event: 'input.event',
      payload: { id, kind: 'view_dismissed', view: entry.view, data: {} },
    });
  }
}

function runCleanup(entry) {
  if (typeof entry.cleanup !== 'function') return;
  try { entry.cleanup(); }
  catch (err) { console.warn('view cleanup failed', err); }
  entry.cleanup = null;
}

function makeViewCard(view, id, audience) {
  // Build via DOM APIs rather than innerHTML — `view` and `id` come from
  // server payloads and would be HTML-injectable if interpolated into a
  // template string. textContent renders them as literal text.
  const el = document.createElement('div');
  const showAudience = audience && AUDIENCE_AWARE_VIEWS.has(view);
  el.className = `view-card${showAudience ? ' audience-' + audience : ''}`;
  el.dataset.viewId = id;

  const header = document.createElement('div');
  header.className = 'view-card-header';

  const typeSpan = document.createElement('span');
  typeSpan.className = 'view-type';
  typeSpan.textContent = view;

  const idSpan = document.createElement('span');
  idSpan.className = 'view-id';
  idSpan.textContent = id;

  const dismissBtn = document.createElement('button');
  dismissBtn.className = 'dismiss';
  dismissBtn.title = 'Dismiss';
  dismissBtn.textContent = '×';

  header.append(typeSpan, idSpan, dismissBtn);

  const body = document.createElement('div');
  body.className = 'view-card-body';

  el.append(header, body);

  dismissBtn.addEventListener('click', () => {
    // Local dismissal — also notify the server so its view state stays
    // consistent. Server may want to log the dismiss for analytics or to
    // suppress an auto-redisplay rule.
    dismissView(id, { notifyServer: true });
  });

  return el;
}

// ---- chrome ----

hideButton.addEventListener('click', () => window.overlay.hide());

// Pressing Esc in the overlay hides it.
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') window.overlay.hide();
});

// ---- bind to main-process events ----

window.overlay.onWsStatus(setWsStatus);
window.overlay.onWsMessage(handleMessage);
