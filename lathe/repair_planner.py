from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .assembly_kernel import refresh_shape_ir
from .asset_graph import AssetGraph
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


@dataclass
class SemanticRepairAction:
    action: str
    target: str
    reason: str
    details: dict[str, Any]
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _find_region(shape_ir: ShapeIR, name: str) -> ShapeRegion | None:
    return next((region for region in shape_ir.regions if region.name == name or region.part == name), None)


def _find_primitive_indices(shape_ir: ShapeIR, region_name: str) -> list[int]:
    return [index for index, primitive in enumerate(shape_ir.primitives) if primitive.region == region_name]


def plan_shape_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    repairs: list[SemanticRepairAction] = []
    expected_parts = {part.name for part in asset_graph.parts}
    actual_parts = {region.part for region in shape_ir.regions}
    for missing in sorted(expected_parts - actual_parts):
        repairs.append(
            SemanticRepairAction(
                action="add_missing_required_part",
                target=missing,
                reason="required part is missing from the authoritative blueprint",
                details={},
            )
        )

    for part in asset_graph.parts:
        if not part.symmetry_mate:
            continue
        left_region = _find_region(shape_ir, part.name)
        right_region = _find_region(shape_ir, part.symmetry_mate)
        if left_region is None or right_region is None:
            repairs.append(
                SemanticRepairAction(
                    action="restore_symmetry_region",
                    target=part.name,
                    reason="a mirrored semantic region is missing",
                    details={"mate": part.symmetry_mate},
                )
            )

    if shape_ir.assessment.get("richness_floor", 0.0) < asset_graph.semantic_requirements.get("minimum_structural_richness", 0.55):
        repairs.append(
            SemanticRepairAction(
                action="increase_structural_richness",
                target=asset_graph.name,
                reason="blueprint richness floor is below the semantic minimum",
                details={},
            )
        )

    hinge_parts = [part for part in asset_graph.parts if part.articulation == "hinge" or "hinge" in part.tags]
    if hinge_parts and not any(region.component == "hinge" for region in shape_ir.regions):
        repairs.append(
            SemanticRepairAction(
                action="restore_hinge_alignment",
                target=hinge_parts[0].name,
                reason="articulated asset declares hinges but the blueprint has no hinge region",
                details={},
            )
        )

    support_parts = [part for part in asset_graph.parts if part.interface_role == "support"]
    if len(support_parts) >= 2:
        left = next((part for part in support_parts if "left" in part.tags), None)
        right = next((part for part in support_parts if "right" in part.tags), None)
        if left and right:
            left_region = _find_region(shape_ir, left.name)
            right_region = _find_region(shape_ir, right.name)
            if left_region and right_region and abs(left_region.center[0] + right_region.center[0]) > max(1.0, abs(left_region.center[0]) * 0.25):
                repairs.append(
                    SemanticRepairAction(
                        action="rebalance_support_feet",
                        target=left.name,
                        reason="support regions are not balanced across the symmetry axis",
                        details={"mate": right.name},
                    )
                )

    if shape_ir.assessment.get("feature_density", 0.0) < asset_graph.semantic_requirements.get("minimum_detail_density", 0.58):
        repairs.append(
            SemanticRepairAction(
                action="add_secondary_features",
                target=asset_graph.name,
                reason="feature density is below the expected fidelity floor",
                details={},
            )
        )

    if shape_ir.assessment.get("edge_treatment_count", 0) < 4:
        repairs.append(
            SemanticRepairAction(
                action="restore_edge_treatment",
                target=asset_graph.name,
                reason="edge treatment is too sparse for believable hard-surface output",
                details={},
            )
        )

    if shape_ir.assessment.get("panel_feature_count", 0) < 3 and asset_graph.family in {"brassbound_chest", "sci_fi_wall_panel", "console_terminal"}:
        repairs.append(
            SemanticRepairAction(
                action="increase_panel_depth",
                target=asset_graph.name,
                reason="panel depth and surface hierarchy are too flat",
                details={},
            )
        )

    if shape_ir.assessment.get("support_feature_count", 0) < 2 and any(part.interface_role == "support" for part in asset_graph.parts):
        repairs.append(
            SemanticRepairAction(
                action="refine_support_layout",
                target=asset_graph.name,
                reason="support regions need stronger visual grounding",
                details={},
            )
        )

    if asset_graph.family == "courier_drone" and "rotor_shroud" not in shape_ir.assessment.get("feature_types", []):
        repairs.append(
            SemanticRepairAction(
                action="shroud_exposed_frame",
                target=asset_graph.name,
                reason="drone frame is too exposed around the rotor pods",
                details={},
            )
        )

    if shape_ir.assessment.get("feature_coherence", 0.0) < asset_graph.semantic_requirements.get("minimum_feature_coherence", 0.56):
        repairs.append(
            SemanticRepairAction(
                action="improve_attachment_integration",
                target=asset_graph.name,
                reason="attachments are not visually integrated into the main body strongly enough",
                details={},
            )
        )

    return repairs


