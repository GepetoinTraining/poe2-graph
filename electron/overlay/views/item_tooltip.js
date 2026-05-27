// Placeholder item-tooltip renderer.
//
// SWAP TARGET: when poe-item-display / poe-item-hover-react are imported,
// replace this module's body with a React mount:
//
//   import ReactDOM from 'react-dom/client';
//   import { ItemDisplay } from 'poe-item-display';
//
//   export function renderItemTooltip(container, data) {
//     const root = container._reactRoot ?? (container._reactRoot = ReactDOM.createRoot(container));
//     root.render(<ItemDisplay item={data} />);
//   }
//
// The MCP server's parse_clipboard_item already produces a JSON shape close
// to what poe-item-display expects (base, rarity, name, item_level, implicits,
// prefixes, suffixes, sockets, corrupted). The shape may need a small
// adapter when the real component lands; see mcp_server/protocol.md.

export function renderItemTooltip(container, data, _meta) {
  if (!data) {
    container.textContent = '(no item data)';
    return;
  }
  const baseName = data.base && data.base.name ? data.base.name : '(unknown base)';
  const name = data.name || baseName;
  const ilvl = data.item_level != null ? `iLvl ${data.item_level}` : '';
  const rarity = data.rarity || '';
  const prefixCount = (data.prefixes || []).length;
  const suffixCount = (data.suffixes || []).length;
  const implicitCount = (data.implicits || []).length;

  container.innerHTML = `
    <div class="item-tooltip-placeholder">
      <div class="item-name">${escapeHtml(name)}</div>
      <div class="item-base">${escapeHtml(baseName)} · ${escapeHtml(rarity)} · ${escapeHtml(ilvl)}</div>
      <div class="item-base">${implicitCount} impl · ${prefixCount} pref · ${suffixCount} suf${data.corrupted ? ' · corrupted' : ''}</div>
      <div class="swap-note">poe-item-display mount point</div>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
