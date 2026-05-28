"""Pack this directory into <name>.mcpb (a ZIP archive).

Stand-in for `mcpb pack` from `@anthropic-ai/mcpb` — same output, no Node
dependency. Reads `manifest.json` for the bundle name; archives every file
in this directory except hidden files, `pack.py` itself, and any existing
`.mcpb` artifact.

Run from the directory that contains manifest.json:

  python pack.py

Output lands next to manifest.json as `<name>.mcpb`.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


SKIP_NAMES = {"pack.py"}
SKIP_SUFFIXES = {".mcpb"}
SKIP_PREFIXES = {".", "__pycache__"}


def _should_skip(rel: Path) -> bool:
    for part in rel.parts:
        if any(part.startswith(p) for p in SKIP_PREFIXES):
            return True
    if rel.name in SKIP_NAMES:
        return True
    if rel.suffix in SKIP_SUFFIXES:
        return True
    return False


def main() -> int:
    here = Path(__file__).resolve().parent
    manifest_path = here / "manifest.json"
    if not manifest_path.is_file():
        print(f"ERROR: manifest.json not found in {here!s}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name")
    if not name:
        print("ERROR: manifest.json is missing required 'name' field", file=sys.stderr)
        return 2

    out_path = here / f"{name}.mcpb"
    if out_path.exists():
        out_path.unlink()

    files: list[Path] = []
    for p in here.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(here)
        if _should_skip(rel):
            continue
        files.append(p)
    # Sort by archive-path (forward-slashed) so the in-archive order is
    # OS-independent — Windows and POSIX produce byte-identical bundles.
    files.sort(key=lambda p: p.relative_to(here).as_posix())

    # Use ZipInfo with a fixed date_time so two packs produce byte-identical
    # archives. zf.write() would otherwise stamp each entry with the source
    # file's mtime, making hash-based update detection see every rebuild as
    # a new artifact. Zip's epoch is 1980-01-01.
    fixed_date = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = f.relative_to(here).as_posix()
            zi = zipfile.ZipInfo(arcname, date_time=fixed_date)
            zi.compress_type = zipfile.ZIP_DEFLATED
            # External attrs 0o644 (regular file, rw-r--r--) — keeps the
            # archive portable; bootstrap.py is launched via `python ...`,
            # never directly, so no exec bit needed.
            zi.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(zi, f.read_bytes())

    size_kb = out_path.stat().st_size / 1024
    print(f"packed {len(files)} files into {out_path.name} ({size_kb:.1f} KB)")
    for f in files:
        print(f"  {f.relative_to(here).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
