// Cycle-summary renderer — close-cycle ROI / hit-rate summary card.
//
// Payload shape:
//   cycle_id, farm_target, roi, hit_rate, div_per_hour, time_invested_minutes,
//   output_count, classified: { price_me, gold_pile }, closed_at
//
// NOT auto-dismissed. ROI is color-coded: green if positive, red if negative.

export function renderCycleSummary(container, data, meta) {
  if (!data) {
    container.textContent = '(no cycle summary)';
    return;
  }

  const audience = (meta && meta.audience) || '30pct';
  const terse = audience === '1pct';

  const root = document.createElement('div');
  root.className = 'cycle-summary';

  // Farm target header
  const targetEl = document.createElement('div');
  targetEl.className = 'csm-target';
  targetEl.textContent = data.farm_target || '(unknown target)';
  root.appendChild(targetEl);

  // ROI — large, color-coded
  const roi = typeof data.roi === 'number' ? data.roi : null;
  const roiEl = document.createElement('div');
  roiEl.className = 'csm-roi';
  if (roi !== null) {
    const positive = roi >= 0;
    roiEl.classList.add(positive ? 'cycle-summary--positive' : 'cycle-summary--negative');
    const roiPct = Math.round(roi * 100);
    roiEl.textContent = terse
      ? `${positive ? '+' : ''}${roiPct}%`
      : `ROI: ${positive ? '+' : ''}${roiPct}%`;
  } else {
    roiEl.textContent = terse ? 'ROI: —' : 'ROI: n/a';
    roiEl.className = 'csm-roi';
  }
  root.appendChild(roiEl);

  // Supporting numbers
  const statsGrid = document.createElement('div');
  statsGrid.className = 'csm-stats';

  function addStat(label, value) {
    const row = document.createElement('div');
    row.className = 'csm-stat-row';
    const k = document.createElement('span');
    k.className = 'csm-stat-key';
    k.textContent = label;
    const v = document.createElement('span');
    v.className = 'csm-stat-val';
    v.textContent = value;
    row.append(k, v);
    statsGrid.appendChild(row);
  }

  if (data.hit_rate != null) {
    const hitPct = Math.round(data.hit_rate * 100);
    addStat(terse ? 'hit' : 'hit rate', `${hitPct}%`);
  }
  if (data.div_per_hour != null) {
    addStat(terse ? 'div/hr' : 'div / hr', String(data.div_per_hour.toFixed(2)));
  }
  if (data.time_invested_minutes != null) {
    addStat(terse ? 'time' : 'time invested', `${data.time_invested_minutes} min`);
  }
  if (data.output_count != null) {
    addStat(terse ? 'out' : 'outputs', String(data.output_count));
  }

  // Classified breakdown (30pct only)
  if (!terse && data.classified) {
    const c = data.classified;
    const parts = [];
    if (c.price_me != null)   parts.push(`sell: ${c.price_me}`);
    if (c.gold_pile != null)  parts.push(`gold: ${c.gold_pile}`);
    if (parts.length) addStat('classified', parts.join(' / '));
  }

  if (statsGrid.children.length) root.appendChild(statsGrid);

  // Closed-at timestamp (30pct only)
  if (!terse && data.closed_at) {
    let displayTs = data.closed_at;
    try {
      const d = new Date(data.closed_at);
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      displayTs = `${hh}:${mm}`;
    } catch { /* use raw string */ }
    const closedEl = document.createElement('div');
    closedEl.className = 'csm-closed-at';
    closedEl.textContent = `closed at ${displayTs}`;
    root.appendChild(closedEl);
  }

  container.replaceChildren(root);
}
