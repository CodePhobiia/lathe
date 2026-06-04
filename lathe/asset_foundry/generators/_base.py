"""Foundry generator base types.

A FoundryAsset is the typed output of any generator: it carries
geometry refs (zones + meshes from PrismMesh/HalfSpacePolyhedron),
semantic sockets, material slots, collision spec, lod policy intent,
style binding, and generator provenance (seed + parameters hash).

Generators do NOT execute geometry kernels. They emit declarative
specifications. The runtime cooker (Foundry F6) consumes these specs
and produces the final mesh + collision + LOD chain + bake artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

GENERATOR_BASE_VERSION = "lathe.asset_foundry.generator_base_v1"


@dataclass(frozen=True)
class SemanticSocket:
    """A socket / attachment point on an asset."""

    socket_id: str
    role: str
    """Semantic role: ``door_entry``, ``lantern_mount``,
    ``waterfall_source``, ``crystal_glow``, ``walkable_endpoint``,
    ``hinge_axis``, etc."""

    position_cm: tuple[float, float, float]
    orientation_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    """Quaternion ``(x, y, z, w)`` in asset-local frame."""

    capacity: int = 1
    """How many compatible attachments fit."""

    allowed_attachments: tuple[str, ...] = ()
    """Optional whitelist of compatible attachment role tokens."""


@dataclass(frozen=True)
class MaterialSlot:
    """One material binding for the asset."""

    slot_id: str
    zone_id_prefix: str
    """Zones whose IDs start with this prefix bind to this slot."""

    material_class: str
    """Material class token from the style pack
    (``wall_plaster``, ``crystal_violet_emissive``, ...)."""

    palette_token: str = ""
    """Optional palette token override."""

    uv_policy: str = "default"
    """One of ``default``, ``trim_sheet``, ``world_scale``,
    ``triplanar``, ``planar_projection``."""


@dataclass(frozen=True)
class CollisionSpec:
    """Spec for the asset's collision proxy."""

    strategy: str
    """One of ``hull``, ``compound_hulls``, ``box``,
    ``capsule``, ``walkable_surface_only``, ``none``."""

    walkable_zones: tuple[str, ...] = ()
    """Zone IDs that contribute to walkable nav (top surface of an
    island, plank ribbon on a bridge, path tiles, etc.)."""

    blocking_zones: tuple[str, ...] = ()
    """Zone IDs that block movement (cliff edges, building walls)."""

    hazard_zones: tuple[str, ...] = ()
    """Zone IDs flagged as hazards (drop edges, waterfall volume)."""


@dataclass(frozen=True)
class LodPolicy:
    """Spec for the LOD chain."""

    lod_levels: int = 4
    target_triangle_counts: tuple[int, ...] = (25000, 8000, 2000, 500)
    """Per-LOD budget. Length should equal lod_levels."""

    preserve_silhouette: bool = True
    drop_at_lod_features: Mapping[str, int] = field(default_factory=dict)
    """feature_name -> LOD index where the feature gets dropped (e.g.
    ``{"fastener_grid": 2, "decal_zone": 3}``)."""


@dataclass(frozen=True)
class GeneratorSpec:
    """The declarative spec one generator emits."""

    generator_id: str
    """Stable name (e.g. ``violet_crystal_cluster``)."""

    parameters: Mapping[str, Any]
    """The parameter set that produced this spec (for reproducibility)."""

    seed: int
    style_pack_id: str
    family: str
    """Object family token (``container``, ``architecture``, ``prop``,
    ``environment_piece``, ``furniture``, ``machine``, ``weapon``)."""

    semantic_parts: tuple[str, ...]
    """Top-level semantic part names emitted by the generator."""

    geometry_payload: Mapping[str, Any]
    """Generator-specific structured geometry: ``mesh`` (PrismMesh /
    HalfSpacePolyhedron), ``transforms``, ``scattered_instances``,
    etc. Generator-defined shape; serializable."""

    material_slots: tuple[MaterialSlot, ...]
    sockets: tuple[SemanticSocket, ...]
    collision: CollisionSpec
    lod_policy: LodPolicy
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FoundryAsset:
    """A full Foundry asset spec ready for runtime cooking + packaging."""

    asset_id: str
    spec: GeneratorSpec
    bbox_cm: tuple[tuple[float, float, float], tuple[float, float, float]]
    quality_ladder_target: int = 5
    """Quality ladder level target (per masterplan §13).
    5 = game-ready. 6 = scene-ready. 7 = hero-quality."""

    notes: str = ""


__all__ = [
    "GENERATOR_BASE_VERSION",
    "CollisionSpec",
    "FoundryAsset",
    "GeneratorSpec",
    "LodPolicy",
    "MaterialSlot",
    "SemanticSocket",
]
