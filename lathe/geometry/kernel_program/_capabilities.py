"""Kernel capability probing + operand validation helpers.

This module groups the small cluster of helpers that interrogate a
:class:`~lathe.geometry.kernel.GeometryKernel` for its advertised
capabilities, enforce capability requirements before executing a
kernel program, and validate operand structure (blend modes, handle
presence, transform-matrix shape) before any kernel call is made.

Every helper here is pure — given the same inputs, returns the same
outputs or raises the same exception. They are the substrate the per-
operation executors call before doing real work.
"""

from __future__ import annotations

from ..kernel import GeometryKernel
from ._core import (
    KernelOperand,
    KernelProgramCapabilityError,
    _capability_names,
)

# Supported blend modes for kernel program operands. The per-op
# executors and operand validators consume this set.
_SUPPORTED_BLEND_MODES: frozenset[str] = frozenset(
    {"union", "subtract", "intersect"}
)


def _kernel_capabilities(kernel: GeometryKernel) -> dict[str, bool]:
    """Return the kernel's advertised capabilities as a {name: bool} dict.

    Probes the kernel via its ``probe()`` method. Tolerates kernels
    that raise on probe (returns an empty capability dict — caller's
    capability checks will then fail with a clear missing-capability
    diagnostic).
    """
    try:
        probe = kernel.probe()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return {}
    if not isinstance(probe, dict):
        return {}
    capabilities = probe.get("capabilities")
    if isinstance(capabilities, dict):
        return {
            str(name): bool(value)
            for name, value in capabilities.items()
            if isinstance(name, str)
        }
    return {name: True for name in _capability_names(capabilities)}


def _require_capabilities(
    kernel: GeometryKernel,
    capabilities: dict[str, bool],
    required: set[str],
) -> None:
    """Raise KernelProgramCapabilityError if any required capability is missing.

    "Missing" means the capability is not in the kernel's advertised
    set OR is advertised as ``False``. Both cases surface as a single
    explicit diagnostic with named missing capabilities.
    """
    missing = sorted(name for name in required if name not in capabilities)
    unsupported = sorted(
        name for name in required if capabilities.get(name) is False
    )
    if missing or unsupported:
        raise KernelProgramCapabilityError(
            kernel,
            required=required,
            advertised=capabilities,
            missing=missing,
            unsupported=unsupported,
        )


def _required_boolean_capabilities(
    operands: list[KernelOperand],
    *,
    batch_union_available: bool = False,
) -> set[str]:
    """Compute the kernel capabilities a boolean program requires.

    The returned set names the operations the kernel must support for
    the program to run without falling back. ``to_trimesh`` is always
    required because the result must be materialised; the boolean ops
    (``union`` / ``batch_union`` / ``difference`` / ``intersection``)
    depend on what the operand blend modes ask for.
    """
    union_count = sum(1 for operand in operands if operand.blend_mode == "union")
    subtract_count = sum(
        1 for operand in operands if operand.blend_mode == "subtract"
    )
    intersect_count = sum(
        1 for operand in operands if operand.blend_mode == "intersect"
    )
    required: set[str] = {"to_trimesh"}
    if union_count > 1:
        required.add("batch_union" if batch_union_available else "union")
    if subtract_count:
        required.add("difference")
    if intersect_count:
        required.add("intersection")
    return required


def _validate_operands(operands: list[KernelOperand]) -> None:
    """Reject empty operand lists and unsupported blend modes."""
    if not operands:
        raise ValueError("kernel program requires at least one operand")
    for operand in operands:
        if operand.blend_mode not in _SUPPORTED_BLEND_MODES:
            raise ValueError(
                "kernel program operand "
                f"{operand.operand_id!r} has unsupported "
                f"blend_mode={operand.blend_mode!r}"
            )


def _validate_hull_operands(operands: list[KernelOperand]) -> None:
    """Reject empty hull operand lists and operands with no handle."""
    if not operands:
        raise ValueError("kernel hull program requires at least one operand")
    for operand in operands:
        if operand.handle is None:
            raise ValueError(
                f"kernel hull operand {operand.operand_id!r} has no handle"
            )


def _validate_minkowski_operands(
    source: KernelOperand, structuring: KernelOperand
) -> None:
    """Reject minkowski operands with no handle on either source or structuring."""
    for role, operand in (("source", source), ("structuring", structuring)):
        if operand.handle is None:
            raise ValueError(
                f"kernel minkowski {role} operand "
                f"{operand.operand_id!r} has no handle"
            )


def _validate_transform_operand(source: KernelOperand) -> None:
    """Reject transform operand with no handle."""
    if source.handle is None:
        raise ValueError(
            f"kernel transform source operand "
            f"{source.operand_id!r} has no handle"
        )


def _validated_transform_matrix(matrix: list[list[float]]) -> list[list[float]]:
    """Coerce a transform matrix to a 4x4 float matrix or raise ValueError."""
    if not isinstance(matrix, list) or len(matrix) != 4:
        raise ValueError(
            "kernel transform matrix must be a 4x4 row-major numeric matrix"
        )
    out: list[list[float]] = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != 4:
            raise ValueError(
                "kernel transform matrix must be a 4x4 row-major numeric matrix"
            )
        out.append([float(value) for value in row])
    return out


__all__ = [
    "_SUPPORTED_BLEND_MODES",
    "_kernel_capabilities",
    "_require_capabilities",
    "_required_boolean_capabilities",
    "_validate_hull_operands",
    "_validate_minkowski_operands",
    "_validate_operands",
    "_validate_transform_operand",
    "_validated_transform_matrix",
]
