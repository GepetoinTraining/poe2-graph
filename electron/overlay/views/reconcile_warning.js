// Reconcile-warning renderer — outputs don't match main inventory.
//
// Payload shape:
//   cycle_id, cycle_output_count, main_received_count,
//   reconciliation_gap, unmatched_output_ids[]
//
// NOT auto-dismissed. Player must click the card's dismiss button.

export function renderReconcileWarning(container, data, meta) {
  if (!data) {
    container.textContent = '(no reconcile data)';
    return;
  }

  const audience = (meta && meta.audience) || '30pct';
  const terse = audience === '1pct';

  const root = document.createElement('div');
  root.className = 'reconcile-warning';

  // Gap headline
  const headline = document.createElement('div');
  headline.className = 'rw-headline';
  const gapNum = document.createElement('span');
  gapNum.className = 'rw-gap-number';
  gapNum.textContent = String(data.reconciliation_gap != null ? data.reconciliation_gap : '?');
  headline.appendChild(gapNum);

  if (!terse) {
    const gapLabel = document.createElement('span');
    gapLabel.className = 'rw-gap-label';
    gapLabel.textContent = ' outputs unaccounted';
    headline.appendChild(gapLabel);
  }
  root.appendChild(headline);

  // Counts row (30pct)
  if (!terse) {
    const counts = document.createElement('div');
    counts.className = 'rw-counts';
    counts.textContent = `cycle: ${data.cycle_output_count ?? '?'} — received: ${data.main_received_count ?? '?'}`;
    root.appendChild(counts);
  }

  // Unmatched IDs — collapsed behind a toggle
  const ids = Array.isArray(data.unmatched_output_ids) ? data.unmatched_output_ids : [];
  if (ids.length) {
    const details = document.createElement('details');
    details.className = 'rw-details';

    const summary = document.createElement('summary');
    summary.className = 'rw-summary';
    summary.textContent = terse
      ? `${ids.length} id${ids.length === 1 ? '' : 's'}`
      : `show ${ids.length} unmatched id${ids.length === 1 ? '' : 's'}`;
    details.appendChild(summary);

    const idList = document.createElement('ul');
    idList.className = 'rw-id-list';
    ids.forEach((id) => {
      const li = document.createElement('li');
      li.textContent = id;
      idList.appendChild(li);
    });
    details.appendChild(idList);
    root.appendChild(details);
  }

  container.replaceChildren(root);
}
