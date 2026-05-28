// Cycle-status renderer — shows current farm cycle state.
//
// Payload shape:
//   cycle_id, status, farm_target, lottery_targets[], opened_at, elapsed_minutes,
//   output_count, classified: { price_me, gold_pile, unclassified }

export function renderCycleStatus(container, data, meta) {
  if (!data) {
    container.textContent = '(no cycle data)';
    return;
  }

  const audience = (meta && meta.audience) || '30pct';
  const terse = audience === '1pct';

  const root = document.createElement('div');
  root.className = 'cycle-status-card';

  // Status badge + farm target row
  const topRow = document.createElement('div');
  topRow.className = 'cs-top-row';

  const targetEl = document.createElement('span');
  targetEl.className = 'cs-farm-target';
  targetEl.textContent = data.farm_target || '(unknown target)';

  const badge = document.createElement('span');
  badge.className = `cs-status-badge cs-status-${String(data.status || 'unknown').toLowerCase()}`;
  badge.textContent = data.status || 'UNKNOWN';

  topRow.append(targetEl, badge);
  root.appendChild(topRow);

  // Elapsed + output count
  const statsRow = document.createElement('div');
  statsRow.className = 'cs-stats-row';

  if (data.elapsed_minutes != null) {
    const elapsed = document.createElement('span');
    elapsed.className = 'cs-stat';
    elapsed.textContent = terse
      ? `${data.elapsed_minutes}m`
      : `${data.elapsed_minutes} min elapsed`;
    statsRow.appendChild(elapsed);
  }

  const outputs = document.createElement('span');
  outputs.className = 'cs-stat';
  outputs.textContent = terse
    ? `${data.output_count || 0} out`
    : `${data.output_count || 0} outputs`;
  statsRow.appendChild(outputs);

  root.appendChild(statsRow);

  // Classification breakdown bar
  const classified = data.classified || {};
  const total = (classified.price_me || 0) + (classified.gold_pile || 0) + (classified.unclassified || 0);

  if (total > 0) {
    const barWrap = document.createElement('div');
    barWrap.className = 'cs-class-bar';

    const pctPriceMe   = Math.round((classified.price_me    || 0) / total * 100);
    const pctGoldPile  = Math.round((classified.gold_pile   || 0) / total * 100);
    const pctUnclass   = Math.max(0, 100 - pctPriceMe - pctGoldPile);

    if (pctPriceMe > 0) {
      const seg = document.createElement('div');
      seg.className = 'cs-bar-seg cs-seg-price-me';
      seg.style.width = `${pctPriceMe}%`;
      barWrap.appendChild(seg);
    }
    if (pctGoldPile > 0) {
      const seg = document.createElement('div');
      seg.className = 'cs-bar-seg cs-seg-gold-pile';
      seg.style.width = `${pctGoldPile}%`;
      barWrap.appendChild(seg);
    }
    if (pctUnclass > 0) {
      const seg = document.createElement('div');
      seg.className = 'cs-bar-seg cs-seg-unclassified';
      seg.style.width = `${pctUnclass}%`;
      barWrap.appendChild(seg);
    }

    root.appendChild(barWrap);

    if (!terse) {
      const legend = document.createElement('div');
      legend.className = 'cs-bar-legend';

      const items = [
        { label: 'sell', count: classified.price_me   || 0, cls: 'cs-leg-price-me' },
        { label: 'gold', count: classified.gold_pile  || 0, cls: 'cs-leg-gold-pile' },
        { label: '?',    count: classified.unclassified || 0, cls: 'cs-leg-unclassified' },
      ];
      items.forEach(({ label, count, cls }) => {
        const chip = document.createElement('span');
        chip.className = `cs-leg-chip ${cls}`;
        chip.textContent = `${label}: ${count}`;
        legend.appendChild(chip);
      });
      root.appendChild(legend);
    }
  }

  // Lottery targets (30pct only)
  if (!terse && Array.isArray(data.lottery_targets) && data.lottery_targets.length) {
    const lRow = document.createElement('div');
    lRow.className = 'cs-lottery-row';
    const lLabel = document.createElement('span');
    lLabel.className = 'cs-lottery-label';
    lLabel.textContent = 'lottery: ';
    lRow.appendChild(lLabel);
    const lVal = document.createElement('span');
    lVal.className = 'cs-lottery-targets';
    lVal.textContent = data.lottery_targets.join(', ');
    lRow.appendChild(lVal);
    root.appendChild(lRow);
  }

  container.replaceChildren(root);
}
