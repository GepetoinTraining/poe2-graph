// "Next action" card — rendered from guides.recommend_next_action output.

export function renderNextActionCard(container, data, meta) {
  if (!data) {
    container.textContent = '(no recommendation)';
    return;
  }
  const audience = (meta && meta.audience) || '30pct';
  const rationale = data.rationale || '(no rationale)';
  const subgoal = data.next_subgoal || null;
  const learning = data.next_learning_goal || null;
  const guideCount = (data.relevant_system_guides || []).length;
  const gaps = data.confidence_gaps || [];

  const parts = [`<p style="margin:0 0 8px">${escapeHtml(rationale)}</p>`];

  if (subgoal) {
    parts.push(`<div><strong>Next:</strong> ${escapeHtml(subgoal.statement || subgoal.id || '(unnamed subgoal)')}</div>`);
    if (subgoal.kind) parts.push(`<div style="color:var(--text-dim);font-size:11px">kind: ${escapeHtml(subgoal.kind)}</div>`);
  }
  if (learning && audience !== '1pct') {
    parts.push(`<div style="margin-top:6px"><strong>Learning:</strong> ${escapeHtml(learning.topic || learning.id || '(unnamed)')}</div>`);
  }
  if (audience !== '1pct') {
    parts.push(`<div style="margin-top:6px;color:var(--text-dim);font-size:11px">${guideCount} relevant guide${guideCount === 1 ? '' : 's'}</div>`);
    if (gaps.length) {
      const gapList = gaps.slice(0, 3).map(g => `${escapeHtml(String(g[0]))} (${(g[1] * 100).toFixed(0)}%)`).join(', ');
      parts.push(`<div style="color:var(--warn);font-size:11px">confidence gaps: ${gapList}</div>`);
    }
  }
  container.innerHTML = parts.join('');
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