def apply_shape_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR, repairs: list[SemanticRepairAction]) -> tuple[ShapeIR, list[dict[str, Any]]]:
    if not repairs:
        return shape_ir, []

    regions = [ShapeRegion(**region.to_dict()) for region in shape_ir.regions]
    primitives = [ShapePrimitive(**primitive.to_dict()) for primitive in shape_ir.primitives]
    applied: list[dict[str, Any]] = []

    def add_region(region: ShapeRegion, primitive: ShapePrimitive) -> None:
        regions.append(region)
        primitives.append(primitive)

    for repair in repairs:
        if repair.action == "add_missing_required_part":
            source_region = next((region for region in regions if region.part == asset_graph.parts[0].name), regions[0] if regions else None)
            if source_region is None:
                continue
            center = (source_region.center[0], source_region.center[1], source_region.center[2] + source_region.extents[2] * 0.28)
            extents = (max(4.0, source_region.extents[0] * 0.18), max(4.0, source_region.extents[1] * 0.18), max(2.0, source_region.extents[2] * 0.12))
            region = ShapeRegion(
                name=f"{repair.target}_repair_region",
                part=repair.target,
                component="panel",
                center=center,
                extents=extents,
                tags=["repair", "panel"],
                adjacency=[source_region.part],
                required=True,
            )
            primitive = ShapePrimitive(
                primitive_type="box",
                part=repair.target,
                center=center,
                extents=extents,
                tags=["repair", "panel"],
                component="panel",
                region=region.name,
            )
            add_region(region, primitive)
            repair.applied = True
        elif repair.action == "restore_symmetry_region":
            mate_name = repair.details.get("mate")
            source_region = _find_region(shape_ir, mate_name)
            if source_region is None:
                source_region = next((region for region in regions if region.part == mate_name), None)
            if source_region is None:
                continue
            mirrored_center = (-source_region.center[0], source_region.center[1], source_region.center[2])
            region = ShapeRegion(
                name=f"{repair.target}_repair_region",
                part=repair.target,
                component=source_region.component,
                center=mirrored_center,
                extents=source_region.extents,
                tags=list(source_region.tags) + ["repair"],
                adjacency=list(source_region.adjacency),
                symmetry_mate=mate_name,
                interface_role=source_region.interface_role,
                required=True,
            )
            primitive_indices = _find_primitive_indices(shape_ir, source_region.name)
            if primitive_indices:
                for index in primitive_indices:
                    source = shape_ir.primitives[index]
                    primitive = ShapePrimitive(
                        primitive_type=source.primitive_type,
                        part=repair.target,
                        center=(-source.center[0], source.center[1], source.center[2]),
                        extents=source.extents,
                        radius=source.radius,
                        height=source.height,
                        axis=source.axis,
                        tags=list(source.tags) + ["repair"],
                        component=source.component,
                        region=region.name,
                    )
                    primitives.append(primitive)
            else:
                primitives.append(
                    ShapePrimitive(
                        primitive_type="box",
                        part=repair.target,
                        center=mirrored_center,
                        extents=source_region.extents,
                        tags=list(source_region.tags) + ["repair"],
                        component=source_region.component,
                        region=region.name,
                    )
                )
            regions.append(region)
            repair.applied = True
        elif repair.action == "increase_structural_richness":
            body_region = next((region for region in regions if region.component in {"shell", "body"}), regions[0] if regions else None)
            if body_region is None:
                continue
            center = (0.0, body_region.center[1], body_region.center[2] - body_region.extents[2] * 0.30)
            extents = (body_region.extents[0] * 0.46, body_region.extents[1] * 0.12, body_region.extents[2] * 0.08)
            region = ShapeRegion(
                name=f"{body_region.part}_brace_repair_region",
                part=body_region.part,
                component="bracket",
                center=center,
                extents=extents,
                tags=["repair", "brace"],
                adjacency=[body_region.part],
                required=False,
            )
            primitive = ShapePrimitive(
                primitive_type="box",
                part=body_region.part,
                center=center,
                extents=extents,
                tags=["repair", "brace"],
                component="bracket",
                region=region.name,
            )
            add_region(region, primitive)
            repair.applied = True
        elif repair.action == "restore_hinge_alignment":
            door_region = next((region for region in regions if region.component in {"door", "lid"}), None)
            if door_region is None:
                continue
            center = (door_region.center[0] - door_region.extents[0] * 0.46, door_region.center[1], door_region.center[2])
            extents = (door_region.extents[0] * 0.08, door_region.extents[1] * 0.12, max(2.0, door_region.extents[2] * 0.08))
            region = ShapeRegion(
                name=f"{repair.target}_repair_region",
                part=repair.target,
                component="hinge",
                center=center,
                extents=extents,
                tags=["repair", "hinge"],
                adjacency=[door_region.part],
                required=False,
            )
            primitive = ShapePrimitive(
                primitive_type="cylinder",
                part=repair.target,
                center=center,
                radius=max(1.0, extents[2] * 0.4),
                height=max(2.0, extents[1]),
                axis="z",
                tags=["repair", "hinge"],
                component="hinge",
                region=region.name,
            )
            add_region(region, primitive)
            repair.applied = True
        elif repair.action == "rebalance_support_feet":
            left_region = _find_region(shape_ir, repair.target)
            right_region = _find_region(shape_ir, repair.details.get("mate"))
            if left_region and right_region:
                balanced_x = max(abs(left_region.center[0]), abs(right_region.center[0]))
                left_region.center = (-balanced_x, left_region.center[1], left_region.center[2])
                right_region.center = (balanced_x, right_region.center[1], right_region.center[2])
                for region_name, sign in ((left_region.name, -1.0), (right_region.name, 1.0)):
                    for index, primitive in enumerate(primitives):
                        if primitive.region == region_name:
                            primitives[index].center = (sign * balanced_x, primitive.center[1], primitive.center[2])
                repair.applied = True
        elif repair.action == "refit_silhouette_region":
            body_region = next((region for region in regions if region.component in {"shell", "body"}), None)
            if body_region is None:
                continue
            body_region.extents = (body_region.extents[0] * 1.04, body_region.extents[1], body_region.extents[2] * 1.04)
            for index, primitive in enumerate(primitives):
                if primitive.region == body_region.name and primitive.extents is not None:
                    primitives[index].extents = body_region.extents
            repair.applied = True

        if repair.applied:
            applied.append(repair.to_dict())

    refreshed = refresh_shape_ir(
        asset_graph,
        ShapeIR(
            asset_name=shape_ir.asset_name,
            family=shape_ir.family,
            blueprint_id=shape_ir.blueprint_id,
            symmetry_axis=shape_ir.symmetry_axis,
            units=shape_ir.units,
            primitives=primitives,
            regions=regions,
            primitives_used=list(shape_ir.primitives_used),
            part_graph=list(shape_ir.part_graph),
            signature=dict(shape_ir.signature),
            assessment=dict(shape_ir.assessment),
        ),
        notes=list(shape_ir.signature.get("blueprint_notes", [])),
    )
    return refreshed, applied


