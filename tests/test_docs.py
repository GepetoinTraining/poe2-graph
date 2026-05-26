"""Tests for the DOCS.xml composer + DOCS/*.md frontmatter loading."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import docs  # noqa: E402


# ----- loading the shipped corpus -----

def test_load_all_finds_all_chapters():
    entries = docs.load_all()
    ids = {e.id for e in entries}
    expected = {
        "byte-format", "build-construction", "graph-queries", "goals",
        "guides", "exile", "poe2db", "updater",
    }
    assert expected <= ids, f"missing: {expected - ids}"


def test_each_entry_has_frontmatter_fields():
    for e in docs.load_all():
        assert e.id, f"{e.file}: missing id"
        assert e.topic, f"{e.id}: missing topic"
        assert e.when_to_read, f"{e.id}: missing when_to_read"
        assert e.priority in ("reference", "action", "flow"), \
            f"{e.id}: bad priority {e.priority!r}"


def test_find_by_tag():
    matches = docs.find_by_tag("two_id")
    assert any(e.id == "byte-format" for e in matches)


def test_find_by_module():
    matches = docs.find_by_module("allocation")
    assert any(e.id == "build-construction" for e in matches)


# ----- xml composer -----

def test_compose_docs_xml_includes_all_entries():
    xml = docs.compose_docs_xml()
    assert "<docs>" in xml
    assert "</docs>" in xml
    for doc_id in ("byte-format", "goals", "guides", "exile"):
        assert f'id="{doc_id}"' in xml


def test_compose_docs_xml_has_when_to_read_blocks():
    xml = docs.compose_docs_xml()
    assert "<when_to_read>" in xml
    assert "</when_to_read>" in xml


def test_compose_docs_xml_has_module_and_tag_elements():
    xml = docs.compose_docs_xml()
    assert '<module name="allocation"/>' in xml
    assert '<tag name="goals"/>' in xml


def test_write_docs_xml_to_tmp(tmp_path):
    out = tmp_path / "DOCS.xml"
    docs.write_docs_xml(out_path=out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert content.startswith('<?xml version="1.0"')
    assert "<docs>" in content


# ----- custom base_dir -----

def test_load_all_with_custom_base_dir(tmp_path):
    base = tmp_path / "DOCS"
    base.mkdir()
    (base / "test.md").write_text(
        "---\n"
        "id: test\n"
        "file: DOCS/test.md\n"
        "topic: A test chapter\n"
        "priority: reference\n"
        "tags: [test]\n"
        "modules: [foo]\n"
        "when_to_read: when testing\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    entries = docs.load_all(base_dir=base)
    assert len(entries) == 1
    assert entries[0].id == "test"
    assert entries[0].tags == ["test"]
    assert entries[0].modules == ["foo"]


def test_compose_with_custom_base_dir(tmp_path):
    base = tmp_path / "DOCS"
    base.mkdir()
    (base / "one.md").write_text(
        "---\nid: one\nfile: DOCS/one.md\ntopic: T\ntags: [a]\nwhen_to_read: x\n---\nb\n",
        encoding="utf-8",
    )
    xml = docs.compose_docs_xml(base_dir=base)
    assert 'id="one"' in xml
    assert '<tag name="a"/>' in xml
