"""Synthesizer trace schema.

A SynthesizerTrace captures every decision the procedural compiler
pipeline makes: which stage emitted which op, which knowledge pack
contributed which default, which policy added which node. Inspectable
at run time for debugging and at audit time for the Rule of Truth
("attempted_via" + "family_dispatch_used: false").

Trace entries are JSON-serializable so they survive into the
package's trace_manifest.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TRACE_KINDS: frozenset[str] = frozenset(
    {
        # Stage entries
        "stage_start",
        "stage_end",
        # Stage 1: resolve_context
        "alias_resolved",
        "alias_missing",
        "style_loaded",
        "policy_loaded",
        # Stage 2: normalize_graph
        "node_deduped",
        "edge_canonicalized",
        "unknown_node_type",
        # Stage 3: expand_policies
        "policy_applied",
        "policy_skipped_precondition",
        "policy_added_node",
        "policy_added_edge",
        # Stage 4: validate_attributes
        "attribute_schema_violation",
        "attribute_schema_extension",
        "attribute_validated",
        # Stage 5: topo_order
        "topo_order_resolved",
        "cycle_in_construction_graph",
        # Stage 5b: placement bindings (anchor-driven placement, M1)
        "placement_binding_start",
        "placement_binding_end",
        "placement_binding_resolved",
        "placement_binding_unresolved",
        "placement_binding_import_failed",
        "anchor_emit_failed",
        "relation_resolve_failed",
        # Stage 6: emit_node_ops
        "generator_resolved",
        "no_generator_for_node",
        "node_op",
        # Stage 7: emit_edge_ops
        "decorator_resolved",
        "no_decorator_for_edge",
        "edge_op",
        # Stage 8: validate_ops
        "emitted_op_outside_shape_ir_v2",
        "ops_validated",
        # Hint resolution
        "hint_resolved",
    }
)


@dataclass(frozen=True)
class TraceEntry:
    """One entry in a SynthesizerTrace. JSON-serializable.

    Fields:
        kind: a member of ``_TRACE_KINDS``. Determines what payload
            is meaningful for this entry.
        stage: which of the 8 pipeline stages emitted this entry
            (``1``-``8``), or ``0`` for cross-stage entries.
        payload: arbitrary JSON-serializable detail.
    """

    kind: str
    stage: int
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in _TRACE_KINDS:
            raise ValueError(
                f"TraceEntry kind {self.kind!r} not in known trace kinds. "
                f"Add it to trace._TRACE_KINDS if this is a legitimate new "
                f"kind."
            )
        if not isinstance(self.stage, int) or not (0 <= self.stage <= 8):
            raise ValueError(
                f"TraceEntry stage must be int 0-8, got {self.stage!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "stage": self.stage, "payload": dict(self.payload)}


@dataclass(frozen=True)
class SynthesizerTrace:
    """All trace entries from one synthesis call.

    ``family_dispatch_used`` is set to ``False`` by construction in
    the pipeline. Any non-False value here means a family-name
    dispatch leaked in and must be hunted down before the next
    commit.
    """

    entries: tuple[TraceEntry, ...]
    family_dispatch_used: bool
    attempted_via: str  # "procedural_engine" canonical

    def __post_init__(self) -> None:
        if self.family_dispatch_used is not False:
            # Hard error — the synthesizer is supposed to never dispatch
            # on family. Tripping this means a regression.
            raise AssertionError(
                "SynthesizerTrace.family_dispatch_used must be False; "
                "the procedural engine does not dispatch on family name."
            )
        if not isinstance(self.entries, tuple):
            raise TypeError("SynthesizerTrace.entries must be a tuple")
        if not isinstance(self.attempted_via, str) or not self.attempted_via:
            raise ValueError("SynthesizerTrace.attempted_via must be non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "family_dispatch_used": self.family_dispatch_used,
            "attempted_via": self.attempted_via,
        }

    def entries_for_stage(self, stage: int) -> tuple[TraceEntry, ...]:
        """Filter entries by stage. Cross-stage entries (stage=0) excluded."""
        return tuple(entry for entry in self.entries if entry.stage == stage)

    def entries_of_kind(self, kind: str) -> tuple[TraceEntry, ...]:
        """Filter entries by kind."""
        return tuple(entry for entry in self.entries if entry.kind == kind)


class TraceBuilder:
    """Mutable trace accumulator for the pipeline.

    The pipeline holds a TraceBuilder during synthesis and freezes it
    to a SynthesizerTrace at the end. TraceBuilder is intentionally
    mutable — synthesis is sequential — but its frozen output is what
    downstream code consumes.
    """

    def __init__(self) -> None:
        self._entries: list[TraceEntry] = []

    def emit(self, kind: str, stage: int, **payload: Any) -> None:
        self._entries.append(TraceEntry(kind=kind, stage=stage, payload=payload))

    def freeze(self) -> SynthesizerTrace:
        return SynthesizerTrace(
            entries=tuple(self._entries),
            family_dispatch_used=False,
            attempted_via="procedural_engine",
        )

    def __len__(self) -> int:
        return len(self._entries)
