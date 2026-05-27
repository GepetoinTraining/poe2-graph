// Create shortcut — drops a desktop icon that launches the Electron app
// in overlay mode. Optional step; the user can decline.

export function renderCreateShortcut(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Desktop shortcut</h1>
      <p>
        Place a <strong>poe2-graph</strong> icon on your desktop. Clicking
        it launches the overlay and starts the MCP server.
      </p>
      <p style="font-size: 12px; color: var(--text-faint);">
        Optional — you can skip and launch via <code>npm start</code> from
        <code>${escapeHtml(ctx.installDir)}/electron</code> instead.
      </p>

      <div style="display: flex; gap: 8px;">
        <button id="create-btn" class="btn primary">Create shortcut</button>
        <button id="skip-btn" class="btn ghost">Skip</button>
      </div>
      <div id="shortcut-status" style="font-size: 12px; color: var(--text-dim);"></div>
    </div>
  `;

  const createBtn = container.querySelector('#create-btn');
  const skipBtn = container.querySelector('#skip-btn');
  const statusEl = container.querySelector('#shortcut-status');

  // Skip-able by default — Next stays available even if user skips
  api.setCanNext(true);

  createBtn.addEventListener('click', async () => {
    createBtn.disabled = true;
    statusEl.textContent = 'creating…';
    try {
      const result = await window.poe2Wizard.createShortcut({
        targetCommand: 'launch-overlay',     // implementation-defined; action resolves
        label: 'poe2-graph',
      });
      if (result.ok) {
        ctx.shortcutPath = result.path;
        statusEl.textContent = `shortcut at ${result.path}`;
      } else {
        statusEl.textContent = `could not create shortcut: ${result.error || 'unknown'}`;
        createBtn.disabled = false;
      }
    } catch (err) {
      statusEl.textContent = `error: ${err.message || err}`;
      createBtn.disabled = false;
    }
  });

  skipBtn.addEventListener('click', () => {
    statusEl.textContent = 'skipped';
    createBtn.disabled = true;
  });

  return { canNext: () => true };
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
