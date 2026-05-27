// Run mcpb/pack.py to produce the .mcpb bundle.

const { exec } = require('child_process');
const { promisify } = require('util');
const path = require('path');
const fs = require('fs');
const execP = promisify(exec);

module.exports = async function packMcpb({ repoDir }) {
  const mcpbDir = path.join(repoDir, 'mcpb');
  const packScript = path.join(mcpbDir, 'pack.py');
  if (!fs.existsSync(packScript)) {
    return { ok: false, error: `pack.py not found at ${packScript}` };
  }
  try {
    const { stdout, stderr } = await execP(`python pack.py`, {
      cwd: mcpbDir,
      timeout: 120_000,
    });
    // Find the .mcpb that was produced. Manifest name = "poe2-graph" → poe2-graph.mcpb.
    const expected = path.join(mcpbDir, 'poe2-graph.mcpb');
    if (!fs.existsSync(expected)) {
      return {
        ok: false,
        error: `pack.py ran but ${expected} is missing`,
        log: (stdout || '') + (stderr || ''),
      };
    }
    return {
      ok: true,
      path: expected,
      log: (stdout || '') + (stderr || ''),
    };
  } catch (err) {
    return {
      ok: false,
      error: String(err.message || err),
      log: (err.stdout || '') + (err.stderr || ''),
    };
  }
};
