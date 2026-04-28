"""Semantic repair planning for shape-stage blueprint output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .assembly_kernel import refresh_shape_ir
from .asset_graph import AssetGraph
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

DEFAULT_MINIMUM_STRUCTURAL_RICHNESS = 0.55
DEFAULT_MINIMUM_DETAIL_DENSITY = 0.58
DEFAULT_MINIMUM_FEATURE_COHERENCE = 0.56
MIN_SUPPORT_PARTS_FOR_BALANCE = 2
MIN_EDGE_TREATMENT_COUNT = 4
MIN_PANEL_FEATURE_COUNT = 3
MIN_SUPPORT_FEATURE_COUNT = 2
PANEL_DEPTH_FAMILIES = {"brassbound_chest", "sci_fi_wall_panel", "console_terminal"}

METRIC_REPAIR_SUGGESTIONS = {
    "part_coverage": ["add_missing_required_part", "split_merged_parts"],
    "silhouette_fidelity": ["refit_silhouette_region", "reselect_candidate"],
    "symmetry_score": ["restore_symmetry_region", "rebalance_support_feet"],
    "interface_score": ["widen_clearance", "restore_hinge_alignment"],
    "structural_richness": ["increase_structural_richness", "split_merged_parts"],
    "adjacency_score": ["restore_hinge_alignment", "split_merged_parts"],
    "detail_density": ["add_secondary_features", "increase_structural_richness"],
    "silhouette_complexity": ["refit_silhouette_region", "add_secondary_features"],
    "edge_readability": ["restore_edge_treatment", "increase_panel_depth"],
    "attachment_integration_quality": [
        "improve_attachment_integration",
        "restore_hinge_alignment",
    ],
    "support_plausibility": ["refine_support_layout", "rebalance_support_feet"],
    "feature_coherence": ["add_secondary_features", "improve_attachment_integration"],
}


@dataclass
class SemanticRepairAction:
    """Planned repair action with the public trace payload fields."""

    action: str
    target: str
    reason: str
    details: dict[str, Any]
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the stable dictionary representation used in traces."""
        return asdict(self)