def suggest_repairs_for_metric(metric: str, metrics: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if metric == "part_coverage":
        suggestions.extend(["add_missing_required_part", "split_merged_parts"])
    elif metric == "silhouette_fidelity":
        suggestions.extend(["refit_silhouette_region", "reselect_candidate"])
    elif metric == "symmetry_score":
        suggestions.extend(["restore_symmetry_region", "rebalance_support_feet"])
    elif metric == "interface_score":
        suggestions.extend(["widen_clearance", "restore_hinge_alignment"])
    elif metric == "structural_richness":
        suggestions.extend(["increase_structural_richness", "split_merged_parts"])
    elif metric == "adjacency_score":
        suggestions.extend(["restore_hinge_alignment", "split_merged_parts"])
    elif metric == "detail_density":
        suggestions.extend(["add_secondary_features", "increase_structural_richness"])
    elif metric == "silhouette_complexity":
        suggestions.extend(["refit_silhouette_region", "add_secondary_features"])
    elif metric == "edge_readability":
        suggestions.extend(["restore_edge_treatment", "increase_panel_depth"])
    elif metric == "attachment_integration_quality":
        suggestions.extend(["improve_attachment_integration", "restore_hinge_alignment"])
    elif metric == "support_plausibility":
        suggestions.extend(["refine_support_layout", "rebalance_support_feet"])
    elif metric == "feature_coherence":
        suggestions.extend(["add_secondary_features", "improve_attachment_integration"])
    if metrics.get("toy_detected"):
        suggestions.append("increase_structural_richness")
    return suggestions
