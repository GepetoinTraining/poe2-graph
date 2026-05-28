"""Single-doc .X.graph read/write — gzip-compressed XML.

The in-flight format for a single graph artifact. Lighter than a bundle;
designed for passing around one XML payload without packaging media or sibling
graphs.
"""

from __future__ import annotations

import gzip
from pathlib import Path


def read_single(path: Path | str) -> str:
    """Return the decompressed XML string from a gzip single-doc .X.graph."""
    with gzip.open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def write_single(path: Path | str, xml_str: str) -> None:
    """Write xml_str as a gzip-compressed single-doc .X.graph."""
    with gzip.open(path, "wb") as fh:
        fh.write(xml_str.encode("utf-8"))
