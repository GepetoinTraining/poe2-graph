"""graph — passive-tree + atlas-tree + build-construction graph layer.

The load-bearing core: byte URL codec, JSON tree loaders, NetworkX graph
queries, mutable Allocation builder, .build file IO, stat string parsing.

This is where one wrong field type bricks the in-game .build render, so
the precision here is deliberate. Use explicit submodule imports — the
namespace is intentionally not re-exported at package level to avoid
shadowing (build_reader and build_writer both export BuildFile etc.).

Standard import patterns:
    from graph.parser import parse, encode_url, Build
    from graph.resolvers import Tree, load_passive_tree
    from graph.allocation import Allocation
    from graph.network import build_graph, shortest_path, steiner_route
    from graph import build_writer  # then build_writer.BuildFile etc.
    from graph import build_reader  # then build_reader.BuildFile etc.
    from graph import stats
"""
