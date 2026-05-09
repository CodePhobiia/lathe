"""Typed authoring context consumed by native shape construction."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .asset_graph import AssetGraph


def _list_of_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _merge_strings(*values: object) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _list_of_strings(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return tuple(merged)


def _dict_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_string_with_source(*items: tuple[str, object]) -> tuple[str, str]:
    for source, value in items:
        text = str(value or "").strip()
        if text:
            return text, source
    return "", ""


def _int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    text = str(value).strip().lower()
    if not text or text == "auto":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted):
        return None
    return converted


def _int_or_default(value: object, default: int = 0) -> int:
    converted = _int_or_none(value)
    return default if converted is None else converted


def _float_or_default(value: object, default: float = 0.0) -> float:
    converted = _float_or_none(value)
    return default if converted is None else converted


def _vector3_or_none(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        out = (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    return out


def _child_module_slot_payloads(layout: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(layout, dict):
        return ()
    slots = layout.get("slots")
    if not isinstance(slots, (list, tuple)):
        return ()
    out: list[dict[str, Any]] = []
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict):
            continue
        module = slot.get("module") if isinstance(slot.get("module"), dict) else {}
        position = _vector3_or_none(slot.get("normalized_position")) or (0.0, 0.0, 0.0)
        out.append(
            {
                "id": str(slot.get("id") or f"slot_{index:02d}"),
                "kind": str(slot.get("kind") or module.get("kind") or "generic"),
                "socket": str(slot.get("socket") or ""),
                "anchor": str(slot.get("anchor") or ""),
                "mount": str(slot.get("mount") or ""),
                "clearance": _float_or_default(slot.get("clearance"), 0.0),
                "normalized_position": list(position),
                "facing_degrees": _float_or_default(slot.get("facing_degrees"), 0.0),
                "module_instance_id": str(module.get("instance_id") or ""),
                "module_template": str(module.get("template") or ""),
                "module_family": str(module.get("family") or ""),
                "module_archetype": str(module.get("archetype") or ""),
            }
        )
    return tuple(out)


def _connection_layout_point_payloads(summary: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(summary, dict):
        return ()
    points = summary.get("layout_points")
    if not isinstance(points, (list, tuple)):
        return ()
    out: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            continue
        position = _vector3_or_none(point.get("normalized_position")) or (0.0, 0.0, 0.0)
        out.append(
            {
                "endpoint": str(point.get("endpoint") or f"endpoint_{index:02d}"),
                "order": _int_or_default(point.get("order"), index),
                "normalized_position": list(position),
            }
        )
    return tuple(out)


def _connection_route_edge_payloads(summary: object) -> tuple[dict[str, str], ...]:
    if not isinstance(summary, dict):
        return ()
    edges = summary.get("route_edges")
    if not isinstance(edges, (list, tuple)):
        return ()
    out: list[dict[str, str]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not source or not target:
            continue
        out.append(
            {
                "source": source,
                "target": target,
                "relation": str(edge.get("relation") or ""),
            }
        )
    return tuple(out)


def _tokens(value: object) -> frozenset[str]:
    text = str(value or "").lower().replace("-", "_").replace(".", "_")
    raw = [token for token in text.split("_") if token]
    tokens: set[str] = set()
    for token in raw:
        tokens.add(token)
        if token.endswith("ies") and len(token) > 3:
            tokens.add(f"{token[:-3]}y")
        elif token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    if tokens & {"fastener", "bolt", "rivet"}:
        tokens.update({"fastener", "bolt", "rivet"})
    if tokens & {"vent", "grille", "slat"}:
        tokens.update({"vent", "grille", "slat"})
    if tokens & {"bracket", "brace", "gusset", "support"}:
        tokens.update({"bracket", "support"})
    if tokens & {"guard", "guarded", "corner_guard"}:
        tokens.update({"guard"})
    if tokens & {"mount", "mounted", "mounting"}:
        tokens.update({"mount"})
    if tokens & {"clasp", "latch", "lock"}:
        tokens.update({"clasp", "latch", "lock"})
    if tokens & {"inset", "panel", "groove"}:
        tokens.update({"inset", "panel", "groove"})
    return frozenset(tokens)


def _density_multiplier(value: str) -> float:
    table = {
        "off": 0.0,
        "none": 0.0,
        "low": 0.55,
        "light": 0.70,
        "medium": 1.0,
        "standard": 1.0,
        "game": 1.0,
        "high": 1.35,
        "dense": 1.55,
        "hero": 1.75,
        "ultra": 2.15,
    }
    return table.get(value.strip().lower(), 1.0)


@dataclass(frozen=True)
class ShapeAuthoringContext:
    """Stable internal view of authoring fields that should drive shape."""

    feature_allow: tuple[str, ...] = ()
    feature_density: str = ""
    feature_density_source: str = ""
    shape_seed: int | None = None
    shape_seed_source: str = ""
    symmetry_axis: str = ""
    panelization: str = ""
    edge_complexity: str = ""
    edge_treatment: str = ""
    style_pack: str = ""
    silhouette_profile: str = ""
    structural_profile: str = ""
    route_structure: str = ""
    style_intensity: float | None = None
    trim_density: float | None = None
    greeble_density: float | None = None
    socket_ids: tuple[str, ...] = ()
    anchor_ids: tuple[str, ...] = ()
    connection_count: int = 0
    route_connection_count: int = 0
    attach_connection_count: int = 0
    support_connection_count: int = 0
    external_connection_count: int = 0
    branch_connection_count: int = 0
    connection_layout_mode: str = ""
    connection_segment_count: int = 0
    connection_path_complexity: float = 0.0
    connection_route_edges: tuple[dict[str, str], ...] = ()
    connection_layout_points: tuple[dict[str, Any], ...] = ()
    child_module_count: int = 0
    module_slot_count: int = 0
    module_slots: tuple[dict[str, Any], ...] = ()
    nested_asset_count: int = 0
    nested_asset_families: tuple[str, ...] = ()
    seam_classes: tuple[str, ...] = ()
    edge_classes: tuple[str, ...] = ()
    integration_rules: tuple[str, ...] = ()
    style_target: str = ""
    asset_class: str = ""
    styles: tuple[str, ...] = ()
    material_zones: tuple[str, ...] = ()
    surface_patterns: tuple[str, ...] = ()
    surface_materials: tuple[str, ...] = ()
    preservation_intents: tuple[str, ...] = ()
    repair_policy_use: str = ""
    repair_policy_mode: str = ""
    repair_policy_allow: tuple[str, ...] = ()
    repair_policy_deny: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = field(default_factory=tuple)

    @property
    def density_multiplier(self) -> float:
        return _density_multiplier(self.feature_density)

    @property
    def allow_tokens(self) -> frozenset[str]:
        tokens: set[str] = set()
        for value in self.feature_allow:
            tokens.update(_tokens(value))
        return frozenset(tokens)

    @property
    def surface_pattern_tokens(self) -> frozenset[str]:
        tokens: set[str] = set()
        for value in self.surface_patterns:
            tokens.update(_tokens(value))
        return frozenset(tokens)

    def matches_allowed_feature(self, *values: object) -> bool:
        allow_tokens = self.allow_tokens
        if not allow_tokens:
            return True
        surface_pattern_tokens = self.surface_pattern_tokens
        for value in values:
            value_tokens = _tokens(value)
            if allow_tokens & value_tokens:
                return True
            if surface_pattern_tokens & value_tokens:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_allow": list(self.feature_allow),
            "feature_density": self.feature_density,
            "feature_density_source": self.feature_density_source,
            "density_multiplier": self.density_multiplier,
            "shape_seed": self.shape_seed,
            "shape_seed_source": self.shape_seed_source,
            "symmetry_axis": self.symmetry_axis,
            "panelization": self.panelization,
            "edge_complexity": self.edge_complexity,
            "edge_treatment": self.edge_treatment,
            "style_pack": self.style_pack,
            "silhouette_profile": self.silhouette_profile,
            "structural_profile": self.structural_profile,
            "route_structure": self.route_structure,
            "style_intensity": self.style_intensity,
            "trim_density": self.trim_density,
            "greeble_density": self.greeble_density,
            "socket_ids": list(self.socket_ids),
            "anchor_ids": list(self.anchor_ids),
            "connection_count": self.connection_count,
            "route_connection_count": self.route_connection_count,
            "attach_connection_count": self.attach_connection_count,
            "support_connection_count": self.support_connection_count,
            "external_connection_count": self.external_connection_count,
            "branch_connection_count": self.branch_connection_count,
            "connection_layout_mode": self.connection_layout_mode,
            "connection_segment_count": self.connection_segment_count,
            "connection_path_complexity": self.connection_path_complexity,
            "connection_route_edges": [dict(edge) for edge in self.connection_route_edges],
            "connection_layout_points": [dict(point) for point in self.connection_layout_points],
            "child_module_count": self.child_module_count,
            "module_slot_count": self.module_slot_count,
            "module_slots": [dict(slot) for slot in self.module_slots],
            "nested_asset_count": self.nested_asset_count,
            "nested_asset_families": list(self.nested_asset_families),
            "seam_classes": list(self.seam_classes),
            "edge_classes": list(self.edge_classes),
            "integration_rules": list(self.integration_rules),
            "style_target": self.style_target,
            "asset_class": self.asset_class,
            "styles": list(self.styles),
            "material_zones": list(self.material_zones),
            "surface_patterns": list(self.surface_patterns),
            "surface_materials": list(self.surface_materials),
            "preservation_intents": list(self.preservation_intents),
            "repair_policy_use": self.repair_policy_use,
            "repair_policy_mode": self.repair_policy_mode,
            "repair_policy_allow": list(self.repair_policy_allow),
            "repair_policy_deny": list(self.repair_policy_deny),
            "source_paths": list(self.source_paths),
        }


def authoring_context_from_asset_graph(asset_graph: AssetGraph) -> ShapeAuthoringContext:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    resolved_family = authoring.get("resolved_family", {})
    family_features = resolved_family.get("features", {}) if isinstance(resolved_family, dict) else {}
    if not isinstance(family_features, dict):
        family_features = {}
    family_surface = resolved_family.get("surface", {}) if isinstance(resolved_family, dict) else {}
    if not isinstance(family_surface, dict):
        family_surface = {}
    geometry = resolved_family.get("geometry", {}) if isinstance(resolved_family, dict) else {}
    if not isinstance(geometry, dict):
        geometry = {}
    source_geometry = authoring.get("source_geometry", {})
    if not isinstance(source_geometry, dict):
        source_geometry = {}
    geometry = {**geometry, **source_geometry}
    source_surface = authoring.get("source_surface", {})
    if not isinstance(source_surface, dict):
        source_surface = {}
    surface = {**family_surface, **source_surface}
    constraints = authoring.get("constraints", {})
    if not isinstance(constraints, dict):
        constraints = {}
    shape_controls = authoring.get("shape_controls", {})
    if not isinstance(shape_controls, dict):
        shape_controls = {}
    connection_layout = asset_graph.connection_layout if isinstance(asset_graph.connection_layout, dict) else {}
    connection_summary = connection_layout.get("summary", {})
    if not isinstance(connection_summary, dict):
        connection_summary = {}
    child_module_layout = authoring.get("child_module_layout", {})
    if not isinstance(child_module_layout, dict):
        child_module_layout = {}
    child_summary = child_module_layout.get("summary", {})
    if not isinstance(child_summary, dict):
        child_summary = {}
    nested_assets = authoring.get("nested_assets", {})
    if not isinstance(nested_assets, dict):
        nested_assets = {}
    family_repair_policy = _dict_or_empty(resolved_family.get("repair_policy"))
    asset_repair_policy = _dict_or_empty(authoring.get("repair_policy"))
    repair_policy = {**family_repair_policy, **asset_repair_policy}
    nested_summary = nested_assets.get("summary", {})
    if not isinstance(nested_summary, dict):
        nested_summary = {}
    nested_families = nested_summary.get("families", {})
    if isinstance(nested_families, dict):
        nested_family_names = tuple(str(key) for key in sorted(nested_families.keys()) if str(key))
    else:
        nested_family_names = ()
    feature_allow = _merge_strings(family_features.get("allow"), authoring.get("feature_allow"))
    feature_density, feature_density_source = _first_string_with_source(
        ("features.density", authoring.get("feature_density")),
        ("build.shape.detail_density", shape_controls.get("detail_density")),
        ("build.shape.feature_density", shape_controls.get("feature_density")),
        ("build.shape.density", shape_controls.get("density")),
        ("family.features.density", family_features.get("density")),
    )
    shape_seed, shape_seed_source = None, ""
    for source, value in (
        ("build.shape.seed", shape_controls.get("seed")),
        ("build.shape.random_seed", shape_controls.get("random_seed")),
    ):
        seed = _int_or_none(value)
        if seed is not None:
            shape_seed, shape_seed_source = seed, source
            break
    return ShapeAuthoringContext(
        feature_allow=feature_allow,
        feature_density=feature_density,
        feature_density_source=feature_density_source,
        shape_seed=shape_seed,
        shape_seed_source=shape_seed_source,
        symmetry_axis=str(asset_graph.symmetry_axis or ""),
        panelization=str(shape_controls.get("panelization") or ""),
        edge_complexity=str(shape_controls.get("edge_complexity") or shape_controls.get("edge_treatment") or ""),
        edge_treatment=str(shape_controls.get("edge_treatment") or ""),
        style_pack=str(shape_controls.get("style_pack") or ""),
        silhouette_profile=str(shape_controls.get("silhouette_profile") or ""),
        structural_profile=str(shape_controls.get("structural_profile") or ""),
        route_structure=str(shape_controls.get("route_structure") or ""),
        style_intensity=_float_or_none(shape_controls.get("style_intensity")),
        trim_density=_float_or_none(shape_controls.get("trim_density")),
        greeble_density=_float_or_none(shape_controls.get("greeble_density")),
        socket_ids=tuple(str(item) for item in asset_graph.sockets if str(item)),
        anchor_ids=tuple(str(item) for item in asset_graph.anchors if str(item)),
        connection_count=_int_or_default(
            connection_summary.get("connection_count") or shape_controls.get("connection_count")
        ),
        route_connection_count=_int_or_default(
            connection_summary.get("route_connection_count")
            or shape_controls.get("connection_route_count")
        ),
        attach_connection_count=_int_or_default(
            connection_summary.get("attach_connection_count")
            or shape_controls.get("connection_attach_count")
        ),
        support_connection_count=_int_or_default(
            connection_summary.get("support_connection_count")
            or shape_controls.get("connection_support_count")
        ),
        external_connection_count=_int_or_default(
            connection_summary.get("external_connection_count")
            or shape_controls.get("connection_external_count")
        ),
        branch_connection_count=_int_or_default(
            connection_summary.get("branch_connection_count")
            or shape_controls.get("connection_branch_count")
        ),
        connection_layout_mode=str(shape_controls.get("connection_layout_mode") or ""),
        connection_segment_count=_int_or_default(shape_controls.get("connection_segment_count")),
        connection_path_complexity=_float_or_default(shape_controls.get("connection_path_complexity")),
        connection_route_edges=_connection_route_edge_payloads(connection_summary),
        connection_layout_points=_connection_layout_point_payloads(connection_summary),
        child_module_count=_int_or_default(shape_controls.get("child_module_count") or child_summary.get("slot_count")),
        module_slot_count=_int_or_default(shape_controls.get("module_slot_count")),
        module_slots=_child_module_slot_payloads(child_module_layout),
        nested_asset_count=_int_or_default(
            shape_controls.get("nested_asset_count") or nested_summary.get("nested_asset_count")
        ),
        nested_asset_families=nested_family_names,
        seam_classes=_list_of_strings(geometry.get("seam_classes")),
        edge_classes=_list_of_strings(geometry.get("edge_classes")),
        integration_rules=_list_of_strings(geometry.get("integration_rules")),
        style_target=str(authoring.get("style_target") or surface.get("style_target") or ""),
        asset_class=str(authoring.get("asset_class") or ""),
        styles=tuple(str(item) for item in asset_graph.styles if str(item)),
        material_zones=_merge_strings(family_surface.get("material_zones"), source_surface.get("material_zones")),
        surface_patterns=_merge_strings(family_surface.get("patterns"), source_surface.get("patterns")),
        surface_materials=_merge_strings(family_surface.get("materials"), source_surface.get("materials")),
        preservation_intents=_merge_strings(
            constraints.get("preserve"),
            shape_controls.get("preserve"),
        ),
        repair_policy_use=str(repair_policy.get("use") or ""),
        repair_policy_mode=str(repair_policy.get("mode") or ""),
        repair_policy_allow=_list_of_strings(repair_policy.get("allow")),
        repair_policy_deny=_list_of_strings(repair_policy.get("deny")),
        source_paths=(
            "features.allow",
            "features.density",
            "build.shape.detail_density",
            "build.shape.seed",
            "build.shape.panelization",
            "build.shape.edge_complexity",
            "build.shape.edge_treatment",
            "build.shape.style_pack",
            "build.shape.silhouette_profile",
            "build.shape.structural_profile",
            "build.shape.route_structure",
            "build.shape.style_intensity",
            "build.shape.trim_density",
            "build.shape.greeble_density",
            "build.interfaces.sockets",
            "build.interfaces.anchors",
            "build.interfaces.connections",
            "build.shape.connection_*",
            "asset_graph.connection_layout.route_edges",
            "asset_graph.connection_layout.layout_points",
            "build.shape.child_module_count",
            "build.shape.module_slot_count",
            "build.shape.nested_asset_count",
            "geometry.seam_classes",
            "geometry.edge_classes",
            "geometry.integration_rules",
            "constraints.preserve",
            "build.shape.preserve",
            "repair_policy.use",
            "repair_policy.mode",
            "repair_policy.allow",
            "repair_policy.deny",
            "intent.asset_class",
            "surface.patterns",
            "surface.material_zones",
        ),
    )
