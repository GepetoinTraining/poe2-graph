// Goal-tracker renderer.
//
// Renders the structured form when the server's payload includes
// `subgoals` / `learning_subgoals` / `confidence_gaps` — the audience-aware
// view from the design system. Falls back to the plain-text rendering when
// only `data.text` is present (current Python server behaviour until
// tools_goals emits structured data).

const STATUS_ICONS = {
  done: '✓',          // ✓
  'in-progress': '›', // ›
  in_progress: '›',
  pending: '○',       // ○
  blocked: '◌',       // ◌
};

export function renderGoalTracker(container, data, meta) {
  if (!data) {
    container.textContent = '(no goal data)';
    return;
  }

  // Structured form: prefer when the server populates it.
  if (Array.isArray(data.subgoals) || Array.isArray(data.learning_subgoals)) {
    container.replaceChildren(structured(data, meta));
    return;
  }

  // Text fallback: matches the legacy `data.text` shape.
  if (data.text) {
    const pre = document.createElement('pre');
    pre.style.fontFamily = 'var(--font-mono)';
    pre.style.fontSize = '12px';
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.margin = '0';
    pre.textContent = data.text;
    container.replaceChildren(pre);
    return;
  }

  // Unknown payload — render JSON for debugging.
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(data, null, 2);
  container.replaceChildren(pre);
}

function structured(data, meta) {
  const audience = (meta && meta.audience) || '30pct';
  const showLearning = audience !== '1pct';
  const showGaps = audience !== '1pct';

  const root = document.createElement('div');
  root.className = 'goal-tracker';

  if (data.statement) {
    const statement = document.createElement('div');
    statement.className = 'statement';
    statement.textContent = data.statement;
    root.appendChild(statement);
  }

  const subgoals = data.subgoals || [];
  if (subgoals.length) {
    const list = document.createElement('div');
    list.className = 'subgoals';
    subgoals.forEach((sg) => list.appendChild(subgoalRow(sg)));
    root.appendChild(list);
  }

  if (showLearning) {
    const learning = data.learning_subgoals || [];
    if (learning.length) {
      const section = document.createElement('div');
      section.className = 'learning-section';
      const label = document.createElement('div');
      label.className = 'label-caps';
      label.style.marginBottom = '5px';
      label.textContent = 'Learning';
      section.appendChild(label);
      learning.forEach((lg) => section.appendChild(learningRow(lg)));
      root.appendChild(section);
    }
  }

  if (showGaps) {
    const gaps = data.confidence_gaps || [];
    if (gaps.length) {
      const row = document.createElement('div');
      row.className = 'gap-row';
      gaps.forEach(([domain, value]) => row.appendChild(gapChip(domain, value)));
      root.appendChild(row);
    }
  }

  return root;
}

function subgoalRow(sg) {
  const wrap = document.createElement('div');

  const top = document.createElement('div');
  top.className = 'subgoal-row';

  const status = normalizeStatus(sg.status);
  const icon = document.createElement('span');
  icon.className = `subgoal-icon ${status}`;
  icon.textContent = STATUS_ICONS[status] || STATUS_ICONS.pending;

  const text = document.createElement('span');
  text.className = `subgoal-text ${status}`;
  text.textContent = sg.statement || sg.id || '(unnamed subgoal)';

  top.append(icon, text);
  wrap.appendChild(top);

  if (sg.progress != null && status !== 'done') {
    const bar = document.createElement('div');
    bar.className = 'subgoal-progress';
    const fill = document.createElement('div');
    fill.className = 'subgoal-progress-fill';
    fill.style.width = `${Math.max(0, Math.min(1, sg.progress)) * 100}%`;
    bar.appendChild(fill);
    wrap.appendChild(bar);
  }

  return wrap;
}

function learningRow(lg) {
  const row = document.createElement('div');
  row.className = 'learning-row';
  const status = normalizeStatus(lg.status);
  const icon = document.createElement('span');
  icon.className = `subgoal-icon ${status}`;
  icon.textContent = STATUS_ICONS[status] || STATUS_ICONS.pending;
  const text = document.createElement('span');
  text.textContent = lg.statement || lg.topic || lg.id || '(unnamed learning goal)';
  row.append(icon, text);
  return row;
}

function gapChip(domain, value) {
  const el = document.createElement('div');
  el.className = 'gap-chip';
  const pct = Math.round(Number(value) * 100);
  el.textContent = `${domain} (${pct}%)`;
  return el;
}

function normalizeStatus(s) {
  if (!s) return 'pending';
  const norm = String(s).toLowerCase().replace('_', '-');
  if (norm === 'in-progress' || norm === 'done' || norm === 'pending' || norm === 'blocked') {
    return norm;
  }
  return 'pending';
}
