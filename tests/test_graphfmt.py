"""Tests for the graphfmt package — .X.graph format dispatch."""

from __future__ import annotations

import gzip
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import graphfmt  # noqa: E402
from graphfmt import (  # noqa: E402
    detect_format,
    read_graph,
    write_graph,
    read_bundle,
    write_bundle,
    read_single,
    write_single,
    dict_to_manifest_xml,
    manifest_to_dict,
)


# ----- helpers -----

def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _gzip_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(text.encode("utf-8"))
    return buf.getvalue()


_MINIMAL_MANIFEST = {
    "bundle_id": "test_bundle",
    "graph_type": "farm",
    "format_version": "1",
    "created_at": "2026-05-27T00:00:00Z",
    "author": "TestAuthor",
    "contents": [
        {"path": "cycle.xml", "role": "primary"},
        {"path": "char.build", "role": "build_snapshot"},
    ],
    "cross_refs": [
        {"from": "cycle.xml", "to": "char.build", "relation": "ran_by"},
    ],
}


# ----- detect_format -----

def test_detect_format_zip_bytes():
    raw = _zip_bytes({"a.xml": b"<x/>"})
    assert detect_format(raw) == "zip"


def test_detect_format_gzip_bytes():
    raw = _gzip_bytes("<root/>")
    assert detect_format(raw) == "gzip"


def test_detect_format_plain_bytes():
    assert detect_format(b"<?xml version='1.0'?><root/>") == "plain"


def test_detect_format_plain_bytes_leading_whitespace():
    assert detect_format(b"  <manifest/>") == "plain"


def test_detect_format_unknown():
    assert detect_format(b"\x00\x01\x02\x03random garbage") == "unknown"


def test_detect_format_path_gzip(tmp_path):
    p = tmp_path / "test.farm.graph"
    write_single(p, "<root/>")
    assert detect_format(p) == "gzip"


def test_detect_format_path_zip(tmp_path):
    p = tmp_path / "test.farm.graph"
    write_bundle(p, manifest=_MINIMAL_MANIFEST, contents={})
    assert detect_format(p) == "zip"


# ----- single read/write round-trips -----

def test_single_roundtrip_simple(tmp_path):
    p = tmp_path / "out.farm.graph"
    xml = "<root><child/></root>"
    write_single(p, xml)
    assert read_single(p) == xml


def test_single_roundtrip_unicode_multiline(tmp_path):
    p = tmp_path / "out.craft.graph"
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<manifest>\n"
        "  <bundle_id>unicode_testé中文</bundle_id>\n"
        "  <author>Pedro García</author>\n"
        "</manifest>\n"
    )
    write_single(p, xml)
    assert read_single(p) == xml


# ----- bundle read/write round-trips -----

def test_bundle_roundtrip(tmp_path):
    p = tmp_path / "test.farm.graph"
    manifest = dict(_MINIMAL_MANIFEST)
    contents = {
        "cycle.xml": "<cycle><run id='1'/></cycle>",
        "char.build": '{"passives": []}',
    }
    readme = "This is the README for the test bundle."
    media = {"screenshot.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00"}

    write_bundle(p, manifest=manifest, contents=contents, readme=readme, media=media)
    result = read_bundle(p)

    assert result["manifest"]["bundle_id"] == "test_bundle"
    assert result["manifest"]["graph_type"] == "farm"
    assert result["contents"]["cycle.xml"] == contents["cycle.xml"]
    assert result["contents"]["char.build"] == contents["char.build"]
    assert result["readme"] == readme
    assert result["media"]["screenshot.png"] == media["screenshot.png"]


def test_bundle_without_readme_and_media(tmp_path):
    p = tmp_path / "bare.farm.graph"
    write_bundle(p, manifest=_MINIMAL_MANIFEST, contents={"a.xml": "<a/>"})
    result = read_bundle(p)
    assert result["readme"] is None
    assert result["media"] == {}
    assert result["contents"]["a.xml"] == "<a/>"


# ----- manifest dict <-> XML round-trip -----

