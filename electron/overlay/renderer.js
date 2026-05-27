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

const RENDERERS = {
  item_tooltip: renderItemTooltip,
  goal_tracker: renderGoalTracker,
  next_action_card: renderNextActionCard,
  map_timer: renderMapTimer,
};

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
    entry = { element, view, audience, data };
    activeViews.set(id, entry);
  } else {
    entry.data = data;
    entry.audience = audience;
    entry.element.classList.remove('audience-1pct', 'audience-30pct');
    if (audience) entry.element.classList.add(`audience-${audience}`);
  }
  const bodyEl = entry.element.querySelector('.view-card-body');
  renderer(bodyEl, data, { audience });
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
    renderer(bodyEl, entry.data, { audience: entry.audience });
  }
}

function onViewDismiss(payload) {
  const entry = activeViews.get(payload.id);
  if (!entry) return;
  entry.element.remove();
  activeViews.delete(payload.id);
  updateActiveViewCount();
}

function makeViewCard(view, id, audience) {
  const el = document.createElement('div');
  el.className = `view-card${audience ? ' audience-' + audience : ''}`;
  el.dataset.viewId = id;
  el.innerHTML = `
    <div class="view-card-header">
      <span class="view-type">${view}</span>
      <span class="view-id">${id}</span>
      <button class="dismiss" title="Dismiss">×</button>
    </div>
    <div class="view-card-body"></div>
  `;
  el.querySelector('.dismiss').addEventListener('click', () => {
    // Local dismissal — also notify the server so its view state stays consistent.
    el.remove();
    activeViews.delete(id);
    updateActiveViewCount();
    window.overlay.send({ event: 'input.event', payload: { id, kind: 'view_dismissed', view, data: {} } });
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
