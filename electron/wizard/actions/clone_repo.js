// git clone — idempotent. Treats an existing dir with a .git subfolder as
// "already cloned" rather than failing.

const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs');
const path = require('path');
const execP = promisify(exec);

module.exports = async function cloneRepo({ repoUrl, targetDir }) {
  if (!repoUrl || !targetDir) {
    return { ok: false, error: 'repoUrl and targetDir are required' };
  }

  // Already exists?
  const dotGit = path.join(targetDir, '.git');
  if (fs.existsSync(dotGit)) {
    return {
      ok: true,
      skipped: true,
      log: `existing checkout detected at ${targetDir} (.git is present)`,
    };
  }

  try {
    fs.mkdirSync(path.dirname(targetDir), { recursive: true });
    const { stdout, stderr } = await execP(
      `git clone --recurse-submodules "${repoUrl}" "${targetDir}"`,
      { timeout: 600_000 }
    );
    return {
      ok: true,
      skipped: false,
      log: (stdout || '') + (stderr || ''),
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err), log: err.stderr || err.stdout || '' };
  }
};
