// Done — final wizard step. Writes the install marker, summarises what
// happened, and tells the user how to re-launch.

export function renderDone(container, ctx, api) {
  container.innerHTML = `
    <div class="page">
      <h1>Setup complete</h1>
      <p>
        poe2-graph is installed at <code>${escapeHtml(ctx.installDir)}</code>.
      </p>
      <h2>What's next</h2>
      <ul>
        <li>Open Claude desktop → Settings → Connectors and confirm the
            poe2-graph bundle is enabled.</li>
        ${ctx.shortcutPath
          ? `<li>Double-click the <strong>poe2-graph</strong> icon on your desktop to launch the overlay.</li>`
          : `<li>Launch the overlay by running <code>npm start</code> in <code>${escapeHtml(ctx.installDir)}/electron</code>.</li>`}
        <li>Press <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd> to toggle the overlay when it's running.</li>
        <li>Ask Claude: <em>"call welcome and show me the response"</em> to verify the MCP tools are wired.</li>
      </ul>
      <p style="font-size: 12px; color: var(--text-faint);">
        Closing this window finishes installation. The next launch of the app
        opens in overlay mode automatically.
      </p>
    </div>
  `;

  // Write the install marker NOW (not at "Finish" — already at the last step
  // so we can guarantee subsequent launches skip the wizard).
  (async () => {
    try {
      await window.poe2Wizard.complete({
        repoDir: ctx.installDir,
        wsPort: ctx.wsPort,
      });
      ctx.installComplete = true;
    } catch (err) {
      console.error('failed to write install marker', err);
    }
  })();

  return { canNext: () => true };
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
