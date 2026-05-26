from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import parser  # noqa: E402
import resolvers  # noqa: E402
import graph  # noqa: E402
from allocation import Allocation  # noqa: E402


PEDRO_URL = (ROOT / "examples" / "pedro-stormweaver.txt").read_text().strip()


def _world():
    tree = resolvers.load_passive_tree()
    g = graph.build_graph(tree)
    return tree, g


# ----- class start lookup (verifies the classStartIndex array fix) -----

def test_class_start_resolves_for_all_twelve_classes():
    tree, g = _world()
    for class_id in range(12):
        start = graph.class_start_node(tree, class_id)
        assert start is not None, f"no start node for class {class_id}"
        assert start in g, f"start node {start} for class {class_id} not in graph"


def test_paired_classes_share_start():
    """PoE 2's new classes share start positions with the originals."""
    tree, _ = _world()
    # (original, paired)
    pairs = [(0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11)]
    for original, paired in pairs:
        assert graph.class_start_node(tree, original) == graph.class_start_node(tree, paired)


def test_ascendancy_start_lookup():
    tree, g = _world()
    asc = graph.ascendancy_start_node(tree, "Sorceress1")  # Stormweaver
    assert asc is not None
    assert asc in g


# ----- mutation basics -----

def test_new_allocation_is_empty():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress", "Stormweaver")
    assert len(alloc) == 0
    assert alloc.character_class == 7
    assert alloc.ascendancy == 1


def test_allocate_by_string_id_and_by_hash():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    rec = alloc.allocate("intelligence11")
    assert rec.node_hash in alloc
    alloc.allocate(rec.node_hash)  # idempotent
    assert len(alloc) == 1


def test_allocate_unknown_id_raises():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    try:
        alloc.allocate("definitely_not_a_real_node")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_deallocate():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    alloc.allocate("intelligence11")
    assert alloc.deallocate("intelligence11") is True
    assert len(alloc) == 0
    assert alloc.deallocate("intelligence11") is False  # idempotent


# ----- load + roundtrip -----

def test_from_url_round_trip():
    tree, g = _world()
    alloc = Allocation.from_url(PEDRO_URL, tree, g)
    assert len(alloc) == 142
    assert alloc.character_class == 7
    assert alloc.ascendancy == 1
    # Identity round-trip
    assert alloc.to_url() == PEDRO_URL


def test_pedro_build_is_contiguous():
    tree, g = _world()
    alloc = Allocation.from_url(PEDRO_URL, tree, g)
    assert alloc.is_contiguous, f"unexpected orphans: {alloc.orphans()}"


# ----- pathing -----

def test_extend_to_witch_ancestral_bond_is_17_hops():
    """Spec §4 sanity check, now via the Allocation API."""
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Witch")  # share start with Sorceress
    # extend from class start to Ancestral Bond
    cost = alloc.cost_to(45202)  # Ancestral Bond hash
    assert cost == 17, f"expected 17, got {cost}"
    newly = alloc.extend_to(45202)
    assert 45202 in alloc
    assert len(newly) == 17
    assert alloc.is_contiguous


def test_extend_to_already_allocated_is_noop():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Witch")
    alloc.extend_to(45202)
    again = alloc.extend_to(45202)
    assert again == []


def test_route_through_multi_target_is_at_most_sum_of_singles():
    """Steiner tree should be <= the sum of independent shortest paths."""
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Witch")
    # Independent costs
    cost_a = alloc.cost_to(45202)  # Ancestral Bond
    # Use any other reachable notable in the main tree
    # Find a real notable that's far from the class start
    reachable_notables = [
        h for h, a in g.nodes(data=True)
        if a.get("isNotable") and not a.get("ascendancyId")
    ]
    target_b = reachable_notables[0]
    cost_b = alloc.cost_to(target_b)
    newly = alloc.route_through(45202, target_b)
    assert len(newly) <= cost_a + cost_b
    assert 45202 in alloc
    assert target_b in alloc


# ----- frontier + nearest notables -----

def test_frontier_grows_with_allocations():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    initial = alloc.frontier
    assert len(initial) > 0  # class start has neighbors
    start = alloc.class_start_hash
    assert start in g
    # Allocate one of the neighbors; frontier should change.
    one = next(iter(initial))
    alloc.allocate(one)
    assert one not in alloc.frontier


def test_nearest_unallocated_notables_returns_sorted():
    tree, g = _world()
    alloc = Allocation.new(tree, g, "Sorceress")
    near = alloc.nearest_unallocated_notables(limit=5)
    assert len(near) == 5
    distances = [d for _, d in near]
    assert distances == sorted(distances)
