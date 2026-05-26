"""DOCS — frontmatter-driven navigation index over DOCS/*.md chapters.

The third XML-composed surface in the skill, alongside EXILE.xml (player state)
and GUIDES.xml (guide catalog). DOCS.xml routes Claude's reading: SKILL.md is
the always-loaded router, DOCS.xml is the always-loaded index, and DOCS/*.md
chapters are loaded only when DOCS.xml's `<when_to_read>` triggers match the
user's intent.

Each DOCS/*.md carries YAML frontmatter:

    ---
    id: <stable_slug>
    file: DOCS/<filename>.md
    topic: <one-line description>
    priority: reference | action | flow
    modules: [module_name, ...]
    tags: [tag, tag, ...]
    when_to_read: |
      <natural-language intent triggers>
    ---

    # Chapter title
    ...

`compose_docs_xml()` walks DOCS/, extracts frontmatter, emits the index.
`write_docs_xml()` writes it next to EXILE.xml in the project dir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

import yaml


DOCS_DIR = Path(__file__).parent / "DOCS"

_FM_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n(.*)$", re.DOTALL)


@dataclass
class DocEntry:
    id: str
    file: str
    topic: str
    priority: str = "reference"           # reference | action | flow
    modules: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    when_to_read: str = ""

    @classmethod
    def from_frontmatter(cls, path: Path, fm: dict) -> "DocEntry":
        return cls(
            id=fm.get("id") or path.stem,
            file=fm.get("file") or f"DOCS/{path.name}",
            topic=fm.get("topic", "").strip(),
            priority=fm.get("priority", "reference"),
            modules=list(fm.get("modules") or []),
            tags=list(fm.get("tags") or []),
            when_to_read=(fm.get("when_to_read") or "").strip(),
        )


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def load_all(base_dir: Optional[Path] = None) -> list[DocEntry]:
    base = base_dir or DOCS_DIR
    if not base.exists():
        return []
    out: list[DocEntry] = []
    for p in sorted(base.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(text)
        if not fm:
            continue
        out.append(DocEntry.from_frontmatter(p, fm))
    return out


def find_by_tag(tag: str, base_dir: Optional[Path] = None) -> list[DocEntry]:
    return [d for d in load_all(base_dir) if tag in d.tags]


def find_by_module(module: str, base_dir: Optional[Path] = None) -> list[DocEntry]:
    return [d for d in load_all(base_dir) if module in d.modules]


def compose_docs_xml(base_dir: Optional[Path] = None) -> str:
    """Build DOCS.xml from frontmatter of every DOCS/*.md."""
    parts: list[str] = ['<?xml version="1.0" encoding="utf-8"?>', "<docs>"]
    for d in load_all(base_dir):
        parts.append(
            f'  <doc id="{xml_escape(d.id)}" file="{xml_escape(d.file)}" '
            f'priority="{xml_escape(d.priority)}">'
        )
        if d.topic:
            parts.append(f'    <topic>{xml_escape(d.topic)}</topic>')
        if d.when_to_read:
            parts.append(f'    <when_to_read>{xml_escape(d.when_to_read)}</when_to_read>')
        for m in d.modules:
            parts.append(f'    <module name="{xml_escape(m)}"/>')
        for t in d.tags:
            parts.append(f'    <tag name="{xml_escape(t)}"/>')
        parts.append("  </doc>")
    parts.append("</docs>\n")
    return "\n".join(parts)


def write_docs_xml(out_path: Optional[Path] = None) -> Path:
    """Write DOCS.xml. Defaults next to EXILE.xml + GUIDES.xml."""
    import exile
    if out_path is None:
        out_path = exile.project_exile_xml_path().with_name("DOCS.xml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(compose_docs_xml(), encoding="utf-8")
    return out_path
