"""Phase 5 internal ShapeIR v2 semantic-operation model + v1 adapter.

Adds a richer authoring layer for shape construction without changing
the runtime handoff. The stable
``lathe.shape.intent_mesh_handoff_v1`` contract is preserved: v2 is an
internal IR used by Phase 6 (grammar lowering) and beyond, while v1
remains the runtime hand-off shape.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 10.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 5.
Architecture reference: ``docs/architecture/shape-ir-v2.md``.

Design summary
--------------

v2 introduces two frozen dataclasses:

- ``ShapeOp`` — one semantic operation (``op``, ``target``, ``parameters``,
  ``purpose``).
- ``ShapeProgram`` — an ordered tuple of ``ShapeOp`` plus ``version``,
  ``asset_name`` and an optional ``family`` hint.

Operations are organised into six families (30 total):

- ``SOLID_OPS`` (6) — primitive solids that introduce new geometry.
- ``BOOLEAN_OPS`` (7) — boolean and construction modifiers.
- ``EDGE_OPS`` (4) — edge-control modifiers (bevels, weighted normals).
- ``REPETITION_OPS`` (5) — semantic repetition / detail strips.
- ``INTEGRATION_OPS`` (4) — attachment / seating ops (sockets, brackets).
- ``WEAR_OPS`` (4) — wear / damage authoring ops.

Required parameters per op are defined in ``_REQUIRED_PARAMS``.

Diagnostic codes
----------------

Adapter and validator emit the following stable diagnostic codes:

- ``unsupported_v2_op`` — the op name is not a member of ``ALL_OPS``.
- ``missing_required_param`` — a required parameter is absent. Each
  missing key yields its own diagnostic; the missing key name follows
  the colon (``missing_required_param: <key>``).
- ``no_v1_equivalent`` — the op is valid in v2 but the v1 IR has no
  primitive that models it. The op is recorded for Phase 6/7+ but is
  not emitted as a v1 record.
- ``parameter_type_mismatch`` — reserved for a future phase. The
  current ``validate_op`` only checks for parameter *presence*; a
  later pass (Phase 8 or earlier, on demand) will type-check parameter
  *values* and emit this code when a value's type does not match the
  expected schema for its op.

Phase placement
---------------

Phase 5 is **internal IR + adapter only**. It does not register a
validator, does not add a top-level key to the validate-stage report,
and does not change ``.lth`` syntax, the schema, or the v1 shape
bundle. Phase 6 will use this infrastructure to lower the
industrial_crate grammar into v2 operations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


_V1Lowerer = Callable[["ShapeOp"], dict[str, Any]]


SHAPE_IR_V2_VERSION = "shape_ir_v2"


SOLID_OPS: frozenset[str] = frozenset(
    {
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.prism",
        "solid.rail",
        "solid.panel",
    }
)


BOOLEAN_OPS: frozenset[str] = frozenset(
    {
        "op.union",
        "op.subtract",
        "op.intersect",
        "op.inset",
        "op.extrude",
        "op.shell",
        "op.cut_panel_line",
    }
)


EDGE_OPS: frozenset[str] = frozenset(
    {
        "op.bevel",
        "op.chamfer",
        "op.weighted_normals",
        "op.mark_hard_edge",
    }
)


REPETITION_OPS: frozenset[str] = frozenset(
    {
        "op.repeat",
        "op.fastener_grid",
        "op.vent_slats",
        "op.trim_band",
        "op.corner_guard_set",
    }
)


INTEGRATION_OPS: frozenset[str] = frozenset(
    {
        "op.socket",
        "op.bracket",
        "op.mount_plate",
        "op.weld_seam",
    }
)


WEAR_OPS: frozenset[str] = frozenset(
    {
        "op.chip_edges",
        "op.scratch_mask",
        "op.dent_mask",
        "op.grime_mask",
    }
)


ALL_OPS: frozenset[str] = (
    SOLID_OPS | BOOLEAN_OPS | EDGE_OPS | REPETITION_OPS | INTEGRATION_OPS | WEAR_OPS
)


_REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    # Solids
    "solid.box": ("width_cm", "height_cm", "depth_cm"),
    "solid.rounded_box": ("width_cm", "height_cm", "depth_cm", "radius_cm"),
    "solid.cylinder": ("radius_cm", "height_cm"),
    "solid.prism": ("width_cm", "height_cm", "depth_cm"),
    "solid.rail": ("length_cm", "profile_cm"),
    "solid.panel": ("width_cm", "height_cm", "thickness_cm"),
    # Boolean / construction
    "op.union": (),
    "op.subtract": (),
    "op.intersect": (),
    "op.inset": ("depth_cm",),
    "op.extrude": ("depth_cm",),
    "op.shell": ("thickness_cm",),
    "op.cut_panel_line": ("width_cm",),
    # Edge control
    "op.bevel": ("width_cm", "segments"),
    "op.chamfer": ("width_cm",),
    "op.weighted_normals": (),
    "op.mark_hard_edge": (),
    # Repetition / detail
    "op.repeat": ("count", "axis"),
    "op.fastener_grid": ("rows", "columns", "spacing_cm"),
    "op.vent_slats": ("count", "spacing_cm"),
    "op.trim_band": ("width_cm",),
    "op.corner_guard_set": ("size_cm",),
    # Integration
    "op.socket": ("clearance_cm",),
    "op.bracket": ("clearance_cm", "mount_type"),
    "op.mount_plate": ("width_cm", "height_cm"),
    "op.weld_seam": ("width_cm",),
    # Wear / damage
    "op.chip_edges": ("amount",),
    "op.scratch_mask": ("amount",),
    "op.dent_mask": ("amount",),
    "op.grime_mask": ("amount",),
}


@dataclass(frozen=True)
class ShapeOp:
    """One semantic shape operation in a ShapeProgram.

    ``target`` is ``None`` for solids that introduce new geometry rather
    than modifying an existing region (e.g. ``solid.box``). ``purpose``
    is an optional human-readable string captured for trace/report use.
    """

    op: str
    target: str | None
    parameters: dict[str, Any]
    purpose: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this operation."""
        return {
            "op": self.op,
            "target": self.target,
            "parameters": dict(self.parameters),
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class ShapeProgram:
    """An ordered sequence of v2 shape operations for a single asset.

    Operations are stored in declaration order; ``to_dict`` preserves
    that order so the JSON shape is deterministic.
    """

    version: str
    asset_name: str
    family: str | None
    ops: tuple[ShapeOp, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for this program."""
        return {
            "version": self.version,
            "asset_name": self.asset_name,
            "family": self.family,
            "ops": [op.to_dict() for op in self.ops],
        }


@dataclass(frozen=True)
class V1AdapterResult:
    """Result of lowering a :class:`ShapeProgram` to v1 records.

    ``v1_records`` are dicts shaped to be compatible with the v1
    ``ShapePrimitive`` payload. ``diagnostics`` collects per-op codes
    (``unsupported_v2_op``, ``missing_required_param``,
    ``no_v1_equivalent``). ``unsupported_ops`` deduplicates the op names
    that had no v1 equivalent; the order matches first occurrence.
    """

    v1_records: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...]
    unsupported_ops: tuple[str, ...]


def validate_op(op: ShapeOp) -> tuple[bool, list[str]]:
    """Return ``(is_valid, diagnostics)`` for ``op``.

    Checks:

    1. ``op.op`` is a member of :data:`ALL_OPS`. If not, returns
       ``(False, ["unsupported_v2_op"])`` and no further checks run.
    2. Every key in ``_REQUIRED_PARAMS[op.op]`` is present in
       ``op.parameters``. Each missing key yields a diagnostic of the
       form ``"missing_required_param: <key>"``.

    Diagnostics are returned as a list of strings in declaration order.
    """
    if op.op not in ALL_OPS:
        return (False, ["unsupported_v2_op"])

    diagnostics: list[str] = []
    required = _REQUIRED_PARAMS.get(op.op, ())
    parameters = op.parameters if isinstance(op.parameters, dict) else {}
    for key in required:
        if key not in parameters:
            diagnostics.append(f"missing_required_param: {key}")
    return (not diagnostics, diagnostics)


def _v1_record_for_solid_box(op: ShapeOp) -> dict[str, Any]:
    """Lower a ``solid.box`` op to a v1-compatible record."""
    parameters = op.parameters
    width = float(parameters["width_cm"])
    height = float(parameters["height_cm"])
    depth = float(parameters["depth_cm"])
    return {
        "primitive_type": "box",
        "part": op.target or "body",
        "center": (0.0, 0.0, 0.0),
        "extents": (width, height, depth),
        "tags": [],
        "blend_mode": "union",
        "rounding": 0.0,
        "v2_op": op.op,
        "v2_purpose": op.purpose,
    }


def _v1_record_for_solid_rounded_box(op: ShapeOp) -> dict[str, Any]:
    """Lower a ``solid.rounded_box`` op to a v1 box record + rounding."""
    parameters = op.parameters
    width = float(parameters["width_cm"])
    height = float(parameters["height_cm"])
    depth = float(parameters["depth_cm"])
    radius = float(parameters["radius_cm"])
    return {
        "primitive_type": "box",
        "part": op.target or "body",
        "center": (0.0, 0.0, 0.0),
        "extents": (width, height, depth),
        "tags": ["rounded"],
        "blend_mode": "union",
        "rounding": radius,
        "v2_op": op.op,
        "v2_purpose": op.purpose,
    }


def _v1_record_for_solid_cylinder(op: ShapeOp) -> dict[str, Any]:
    """Lower a ``solid.cylinder`` op to a v1-compatible cylinder record."""
    parameters = op.parameters
    radius = float(parameters["radius_cm"])
    height = float(parameters["height_cm"])
    return {
        "primitive_type": "cylinder",
        "part": op.target or "body",
        "center": (0.0, 0.0, 0.0),
        "radius": radius,
        "height": height,
        "axis": "y",
        "tags": [],
        "blend_mode": "union",
        "rounding": 0.0,
        "v2_op": op.op,
        "v2_purpose": op.purpose,
    }


def _v1_record_for_solid_prism(op: ShapeOp) -> dict[str, Any]:
    """Lower a ``solid.prism`` op to a v1 box record (best-effort).

    v1 does not model prisms directly; we approximate as an axis-aligned
    box with the same extents and tag the record as ``prism_approx``.
    """
    parameters = op.parameters
    width = float(parameters["width_cm"])
    height = float(parameters["height_cm"])
    depth = float(parameters["depth_cm"])
    return {
        "primitive_type": "box",
        "part": op.target or "body",
        "center": (0.0, 0.0, 0.0),
        "extents": (width, height, depth),
        "tags": ["prism_approx"],
        "blend_mode": "union",
        "rounding": 0.0,
        "v2_op": op.op,
        "v2_purpose": op.purpose,
    }


_V1_LOWERERS: dict[str, _V1Lowerer] = {
    "solid.box": _v1_record_for_solid_box,
    "solid.rounded_box": _v1_record_for_solid_rounded_box,
    "solid.cylinder": _v1_record_for_solid_cylinder,
    "solid.prism": _v1_record_for_solid_prism,
}


def lower_to_v1(program: ShapeProgram) -> V1AdapterResult:
    """Lower a :class:`ShapeProgram` to v1-compatible records.

    Walks ``program.ops`` in declaration order. For each op:

    - If the op name is not a member of :data:`ALL_OPS`, emit an
      ``unsupported_v2_op`` diagnostic and record the op name in
      ``unsupported_ops``. No v1 record is produced.
    - If any required parameter is absent, emit one
      ``missing_required_param`` diagnostic per missing key and skip
      the v1 record.
    - If the op is a v1-lowerable solid (``solid.box``,
      ``solid.rounded_box``, ``solid.cylinder``, ``solid.prism``),
      produce the corresponding v1 record.
    - Otherwise the op is valid in v2 but has no v1 equivalent: emit a
      ``no_v1_equivalent`` diagnostic. The op is recorded for Phase 6/7+
      consumers; no v1 record is produced.

    Determinism: identical inputs always yield identical outputs;
    operation order is preserved.
    """
    v1_records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    unsupported_ops: list[str] = []
    seen_unsupported: set[str] = set()

    for op in program.ops:
        if op.op not in ALL_OPS:
            diagnostics.append(
                {
                    "code": "unsupported_v2_op",
                    "op": op.op,
                    "reason": (
                        f"op '{op.op}' is not a member of any ShapeIR v2 "
                        "operation family"
                    ),
                }
            )
            if op.op not in seen_unsupported:
                unsupported_ops.append(op.op)
                seen_unsupported.add(op.op)
            continue

        required = _REQUIRED_PARAMS.get(op.op, ())
        parameters = op.parameters if isinstance(op.parameters, dict) else {}
        missing = [key for key in required if key not in parameters]
        if missing:
            for key in missing:
                diagnostics.append(
                    {
                        "code": "missing_required_param",
                        "op": op.op,
                        "reason": f"required parameter '{key}' is absent",
                    }
                )
            continue

        lowerer = _V1_LOWERERS.get(op.op)
        if lowerer is None:
            diagnostics.append(
                {
                    "code": "no_v1_equivalent",
                    "op": op.op,
                    "reason": (
                        f"op '{op.op}' is valid in ShapeIR v2 but has no "
                        "v1 primitive equivalent"
                    ),
                }
            )
            continue

        v1_records.append(lowerer(op))

    return V1AdapterResult(
        v1_records=tuple(v1_records),
        diagnostics=tuple(diagnostics),
        unsupported_ops=tuple(unsupported_ops),
    )
