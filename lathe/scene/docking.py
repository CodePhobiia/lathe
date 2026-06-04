"""Asset-to-asset docking resolver (Wave 10 / research §10).

Each asset exports interface ports (``InterfacePort`` in
``lathe.runtime.asset_contract``). Docking matches source's port
against target's port by kind + dimensions + load + orientation +
clearance + style/material compatibility.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..runtime.asset_contract import InterfacePort

CONTRACT_VERSION = "lathe.scene.docking_v1"


# Compatible interface kinds. A source kind can dock with target kinds
# in its mapping.
_KIND_COMPATIBILITY: Mapping[str, frozenset[str]] = {
    "support_footprint": frozenset({"stack_receive", "support_surface_grid"}),
    "stack_receive": frozenset({"support_footprint"}),
    "support_surface_grid": frozenset({"support_footprint"}),
    "hinge_attach": frozenset({"hinge_target"}),
    "hinge_target": frozenset({"hinge_attach"}),
    "latch_target": frozenset({"latch_anchor"}),
    "latch_anchor": frozenset({"latch_target"}),
}


@dataclass(frozen=True)
class DockingResult:
    """Outcome of a docking attempt."""

    valid: bool
    source_port_id: str
    target_port_id: str
    transform_world_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rejection_reason: str = ""
    style_compatibility_score: float = 1.0


def kinds_compatible(source_kind: str, target_kind: str) -> bool:
    return target_kind in _KIND_COMPATIBILITY.get(source_kind, frozenset())


def dimensions_compatible(
    source: InterfacePort, target: InterfacePort, tolerance_cm: float = 5.0
) -> bool:
    """Are the source/target bounding regions within tolerance on each axis?"""
    sx, sy, sz = source.bounds_cm
    tx, ty, tz = target.bounds_cm
    return (
        abs(sx - tx) <= tolerance_cm
        and abs(sy - ty) <= tolerance_cm
        and abs(sz - tz) <= tolerance_cm
    )


def load_compatible(source: InterfacePort, target: InterfacePort) -> bool:
    """Does the target have enough load capacity for the source?

    For now: if the target declares a load_capacity_kg and the source's
    load_capacity_kg is non-zero (the source mass), require target ≥
    source. When either is unspecified (0), default to compatible.
    """
    if target.load_capacity_kg <= 0:
        return True
    if source.load_capacity_kg <= 0:
        return True
    return target.load_capacity_kg >= source.load_capacity_kg


def texel_density_score(source: InterfacePort, target: InterfacePort) -> float:
    """Texel-density matching score (1.0 = exact match, 0.0 = >2x mismatch)."""
    if source.texel_density <= 0 or target.texel_density <= 0:
        return 1.0
    ratio = source.texel_density / target.texel_density
    if ratio < 1.0:
        ratio = 1.0 / ratio
    if ratio <= 1.1:
        return 1.0
    if ratio >= 2.0:
        return 0.0
    return 1.0 - (ratio - 1.1) / 0.9


def attempt_dock(
    source: InterfacePort,
    target: InterfacePort,
    dimension_tolerance_cm: float = 5.0,
) -> DockingResult:
    """Try to dock source onto target. Returns a DockingResult."""
    if not kinds_compatible(source.kind, target.kind):
        return DockingResult(
            valid=False,
            source_port_id=source.interface_id,
            target_port_id=target.interface_id,
            rejection_reason=f"kind {source.kind!r} not compatible with {target.kind!r}",
        )
    if not dimensions_compatible(source, target, dimension_tolerance_cm):
        return DockingResult(
            valid=False,
            source_port_id=source.interface_id,
            target_port_id=target.interface_id,
            rejection_reason=(
                f"dimensions outside tolerance {dimension_tolerance_cm}cm: "
                f"source={source.bounds_cm} target={target.bounds_cm}"
            ),
        )
    if not load_compatible(source, target):
        return DockingResult(
            valid=False,
            source_port_id=source.interface_id,
            target_port_id=target.interface_id,
            rejection_reason=(
                f"target load_capacity_kg {target.load_capacity_kg} insufficient "
                f"for source {source.load_capacity_kg}"
            ),
        )
    style_score = texel_density_score(source, target)
    return DockingResult(
        valid=True,
        source_port_id=source.interface_id,
        target_port_id=target.interface_id,
        transform_world_cm=target.frame_cm,
        style_compatibility_score=style_score,
    )


def best_docking(
    source: InterfacePort,
    candidates: Iterable[InterfacePort],
    dimension_tolerance_cm: float = 5.0,
) -> DockingResult | None:
    """Try all candidate target ports; return the best-scoring valid dock or None."""
    best: DockingResult | None = None
    for c in candidates:
        result = attempt_dock(source, c, dimension_tolerance_cm)
        if not result.valid:
            continue
        if best is None or result.style_compatibility_score > best.style_compatibility_score:
            best = result
    return best


__all__ = [
    "CONTRACT_VERSION",
    "DockingResult",
    "kinds_compatible",
    "dimensions_compatible",
    "load_compatible",
    "texel_density_score",
    "attempt_dock",
    "best_docking",
]
