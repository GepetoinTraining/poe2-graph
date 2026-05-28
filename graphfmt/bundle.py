"""Bundle .X.graph read/write — zip archive.

A published bundle is a zip containing:
  manifest.xml          required
  *.xml, *.build,
  *.farm.graph,
  *.craft.graph,
  *.guide.graph         text/XML content -> loaded as utf-8 strings into 'contents'
  README.md             optional, surfaced as its own 'readme' key
  everything else       binary blobs -> 'media' as raw bytes

Returns / accepts plain dicts. No wrapper classes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

from graphfmt.manifest import dict_to_manifest_xml, manifest_to_dict


# Extensions treated as text/XML content (decoded to str, stored in 'contents').
_TEXT_EXTENSIONS = {".xml", ".build", ".farm.graph", ".craft.graph", ".guide.graph"}


def _is_text_member(name: str) -> bool:
    """True if the zip member should be decoded as utf-8 text."""
    p = Path(name)
    if p.name == "manifest.xml":
        return False  # handled separately
    if p.name == "README.md":
        return False  # handled separately
    # Check suffix chain: "atlas.guide.graph" -> suffix is ".graph", but we also
    # need to catch ".farm.graph". Build the suffix from the last two parts.
    suffixes = "".join(p.suffixes)  # e.g. ".farm.graph"
    for ext in _TEXT_EXTENSIONS:
        if suffixes.endswith(ext):
            return True
    return False


# ----- reader -----

def read_bundle(path: Path | str) -> dict:
    """Read a zip-bundled .X.graph.

    Returns:
      {
        'manifest': dict,
        'contents': {filename: xml_str},
        'readme':   str | None,
        'media':    {filename: bytes},
      }

    Raises ValueError if manifest.xml is missing.
    """
    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())

        if "manifest.xml" not in names:
            raise ValueError(
                f"bundle at {path!r} is missing manifest.xml — not a valid .X.graph bundle"
            )

        manifest_xml = zf.read("manifest.xml").decode("utf-8")
        manifest = manifest_to_dict(manifest_xml)

        readme: Optional[str] = None
        if "README.md" in names:
            readme = zf.read("README.md").decode("utf-8")

        contents: dict[str, str] = {}
        media: dict[str, bytes] = {}

        for name in names:
            if name in ("manifest.xml", "README.md"):
                continue
            raw = zf.read(name)
            if _is_text_member(name):
                contents[name] = raw.decode("utf-8")
            else:
                media[name] = raw

    return {
        "manifest": manifest,
        "contents": contents,
        "readme": readme,
        "media": media,
    }


# ----- writer -----

def write_bundle(
    path: Path | str,
    *,
    manifest: dict,
    contents: dict[str, str],
    readme: Optional[str] = None,
    media: Optional[dict[str, bytes]] = None,
) -> None:
    """Write a zip-bundled .X.graph.

    manifest is serialised to manifest.xml automatically.
    contents[filename] -> string (written as utf-8).
    readme -> README.md (optional).
    media[filename] -> bytes (optional).
    """
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.xml", dict_to_manifest_xml(manifest).encode("utf-8"))

        for name, text in contents.items():
            zf.writestr(name, text.encode("utf-8"))

        if readme is not None:
            zf.writestr("README.md", readme.encode("utf-8"))

        if media:
            for name, raw in media.items():
                zf.writestr(name, raw)
