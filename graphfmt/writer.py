"""Top-level writer: dispatches by content shape."""

from __future__ import annotations

from pathlib import Path

from graphfmt.bundle import write_bundle
from graphfmt.single import write_single


def write_graph(path: Path | str, content) -> None:
    """Write a .X.graph file, dispatching by content shape.

    content may be:
      str                           -> gzip single-doc
      {'kind': 'single', 'xml': s} -> gzip single-doc
      {'kind': 'bundle', ...}       -> zip bundle (keys forwarded to write_bundle)
    """
    if isinstance(content, str):
        write_single(path, content)
        return

    if isinstance(content, dict):
        kind = content.get("kind")

        if kind == "single":
            write_single(path, content["xml"])
            return

        if kind == "bundle":
            write_bundle(
                path,
                manifest=content["manifest"],
                contents=content.get("contents", {}),
                readme=content.get("readme"),
                media=content.get("media"),
            )
            return

    raise TypeError(
        f"write_graph: expected str or dict with 'kind', got {type(content).__name__!r}"
    )
