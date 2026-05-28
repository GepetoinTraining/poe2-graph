// "Next action" card — rendered from goals.recommend_next_action output.
//
// Audience-aware: 1pct shows the rationale + next subgoal only. 30pct adds
// the learning goal, the count of relevant system guides, and the top
// confidence-gap chips. The audience-marker left border is applied by
// renderer.js, not here.

export function renderNextActionCard(container, data, meta) {
  if (!data) {
    container.textContent = '(no recommendation)';
    return;
  }

  const audience = (meta && meta.audience) || '30pct';
  const show30 = audience !== '1pct';

  const root = document.createElement('div');
  root.className = 'next-action';

  // Rationale — always shown.
  const rationale = document.createElement('p');
  rationale.className = 'rationale';
  rationale.textContent = data.rationale || '(no rationale)';
  root.appendChild(rationale);

  // Next subgoal — always shown.
  if (data.next_subgoal) {
    const wrap = document.createElement('div');
    const label = document.createElement('span');
    label.className = 'label-inline';
    label.textContent = 'Next: ';
    const strong = document.createElement('strong');
    strong.textContent = data.next_subgoal.statement || data.next_subgoal.id || '(unnamed subgoal)';
    wrap.append(label, strong);
    if (data.next_subgoal.kind) {
      const kind = document.createElement('div');
      kind.className = 'kind';
      kind.textContent = `kind: ${data.next_subgoal.kind}`;
      wrap.appendChild(kind);
    }
    root.appendChild(wrap);
  }

  if (show30 && data.next_learning_goal) {
    const wrap = document.createElement('div');
    const label = document.createElement('span');
    label.className = 'label-inline';
    label.textContent = 'Learning: ';
    const topic = document.createElement('span');
    topic.className = 'learning-topic';
    topic.textContent = data.next_learning_goal.topic || data.next_learning_goal.id || '(unnamed)';
    wrap.append(label, topic);
    root.appendChild(wrap);
  }

  if (show30) {
    const guides = data.relevant_system_guides || [];
    if (guides.length) {
      const meta = document.createElement('div');
      meta.className = 'guides-meta';
      meta.textContent = `${guides.length} relevant guide${guides.length === 1 ? '' : 's'}`;
      root.appendChild(meta);
    }
  }

  if (show30) {
    const gaps = data.confidence_gaps || [];
    if (gaps.length) {
      const row = document.createElement('div');
      row.className = 'gap-row';
      gaps.slice(0, 3).forEach(([domain, value]) => {
        const chip = document.createElement('div');
        chip.className = 'gap-chip';
        const pct = Math.round(Number(value) * 100);
        chip.textContent = `${domain} (${pct}%)`;
        row.appendChild(chip);
      });
      root.appendChild(row);
    }
  }

  container.replaceChildren(root);
}
