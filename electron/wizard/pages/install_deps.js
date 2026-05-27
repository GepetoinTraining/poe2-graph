// Install deps — runs `pip install -r requirements.txt` and
// `npm install` inside electron/.

export function renderInstallDeps(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Installing dependencies</h1>
      <p>This runs <code>pip install -r requirements.txt</code> and
        <code>npm install</code> inside <code>electron/</code>. Can take
        a couple of minutes the first time.</p>
      <button id="start-install" class="btn primary" style="align-self: flex-start;">Start install</button>
      <div>
        <h2 style="margin-top:8px;">Python (pip)</h2>
        <div id="pip-log" class="log-box" style="display:none;"></div>
      </div>
      <div>
        <h2>Node (npm)</h2>
        <div id="npm-log" class="log-box" style="display:none;"></div>
      </div>
      <div id="install-status" style="font-size: 12px; color: var(--text-dim);"></div>
    </div>
  `;

  const startBtn = container.querySelector('#start-install');
  const pipLog = container.querySelector('#pip-log');
  const npmLog = container.querySelector('#npm-log');
  const statusEl = container.querySelector('#install-status');

  api.setCanNext(false);

  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true;
    statusEl.textContent = 'running pip install…';
    pipLog.style.display = 'block';
    pipLog.textContent = '';
    let pipResult;
    try {
      pipResult = await window.poe2Wizard.installPythonDeps({ repoDir: ctx.installDir });
      pipLog.textContent = pipResult.log || '';
    } catch (err) {
      statusEl.textContent = `pip error: ${err.message || err}`;
      startBtn.disabled = false;
      return;
    }
    if (!pipResult.ok) {
      statusEl.textContent = `pip failed: ${pipResult.error || 'unknown'}`;
      startBtn.disabled = false;
      return;
    }

    statusEl.textContent = 'running npm install…';
    npmLog.style.display = 'block';
    npmLog.textContent = '';
    let npmResult;
    try {
      npmResult = await window.poe2Wizard.installNodeDeps({ repoDir: ctx.installDir });
      npmLog.textContent = npmResult.log || '';
    } catch (err) {
      statusEl.textContent = `npm error: ${err.message || err}`;
      startBtn.disabled = false;
      return;
    }
    if (!npmResult.ok) {
      statusEl.textContent = `npm failed: ${npmResult.error || 'unknown'}`;
      startBtn.disabled = false;
      return;
    }

    statusEl.textContent = 'all deps installed';
    api.setCanNext(true);
  });

  return { canNext: () => false };
}
