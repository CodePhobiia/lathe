"""Foundry generator: AlpinePine (stylized low-poly pine tree).

Per masterplan §16.4 + northstar §10.3.3. Stacked conical foliage
masses on a tapered trunk, flat normals, scale variants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..polyhedron import build_prism_mesh
from ._base import (
    CollisionSpec,
    FoundryAsset,
    GeneratorSpec,
    LodPolicy,
    MaterialSlot,
    SemanticSocket,
)

_GENERATOR_ID = "alpine_pine"


@dataclass(frozen=True)
class AlpinePineParameters:
    seed: int = 0
    trunk_height_cm: float = 30.0
    trunk_base_radius_cm: float = 4.5
    trunk_top_radius_cm: float = 3.0
    foliage_layers: int = 4
    """Number of stacked conical foliage masses."""
    foliage_base_radius_cm: float = 28.0
    foliage_layer_height_cm: float = 22.0
    foliage_sides: int = 6
    """Per-foliage-layer prism sides (low-poly faceted)."""
    foliage_top_taper: float = 0.6
    asymmetry_factor: float = 0.15
    """Lateral asymmetry in foliage layer placement (0 = perfectly
    symmetric)."""


def build_alpine_pine(
    params: AlpinePineParameters | None = None,
    *,
    asset_id: str = "alpine_pine_a",
) -> FoundryAsset:
    """Build an AlpinePine asset spec."""
    p = params if params is not None else AlpinePineParameters()
    # Trunk prism.
    trunk_mesh = build_prism_mesh(
        sides=6,
        base_radius_cm=p.trunk_base_radius_cm,
        height_cm=p.trunk_height_cm,
        top_radius_cm=p.trunk_top_radius_cm,
        base_z_cm=0.0,
        zone_prefix=f"{asset_id}.trunk",
    )
    # Foliage prisms — stacked.
    foliage_meshes: list[dict[str, Any]] = []
    current_z = p.trunk_height_cm * 0.4
    for layer in range(p.foliage_layers):
        t = layer / max(1, p.foliage_layers - 1) if p.foliage_layers > 1 else 0.0
        base_r = p.foliage_base_radius_cm * (1.0 - 0.55 * t)
        top_r = base_r * max(0.0, 1.0 - p.foliage_top_taper)
        layer_h = p.foliage_layer_height_cm * (1.0 - 0.25 * t)
        # Asymmetric offset based on seed + layer.
        offset_x = (
            ((p.seed * (layer + 1)) % 1000 / 1000.0 - 0.5) * p.asymmetry_factor * base_r
        )
        offset_y = (
            ((p.seed * (layer + 3)) % 1000 / 1000.0 - 0.5) * p.asymmetry_factor * base_r
        )
        mesh = build_prism_mesh(
            sides=p.foliage_sides,
            base_radius_cm=base_r,
            height_cm=layer_h,
            top_radius_cm=top_r,
            base_z_cm=current_z,
            twist_deg=15.0 * layer,
            zone_prefix=f"{asset_id}.foliage_{layer:02d}",
        )
        foliage_meshes.append(
            {
                "layer": layer,
                "translation_cm": [offset_x, offset_y, 0.0],
                "base_z_cm": current_z,
                "base_radius_cm": base_r,
                "top_radius_cm": top_r,
                "height_cm": layer_h,
                "vertex_count": mesh.vertex_count(),
                "face_count": mesh.face_count(),
                "zone_id_prefix": f"{asset_id}.foliage_{layer:02d}",
            }
        )
        current_z += layer_h * 0.65

    bbox_cm = (
        (-p.foliage_base_radius_cm, -p.foliage_base_radius_cm, 0.0),
        (p.foliage_base_radius_cm, p.foliage_base_radius_cm, current_z),
    )

    geometry_payload: dict[str, Any] = {
        "kind": "stacked_conical_tree",
        "trunk": {
            "zone_id_prefix": f"{asset_id}.trunk",
            "vertex_count": trunk_mesh.vertex_count(),
            "face_count": trunk_mesh.face_count(),
            "height_cm": p.trunk_height_cm,
            "base_radius_cm": p.trunk_base_radius_cm,
            "top_radius_cm": p.trunk_top_radius_cm,
        },
        "foliage_layers": foliage_meshes,
    }

    material_slots = (
        MaterialSlot(
            slot_id="trunk",
            zone_id_prefix=f"{asset_id}.trunk",
            material_class="wood_warm_brown",
            uv_policy="world_scale",
        ),
        MaterialSlot(
            slot_id="foliage_high",
            zone_id_prefix=f"{asset_id}.foliage_03",
            material_class="tree_teal",
        ),
        MaterialSlot(
            slot_id="foliage_mid",
            zone_id_prefix=f"{asset_id}.foliage_02",
            material_class="tree_deep_green",
        ),
        MaterialSlot(
            slot_id="foliage_lower",
            zone_id_prefix=f"{asset_id}.foliage",
            material_class="tree_olive",
        ),
    )

    sockets = (
        SemanticSocket(
            socket_id="root_anchor",
            role="ground_anchor",
            position_cm=(0.0, 0.0, 0.0),
        ),
        SemanticSocket(
            socket_id="top_marker",
            role="scatter_anchor_top",
            position_cm=(0.0, 0.0, current_z),
        ),
    )

    collision = CollisionSpec(
        strategy="capsule",
        walkable_zones=(),
        blocking_zones=(f"{asset_id}.trunk",),
        hazard_zones=(),
    )

    lod_policy = LodPolicy(
        lod_levels=4,
        target_triangle_counts=(2500, 800, 250, 80),
        preserve_silhouette=True,
        drop_at_lod_features={"asymmetric_offset": 2},
    )

    spec = GeneratorSpec(
        generator_id=_GENERATOR_ID,
        parameters={
            "seed": p.seed,
            "trunk_height_cm": p.trunk_height_cm,
            "trunk_base_radius_cm": p.trunk_base_radius_cm,
            "trunk_top_radius_cm": p.trunk_top_radius_cm,
            "foliage_layers": p.foliage_layers,
            "foliage_base_radius_cm": p.foliage_base_radius_cm,
            "foliage_layer_height_cm": p.foliage_layer_height_cm,
            "foliage_sides": p.foliage_sides,
            "foliage_top_taper": p.foliage_top_taper,
            "asymmetry_factor": p.asymmetry_factor,
        },
        seed=p.seed,
        style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
        family="environment_piece",
        semantic_parts=("trunk",) + tuple(f"foliage_{i:02d}" for i in range(p.foliage_layers)),
        geometry_payload=geometry_payload,
        material_slots=material_slots,
        sockets=sockets,
        collision=collision,
        lod_policy=lod_policy,
        diagnostics=(),
    )

    return FoundryAsset(
        asset_id=asset_id,
        spec=spec,
        bbox_cm=bbox_cm,
        quality_ladder_target=5,
        notes="Foundry F5 — AlpinePine stacked conical foliage.",
    )


__all__ = ["AlpinePineParameters", "build_alpine_pine"]
