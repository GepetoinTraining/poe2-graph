// Detect Python / Git / Node availability + versions.
//
// Shell out to `python --version` etc. Returns a structured object the
// wizard's prereq_check page can render.
//
// Cross-platform: on Windows, `python` may be the Microsoft Store stub that
// opens the Store on invocation. We try `python` first, fall back to `py -3`
// on Windows. Versions are parsed leniently — any 3.x with x >= 11 is OK.

const { exec } = require('child_process');
const { promisify } = require('util');
const execP = promisify(exec);

const REQUIRED = {
  python: { min: [3, 11], commands: ['python', 'py -3', 'python3'] },
  git:    { min: [2, 0],  commands: ['git'] },
  node:   { min: [18, 0], commands: ['node'] },
};

async function getVersion(cmd) {
  // `cmd` like "python" or "py -3" — split into argv
  const parts = cmd.split(/\s+/);
  const tool = parts[0];
  const args = [...parts.slice(1), '--version'];
  try {
    const { stdout, stderr } = await execP([tool, ...args].join(' '), { timeout: 6000 });
    const raw = (stdout || stderr || '').trim();
    const match = raw.match(/(\d+)\.(\d+)(?:\.(\d+))?/);
    if (!match) return { ok: false, raw, reason: 'version not parseable' };
    return {
      ok: true,
      command: cmd,
      raw,
      major: parseInt(match[1], 10),
      minor: parseInt(match[2], 10),
      patch: parseInt(match[3] || '0', 10),
    };
  } catch (err) {
    return { ok: false, command: cmd, error: String(err.message || err) };
  }
}

function compareMin(found, min) {
  if (found.major > min[0]) return true;
  if (found.major < min[0]) return false;
  return found.minor >= min[1];
}

async function detectOne(name) {
  const spec = REQUIRED[name];
  for (const cmd of spec.commands) {
    const v = await getVersion(cmd);
    if (v.ok) {
      v.meets_min = compareMin(v, spec.min);
      v.min_required = spec.min.join('.');
      return v;
    }
  }
  return {
    ok: false,
    min_required: spec.min.join('.'),
    tried: spec.commands,
    error: `Not found on PATH. Tried: ${spec.commands.join(', ')}`,
  };
}

module.exports = async function detectPrereqs() {
  const [python, git, node] = await Promise.all([
    detectOne('python'),
    detectOne('git'),
    detectOne('node'),
  ]);
  return {
    python,
    git,
    node,
    all_ok: python.ok && python.meets_min && git.ok && git.meets_min && node.ok && node.meets_min,
  };
};
