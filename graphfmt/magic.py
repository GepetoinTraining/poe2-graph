"""Magic-header detection for .X.graph files.

Both zip bundles and gzip single-docs share the same extension. The physical
format is identified by inspecting the first 4 bytes of the file or bytes object.

Zip magic:   PK\x03\x04  (local file header)
             PK\x05\x06  (empty archive — treated as zip)
Gzip magic:  \x1f\x8b
Plain:       anything starting with '<' or whitespace then '<' (XML declaration)
Unknown:     anything else
"""

from __future__ import annotations

from pathlib import Path


def detect_format(source: Path | str | bytes) -> str:
    """Return 'zip', 'gzip', 'plain', or 'unknown'.

    source may be a path-like (file is opened and the first 8 bytes read) or
    raw bytes (the header bytes themselves; at least 4 bytes recommended).
    """
    if isinstance(source, (str, Path)):
        with open(source, "rb") as fh:
            header = fh.read(8)
    else:
        header = source[:8]

    if len(header) < 2:
        return "unknown"

    if header[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return "zip"

    if header[:2] == b"\x1f\x8b":
        return "gzip"

    # Sniff for XML: skip leading whitespace then look for '<'
    stripped = header.lstrip(b" \t\r\n")
    if stripped and stripped[0:1] == b"<":
        return "plain"

    return "unknown"
