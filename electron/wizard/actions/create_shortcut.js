// Create a desktop shortcut that launches the Electron overlay.
//
// Platform-specific:
//   Windows  — .lnk via Electron's app.setUserTasks not applicable here;
//              we shell out to PowerShell's WScript.Shell COM helper.
//   macOS    — write a small .command shell script on Desktop (executable).
//   Linux    — write a .desktop file (FreeDesktop spec).
//
// The shortcut runs the currently-running Electron app (process.execPath)
// with --force-overlay so subsequent launches skip the install marker check
// branch and go straight to overlay mode.

const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFile } = require('child_process');
const { promisify } = require('util');
const execFileP = promisify(execFile);

module.exports = async function createShortcut({ label }) {
  const desktopPath = app.getPath('desktop');
  const target = process.execPath;        // path to the running Electron binary
  const args = ['--force-overlay'];
  const cwd = app.getAppPath();
  const safeLabel = (label || 'poe2-graph').replace(/[<>:"/\\|?*]/g, '_');

  try {
    if (process.platform === 'win32') {
      return await createWindowsShortcut({ desktopPath, target, args, cwd, label: safeLabel });
    } else if (process.platform === 'darwin') {
      return await createMacShortcut({ desktopPath, target, args, cwd, label: safeLabel });
    } else {
      return await createLinuxShortcut({ desktopPath, target, args, cwd, label: safeLabel });
    }
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
};

async function createWindowsShortcut({ desktopPath, target, args, cwd, label }) {
  const lnkPath = path.join(desktopPath, `${label}.lnk`);
  const argString = args.join(' ');

  // Write the PowerShell to a temp .ps1 and invoke with -File. This avoids the
  // quote-escape minefield of -Command "<inline string>": single quotes inside
  // the script don't need to survive a CreateProcess command-line parse.
  const psScript = [
    `$s = New-Object -ComObject WScript.Shell`,
    `$sc = $s.CreateShortcut(${psString(lnkPath)})`,
    `$sc.TargetPath = ${psString(target)}`,
    `$sc.Arguments = ${psString(argString)}`,
    `$sc.WorkingDirectory = ${psString(cwd)}`,
    `$sc.IconLocation = ${psString(target)}`,
    `$sc.Save()`,
  ].join('\n');

  const tmpFile = path.join(os.tmpdir(), `poe2-graph-shortcut-${process.pid}-${Date.now()}.ps1`);
  fs.writeFileSync(tmpFile, psScript, 'utf8');

  try {
    await execFileP('powershell', [
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', tmpFile,
    ], { timeout: 30_000 });
  } finally {
    try { fs.unlinkSync(tmpFile); } catch { /* ignore */ }
  }

  if (!fs.existsSync(lnkPath)) {
    return { ok: false, error: 'shortcut creation reported success but .lnk is missing' };
  }
  return { ok: true, path: lnkPath };
}

// PowerShell single-quoted string literal: ' is the only metacharacter, doubled
// to escape. Embedded $/`/"/% are literal inside single quotes.
function psString(s) {
  return `'${String(s).replace(/'/g, "''")}'`;
}

async function createMacShortcut({ desktopPath, target, args, cwd, label }) {
  const scriptPath = path.join(desktopPath, `${label}.command`);
  const argString = args.map(a => `"${a}"`).join(' ');
  const body = `#!/bin/sh\ncd "${cwd}"\nexec "${target}" ${argString}\n`;
  fs.writeFileSync(scriptPath, body, { mode: 0o755 });
  return { ok: true, path: scriptPath };
}

async function createLinuxShortcut({ desktopPath, target, args, cwd, label }) {
  const filePath = path.join(desktopPath, `${label}.desktop`);
  const argString = args.join(' ');
  const body =
`[Desktop Entry]
Type=Application
Name=${label}
Exec=${target} ${argString}
Path=${cwd}
Terminal=false
Icon=${target}
`;
  fs.writeFileSync(filePath, body, { mode: 0o755 });
  return { ok: true, path: filePath };
}
