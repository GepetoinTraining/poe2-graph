"""farm — farming cycle lifecycle for poe2-graph.

Public API (all functions imported here for convenience):

    declare_cycle   -- insert cycle root + targets + inputs; status='DECLARED'
    open_cycle      -- DECLARED -> ACTIVE; records currency snapshot
    record_output   -- append an output node to an ACTIVE cycle
    classify_outputs-- mod-regex classification pass (§5)
    reconcile_cycle -- double-booked reconciliation query (§5)
    close_cycle     -- ACTIVE -> CLOSED; computes ROI / hit-rate / div-per-hour
    get_cycle       -- full cycle dict (outputs included)
    list_cycles     -- filter by status / farm_target
    export_cycle_bundle -- serialize closed cycle to .farm.graph bundle
"""

from __future__ import annotations

from farm.lifecycle import declare_cycle, open_cycle, record_output, get_cycle, list_cycles
from farm.classify import classify_outputs
from farm.reconcile import reconcile_cycle
from farm.summarize import close_cycle
from farm.export import export_cycle_bundle

__all__ = [
    "declare_cycle",
    "open_cycle",
    "record_output",
    "classify_outputs",
    "reconcile_cycle",
    "close_cycle",
    "get_cycle",
    "list_cycles",
    "export_cycle_bundle",
]
