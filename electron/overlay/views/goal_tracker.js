// Goal-tracker renderer. Right now the server sends a text payload (the
// WoW-tracker rendering); a structured form will come later for richer UI.

export function renderGoalTracker(container, data, _meta) {
  if (!data) {
    container.textContent = '(no goal data)';
    return;
  }
  if (data.text) {
    const pre = document.createElement('pre');
    pre.style.fontFamily = 'Consolas, monospace';
    pre.style.fontSize = '12px';
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.margin = '0';
    pre.textContent = data.text;
    container.replaceChildren(pre);
    return;
  }
  // Structured form, when it arrives — fall through to JSON for now.
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(data, null, 2);
  container.replaceChildren(pre);
}
