// Install location — user picks where the repo goes. Default is
// ~/poe2-graph. We don't open a native folder dialog yet — text input is
// fine for v1, and avoids the Electron-dialog import noise.

export function renderInstallLocation(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Pick install location</h1>
      <p>
        The poe2-graph repo will be cloned here. This folder is where your
        player profile (<code>EXILE/</code>) and live data lives — keep it
        somewhere you won't accidentally delete.
      </p>
      <label class="field">
        Install directory
        <input type="text" id="install-dir" value="${escapeHtml(ctx.installDir || '')}" />
      </label>
      <label class="field">
        Repository URL
        <input type="text" id="repo-url" value="${escapeHtml(ctx.repoUrl || '')}" />
      </label>
      <p style="font-size: 12px; color: var(--text-faint);">
        Leave the repo URL default unless you've forked the project.
      </p>
    </div>
  `;

  const dirInput = container.querySelector('#install-dir');
  const urlInput = container.querySelector('#repo-url');

  dirInput.addEventListener('input', () => {
    ctx.installDir = dirInput.value.trim();
    api.setCanNext(!!ctx.installDir && !!ctx.repoUrl);
  });
  urlInput.addEventListener('input', () => {
    ctx.repoUrl = urlInput.value.trim();
    api.setCanNext(!!ctx.installDir && !!ctx.repoUrl);
  });

  return {
    canNext: () => !!(ctx.installDir && ctx.repoUrl),
  };
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
