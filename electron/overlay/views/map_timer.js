// Map-timer renderer — only view that maintains its own animation state.
// Server sends start event; renderer ticks locally; renderer.js's dismiss
// path calls the returned `cleanup` to stop the ticker.

const tickers = new Map();   // container DOM element → interval handle

export function renderMapTimer(container, data, _meta) {
  if (!data) {
    container.textContent = '(no timer data)';
    return;
  }
  // Server sends `started_at` as ISO 8601 (see mcp_server/protocol.md).
  // Fall back to `started_at_epoch` for backwards compat with older payloads.
  const startedAtMs = data.started_at
    ? new Date(data.started_at).getTime()
    : (data.started_at_epoch || 0) * 1000;
  const target = data.target_seconds || 0;

  // Defensive: stop any previous ticker on this container before starting a
  // new one. Renderer.js also runs the prior cleanup on re-render, but the
  // self-check costs nothing and survives manual reuse of this module.
  stopTicker(container);

  const display = document.createElement('div');
  display.className = 'timer-display';

  const progress = document.createElement('div');
  progress.className = 'timer-progress';
  const fill = document.createElement('div');
  fill.className = 'timer-progress-fill';
  progress.appendChild(fill);

  const meta = document.createElement('div');
  meta.className = 'timer-meta';

  container.replaceChildren(display, progress, meta);
  // The progress bar only makes sense when there's a target.
  if (target <= 0) progress.style.display = 'none';

  function paint() {
    const elapsed = Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000));
    const remaining = target - elapsed;
    const expired = target > 0 && remaining <= 0;
    const warn = !expired && target > 0 && remaining <= 60;

    display.classList.toggle('expired', expired);
    display.classList.toggle('warn', warn);
    fill.classList.toggle('expired', expired);
    fill.classList.toggle('warn', warn);

    if (expired) {
      display.textContent = `+${formatMMSS(-remaining)} over`;
    } else if (target > 0) {
      display.textContent = formatMMSS(remaining);
    } else {
      display.textContent = formatMMSS(elapsed);
    }

    if (target > 0) {
      const pct = Math.min(100, (elapsed / target) * 100);
      fill.style.width = `${pct}%`;
      meta.textContent = `${elapsed}s elapsed · ${target}s target`;
    } else {
      meta.textContent = `${elapsed}s elapsed`;
    }
  }

  paint();
  const handle = setInterval(paint, 1000);
  tickers.set(container, handle);

  // The renderer (and Claude-side dismiss_view through the WS bridge) calls
  // this to stop the tick and release the interval handle.
  return { cleanup: () => stopTicker(container) };
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
