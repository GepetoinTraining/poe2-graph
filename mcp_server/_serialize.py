"""Helpers for converting toolkit dataclasses to JSON-safe payloads.

The MCP transport requires JSON-serializable returns. Most of poe2-graph's
dataclasses (PlayerGoal, SubGoal, SystemGuide, Creator, ...) round-trip
cleanly via `dataclasses.asdict`, but some carry frozensets, paths, or
nested dataclasses that need normalization.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively normalise a value for JSON serialization.

    Handles dataclasses, dicts, lists/tuples/sets/frozensets, Paths, and
    primitive types. Anything else falls back to repr() so the call never
    crashes — losing fidelity is better than crashing the tool surface.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((to_jsonable(v) for v in obj), key=lambda x: str(x))
    if hasattr(obj, "__dict__"):
        return {k: to_jsonable(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return repr(obj)
