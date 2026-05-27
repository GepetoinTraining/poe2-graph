from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph import parser  # noqa: E402
from graph import resolvers  # noqa: E402
from graph import network as graph  # noqa: E402


PEDRO_URL = (ROOT / "examples" / "pedro-stormweaver.txt").read_text().strip()


def test_build_graph_node_count():
    tree = resolvers.load_passive_tree()
    g = graph.build_graph(tree)
    # Graph excludes the structural 'root' node (no skill hash).
    assert g.number_of_nodes() == 5101


def test_summarize_pedro_build():
    tree = resolvers.load_passive_tree()
    build = parser.parse(PEDRO_URL)
    summary = graph.summarize(build, tree)

    assert summary.character_class == "Sorceress"
    assert summary.ascendancy == "Stormweaver"
    assert summary.total_records == 142

    # Spec §3: 28 weapon-set-tagged + 5 set+override = 33 records have a weapon_set byte.
    # The other 109 records have weapon_set=None.
    set_tagged = sum(c for ws, c in summary.weapon_set_split.items() if ws is not None)
    assert set_tagged == 33

    # 34 skill_override + 5 set+override = 39 attribute choices were made.
    assert sum(summary.attribute_choices.values()) == 39


def test_diff_builds_self_is_no_diff():
    build = parser.parse(PEDRO_URL)
    d = graph.diff_builds(build, build)
    assert d["only_a"] == set()
    assert d["only_b"] == set()
    assert d["shared"] == graph.allocated_hashes(build)
