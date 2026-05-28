"""Manifest XML serialisation helpers.

The manifest is a small XML document describing the contents of a bundle.
These helpers convert between the XML text and a plain dict, keeping all
data as strings (no type coercion).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape


# ----- dict -> XML -----

def dict_to_manifest_xml(d: dict) -> str:
    """Serialise a manifest dict to XML string.

    All top-level scalar keys become child text elements. 'contents' and
    'cross_refs' are rendered as structured sub-elements.
    """
    parts: list[str] = ['<?xml version="1.0" encoding="utf-8"?>', "<manifest>"]

    scalar_keys = ("bundle_id", "graph_type", "format_version", "created_at", "author")
    for key in scalar_keys:
        if key in d:
            parts.append(f"  <{key}>{xml_escape(str(d[key]))}</{key}>")

    # any extra scalar keys the caller added
    known = set(scalar_keys) | {"contents", "cross_refs"}
    for key, val in d.items():
        if key not in known and isinstance(val, str):
            parts.append(f"  <{key}>{xml_escape(val)}</{key}>")

    if "contents" in d:
        parts.append("  <contents>")
        for entry in d["contents"]:
            path = xml_escape(entry.get("path", ""))
            role = xml_escape(entry.get("role", ""))
            parts.append(f'    <file path="{path}" role="{role}"/>')
        parts.append("  </contents>")

    if "cross_refs" in d:
        parts.append("  <cross_refs>")
        for ref in d["cross_refs"]:
            from_ = xml_escape(ref.get("from", ""))
            to = xml_escape(ref.get("to", ""))
            relation = xml_escape(ref.get("relation", ""))
            parts.append(f'    <ref from="{from_}" to="{to}" relation="{relation}"/>')
        parts.append("  </cross_refs>")

    parts.append("</manifest>\n")
    return "\n".join(parts)


# ----- XML -> dict -----

def manifest_to_dict(xml_text: str) -> dict:
    """Parse manifest XML into a plain dict.

    Scalar child elements become string values. <contents> becomes a list of
    dicts with 'path' and 'role'. <cross_refs> becomes a list of dicts with
    'from', 'to', and 'relation'.
    """
    root = ET.fromstring(xml_text)
    d: dict = {}

    structured = {"contents", "cross_refs"}

    for child in root:
        tag = child.tag

        if tag == "contents":
            d["contents"] = [
                {"path": f.get("path", ""), "role": f.get("role", "")}
                for f in child
                if f.tag == "file"
            ]

        elif tag == "cross_refs":
            d["cross_refs"] = [
                {
                    "from": r.get("from", ""),
                    "to": r.get("to", ""),
                    "relation": r.get("relation", ""),
                }
                for r in child
                if r.tag == "ref"
            ]

        else:
            d[tag] = (child.text or "").strip()

    return d