def test_manifest_roundtrip_full():
    xml = dict_to_manifest_xml(_MINIMAL_MANIFEST)
    assert "<manifest>" in xml
    assert "<bundle_id>test_bundle</bundle_id>" in xml
    assert 'path="cycle.xml"' in xml
    assert 'role="primary"' in xml
    assert 'relation="ran_by"' in xml

    recovered = manifest_to_dict(xml)
    assert recovered["bundle_id"] == "test_bundle"
    assert recovered["graph_type"] == "farm"
    assert recovered["format_version"] == "1"
    assert recovered["author"] == "TestAuthor"
    assert len(recovered["contents"]) == 2
    assert recovered["contents"][0] == {"path": "cycle.xml", "role": "primary"}
    assert len(recovered["cross_refs"]) == 1
    assert recovered["cross_refs"][0] == {
        "from": "cycle.xml", "to": "char.build", "relation": "ran_by"
    }


def test_manifest_roundtrip_no_cross_refs():
    d = {
        "bundle_id": "nocross",
        "graph_type": "guide",
        "format_version": "1",
        "created_at": "2026-01-01T00:00:00Z",
        "author": "Bot",
        "contents": [{"path": "main.xml", "role": "primary"}],
    }
    xml = dict_to_manifest_xml(d)
    recovered = manifest_to_dict(xml)
    assert recovered["bundle_id"] == "nocross"
    assert "cross_refs" not in recovered
    assert recovered["contents"][0]["path"] == "main.xml"


# ----- read_graph dispatch -----

def test_read_graph_dispatches_gzip(tmp_path):
    p = tmp_path / "single.farm.graph"
    xml = "<root><node id='1'/></root>"
    write_single(p, xml)
    result = read_graph(p)
    assert result["kind"] == "single"
    assert result["xml"] == xml


def test_read_graph_dispatches_zip(tmp_path):
    p = tmp_path / "bundle.farm.graph"
    write_bundle(
        p,
        manifest=_MINIMAL_MANIFEST,
        contents={"cycle.xml": "<cycle/>"},
    )
    result = read_graph(p)
    assert result["kind"] == "bundle"
    assert result["manifest"]["bundle_id"] == "test_bundle"
    assert result["contents"]["cycle.xml"] == "<cycle/>"


def test_read_graph_dispatches_plain(tmp_path):
    p = tmp_path / "plain.farm.graph"
    xml = "<plain>hello</plain>"
    p.write_text(xml, encoding="utf-8")
    result = read_graph(p)
    assert result["kind"] == "single"
    assert result["xml"] == xml


def test_read_graph_raises_on_unknown(tmp_path):
    p = tmp_path / "garbage.farm.graph"
    p.write_bytes(b"\x00\x01\x02\x03garbage")
    try:
        read_graph(p)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unrecognised format" in str(exc)


# ----- write_graph dispatch -----

def test_write_graph_str_produces_gzip(tmp_path):
    p = tmp_path / "out.farm.graph"
    xml = "<farm><cycle/></farm>"
    write_graph(p, xml)
    assert detect_format(p) == "gzip"
    assert read_single(p) == xml


def test_write_graph_single_dict_produces_gzip(tmp_path):
    p = tmp_path / "out.craft.graph"
    xml = "<craft/>"
    write_graph(p, {"kind": "single", "xml": xml})
    assert detect_format(p) == "gzip"
    assert read_single(p) == xml


def test_write_graph_bundle_dict_produces_zip(tmp_path):
    p = tmp_path / "out.guide.graph"
    write_graph(p, {
        "kind": "bundle",
        "manifest": _MINIMAL_MANIFEST,
        "contents": {"guide.xml": "<guide/>"},
        "readme": "Hello",
        "media": None,
    })
    assert detect_format(p) == "zip"
    result = read_bundle(p)
    assert result["manifest"]["bundle_id"] == "test_bundle"
    assert result["contents"]["guide.xml"] == "<guide/>"
    assert result["readme"] == "Hello"


# ----- error cases -----

def test_missing_manifest_raises_value_error(tmp_path):
    p = tmp_path / "bad.farm.graph"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("cycle.xml", "<cycle/>")
    p.write_bytes(buf.getvalue())
    try:
        read_bundle(p)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "manifest.xml" in str(exc)


def test_media_bytes_exact_roundtrip(tmp_path):
    p = tmp_path / "media.farm.graph"
    # Simulate a PNG header followed by random bytes
    png_header = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
    write_bundle(
        p,
        manifest=_MINIMAL_MANIFEST,
        contents={},
        media={"image.png": png_header},
    )
    result = read_bundle(p)
    assert result["media"]["image.png"] == png_header
