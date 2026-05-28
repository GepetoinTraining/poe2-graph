"""XML fragment helpers for store payloads.

Payloads are XML strings (fragments or full documents). These helpers give the
rest of the codebase a thin, predictable interface for reading and writing
individual values without requiring them to touch ElementTree directly.

Supported xpath shapes (subset — not a full XPath engine):
  /elem                   -- element text
  /elem/child             -- nested element text
  /elem/@attr             -- attribute on the element
  /elem/child/@attr       -- attribute on a nested element

For writing, xml_set creates the element path if missing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional


def _parse(payload: str) -> ET.Element:
    """Parse an XML payload string, wrapping bare fragments in a root if needed."""
    try:
        return ET.fromstring(payload)
    except ET.ParseError:
        # Bare fragment with no single root — wrap it.
        return ET.fromstring(f"<_root>{payload}</_root>")


def _split_path(xpath: str) -> tuple[list[str], Optional[str]]:
    """Split '/elem/child/@attr' into (['elem', 'child'], 'attr') or (['elem', 'child'], None)."""
    parts = [p for p in xpath.strip("/").split("/") if p]
    if parts and parts[-1].startswith("@"):
        return parts[:-1], parts[-1][1:]
    return parts, None


def xml_extract(payload: str, xpath: str) -> Optional[str]:
    """Return text of first matching element or attribute value, or None.

    Examples:
      xml_extract('<output classification="rare"/>', '/output/@classification') -> 'rare'
      xml_extract('<mods>life regen</mods>', '/mods') -> 'life regen'
    """
    root = _parse(payload)
    path_parts, attr = _split_path(xpath)

    if not path_parts:
        return None

    # The parsed root might be the element itself (if payload was a full doc)
    # or a synthetic _root wrapper.
    if root.tag == "_root":
        # Bare fragment: first element under wrapper is the real root.
        candidates = list(root)
        if not candidates:
            return None
        node: Optional[ET.Element] = candidates[0]
    else:
        node = root

    # Walk the path. The first segment is the root tag itself — skip if it matches.
    segments = list(path_parts)
    if node is not None and segments and node.tag == segments[0]:
        segments = segments[1:]

    for seg in segments:
        if node is None:
            return None
        node = node.find(seg)

    if node is None:
        return None

    if attr is not None:
        return node.get(attr)
    return node.text


def xml_set(payload: str, xpath: str, value: str) -> str:
    """Return a new payload string with the element or attribute set to value.

    Creates the element path if it does not exist. If the payload is a bare
    fragment, it is returned as a bare fragment (same root tag).

    Examples:
      xml_set('<output/>', '/output/@classification', 'rare')
      xml_set('<output><mods/></output>', '/output/mods', 'life regen')
    """
    was_fragment = False
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        root = ET.fromstring(f"<_root>{payload}</_root>")
        was_fragment = True

    path_parts, attr = _split_path(xpath)

    if not path_parts:
        raise ValueError(f"xpath must contain at least one element: {xpath!r}")

    # Determine real root vs wrapper.
    if root.tag == "_root":
        children = list(root)
        actual_root: ET.Element = children[0] if children else ET.SubElement(root, path_parts[0])
    else:
        actual_root = root

    segments = list(path_parts)
    if segments and actual_root.tag == segments[0]:
        segments = segments[1:]

    # Walk/create the element chain.
    node = actual_root
    for seg in segments:
        child = node.find(seg)
        if child is None:
            child = ET.SubElement(node, seg)
        node = child

    if attr is not None:
        node.set(attr, value)
    else:
        node.text = value

    if was_fragment:
        # Serialize children of _root wrapper, not the wrapper itself.
        inner = "".join(ET.tostring(c, encoding="unicode") for c in root)
        return inner
    return ET.tostring(root, encoding="unicode")
