"""``lathe.surface.zone_binding_v1`` — intent zones survive topology.

The pre-contract failure mode (per newresearch §5 + §B8): every face
in the final fused mesh collapses to a single label, so material
zones, UV groups, decals, and wear masks all lose their attribution
target. The structural fix is to attach ``ZoneTag`` records to faces
at synthesis time and carry them through the topology/UV/surface
stages so the package stage can group faces by zone and emit
UsdGeomSubsets or glTF mesh primitives with material slot bindings.

This module defines the contract surface: ``ZoneTag``, ``ZoneAtlas``,
and the grouping helpers the surface/package stages call.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.surface.zone_binding_v1"


@dataclass(frozen=True)
class ZoneTag:
    """A semantic tag attached to a face / face group.

    All fields are optional except ``zone_id``. Downstream stages read
    whichever fields they care about — the surface stage reads
    ``material_class`` + ``uv_policy``, the UV stage reads
    ``texel_weight`` + ``uv_policy``, the package stage reads all of
    them when emitting subsets.
    """

    zone_id: str
    material_class: str = "unspecified"
    uv_policy: str = "box_projected_worldscale"
    decal_allowed: bool = False
    wear_role: str = ""
    source_node_id: str = ""
    feature_id: str = ""
    style_role: str = ""
    contact_role: str = ""
    exposure_role: str = ""
    texel_weight: float = 1.0
    lod_importance: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FaceZoneAssignment:
    """Per-face ZoneTag reference. Used by topology + surface stages."""

    face_index: int
    zone_id: str


@dataclass(frozen=True)
class ZoneAtlas:
    """A collection of ZoneTags + face assignments for one mesh."""

    zones: tuple[ZoneTag, ...]
    face_assignments: tuple[FaceZoneAssignment, ...]

    def zone_by_id(self, zone_id: str) -> ZoneTag | None:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        return None

    def face_count(self) -> int:
        return len(self.face_assignments)

    def faces_for_zone(self, zone_id: str) -> tuple[int, ...]:
        return tuple(
            fa.face_index for fa in self.face_assignments if fa.zone_id == zone_id
        )


def group_faces_by_material_class(atlas: ZoneAtlas) -> dict[str, list[int]]:
    """Return {material_class: [face_index, ...]} for the package stage.

    Faces whose zone has no material_class fall under the
    ``"unspecified"`` bucket so the exporter can still emit them.
    """
    by_material: dict[str, list[int]] = {}
    zone_map = {z.zone_id: z for z in atlas.zones}
    for fa in atlas.face_assignments:
        zone = zone_map.get(fa.zone_id)
        if zone is None:
            by_material.setdefault("unspecified", []).append(fa.face_index)
            continue
        by_material.setdefault(zone.material_class or "unspecified", []).append(fa.face_index)
    return by_material


def group_faces_by_uv_policy(atlas: ZoneAtlas) -> dict[str, list[int]]:
    """Return {uv_policy: [face_index, ...]} for the UV stage."""
    by_policy: dict[str, list[int]] = {}
    zone_map = {z.zone_id: z for z in atlas.zones}
    for fa in atlas.face_assignments:
        zone = zone_map.get(fa.zone_id)
        policy = zone.uv_policy if zone is not None else "box_projected_worldscale"
        by_policy.setdefault(policy, []).append(fa.face_index)
    return by_policy


def atlas_from_face_parts(
    face_parts: Iterable[str],
    region_id_by_part: Mapping[str, str] | None = None,
    material_by_region: Mapping[str, str] | None = None,
) -> ZoneAtlas:
    """Build a ZoneAtlas from existing face_parts attribution.

    Used by the topology stage as a bridge from the legacy face_parts
    list (one label per face) to the new zone-tag system. Each unique
    face_part becomes one zone; the optional dicts let callers route
    parts → region_ids → material classes.
    """
    region_map = dict(region_id_by_part or {})
    material_map = dict(material_by_region or {})
    unique_parts = list(dict.fromkeys(face_parts))  # preserve order
    zones: list[ZoneTag] = []
    for part in unique_parts:
        region_id = region_map.get(part, part)
        material_class = material_map.get(region_id, "unspecified")
        zones.append(
            ZoneTag(
                zone_id=region_id,
                material_class=material_class,
                source_node_id=part,
                feature_id=part,
            )
        )
    face_assignments: list[FaceZoneAssignment] = []
    for idx, part in enumerate(face_parts):
        face_assignments.append(
            FaceZoneAssignment(face_index=idx, zone_id=region_map.get(part, part))
        )
    return ZoneAtlas(zones=tuple(zones), face_assignments=tuple(face_assignments))


__all__ = [
    "CONTRACT_VERSION",
    "ZoneTag",
    "FaceZoneAssignment",
    "ZoneAtlas",
    "group_faces_by_material_class",
    "group_faces_by_uv_policy",
    "atlas_from_face_parts",
]
