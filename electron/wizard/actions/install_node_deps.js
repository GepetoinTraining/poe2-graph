// npm install inside the cloned repo's electron/ subdir.

const { execFile } = require('child_process');
const { promisify } = require('util');
const path = require('path');
const fs = require('fs');
const execFileP = promisify(execFile);

// On Windows, `npm` is `npm.cmd` (a batch shim); Node 18+ refuses to launch
// .cmd/.bat via execFile without shell:true. Resolve the right binary per
// platform — no user input flows into either branch.
const NPM_CMD = process.platform === 'win32' ? 'npm.cmd' : 'npm';

module.exports = async function installNodeDeps({ repoDir }) {
  const electronDir = path.join(repoDir, 'electron');
  if (!fs.existsSync(path.join(electronDir, 'package.json'))) {
    return { ok: false, error: `electron/package.json not found at ${electronDir}` };
  }
  try {
    const { stdout, stderr } = await execFileP(NPM_CMD, ['install'], {
      cwd: electronDir,
      timeout: 600_000,
      maxBuffer: 8 * 1024 * 1024,
    });
    return { ok: true, log: (stdout || '') + (stderr || '') };
  } catch (err) {
    return {
      ok: false,
      error: String(err.message || err),
      log: (err.stdout || '') + (err.stderr || ''),
    };
  }
};
