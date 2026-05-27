// Welcome — first wizard step. Explains what the install will do.

export function renderWelcome(container, ctx, _api) {
  container.innerHTML = `
    <div class="page">
      <h1>Welcome to poe2-graph</h1>
      <p>
        A Claude-native toolkit for Path of Exile 2: build planning, goal
        decomposition, in-game item parsing, system guides, and an in-game
        overlay for during-play assistance.
      </p>

      <h2>What this wizard will do</h2>
      <ul>
        <li>Check that <code>python</code>, <code>git</code>, and <code>node</code> are installed</li>
        <li>Clone the <code>poe2-graph</code> repo to a folder you choose</li>
        <li>Install Python + Node dependencies</li>
        <li>Pack the <code>.mcpb</code> bundle for the Claude desktop app</li>
        <li>Drop a desktop shortcut so you can launch the overlay later</li>
      </ul>

      <h2>What you'll need</h2>
      <ul>
        <li><strong>Python 3.11+</strong> (we'll detect it; if missing, we'll point you at the download)</li>
        <li><strong>Git</strong> (any modern version)</li>
        <li>A few minutes of attention — most of the steps run themselves</li>
      </ul>

      <p style="color: var(--text-faint); font-size: 12px;">
        Nothing leaves your machine. Account credentials and EXILE/ player state
        live only in the repo folder you choose.
      </p>
    </div>
  `;
  return {};
}
