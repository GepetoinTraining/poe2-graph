"""Top-level reader: dispatches by magic header."""

from __future__ import annotations

from pathlib import Path

from graphfmt.magic import detect_format
from graphfmt.bundle import read_bundle
from graphfmt.single import read_single


def read_graph(path: Path | str) -> dict:
    """Read a .X.graph file, dispatching by magic header.

    Returns:
      zip   -> {'kind': 'bundle', 'manifest': dict, 'contents': dict, 'readme': str|None, 'media': dict}
      gzip  -> {'kind': 'single', 'xml': str}
      plain -> {'kind': 'single', 'xml': str}

    Raises ValueError on unknown format.
    """
    fmt = detect_format(path)

    if fmt == "zip":
        result = read_bundle(path)
        result["kind"] = "bundle"
        return result

    if fmt == "gzip":
        return {"kind": "single", "xml": read_single(path)}

    if fmt == "plain":
        return {"kind": "single", "xml": Path(path).read_text(encoding="utf-8")}

    raise ValueError(
        f"cannot read {path!r}: unrecognised format (not zip, gzip, or plain XML)"
    )
