// Classify-alert renderer — flash notification when a drop hits price_me.
//
// Payload shape:
//   cycle_id, output_id, item_summary, matched_pattern, suggested_trade_query
//
// Auto-dismisses after 8 seconds unless the card is hovered.
// Dismiss is achieved by sending a view_dismissed input.event so the server
// keeps its view state consistent.

const AUTO_DISMISS_MS = 8000;

export function renderClassifyAlert(container, data, meta) {
  if (!data) {
    container.textContent = '(no classify data)';
    return;
  }

  const audience = (meta && meta.audience) || '30pct';
  const terse = audience === '1pct';

  const root = document.createElement('div');
  root.className = 'classify-alert';

  // Item summary — primary text
  const summary = document.createElement('div');
  summary.className = 'ca-item-summary';
  summary.textContent = data.item_summary || '(unknown item)';
  root.appendChild(summary);

  // Matched pattern — secondary
  if (data.matched_pattern) {
    const pattern = document.createElement('div');
    pattern.className = 'ca-matched-pattern';
    pattern.textContent = terse
      ? data.matched_pattern
      : `matched: ${data.matched_pattern}`;
    root.appendChild(pattern);
  }

  // Trade query button (30pct + non-null)
  if (!terse && data.suggested_trade_query) {
    const tradeBtn = document.createElement('button');
    tradeBtn.className = 'ca-trade-btn';
    tradeBtn.textContent = 'open in trade';
    tradeBtn.addEventListener('click', () => {
      // Send the trade query as a user action; the server or a future
      // integration handles opening the browser. For now, emit as input.event.
      try {
        window.overlay.send({
          event: 'input.event',
          payload: {
            kind: 'trade_query_open',
            data: data.suggested_trade_query,
          },
        });
      } catch { /* no-op if send is unavailable */ }
    });
    root.appendChild(tradeBtn);
  }

  container.replaceChildren(root);

  // Auto-dismiss: start the 8-second countdown, pausing on hover.
  let dismissTimer = null;
  let hovered = false;

  function startTimer() {
    if (dismissTimer) clearTimeout(dismissTimer);
    dismissTimer = setTimeout(() => {
      if (!hovered) triggerDismiss();
    }, AUTO_DISMISS_MS);
  }

  function triggerDismiss() {
    if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }
    // Walk up to the view-card element to read the view id.
    const card = container.closest('[data-view-id]');
    if (!card) return;
    const viewId = card.dataset.viewId;
    if (!viewId) return;
    // Notify the server (server unregisters; overlay's onViewDismiss fires).
    try {
      window.overlay.send({
        event: 'input.event',
        payload: { id: viewId, kind: 'view_dismissed', data: {} },
      });
    } catch { /* no-op */ }
  }

  root.addEventListener('mouseenter', () => {
    hovered = true;
    if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }
  });
  root.addEventListener('mouseleave', () => {
    hovered = false;
    startTimer();
  });

  startTimer();

  return {
    cleanup() {
      if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }
    },
  };
}
