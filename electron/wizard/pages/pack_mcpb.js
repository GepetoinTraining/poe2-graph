// Pack .mcpb — runs mcpb/pack.py, then offers the user a button to open the
// resulting file in Claude desktop (which is the platform's "import a bundle"
// flow if Claude is registered for the .mcpb extension).

export function renderPackMcpb(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Pack the Claude bundle</h1>
      <p>
        We'll build <code>poe2-graph.mcpb</code> from the manifest in
        <code>mcpb/</code>. Then click <em>Open in Claude</em> to register
        it with Claude desktop.
      </p>
      <button id="pack-btn" class="btn primary" style="align-self: flex-start;">Pack .mcpb</button>
      <div id="pack-status" style="font-size: 12px; color: var(--text-dim);"></div>
      <button id="open-claude" class="btn" style="align-self: flex-start; display:none;">Open in Claude desktop</button>
      <p style="font-size: 12px; color: var(--text-faint);">
        If Claude desktop doesn't open automatically, find the file at the path
        shown above and drag it into Claude → Settings → Connectors.
      </p>
    </div>
  `;
  const packBtn = container.querySelector('#pack-btn');
  const statusEl = container.querySelector('#pack-status');
  const openBtn = container.querySelector('#open-claude');

  api.setCanNext(false);

  packBtn.addEventListener('click', async () => {
    packBtn.disabled = true;
    statusEl.textContent = 'packing…';
    try {
      const result = await window.poe2Wizard.packMcpb({ repoDir: ctx.installDir });
      if (!result.ok) {
        statusEl.textContent = `pack failed: ${result.error || 'unknown'}`;
        packBtn.disabled = false;
        return;
      }
      ctx.mcpbPath = result.path;
      statusEl.textContent = `packed → ${result.path}`;
      openBtn.style.display = '';
      api.setCanNext(true);
    } catch (err) {
      statusEl.textContent = `error: ${err.message || err}`;
      packBtn.disabled = false;
    }
  });

  openBtn.addEventListener('click', async () => {
    if (ctx.mcpbPath) await window.poe2Wizard.openPath(ctx.mcpbPath);
  });

  return { canNext: () => !!ctx.mcpbPath };
}
