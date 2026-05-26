from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import parser  # noqa: E402
import resolvers  # noqa: E402
import build_writer as bw  # noqa: E402
import build_reader as br  # noqa: E402


PEDRO_URL = (ROOT / "examples" / "pedro-stormweaver.txt").read_text().strip()


def test_markup_helpers_compose():
    assert bw.red("hi") == "<red>{hi}"
    assert bw.medium(bw.red("hi")) == "<m>{<red>{hi}}"
    assert bw.rgb(255, 128, 0, "x") == "<rgb(255,128,0)>{x}"


def test_passive_bare_string_when_no_annotations():
    p = bw.PassiveEntry(id="intelligence11")
    assert p.to_dict() == "intelligence11"


def test_passive_rich_when_annotated():
    p = bw.PassiveEntry(
        id="intelligence45",
        additional_text=bw.medium(bw.blue("Pick after Crit Overload")),
        level_interval=[55, 65],
        weapon_set=1,
    )
    out = p.to_dict()
    assert isinstance(out, dict)
    assert out["id"] == "intelligence45"
    assert out["weapon_set"] == 1
    assert out["level_interval"] == [55, 65]
    assert "<m>{<blue>{Pick after Crit Overload}}" == out["additional_text"]


def test_from_build_pedro_url():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    bf = bw.from_build(build, tree, name="Test", author="claude")

    assert bf.name == "Test"
    assert bf.author == "claude"
    assert bf.ascendancy == "Sorceress1"
    # 142 records all have string ids (no orphan-from-id nodes in this build)
    assert len(bf.passives) == 142


def test_from_build_preserves_weapon_set():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    bf = bw.from_build(build, tree)
    set_tagged = [p for p in bf.passives if p.weapon_set is not None]
    # spec §3: 28 + 5 = 33 records carry weapon_set
    assert len(set_tagged) == 33


def test_roundtrip_through_build_reader():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    bf = bw.from_build(build, tree, name="rt", author="claude")
    encoded = bf.to_json()
    decoded = br.parse(json.loads(encoded))
    assert decoded.name == "rt"
    assert decoded.author == "claude"
    assert decoded.ascendancy == "Sorceress1"
    assert len(decoded.passives) == 142
    decoded_ids = [p.id for p in decoded.passives]
    original_ids = [p.id for p in bf.passives]
    assert decoded_ids == original_ids


def test_validate_catches_unknown_passive():
    tree = resolvers.load_passive_tree()
    bf = bw.BuildFile(passives=[bw.PassiveEntry(id="totally_made_up_id")])
    warnings = bw.validate(bf, tree)
    assert any("totally_made_up_id" in w for w in warnings)


def test_validate_passes_for_real_ids():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    bf = bw.from_build(build, tree)
    assert bw.validate(bf, tree) == []


def test_annotations_apply():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    first_hash = build.records[0].node_hash
    note = bw.gold("starts here")
    bf = bw.from_build(build, tree, annotations={first_hash: note})
    found = [p for p in bf.passives if p.additional_text == note]
    assert len(found) == 1
