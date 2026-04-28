from __future__ import annotations

from copy import deepcopy

from .assembly_kernel import BlueprintComponent, refresh_shape_ir
from .asset_graph import AssetGraph
from .feature_ops import (
    clasp_set_features,
    edge_break_features,
    fastener_strip_features,
    hinge_set_features,
    panel_frame_features,
    recessed_handle_features,
    rotor_shroud_features,
    support_bracket_features,
    trim_band_features,
)
from .repair_planner import SemanticRepairAction
from .repair_planner import apply_shape_repairs as _apply_semantic_repairs
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


def _component_from_region(shape_ir: ShapeIR, region: ShapeRegion) -> BlueprintComponent:
    return BlueprintComponent(
        name=region.name,
        component_type=region.component,
        part=region.part,
        center=region.center,
        extents=region.extents,
        tags=list(region.tags),
        adjacency=list(region.adjacency),
        symmetry_mate=region.symmetry_mate,
        interface_role=region.interface_role,
    )


def _region(shape_ir: ShapeIR, predicate) -> list[ShapeRegion]:
    return [region for region in shape_ir.regions if predicate(region)]


def execute_shape_repairs(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    repairs: list[SemanticRepairAction],
    *,
    max_repairs: int | None = None,
) -> tuple[ShapeIR, list[dict[str, object]]]:
    if not repairs:
        return shape_ir, []

    limit = max_repairs if max_repairs is not None else max(1, len(repairs))
    base_actions = {
        "add_missing_required_part",
        "restore_symmetry_region",
        "increase_structural_richness",
        "restore_hinge_alignment",
        "rebalance_support_feet",
        "refit_silhouette_region",
    }
    base_repairs = [repair for repair in repairs if repair.action in base_actions][:limit]
    custom_repairs = [repair for repair in repairs if repair.action not in base_actions][
        : max(0, limit - len(base_repairs))
    ]

    repaired_shape_ir, applied = _apply_semantic_repairs(asset_graph, shape_ir, base_repairs)
    if not custom_repairs:
        return repaired_shape_ir, applied

    working = deepcopy(repaired_shape_ir)
    custom_applied: list[dict[str, object]] = []

    def add_feature_primitives(primitives: list[ShapePrimitive]) -> None:
        working.primitives.extend(primitives)

    for repair in custom_repairs:
        if repair.action == "add_secondary_features":
            shell_region = next(
                (region for region in working.regions if region.component in {"shell", "body"}), None
            )
            if shell_region is None:
                continue
            component = _component_from_region(working, shell_region)
            add_feature_primitives(trim_band_features(component, depth_scale=1.12, thickness_scale=1.0))
            add_feature_primitives(
                fastener_strip_features(component, count=4, depth_scale=1.0, size_scale=0.95)
            )
            repair.applied = True
        elif repair.action == "restore_edge_treatment":
            targets = _region(
                working, lambda region: region.component in {"shell", "body", "lid", "door", "bezel", "frame"}
            )
            if not targets:
                continue
            for region in targets[:3]:
                add_feature_primitives(
                    edge_break_features(
                        _component_from_region(working, region), depth_scale=1.08, thickness_scale=1.05
                    )
                )
            repair.applied = True
        elif repair.action == "increase_panel_depth":
            targets = _region(working, lambda region: region.component in {"panel", "bezel", "door", "lid"})
            if not targets:
                continue
            for region in targets:
                region.extents = (region.extents[0], region.extents[1], region.extents[2] * 1.18)
                add_feature_primitives(
                    panel_frame_features(
                        _component_from_region(working, region), depth_scale=1.22, thickness_scale=1.02
                    )
                )
            repair.applied = True
        elif repair.action == "refine_support_layout":
            targets = _region(
                working,
                lambda region: (
                    region.interface_role == "support" or region.component in {"foot", "stand", "bracket"}
                ),
            )
            if not targets:
                continue
            for region in targets:
                x, y, z = region.center
                region.center = (x * 1.10 if x != 0 else x, y, z)
                add_feature_primitives(
                    support_bracket_features(_component_from_region(working, region), depth_scale=1.08)
                )
            repair.applied = True
        elif repair.action == "shroud_exposed_frame":
            pods = _region(working, lambda region: region.component == "rotor_pod")
            if not pods:
                continue
            for region in pods:
                add_feature_primitives(
                    rotor_shroud_features(_component_from_region(working, region), scale=1.06)
                )
            repair.applied = True
        elif repair.action == "regularize_symmetry":
            mirrored_pairs = [
                (
                    region,
                    next(
                        (
                            candidate
                            for candidate in working.regions
                            if candidate.part == region.symmetry_mate
                        ),
                        None,
                    ),
                )
                for region in working.regions
                if region.symmetry_mate
            ]
            changed = False
            for left, right in mirrored_pairs:
                if right is None:
                    continue
                span = max(abs(left.center[0]), abs(right.center[0]))
                left.center = (-span, left.center[1], left.center[2])
                right.center = (span, right.center[1], right.center[2])
                changed = True
            repair.applied = changed
        elif repair.action == "improve_attachment_integration":
            targets = _region(
                working, lambda region: region.component in {"handle", "hinge", "lock_plate", "latch", "door"}
            )
            if not targets:
                continue
            for region in targets:
                component = _component_from_region(working, region)
                if region.component == "handle":
                    add_feature_primitives(recessed_handle_features(component, depth_scale=1.05))
                elif region.component == "hinge":
                    add_feature_primitives(hinge_set_features(component, depth_scale=1.0))
                else:
                    add_feature_primitives(clasp_set_features(component, depth_scale=1.0))
            repair.applied = True

        if repair.applied:
            custom_applied.append(repair.to_dict())

    refreshed = refresh_shape_ir(
        asset_graph, working, notes=list(working.signature.get("blueprint_notes", []))
    )
    return refreshed, applied + custom_applied
