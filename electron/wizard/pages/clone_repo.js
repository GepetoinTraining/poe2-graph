// Clone repo — runs `git clone` into the chosen install dir. Shows live
// stdout/stderr from git in a log box. Idempotent: if the dir already
// contains a valid poe2-graph checkout we accept it as-is.

export function renderCloneRepo(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Cloning repository</h1>
      <p>
        Cloning <code>${escapeHtml(ctx.repoUrl)}</code> →
        <code>${escapeHtml(ctx.installDir)}</code>
      </p>
      <button id="start-clone" class="btn primary" style="align-self: flex-start;">Start clone</button>
      <div id="clone-log" class="log-box" style="display:none;"></div>
      <div id="clone-status" style="font-size: 12px; color: var(--text-dim);"></div>
    </div>
  `;

  const startBtn = container.querySelector('#start-clone');
  const logBox = container.querySelector('#clone-log');
  const statusEl = container.querySelector('#clone-status');

  api.setCanNext(false);

  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true;
    logBox.style.display = 'block';
    logBox.textContent = `running: git clone ${ctx.repoUrl} ${ctx.installDir}\n`;
    statusEl.textContent = 'cloning…';
    try {
      const result = await window.poe2Wizard.cloneRepo({
        repoUrl: ctx.repoUrl,
        targetDir: ctx.installDir,
      });
      logBox.textContent += (result.log || '').trim() + '\n';
      if (result.ok) {
        statusEl.textContent = result.skipped
          ? 'existing checkout detected — using it'
          : 'clone complete';
        api.setCanNext(true);
      } else {
        statusEl.textContent = `clone failed: ${result.error}`;
        startBtn.disabled = false;
      }
    } catch (err) {
      statusEl.textContent = `error: ${err.message || err}`;
      startBtn.disabled = false;
    }
  });

  return { canNext: () => false };
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
