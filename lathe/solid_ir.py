"""Solid IR: boundary-representation primitives for the shape stage.

Represents solids as half-space / CSG-friendly structures used
internally by scaffold compilation and feature fusion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SolidOp:
    """SolidOp."""

    op: str
    primitive_type: str
    part: str
    region: str | None
    component: str | None
    params: dict[str, Any]
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class SolidIR:
    """SolidIR."""

    asset_name: str
    family: str
    operations: list[SolidOp]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return {
            "asset_name": self.asset_name,
            "family": self.family,
            "operations": [operation.to_dict() for operation in self.operations],
            "notes": list(self.notes),
        }
