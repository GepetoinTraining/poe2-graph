// Map-timer renderer — only view in Phase 2 that maintains its own animation
// state. Server sends start event; renderer ticks locally; view.dismiss stops it.

const tickers = new Map();   // container DOM element → interval handle

export function renderMapTimer(container, data, _meta) {
  if (!data) {
    container.textContent = '(no timer data)';
    return;
  }
  const startedAtMs = (data.started_at_epoch || 0) * 1000;
  const target = data.target_seconds || 0;

  // Stop any previous ticker on this container (re-render)
  stopTicker(container);

  const display = document.createElement('div');
  display.className = 'timer-display';
  container.replaceChildren(display);

  function paint() {
    const elapsed = Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000));
    const remaining = target - elapsed;
    if (target > 0 && remaining <= 0) {
      display.classList.add('expired');
      display.textContent = `+${formatMMSS(-remaining)} over`;
    } else if (target > 0) {
      display.classList.remove('expired');
      display.textContent = formatMMSS(remaining);
    } else {
      display.textContent = formatMMSS(elapsed);
    }
  }

  paint();
  const handle = setInterval(paint, 1000);
  tickers.set(container, handle);

  // Best-effort cleanup if the container is removed by view.dismiss.
  // The MutationObserver watches the container's parent for removal.
  const parent = container.parentElement;
  if (parent) {
    const obs = new MutationObserver(() => {
      if (!document.contains(container)) {
        stopTicker(container);
        obs.disconnect();
      }
    });
    obs.observe(parent, { childList: true, subtree: true });
  }
}

function stopTicker(container) {
  const handle = tickers.get(container);
  if (handle != null) {
    clearInterval(handle);
    tickers.delete(container);
  }
}

function formatMMSS(secs) {
  const s = Math.max(0, Math.floor(secs));
  const mm = Math.floor(s / 60).toString().padStart(2, '0');
  const ss = (s % 60).toString().padStart(2, '0');
  return `${mm}:${ss}`;
}
