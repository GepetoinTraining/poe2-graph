// Prerequisites — runs detect_prereqs and shows results inline. Install-link
// buttons for each missing dep; recheck button after the user installs.

const INSTALL_LINKS = {
  python: 'https://www.python.org/downloads/',
  git: 'https://git-scm.com/downloads',
  node: 'https://nodejs.org/en/download/',
};

const DISPLAY_NAMES = {
  python: 'Python',
  git: 'Git',
  node: 'Node.js',
};

export function renderPrereqCheck(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Checking prerequisites</h1>
      <p>poe2-graph needs Python 3.11+, Git, and Node.js. We'll detect them
        on your <code>PATH</code> and link you to install pages if anything's
        missing.</p>
      <div id="prereq-rows"></div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:4px;">
        <button id="recheck-btn" class="btn">Re-check</button>
        <span id="recheck-status" style="color: var(--text-dim); font-size: 12px;"></span>
      </div>
    </div>
  `;

  const rowsEl = container.querySelector('#prereq-rows');
  const recheckBtn = container.querySelector('#recheck-btn');
  const recheckStatus = container.querySelector('#recheck-status');

  async function runDetection() {
    recheckBtn.disabled = true;
    recheckStatus.textContent = 'checking…';
    api.setCanNext(false);
    try {
      ctx.prereqs = await window.poe2Wizard.detectPrereqs();
    } catch (err) {
      recheckStatus.textContent = `error: ${err.message || err}`;
      recheckBtn.disabled = false;
      return;
    }
    renderRows(rowsEl, ctx.prereqs);
    recheckStatus.textContent = ctx.prereqs.all_ok
      ? 'all good — you can proceed'
      : 'install the missing items, then re-check';
    api.setCanNext(!!ctx.prereqs.all_ok);
    recheckBtn.disabled = false;
  }

  recheckBtn.addEventListener('click', runDetection);

  // Kick off on mount
  runDetection();

  return {
    canNext: () => !!(ctx.prereqs && ctx.prereqs.all_ok),
  };
}

function renderRows(container, prereqs) {
  container.innerHTML = '';
  for (const key of ['python', 'git', 'node']) {
    const info = prereqs[key];
    const row = document.createElement('div');
    const status = !info.ok ? 'bad' : (info.meets_min ? 'ok' : 'warn');
    row.className = `prereq-row ${status}`;
    row.innerHTML = `
      <div class="icon">${status === 'ok' ? '✓' : status === 'warn' ? '!' : '×'}</div>
      <div>
        <div class="name">${DISPLAY_NAMES[key]}</div>
        <div class="detail">${formatDetail(info)}</div>
      </div>
      <div>
        ${!info.ok || !info.meets_min
          ? `<button class="action-link" data-key="${key}">install</button>`
          : ''}
      </div>
    `;
    const installBtn = row.querySelector('.action-link');
    if (installBtn) {
      installBtn.addEventListener('click', () => {
        window.poe2Wizard.openExternal(INSTALL_LINKS[key]);
      });
    }
    container.appendChild(row);
  }
}

function formatDetail(info) {
  if (!info.ok) return `not found · needs ${info.min_required}+`;
  if (!info.meets_min) return `found ${info.major}.${info.minor} · needs ${info.min_required}+`;
  return `${info.command} · ${info.raw}`;
}
