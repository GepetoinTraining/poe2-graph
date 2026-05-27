"""System guide + creator + case study lookup tools."""

from __future__ import annotations

from typing import Any, Optional

import guides

from ._serialize import to_jsonable


def load_system_guide(guide_id: str) -> Optional[dict[str, Any]]:
    """Return the SystemGuide for `guide_id` (or None)."""
    sg = guides.load_system_guide(guide_id)
    return to_jsonable(sg) if sg is not None else None


def list_system_guides(*, game: Optional[str] = None) -> list[dict[str, Any]]:
    """All SystemGuides, optionally filtered by game ('poe1' | 'poe2' | 'both')."""
    sgs = guides.list_system_guides()
    if game is not None:
        sgs = [sg for sg in sgs if sg.game in (game, "both")]
    return [to_jsonable(sg) for sg in sgs]


def system_guides_for_edge(edge_name: str) -> list[dict[str, Any]]:
    """SystemGuides whose `transmits` includes `edge_name`."""
    return [to_jsonable(sg) for sg in guides.system_guides_for_edge(edge_name)]


def load_creator(handle: str) -> Optional[dict[str, Any]]:
    """Return one Creator by handle (or None)."""
    c = guides.load_creator(handle)
    return to_jsonable(c) if c is not None else None


def list_creators(*, community_filter: Optional[str] = None) -> list[dict[str, Any]]:
    """All Creators. `community_filter` matches a style_tag, e.g. 'community_women'."""
    creators = guides.list_creators()
    if community_filter:
        creators = [c for c in creators if community_filter in (getattr(c, "style_tags", []) or [])]
    return [to_jsonable(c) for c in creators]


def creators_who_transmit(edge_name: str, min_confidence: float = 0.5) -> list[dict[str, Any]]:
    """Creators whose transmits an edge at `min_confidence` or above."""
    return [to_jsonable(c) for c in guides.creators_who_transmit(edge_name, min_confidence=min_confidence)]


def load_case_study(case_id: str) -> Optional[dict[str, Any]]:
    """Return one case study by id (or None)."""
    cs = guides.load_case_study(case_id)
    return to_jsonable(cs) if cs is not None else None


def list_case_studies() -> list[dict[str, Any]]:
    """All case studies."""
    return [to_jsonable(cs) for cs in guides.list_case_studies()]


def load_edge_taxonomy() -> list[dict[str, Any]]:
    """The 16-edge taxonomy (postures + patterns that distinguish skilled play)."""
    return [to_jsonable(e) for e in guides.load_edge_taxonomy()]
