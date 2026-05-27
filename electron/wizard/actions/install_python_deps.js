// pip install -r requirements.txt
//
// Uses whatever `python` resolves to on PATH (the prereq check has already
// validated it). Captures combined stdout+stderr to surface in the UI.

const { exec } = require('child_process');
const { promisify } = require('util');
const path = require('path');
const fs = require('fs');
const execP = promisify(exec);

module.exports = async function installPythonDeps({ repoDir }) {
  const requirements = path.join(repoDir, 'requirements.txt');
  if (!fs.existsSync(requirements)) {
    return { ok: false, error: `requirements.txt not found at ${requirements}` };
  }
  try {
    const { stdout, stderr } = await execP(
      `python -m pip install -r "${requirements}"`,
      { cwd: repoDir, timeout: 600_000, maxBuffer: 4 * 1024 * 1024 }
    );
    return { ok: true, log: (stdout || '') + (stderr || '') };
  } catch (err) {
    return {
      ok: false,
      error: String(err.message || err),
      log: (err.stdout || '') + (err.stderr || ''),
    };
  }
};
