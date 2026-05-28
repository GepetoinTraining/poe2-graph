// Item-tooltip renderer.
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
// Until then, this renders an in-game-style tooltip with rarity tints,
// implicit + prefix + suffix sections divided by accent hairlines, and a
// "Proposed craft" block dimmed + italic with an accent left border to
// distinguish suggestions from actual rolls.

export function renderItemTooltip(container, data, _meta) {
  if (!data) {
    container.textContent = '(no item data)';
    return;
  }

  const root = document.createElement('div');
  root.className = 'item-tooltip';

  // Name + base header
  const baseName = (data.base && data.base.name) || '(unknown base)';
  const rarity = data.rarity || 'normal';
  const name = document.createElement('div');
  name.className = `item-name rarity-${String(rarity).toLowerCase()}`;
  name.textContent = data.name || baseName;
  root.appendChild(name);

  const baseLine = document.createElement('div');
  baseLine.className = 'item-base';
  const ilvl = data.item_level != null ? `iLvl ${data.item_level}` : '';
  baseLine.textContent = [baseName, capitalize(rarity), ilvl].filter(Boolean).join(' · ');
  root.appendChild(baseLine);

  // Implicits
  const implicits = data.implicits || [];
  if (implicits.length) {
    root.appendChild(hr());
    implicits.forEach((m) => root.appendChild(modLine(m, 'implicit')));
  }

  // Explicits — prefixes then suffixes, same visual treatment
  const prefixes = data.prefixes || [];
  const suffixes = data.suffixes || [];
  if (prefixes.length || suffixes.length) {
    root.appendChild(hr());
    prefixes.forEach((m) => root.appendChild(modLine(m)));
    suffixes.forEach((m) => root.appendChild(modLine(m)));
  }

  // Proposed-craft section — distinct visual (italic + dim + accent border).
  const proposed = data.proposed_prefixes || data.proposed_mods || [];
  if (proposed.length) {
    root.appendChild(hr());
    const label = document.createElement('div');
    label.className = 'proposed-label';
    label.textContent = 'Proposed craft';
    root.appendChild(label);
    proposed.forEach((m) => root.appendChild(modLine(m, 'proposed')));
  }

  if (data.corrupted) {
    const corrupted = document.createElement('div');
    corrupted.className = 'item-corrupted';
    corrupted.textContent = 'Corrupted';
    root.appendChild(corrupted);
  }

  // Phase 2 marker — removed once the real poe-item-display component swaps in.
  const swap = document.createElement('div');
  swap.className = 'swap-note';
  swap.textContent = 'poe-item-display mount point';
  root.appendChild(swap);

  container.replaceChildren(root);
}

function hr() {
  const el = document.createElement('div');
  el.className = 'item-hr';
  return el;
}

function modLine(mod, variant) {
  const el = document.createElement('div');
  el.className = 'item-mod' + (variant ? ` ${variant}` : '');
  const text = mod.name || mod.template || mod.render || '';
  // textContent handles the bulk; tier (if present) is dimmer + smaller.
  el.textContent = text;
  if (mod.tier) {
    const tier = document.createElement('span');
    tier.className = 'tier';
    tier.textContent = ` ${mod.tier}`;
    el.appendChild(tier);
  }
  return el;
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}
