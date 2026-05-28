"""graphfmt — read and write .X.graph files.

Format dispatch:
  zip bundle      -> manifest.xml + content XMLs + media, packaged as a zip archive
  gzip single-doc -> one gzip-compressed XML document
  plain XML       -> uncompressed XML, accepted as a fallback for dev/testing

The reader auto-detects format by magic header (PK for zip, 0x1f8b for gzip).
Users see a single .X.graph extension; the tool handles both wire formats.
"""

from __future__ import annotations

from graphfmt.magic import detect_format
from graphfmt.reader import read_graph
from graphfmt.writer import write_graph
from graphfmt.bundle import read_bundle, write_bundle
from graphfmt.single import read_single, write_single
from graphfmt.manifest import dict_to_manifest_xml, manifest_to_dict

__all__ = [
    "detect_format",
    "read_graph",
    "write_graph",
    "read_bundle",
    "write_bundle",
    "read_single",
    "write_single",
    "dict_to_manifest_xml",
    "manifest_to_dict",
]
