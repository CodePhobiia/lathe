"""Surface IR: V1.2 surface-stage intermediate representation.

Captures the lowered ``surface_control_pack``, atlas assembly,
decal and mask programs that feed the surface backend.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SurfaceIR:
    """SurfaceIR."""
    program: str = ""
    material_graph: str = ""
    backend: str = ""
    policy: str = ""
    patterns: list[str] = field(default_factory=list)
    palette: str = ""
    material_zones: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    decals: list[str] = field(default_factory=list)
    bake: list[str] = field(default_factory=list)
    decal_libraries: list[str] = field(default_factory=list)
    mask_programs: list[str] = field(default_factory=list)
    trim_sheets: list[str] = field(default_factory=list)
    authoring: dict[str, Any] = field(default_factory=dict)
    resolved_surface_program: dict[str, Any] = field(default_factory=dict)
    resolved_material_graph: dict[str, Any] = field(default_factory=dict)
    resolved_surface_backend: dict[str, Any] = field(default_factory=dict)
    resolved_surface_policy: dict[str, Any] = field(default_factory=dict)
    resolved_patterns: list[dict[str, Any]] = field(default_factory=list)
    resolved_palette: dict[str, Any] = field(default_factory=dict)
    resolved_materials: dict[str, Any] = field(default_factory=dict)
    resolved_decal_libraries: list[dict[str, Any]] = field(default_factory=list)
    resolved_mask_programs: list[dict[str, Any]] = field(default_factory=list)
    resolved_trim_sheets: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "SurfaceIR":
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        surface = asset.get("surface", {})
        return cls(
            program=str(surface.get("program", "")),
            material_graph=str(surface.get("material_graph", "")),
            backend=str(surface.get("backend", "")),
            policy=str(surface.get("policy", "")),
            patterns=list(surface.get("patterns", [])),
            palette=str(surface.get("palette", "")),
            material_zones=list(surface.get("material_zones", [])),
            materials=list(surface.get("materials", [])),
            decals=list(surface.get("decals", [])),
            bake=list(surface.get("bake", [])),
            decal_libraries=list(surface.get("decal_libraries", [])),
            mask_programs=list(surface.get("mask_programs", [])),
            trim_sheets=list(surface.get("trim_sheets", [])),
            authoring=dict(surface.get("authoring", {})),
            resolved_surface_program=dict(surface.get("resolved_surface_program", {})),
            resolved_material_graph=dict(surface.get("resolved_material_graph", {})),
            resolved_surface_backend=dict(surface.get("resolved_surface_backend", {})),
            resolved_surface_policy=dict(surface.get("resolved_surface_policy", {})),
            resolved_patterns=list(surface.get("resolved_patterns", [])),
            resolved_palette=dict(surface.get("resolved_palette", {})),
            resolved_materials=dict(surface.get("resolved_materials", {})),
            resolved_decal_libraries=list(surface.get("resolved_decal_libraries", [])),
            resolved_mask_programs=list(surface.get("resolved_mask_programs", [])),
            resolved_trim_sheets=list(surface.get("resolved_trim_sheets", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
