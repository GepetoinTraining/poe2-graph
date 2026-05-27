// Wizard renderer — owns the step-machine, navigation, and shared state.
//
// Pages are pure functions: render(container, ctx) → optional { onNext, canNext }.
// `ctx` is the shared wizard state object — pages mutate it as the user
// progresses, and the renderer reads it back to decide whether Next is enabled.

import { renderWelcome }         from './pages/welcome.js';
import { renderPrereqCheck }     from './pages/prereq_check.js';
import { renderInstallLocation } from './pages/install_location.js';
import { renderCloneRepo }       from './pages/clone_repo.js';
import { renderInstallDeps }     from './pages/install_deps.js';
import { renderPackMcpb }        from './pages/pack_mcpb.js';
import { renderCreateShortcut }  from './pages/create_shortcut.js';
import { renderDone }            from './pages/done.js';

// ----- step definitions -----

const STEPS = [
  { id: 'welcome',           title: 'Welcome',          render: renderWelcome },
  { id: 'prereqs',           title: 'Prerequisites',    render: renderPrereqCheck },
  { id: 'install_location',  title: 'Install location', render: renderInstallLocation },
  { id: 'clone_repo',        title: 'Clone repo',       render: renderCloneRepo },
  { id: 'install_deps',      title: 'Install deps',     render: renderInstallDeps },
  { id: 'pack_mcpb',         title: 'Pack .mcpb',       render: renderPackMcpb },
  { id: 'create_shortcut',   title: 'Desktop icon',     render: renderCreateShortcut },
  { id: 'done',              title: 'Done',             render: renderDone },
];

// ----- shared state -----

const ctx = {
  defaults: null,                  // populated on init via getDefaults()
  prereqs: null,                   // { python: {...}, git: {...}, node: {...} }
  installDir: null,                // string user picked
  repoUrl: 'https://github.com/GepetoinTraining/poe2-graph.git',
  wsPort: '8889',                  // optional Electron-bridge port
  cloneLog: [],
  pythonInstallLog: [],
  nodeInstallLog: [],
  mcpbPath: null,
  shortcutPath: null,
  installComplete: false,
};

let stepIndex = 0;
let pageHooks = {};                // { onNext?, canNext? } from the current page

// ----- DOM refs -----

const bodyEl     = document.getElementById('wizard-body');
const progressEl = document.getElementById('wizard-progress');
const backBtn    = document.getElementById('btn-back');
const nextBtn    = document.getElementById('btn-next');
const cancelBtn  = document.getElementById('btn-cancel');

// ----- API for pages -----

export function setCanNext(allowed) {
  nextBtn.disabled = !allowed;
}

export function updateProgress() {
  renderProgress();
}

// ----- rendering -----

function renderProgress() {
  progressEl.innerHTML = '';
  STEPS.forEach((step, i) => {
    const el = document.createElement('div');
    el.className = 'step' + (i === stepIndex ? ' current' : i < stepIndex ? ' done' : '');
    el.innerHTML = `<span class="step-num">${i < stepIndex ? '✓' : i + 1}</span><span>${step.title}</span>`;
    progressEl.appendChild(el);
  });
}

function renderStep() {
  const step = STEPS[stepIndex];
  bodyEl.innerHTML = '';
  pageHooks = {};

  // Cancel button — leave on the first step, become "Cancel install" thereafter
  cancelBtn.textContent = stepIndex === 0 ? 'Cancel' : 'Cancel install';

  // Back disabled on first + done pages
  backBtn.disabled = stepIndex === 0 || step.id === 'done';

  // Reset Next button label + state — pages override via hooks
  nextBtn.textContent = (stepIndex === STEPS.length - 1) ? 'Finish' : 'Next →';
  nextBtn.disabled = false;

  // Pages return optional hooks. They may also call setCanNext() asynchronously.
  const result = step.render(bodyEl, ctx, { setCanNext, updateProgress });
  if (result && typeof result === 'object') {
    pageHooks = result;
    if (typeof result.canNext === 'function') {
      setCanNext(result.canNext());
    }
  }

  renderProgress();
}

// ----- navigation -----

async function gotoNext() {
  if (pageHooks.onNext) {
    const proceed = await pageHooks.onNext();
    if (proceed === false) return;       // page vetoed
  }
  if (stepIndex < STEPS.length - 1) {
    stepIndex += 1;
    renderStep();
  } else {
    // Finish button on the final page closes the wizard.
    window.close();
  }
}

function gotoBack() {
  if (stepIndex > 0) {
    stepIndex -= 1;
    renderStep();
  }
}

function cancelWizard() {
  if (stepIndex === 0) {
    window.close();
    return;
  }
  const ok = confirm('Cancel setup? You can re-run the wizard later by launching the app again.');
  if (ok) window.close();
}

// ----- wire UI -----

backBtn.addEventListener('click', gotoBack);
nextBtn.addEventListener('click', gotoNext);
cancelBtn.addEventListener('click', cancelWizard);

// ----- bootstrap -----

(async () => {
  try {
    ctx.defaults = await window.poe2Wizard.getDefaults();
    if (!ctx.installDir) ctx.installDir = ctx.defaults.defaultInstallDir;
  } catch (err) {
    console.error('failed to load defaults', err);
  }
  renderStep();
})();