def _repair(
    *,
    action: str,
    target: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> SemanticRepairAction:
    return SemanticRepairAction(
        action=action,
        target=target,
        reason=reason,
        details={} if details is None else details,
    )


def _find_region(shape_ir: ShapeIR, name: object) -> ShapeRegion | None:
    return next(
        (region for region in shape_ir.regions if name in {region.name, region.part}),
        None,
    )


def _find_primitive_indices(shape_ir: ShapeIR, region_name: str) -> list[int]:
    return [index for index, primitive in enumerate(shape_ir.primitives) if primitive.region == region_name]


def _missing_required_part_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    expected_parts = {part.name for part in asset_graph.parts}
    actual_parts = {region.part for region in shape_ir.regions}
    return [
        _repair(
            action="add_missing_required_part",
            target=missing,
            reason="required part is missing from the authoritative blueprint",
        )
        for missing in sorted(expected_parts - actual_parts)
    ]


def _symmetry_region_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    repairs: list[SemanticRepairAction] = []
    for part in asset_graph.parts:
        if not part.symmetry_mate:
            continue
        left_region = _find_region(shape_ir, part.name)
        right_region = _find_region(shape_ir, part.symmetry_mate)
        if left_region is None or right_region is None:
            repairs.append(
                _repair(
                    action="restore_symmetry_region",
                    target=part.name,
                    reason="a mirrored semantic region is missing",
                    details={"mate": part.symmetry_mate},
                )
            )
    return repairs


def _structural_richness_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    minimum_richness = asset_graph.semantic_requirements.get(
        "minimum_structural_richness",
        DEFAULT_MINIMUM_STRUCTURAL_RICHNESS,
    )
    if shape_ir.assessment.get("richness_floor", 0.0) >= minimum_richness:
        return []
    return [
        _repair(
            action="increase_structural_richness",
            target=asset_graph.name,
            reason="blueprint richness floor is below the semantic minimum",
        )
    ]


def _hinge_alignment_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    hinge_parts = [part for part in asset_graph.parts if part.articulation == "hinge" or "hinge" in part.tags]
    if not hinge_parts or any(region.component == "hinge" for region in shape_ir.regions):
        return []
    return [
        _repair(
            action="restore_hinge_alignment",
            target=hinge_parts[0].name,
            reason="articulated asset declares hinges but the blueprint has no hinge region",
        )
    ]


def _support_balance_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    support_parts = [part for part in asset_graph.parts if part.interface_role == "support"]
    if len(support_parts) < MIN_SUPPORT_PARTS_FOR_BALANCE:
        return []

    left = next((part for part in support_parts if "left" in part.tags), None)
    right = next((part for part in support_parts if "right" in part.tags), None)
    if left is None or right is None:
        return []

    left_region = _find_region(shape_ir, left.name)
    right_region = _find_region(shape_ir, right.name)
    if left_region is None or right_region is None:
        return []

    center_delta = abs(left_region.center[0] + right_region.center[0])
    allowed_delta = max(1.0, abs(left_region.center[0]) * 0.25)
    if center_delta <= allowed_delta:
        return []

    return [
        _repair(
            action="rebalance_support_feet",
            target=left.name,
            reason="support regions are not balanced across the symmetry axis",
            details={"mate": right.name},
        )
    ]


def _feature_density_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    minimum_density = asset_graph.semantic_requirements.get(
        "minimum_detail_density",
        DEFAULT_MINIMUM_DETAIL_DENSITY,
    )
    if shape_ir.assessment.get("feature_density", 0.0) >= minimum_density:
        return []
    return [
        _repair(
            action="add_secondary_features",
            target=asset_graph.name,
            reason="feature density is below the expected fidelity floor",
        )
    ]


def _surface_feature_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    repairs: list[SemanticRepairAction] = []
    assessment = shape_ir.assessment
    if assessment.get("edge_treatment_count", 0) < MIN_EDGE_TREATMENT_COUNT:
        repairs.append(
            _repair(
                action="restore_edge_treatment",
                target=asset_graph.name,
                reason="edge treatment is too sparse for believable hard-surface output",
            )
        )
    if (
        assessment.get("panel_feature_count", 0) < MIN_PANEL_FEATURE_COUNT
        and asset_graph.family in PANEL_DEPTH_FAMILIES
    ):
        repairs.append(
            _repair(
                action="increase_panel_depth",
                target=asset_graph.name,
                reason="panel depth and surface hierarchy are too flat",
            )
        )
    return repairs


def _support_layout_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    has_support_part = any(part.interface_role == "support" for part in asset_graph.parts)
    if (
        shape_ir.assessment.get("support_feature_count", 0) >= MIN_SUPPORT_FEATURE_COUNT
        or not has_support_part
    ):
        return []
    return [
        _repair(
            action="refine_support_layout",
            target=asset_graph.name,
            reason="support regions need stronger visual grounding",
        )
    ]


def _drone_shroud_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    feature_types = shape_ir.assessment.get("feature_types", [])
    if asset_graph.family != "courier_drone" or "rotor_shroud" in feature_types:
        return []
    return [
        _repair(
            action="shroud_exposed_frame",
            target=asset_graph.name,
            reason="drone frame is too exposed around the rotor pods",
        )
    ]


def _feature_coherence_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    minimum_coherence = asset_graph.semantic_requirements.get(
        "minimum_feature_coherence",
        DEFAULT_MINIMUM_FEATURE_COHERENCE,
    )
    if shape_ir.assessment.get("feature_coherence", 0.0) >= minimum_coherence:
        return []
    return [
        _repair(
            action="improve_attachment_integration",
            target=asset_graph.name,
            reason="attachments are not visually integrated into the main body strongly enough",
        )
    ]


def plan_shape_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> list[SemanticRepairAction]:
    """Plan semantic repair actions without mutating the input shape IR."""
    repairs: list[SemanticRepairAction] = []
    repairs.extend(_missing_required_part_repairs(asset_graph, shape_ir))
    repairs.extend(_symmetry_region_repairs(asset_graph, shape_ir))
    repairs.extend(_structural_richness_repairs(asset_graph, shape_ir))
    repairs.extend(_hinge_alignment_repairs(asset_graph, shape_ir))
    repairs.extend(_support_balance_repairs(asset_graph, shape_ir))
    repairs.extend(_feature_density_repairs(asset_graph, shape_ir))
    repairs.extend(_surface_feature_repairs(asset_graph, shape_ir))
    repairs.extend(_support_layout_repairs(asset_graph, shape_ir))
    repairs.extend(_drone_shroud_repairs(asset_graph, shape_ir))
    repairs.extend(_feature_coherence_repairs(asset_graph, shape_ir))
    return repairs


class _ShapeRepairApplier:
    def __init__(self, asset_graph: AssetGraph, shape_ir: ShapeIR) -> None:
        self.asset_graph = asset_graph
        self.shape_ir = shape_ir
        self.regions = [ShapeRegion(**region.to_dict()) for region in shape_ir.regions]
        self.primitives = [ShapePrimitive(**primitive.to_dict()) for primitive in shape_ir.primitives]

    def run(self, repairs: list[SemanticRepairAction]) -> tuple[ShapeIR, list[dict[str, Any]]]:
        applied: list[dict[str, Any]] = []
        for repair in repairs:
            skip_append = self._apply_repair(repair)
            if skip_append:
                continue
            if repair.applied:
                applied.append(repair.to_dict())
        return self._refresh(), applied

    def _apply_repair(self, repair: SemanticRepairAction) -> bool:
        if repair.action == "rebalance_support_feet":
            if self._rebalance_support_feet(repair):
                repair.applied = True
            return False

        handler = {
            "add_missing_required_part": self._add_missing_required_part,
            "restore_symmetry_region": self._restore_symmetry_region,
            "increase_structural_richness": self._increase_structural_richness,
            "restore_hinge_alignment": self._restore_hinge_alignment,
            "refit_silhouette_region": self._refit_silhouette_region,
        }.get(repair.action)
        if handler is None:
            return False
        if handler(repair):
            repair.applied = True
            return False
        return True

    def _add_region(self, region: ShapeRegion, primitive: ShapePrimitive) -> None:
        self.regions.append(region)
        self.primitives.append(primitive)

    def _add_missing_required_part(self, repair: SemanticRepairAction) -> bool:
        source_region = self._source_region_for_missing_part()
        if source_region is None:
            return False

        center = (
            source_region.center[0],
            source_region.center[1],
            source_region.center[2] + source_region.extents[2] * 0.28,
        )
        extents = (
            max(4.0, source_region.extents[0] * 0.18),
            max(4.0, source_region.extents[1] * 0.18),
            max(2.0, source_region.extents[2] * 0.12),
        )
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
        self._add_region(region, primitive)
        return True

    def _source_region_for_missing_part(self) -> ShapeRegion | None:
        if not self.regions:
            return None
        source_part_name = self.asset_graph.parts[0].name
        return next(
            (region for region in self.regions if region.part == source_part_name),
            self.regions[0],
        )

    def _restore_symmetry_region(self, repair: SemanticRepairAction) -> bool:
        mate_name = repair.details.get("mate")
        source_region = _find_region(self.shape_ir, mate_name)
        if source_region is None:
            source_region = next(
                (region for region in self.regions if region.part == mate_name),
                None,
            )
        if source_region is None:
            return False

        mirrored_center = (
            -source_region.center[0],
            source_region.center[1],
            source_region.center[2],
        )
        region = self._mirrored_region(repair, source_region, mirrored_center)
        self._append_mirrored_primitives(repair, source_region, region, mirrored_center)
        self.regions.append(region)
        return True

    @staticmethod
    def _mirrored_region(
        repair: SemanticRepairAction,
        source_region: ShapeRegion,
        mirrored_center: tuple[float, float, float],
    ) -> ShapeRegion:
        mate_name = repair.details.get("mate")
        return ShapeRegion(
            name=f"{repair.target}_repair_region",
            part=repair.target,
            component=source_region.component,
            center=mirrored_center,
            extents=source_region.extents,
            tags=[*list(source_region.tags), "repair"],
            adjacency=list(source_region.adjacency),
            symmetry_mate=mate_name,
            interface_role=source_region.interface_role,
            required=True,
        )

    def _append_mirrored_primitives(
        self,
        repair: SemanticRepairAction,
        source_region: ShapeRegion,
        region: ShapeRegion,
        mirrored_center: tuple[float, float, float],
    ) -> None:
        primitive_indices = _find_primitive_indices(self.shape_ir, source_region.name)
        if not primitive_indices:
            self.primitives.append(
                ShapePrimitive(
                    primitive_type="box",
                    part=repair.target,
                    center=mirrored_center,
                    extents=source_region.extents,
                    tags=[*list(source_region.tags), "repair"],
                    component=source_region.component,
                    region=region.name,
                )
            )
            return

        for index in primitive_indices:
            source = self.shape_ir.primitives[index]
            self.primitives.append(
                ShapePrimitive(
                    primitive_type=source.primitive_type,
                    part=repair.target,
                    center=(-source.center[0], source.center[1], source.center[2]),
                    extents=source.extents,
                    radius=source.radius,
                    height=source.height,
                    axis=source.axis,
                    tags=[*list(source.tags), "repair"],
                    component=source.component,
                    region=region.name,
                )
            )

    def _increase_structural_richness(self, repair: SemanticRepairAction) -> bool:
        body_region = self._first_body_region(default_to_first=True)
        if body_region is None:
            return False

        center = (
            0.0,
            body_region.center[1],
            body_region.center[2] - body_region.extents[2] * 0.30,
        )
        extents = (
            body_region.extents[0] * 0.46,
            body_region.extents[1] * 0.12,
            body_region.extents[2] * 0.08,
        )
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
        self._add_region(region, primitive)
        return True

    def _first_body_region(self, *, default_to_first: bool) -> ShapeRegion | None:
        default = self.regions[0] if default_to_first and self.regions else None
        return next(
            (region for region in self.regions if region.component in {"shell", "body"}),
            default,
        )

    def _restore_hinge_alignment(self, repair: SemanticRepairAction) -> bool:
        door_region = next(
            (region for region in self.regions if region.component in {"door", "lid"}),
            None,
        )
        if door_region is None:
            return False

        center = (
            door_region.center[0] - door_region.extents[0] * 0.46,
            door_region.center[1],
            door_region.center[2],
        )
        extents = (
            door_region.extents[0] * 0.08,
            door_region.extents[1] * 0.12,
            max(2.0, door_region.extents[2] * 0.08),
        )
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
        self._add_region(region, primitive)
        return True

    def _rebalance_support_feet(self, repair: SemanticRepairAction) -> bool:
        left_region = _find_region(self.shape_ir, repair.target)
        right_region = _find_region(self.shape_ir, repair.details.get("mate"))
        if left_region is None or right_region is None:
            return False

        balanced_x = max(abs(left_region.center[0]), abs(right_region.center[0]))
        left_region.center = (-balanced_x, left_region.center[1], left_region.center[2])
        right_region.center = (balanced_x, right_region.center[1], right_region.center[2])
        for region_name, sign in ((left_region.name, -1.0), (right_region.name, 1.0)):
            for index, primitive in enumerate(self.primitives):
                if primitive.region == region_name:
                    self.primitives[index].center = (
                        sign * balanced_x,
                        primitive.center[1],
                        primitive.center[2],
                    )
        return True

    def _refit_silhouette_region(self, repair: SemanticRepairAction) -> bool:
        body_region = self._first_body_region(default_to_first=False)
        if body_region is None:
            return False

        body_region.extents = (
            body_region.extents[0] * 1.04,
            body_region.extents[1],
            body_region.extents[2] * 1.04,
        )
        for index, primitive in enumerate(self.primitives):
            if primitive.region == body_region.name and primitive.extents is not None:
                self.primitives[index].extents = body_region.extents
        return True

    def _refresh(self) -> ShapeIR:
        return refresh_shape_ir(
            self.asset_graph,
            ShapeIR(
                asset_name=self.shape_ir.asset_name,
                family=self.shape_ir.family,
                blueprint_id=self.shape_ir.blueprint_id,
                symmetry_axis=self.shape_ir.symmetry_axis,
                units=self.shape_ir.units,
                primitives=self.primitives,
                regions=self.regions,
                primitives_used=list(self.shape_ir.primitives_used),
                part_graph=list(self.shape_ir.part_graph),
                signature=dict(self.shape_ir.signature),
                assessment=dict(self.shape_ir.assessment),
            ),
            notes=list(self.shape_ir.signature.get("blueprint_notes", [])),
        )


def apply_shape_repairs(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    repairs: list[SemanticRepairAction],
) -> tuple[ShapeIR, list[dict[str, Any]]]:
    """Apply supported shape repairs and return the refreshed IR plus trace."""
    if not repairs:
        return shape_ir, []
    return _ShapeRepairApplier(asset_graph, shape_ir).run(repairs)


def suggest_repairs_for_metric(metric: str, metrics: dict[str, Any]) -> list[str]:
    """Return ordered repair action names suggested by a failed metric."""
    suggestions = list(METRIC_REPAIR_SUGGESTIONS.get(metric, []))
    if metrics.get("toy_detected"):
        suggestions.append("increase_structural_richness")
    return suggestions
