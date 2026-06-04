"""Core data types and operation-count helpers for the KernelProgram.

This module is the lowest-dependency leaf of the kernel_program
package. It defines:

- :class:`KernelOperand` — one already-built kernel handle plus its
  construction provenance.
- :class:`KernelProgramResult` — executed kernel-program output and
  trace metadata.
- :class:`KernelProgramCapabilityError` — raised when a kernel does
  not explicitly support a required capability.
- Per-operation ``*_operation_count`` helpers — small pure functions
  that compute how many backend calls a kernel program will need.

Every other module in ``lathe/geometry/kernel_program/`` imports its
public names from here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import trimesh

from ..kernel import GeometryKernel


@dataclass(frozen=True)
class KernelOperand:
    """One already-built kernel handle plus its construction provenance."""

    operand_id: str
    handle: Any
    source_mesh: trimesh.Trimesh | None = None
    blend_mode: str = "union"
    part: str | None = None
    primitive_type: str | None = None
    source_index: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    source_mesh_face_count: int | None = None
    source_mesh_watertight: bool | None = None
    source_mesh_body_count: int | None = None
    source_mesh_repaired: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def trace_record(self) -> dict[str, Any]:
        """Return serializable provenance without the opaque kernel handle."""
        return {
            "id": self.operand_id,
            "blend_mode": self.blend_mode,
            "part": self.part,
            "primitive_type": self.primitive_type,
            "source_index": self.source_index,
            "tags": list(self.tags),
            "source_mesh_face_count": self.source_mesh_face_count,
            "source_mesh_watertight": self.source_mesh_watertight,
            "source_mesh_body_count": self.source_mesh_body_count,
            "source_mesh_repaired": self.source_mesh_repaired,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class KernelProgramResult:
    """Executed kernel-program output and trace metadata."""

    mesh: trimesh.Trimesh
    handle: Any
    operation_count: int
    details: dict[str, Any]


class KernelProgramCapabilityError(ValueError):
    """Raised when a kernel does not explicitly support a required capability."""

    def __init__(
        self,
        kernel: GeometryKernel,
        *,
        required: set[str],
        advertised: dict[str, bool],
        missing: list[str],
        unsupported: list[str],
    ) -> None:
        self.details = {
            "code": "kernel_program_missing_capability",
            "kernel": getattr(kernel, "name", ""),
            "required_capabilities": sorted(required),
            "advertised_capabilities": sorted(advertised),
            "missing_capabilities": list(missing),
            "unsupported_capabilities": list(unsupported),
        }
        self.code = str(self.details["code"])
        super().__init__(
            f"geometry kernel {getattr(kernel, 'name', '')!r} does not explicitly "
            f"support required capabilities: {sorted(set(missing) | set(unsupported))!r}"
        )


# ----- Per-operation count helpers -----
#
# Each function computes how many backend kernel calls a given kernel
# program will need. Pure functions; no side effects; trivially
# testable.


def boolean_operation_count(operands: list[KernelOperand]) -> int:
    """Return the number of boolean calls needed for this ordered program."""
    union_count = sum(1 for operand in operands if operand.blend_mode == "union")
    subtract_count = sum(1 for operand in operands if operand.blend_mode == "subtract")
    intersect_count = sum(1 for operand in operands if operand.blend_mode == "intersect")
    if union_count:
        return max(0, union_count - 1) + subtract_count + intersect_count
    return max(0, intersect_count - 1) + subtract_count


def boolean_kernel_call_count(
    operands: list[KernelOperand],
    *,
    batch_union_available: bool = False,
) -> int:
    """Return the estimated backend calls needed for this boolean program."""
    union_count = sum(1 for operand in operands if operand.blend_mode == "union")
    subtract_count = sum(1 for operand in operands if operand.blend_mode == "subtract")
    intersect_count = sum(1 for operand in operands if operand.blend_mode == "intersect")
    if union_count:
        union_calls = 1 if batch_union_available and union_count > 1 else max(0, union_count - 1)
        return union_calls + subtract_count + intersect_count
    return max(0, intersect_count - 1) + subtract_count


def hull_operation_count(operands: list[KernelOperand]) -> int:
    """Return the number of kernel calls needed for a convex-hull program."""
    return 1 if operands else 0


def minkowski_operation_count(
    source: KernelOperand | None, structuring: KernelOperand | None
) -> int:
    """Return the kernel-program calls needed for a Minkowski construction."""
    return 1 if source is not None and structuring is not None else 0


def transform_operation_count(source: KernelOperand | None) -> int:
    """Return the number of kernel calls needed for a transform program."""
    return 1 if source is not None else 0


def deform_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a deform program."""
    return 1 if source is not None else 0


def refine_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a mesh refine program."""
    return 1 if source is not None else 0


def carve_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a mesh carve program."""
    return 1 if source is not None else 0


def polyextrude_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a polyextrude program."""
    return 1 if source is not None else 0


def component_assembly_operation_count(operands: list[KernelOperand]) -> int:
    """Return the number of traced calls represented by a component assembly."""
    if not operands:
        return 0
    if any(
        str(operand.blend_mode or "union") in {"subtract", "intersect"}
        for operand in operands
    ):
        return boolean_operation_count(operands)
    return 1


def profile_path_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a profile/path program."""
    return 1 if source is not None else 0


def sdf_field_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by an implicit-field program."""
    return 1 if source is not None else 0


def terrain_field_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced calls represented by a terrain heightfield program."""
    return 1 if source is not None else 0


def import_operation_count(source: KernelOperand | None) -> int:
    """Return the number of traced import calls represented by this program."""
    return 1 if source is not None else 0


def instances_operation_count(
    source: KernelOperand | None, matrices: list[list[list[float]]]
) -> int:
    """Return kernel calls needed for transform-each + union instances."""
    if source is None or not matrices:
        return 0
    return len(matrices) + max(0, len(matrices) - 1)


# ----- Capability helpers (used by per-op executors) -----


def _capability_names(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return (str(name) for name in value)
    if isinstance(value, Iterable):
        return (str(name) for name in value)
    return (str(value),)


def _required_capability_list(
    capabilities: Iterable[str] | str,
    *extra: Any,
) -> list[str]:
    ordered: list[str] = []
    for capability_group in (capabilities, *extra):
        for capability in _capability_names(capability_group):
            text = str(capability or "").strip()
            if text and text not in ordered:
                ordered.append(text)
    return ordered


def _exact_rebuild_required_capabilities(payload: dict[str, Any] | None) -> list[str]:
    """Return capabilities required by exact rebuild paths that must inspect output."""
    if not isinstance(payload, dict):
        return []
    return _required_capability_list(
        payload.get("required_capabilities") or [],
        "to_trimesh",
    )


__all__ = [
    "KernelOperand",
    "KernelProgramCapabilityError",
    "KernelProgramResult",
    "_capability_names",
    "_exact_rebuild_required_capabilities",
    "_required_capability_list",
    "boolean_kernel_call_count",
    "boolean_operation_count",
    "carve_operation_count",
    "component_assembly_operation_count",
    "deform_operation_count",
    "hull_operation_count",
    "import_operation_count",
    "instances_operation_count",
    "minkowski_operation_count",
    "polyextrude_operation_count",
    "profile_path_operation_count",
    "refine_operation_count",
    "sdf_field_operation_count",
    "terrain_field_operation_count",
    "transform_operation_count",
]
