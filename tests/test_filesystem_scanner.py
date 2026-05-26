from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import filesystem_scanner as fs  # noqa: E402


def _fake_probes(tmp_path) -> list[fs.Probe]:
    """Build probes pointing at tmp paths so tests are hermetic."""
    return [
        fs.Probe(
            name="fake_pob",
            game="poe1",
            candidate_paths=[str(tmp_path / "PathOfBuilding")],
            tags=["pob_user"],
        ),
        fs.Probe(
            name="fake_overlay",
            game="poe1",
            candidate_paths=[str(tmp_path / "missing"), str(tmp_path / "PoeOverlay")],
            tags=["trade_overlay_user"],
        ),
        fs.Probe(
            name="fake_neither",
            game="poe2",
            candidate_paths=[str(tmp_path / "definitely_missing")],
            tags=["should_not_appear"],
        ),
    ]


def test_scan_returns_one_result_per_probe(tmp_path):
    (tmp_path / "PathOfBuilding").mkdir()
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    assert len(results) == 3


def test_scan_marks_found_correctly(tmp_path):
    (tmp_path / "PathOfBuilding").mkdir()
    (tmp_path / "PoeOverlay").mkdir()
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    by_name = {r.probe.name: r for r in results}
    assert by_name["fake_pob"].found
    assert by_name["fake_overlay"].found
    assert not by_name["fake_neither"].found


def test_scan_records_first_matching_candidate(tmp_path):
    """Probe with multiple candidates picks the first that exists."""
    (tmp_path / "PoeOverlay").mkdir()  # second candidate
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    overlay = next(r for r in results if r.probe.name == "fake_overlay")
    assert overlay.found
    assert overlay.matched_path == tmp_path / "PoeOverlay"


def test_found_tags_dedupes_and_sorts(tmp_path):
    (tmp_path / "PathOfBuilding").mkdir()
    (tmp_path / "PoeOverlay").mkdir()
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    tags = fs.found_tags(results)
    assert tags == ["pob_user", "trade_overlay_user"]
    assert "should_not_appear" not in tags


def test_tools_per_game_groups_results(tmp_path):
    (tmp_path / "PathOfBuilding").mkdir()
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    per_game = fs.tools_per_game(results)
    assert per_game == {"poe1": ["fake_pob"]}


def test_count_filter_files(tmp_path):
    """The poe1_userdata probe counts .filter files in its dir."""
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    (userdata / "my.filter").write_text("dummy")
    (userdata / "second.filter").write_text("dummy")
    (userdata / "notes.txt").write_text("dummy")  # should not be counted

    probe = fs.Probe(
        name="poe1_userdata",
        game="poe1",
        candidate_paths=[str(userdata)],
        tags=["poe1_user_data"],
    )
    results = fs.scan([probe])
    assert results[0].extra["filter_files"] == 2
    assert results[0].extra["filter_engagement"] == "custom"


def test_count_filter_files_zero_means_default(tmp_path):
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    probe = fs.Probe(
        name="poe1_userdata", game="poe1",
        candidate_paths=[str(userdata)], tags=[],
    )
    results = fs.scan([probe])
    assert results[0].extra["filter_files"] == 0
    assert results[0].extra["filter_engagement"] == "default"


def test_count_build_files(tmp_path):
    """The poe2_buildplanner probe counts .build files."""
    bp = tmp_path / "BuildPlanner"
    bp.mkdir()
    (bp / "stormweaver.build").write_text("{}")
    probe = fs.Probe(
        name="poe2_buildplanner", game="poe2",
        candidate_paths=[str(bp)], tags=["buildplanner_aware"],
    )
    results = fs.scan([probe])
    assert results[0].extra["build_files"] == 1


def test_summary_is_human_readable(tmp_path):
    (tmp_path / "PathOfBuilding").mkdir()
    probes = _fake_probes(tmp_path)
    results = fs.scan(probes)
    text = fs.summary(results)
    assert "PoE 1" in text
    assert "PoE 2" in text
    assert "fake_pob" in text
    assert "[OK]" in text
    assert "[--]" in text


def test_known_probes_have_unique_names():
    """Sanity check on the registry."""
    names = [p.name for p in fs.KNOWN_PROBES]
    assert len(names) == len(set(names)), "duplicate probe names in KNOWN_PROBES"


def test_known_probes_each_have_at_least_one_path():
    for p in fs.KNOWN_PROBES:
        assert len(p.candidate_paths) >= 1, f"{p.name} has no candidate paths"


def test_known_probes_all_game_tagged_or_explicitly_none():
    for p in fs.KNOWN_PROBES:
        assert p.game in (None, "poe1", "poe2"), f"{p.name} has invalid game={p.game}"
