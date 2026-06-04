"""Assembly-kernel dataclasses and shared constants.

Extracted from :mod:`lathe.assembly_kernel` per the P1 module
decomposition (`docs/asset-quality/p0-p1-stabilization-execution-plan.md`
§6). The dataclasses define the assembly blueprint contract; the
constant pins the numeric tolerance used across the kernel.

The public names below are re-exported from ``lathe.assembly_kernel`` so
existing ``from lathe.assembly_kernel import BlueprintComponent`` and
``from lathe.assembly_kernel import AssemblyBlueprint`` callers continue
to work unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

NUMERIC_EPSILON = 1e-6


@dataclass
class BlueprintComponent:
    """BlueprintComponent."""

    name: str
    component_type: str
    part: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    tags: list[str] = field(default_factory=list)
    adjacency: list[str] = field(default_factory=list)
    axis: str = "y"
    radius: float | None = None
    height: float | None = None
    symmetry_mate: str | None = None
    interface_role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class AssemblyBlueprint:
    """AssemblyBlueprint."""

    blueprint_id: str
    family: str
    components: list[BlueprintComponent]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        payload = asdict(self)
        payload["components"] = [component.to_dict() for component in self.components]
        return payload


__all__ = [
    "NUMERIC_EPSILON",
    "AssemblyBlueprint",
    "BlueprintComponent",
]
