from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _token_set(value: str | None) -> set[str]:
    if not value:
        return set()
    lowered = value.lower().replace("-", "_").replace(" ", "_")
    return {token for token in lowered.split("_") if token}


def infer_asset_family(asset: dict[str, Any]) -> str:
    resolved_family = asset.get("assembly", {}).get("resolved_family", {})
    explicit_family = (
        resolved_family.get("values", {}).get("runtime_family")
        or resolved_family.get("values", {}).get("family_key")
        or asset.get("assembly", {}).get("family")
    )
    if explicit_family:
        return str(explicit_family)

    role = str(asset.get("intent", {}).get("role", "")).lower()
    parts = [str(item).lower() for item in asset.get("intent", {}).get("parts", [])]
    kind = str(asset.get("kind", ""))
    tokens = _token_set(role) | {token for part in parts for token in _token_set(part)}

    if {"chest", "loot"} & tokens or {"lid_panel", "front_hatch", "lock_plate"} <= set(parts):
        return "brassbound_chest"
    if "drone" in tokens or sum(1 for part in parts if "rotor" in part or "prop" in part or "fan" in part) >= 4:
        return "courier_drone"
    if kind == "env_module" and {"wall", "screen", "vent", "mount"} & tokens:
        return "sci_fi_wall_panel"
    if "crate" in tokens:
        return "industrial_crate"
    if "door" in tokens:
        return "mechanical_door"
    if {"console", "terminal"} & tokens:
        return "console_terminal"
    if {"panel", "screen", "vent"} & tokens or (kind == "env_module" and {"wall", "screen", "vent"} & tokens):
        return "sci_fi_wall_panel"
    if kind == "env_module":
        return "env_module_generic"
    if kind == "mechanical_assembly":
        return "mechanical_assembly_generic"
    return "hard_surface_prop_generic"


def infer_blueprint_id(asset: dict[str, Any]) -> str:
    resolved_family = asset.get("assembly", {}).get("resolved_family", {})
    explicit_blueprint = resolved_family.get("values", {}).get("blueprint_id")
    if explicit_blueprint:
        return str(explicit_blueprint)
    family = infer_asset_family(asset)
    return {
        "brassbound_chest": "lathe.blueprint.hard_surface_chest_v1",
        "courier_drone": "lathe.blueprint.mechanical_quad_drone_v1",
        "sci_fi_wall_panel": "lathe.blueprint.env_wall_panel_v1",
        "industrial_crate": "lathe.blueprint.hard_surface_crate_v1",
        "mechanical_door": "lathe.blueprint.env_mechanical_door_v1",
        "console_terminal": "lathe.blueprint.hard_surface_console_terminal_v1",
        "service_cabinet": "lathe.blueprint.hard_surface_service_cabinet_v1",
        "control_pedestal": "lathe.blueprint.hard_surface_control_pedestal_v1",
        "supply_container": "lathe.blueprint.hard_surface_supply_container_v1",
        "env_module_generic": "lathe.blueprint.env_module_generic_v1",
        "mechanical_assembly_generic": "lathe.blueprint.mechanical_assembly_generic_v1",
        "hard_surface_prop_generic": "lathe.blueprint.hard_surface_prop_generic_v1",
    }[family]


def _part_tags(name: str) -> list[str]:
    lname = name.lower()
    tags: set[str] = set()
    for token in (
        "body",
        "shell",
        "lid",
        "hatch",
        "door",
        "hinge",
        "lock",
        "latch",
        "plate",
        "handle",
        "foot",
        "leg",
        "stand",
        "panel",
        "screen",
        "frame",
        "bezel",
        "vent",
        "grille",
        "rotor",
        "cargo",
        "sensor",
        "camera",
        "anchor",
        "socket",
        "mount",
        "console",
        "threshold",
    ):
        if token in lname:
            tags.add(token)
    if lname.endswith("_l") or "_l" in lname or lname.endswith(" left"):
        tags.add("left")
    if lname.endswith("_r") or "_r" in lname or lname.endswith(" right"):
        tags.add("right")
    if lname.endswith("_fl") or "_fl" in lname:
        tags.update({"front", "left"})
    if lname.endswith("_fr") or "_fr" in lname:
        tags.update({"front", "right"})
    if lname.endswith("_rl") or "_rl" in lname:
        tags.update({"rear", "left"})
    if lname.endswith("_rr") or "_rr" in lname:
        tags.update({"rear", "right"})
    if "top" in lname:
        tags.add("top")
    if "bottom" in lname:
        tags.add("bottom")
    return sorted(tags)


def _symmetry_mate(name: str, part_names: set[str]) -> str | None:
    candidates = [
        (name.replace("_l", "_r"), "_l"),
        (name.replace("_r", "_l"), "_r"),
        (name.replace("_fl", "_fr"), "_fl"),
        (name.replace("_fr", "_fl"), "_fr"),
        (name.replace("_rl", "_rr"), "_rl"),
        (name.replace("_rr", "_rl"), "_rr"),
    ]
    for candidate, token in candidates:
        if token in name and candidate in part_names:
            return candidate
    return None


def _assembly_role(tags: list[str]) -> str | None:
    ordered_roles = [
        "body",
        "shell",
        "panel",
        "frame",
        "lid",
        "door",
        "hinge",
        "lock",
        "latch",
        "handle",
        "foot",
        "stand",
        "leg",
        "vent",
        "grille",
        "screen",
        "bezel",
        "rotor",
        "anchor",
        "socket",
        "threshold",
    ]
    for role in ordered_roles:
        if role in tags:
            return role
    return None


def _infer_part_graph(parts: list["PartNode"]) -> list[dict[str, str]]:
    part_names = {part.name for part in parts}
    edges: set[tuple[str, str]] = set()

    def connect(left: str, right: str) -> None:
        if left not in part_names or right not in part_names or left == right:
            return
        edges.add(tuple(sorted((left, right))))

    body_name = next((part.name for part in parts if part.assembly_role in {"body", "shell"}), parts[0].name if parts else None)
    for part in parts:
        if body_name and part.name != body_name:
            connect(body_name, part.name)

    tag_pairs = [
        ("lid", "lock"),
        ("door", "lock"),
        ("door", "handle"),
        ("screen", "frame"),
        ("screen", "bezel"),
        ("panel", "frame"),
        ("vent", "panel"),
        ("rotor", "body"),
        ("foot", "body"),
        ("stand", "body"),
        ("leg", "body"),
        ("anchor", "body"),
        ("socket", "body"),
        ("threshold", "door"),
    ]
    for left_tag, right_tag in tag_pairs:
        left_parts = [part.name for part in parts if left_tag in part.tags]
        right_parts = [part.name for part in parts if right_tag in part.tags]
        for left_name in left_parts:
            for right_name in right_parts:
                connect(left_name, right_name)

    return [{"from": left, "to": right} for left, right in sorted(edges)]


@dataclass
class PartNode:
    name: str
    tags: list[str] = field(default_factory=list)
    symmetry_mate: str | None = None
    articulation: str | None = None
    interface_role: str | None = None
    assembly_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetGraph:
    name: str
    kind: str
    family: str
    blueprint_id: str
    role: str
    scale_cm: float
    symmetry_axis: str | None
    validation_threshold: float
    critic_name: str | None
    parts: list[PartNode]
    joints: list[str]
    sockets: list[str]
    anchors: list[str]
    materials: list[str]
    styles: list[str]
    interactions: list[str]
    part_graph: list[dict[str, str]]
    semantic_requirements: dict[str, Any]
    authoring: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parts"] = [part.to_dict() for part in self.parts]
        return payload


def _scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    scale = intent.get("scale")
    if isinstance(scale, dict) and scale.get("type") == "unit":
        value = float(scale["value"])
        unit = scale["unit"]
        if unit == "mm":
            return value / 10.0
        if unit == "cm":
            return value
        if unit == "m":
            return value * 100.0
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def build_asset_graph(asset: dict[str, Any]) -> AssetGraph:
    part_names = [str(item) for item in asset.get("intent", {}).get("parts", [])]
    family = infer_asset_family(asset)
    blueprint_id = infer_blueprint_id(asset)
    resolved_components = list(asset.get("assembly", {}).get("resolved_components", []))
    component_by_part: dict[str, dict[str, Any]] = {}
    for component in resolved_components:
        values = component.get("values", {})
        part_name = values.get("part")
        if part_name:
            component_by_part[str(part_name)] = component
    part_name_set = set(part_names)
    parts: list[PartNode] = []
    for name in part_names:
        component = component_by_part.get(name, {})
        component_values = component.get("values", {})
        component_tags = list(component_values.get("tags", []))
        component_type = component.get("geometry", {}).get("component_type") or component_values.get("component_type")
        tags = sorted(set(_part_tags(name) + component_tags + ([str(component_type)] if component_type else [])))
        articulation = component_values.get("articulation") or ("hinge" if any(tag in tags for tag in ("lid", "door", "hatch")) else None)
        interface_role = component_values.get("interface_role") or ("grip" if "handle" in tags else "support" if any(tag in tags for tag in ("foot", "leg", "stand")) else None)
        parts.append(
            PartNode(
                name=name,
                tags=tags,
                symmetry_mate=_symmetry_mate(name, part_name_set),
                articulation=articulation,
                interface_role=interface_role,
                assembly_role=str(component_type) if component_type else _assembly_role(tags),
            )
        )
    symmetry_axis = asset.get("build", {}).get("shape", {}).get("symmetry")
    if symmetry_axis in {"auto", None, ""}:
        symmetry_axis = "x"

    semantic_requirements = {
        "minimum_part_coverage": 0.75,
        "minimum_silhouette_fidelity": 0.72,
        "minimum_structural_richness": 0.55,
        "minimum_symmetry_score": 0.60,
        "minimum_interface_score": 0.60,
        "minimum_adjacency_score": 0.58,
        "maximum_fragmentation_penalty": 0.45,
        "minimum_detail_density": 0.58,
        "minimum_silhouette_complexity": 0.58,
        "minimum_edge_readability": 0.55,
        "minimum_attachment_integration_quality": 0.58,
        "minimum_support_plausibility": 0.52,
        "minimum_feature_coherence": 0.56,
        "minimum_geometry_integration_quality": 0.0,
        "minimum_surface_authoring_quality": 0.0,
        "maximum_primitive_likeness_penalty": 0.44,
        "maximum_assembled_primitives_penalty": 0.42,
    }
    if family == "brassbound_chest":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.85,
                "minimum_silhouette_fidelity": 0.82,
                "minimum_structural_richness": 0.68,
                "minimum_symmetry_score": 0.78,
                "minimum_interface_score": 0.70,
                "minimum_adjacency_score": 0.72,
                "maximum_fragmentation_penalty": 0.22,
                "minimum_detail_density": 0.76,
                "minimum_silhouette_complexity": 0.72,
                "minimum_edge_readability": 0.72,
                "minimum_attachment_integration_quality": 0.74,
                "minimum_support_plausibility": 0.68,
                "minimum_feature_coherence": 0.74,
                "minimum_geometry_integration_quality": 0.85,
                "minimum_surface_authoring_quality": 0.70,
                "maximum_primitive_likeness_penalty": 0.18,
                "maximum_assembled_primitives_penalty": 0.20,
            }
        )
    elif family == "courier_drone":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.90,
                "minimum_silhouette_fidelity": 0.80,
                "minimum_structural_richness": 0.72,
                "minimum_symmetry_score": 0.82,
                "minimum_interface_score": 0.68,
                "minimum_adjacency_score": 0.74,
                "maximum_fragmentation_penalty": 0.20,
                "minimum_detail_density": 0.74,
                "minimum_silhouette_complexity": 0.70,
                "minimum_edge_readability": 0.70,
                "minimum_attachment_integration_quality": 0.76,
                "minimum_support_plausibility": 0.64,
                "minimum_feature_coherence": 0.72,
                "minimum_geometry_integration_quality": 0.85,
                "minimum_surface_authoring_quality": 0.70,
                "maximum_primitive_likeness_penalty": 0.18,
                "maximum_assembled_primitives_penalty": 0.18,
            }
        )
    elif family == "sci_fi_wall_panel":
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.80,
                "minimum_silhouette_fidelity": 0.76,
                "minimum_structural_richness": 0.62,
                "minimum_symmetry_score": 0.55,
                "minimum_interface_score": 0.64,
                "minimum_adjacency_score": 0.66,
                "maximum_fragmentation_penalty": 0.26,
                "minimum_detail_density": 0.68,
                "minimum_silhouette_complexity": 0.70,
                "minimum_edge_readability": 0.66,
                "minimum_attachment_integration_quality": 0.68,
                "minimum_support_plausibility": 0.58,
                "minimum_feature_coherence": 0.68,
                "maximum_primitive_likeness_penalty": 0.24,
                "maximum_assembled_primitives_penalty": 0.26,
            }
        )
    elif family in {"industrial_crate", "mechanical_door", "console_terminal", "service_cabinet", "control_pedestal", "supply_container"}:
        semantic_requirements.update(
            {
                "minimum_part_coverage": 0.84,
                "minimum_silhouette_fidelity": 0.78,
                "minimum_structural_richness": 0.66,
                "minimum_symmetry_score": 0.62,
                "minimum_interface_score": 0.64,
                "minimum_adjacency_score": 0.68,
                "maximum_fragmentation_penalty": 0.24,
                "minimum_detail_density": 0.70,
                "minimum_silhouette_complexity": 0.68,
                "minimum_edge_readability": 0.66,
                "minimum_attachment_integration_quality": 0.70,
                "minimum_support_plausibility": 0.60,
                "minimum_feature_coherence": 0.68,
                "minimum_geometry_integration_quality": 0.80 if family in {"console_terminal", "control_pedestal"} else 0.78,
                "minimum_surface_authoring_quality": 0.72 if family in {"console_terminal", "mechanical_door", "control_pedestal"} else 0.70,
                "maximum_primitive_likeness_penalty": 0.22,
                "maximum_assembled_primitives_penalty": 0.24,
            }
        )
        if family == "service_cabinet":
            semantic_requirements.update(
                {
                    "minimum_symmetry_score": 0.50,
                    "minimum_adjacency_score": 0.66,
                }
            )
        if family == "control_pedestal":
            semantic_requirements.update(
                {
                    "minimum_silhouette_fidelity": 0.75,
                }
            )

    space_spec = asset.get("space", {})
    objectives = list(space_spec.get("objectives", []))
    search_best_of = int(space_spec.get("select", {}).get("best_of", 0) or 0)
    feature_density = str(asset.get("features", {}).get("density", "") or "")
    semantic_requirements["language_feature_density"] = feature_density
    semantic_requirements["language_search_best_of"] = search_best_of

    return AssetGraph(
        name=asset["name"],
        kind=str(asset.get("kind")),
        family=family,
        blueprint_id=blueprint_id,
        role=str(asset.get("intent", {}).get("role", "")),
        scale_cm=_scale_cm(asset),
        symmetry_axis=str(symmetry_axis) if symmetry_axis else None,
        validation_threshold=float(asset.get("validate", {}).get("threshold", 0.80)),
        critic_name=asset.get("validate", {}).get("score"),
        parts=parts,
        joints=[str(item) for item in asset.get("build", {}).get("rig", {}).get("joints", [])],
        sockets=[str(item) for item in asset.get("build", {}).get("interfaces", {}).get("sockets", [])],
        anchors=[str(item) for item in asset.get("build", {}).get("interfaces", {}).get("anchors", [])],
        materials=[str(item) for item in asset.get("intent", {}).get("materials", [])],
        styles=[str(item) for item in asset.get("intent", {}).get("style", [])],
        interactions=[str(item) for item in asset.get("intent", {}).get("interactions", [])],
        part_graph=_infer_part_graph(parts),
        semantic_requirements=semantic_requirements,
        authoring={
            "family_ref": asset.get("assembly", {}).get("family", ""),
            "from_family": asset.get("from", ""),
            "kit_ref": asset.get("assembly", {}).get("kit", ""),
            "resolved_kit": asset.get("assembly", {}).get("resolved_kit", {}),
            "resolved_family": asset.get("assembly", {}).get("resolved_family", {}),
            "components": resolved_components,
            "traits": asset.get("assembly", {}).get("resolved_traits", []),
            "mechanisms": asset.get("assembly", {}).get("resolved_mechanisms", []),
            "source_surface": asset.get("surface", {}),
            "surface_program": asset.get("surface", {}).get("program", ""),
            "surface_patterns": asset.get("surface", {}).get("patterns", []),
            "space": space_spec,
            "repair_policy": asset.get("repair_policy", {}),
            "fit": asset.get("fit", {}),
            "transfer": asset.get("transfer", {}),
            "reuse": asset.get("reuse", {}),
            "constraints": asset.get("constraints", {}),
            "ingest": asset.get("ingest", {}),
            "assembly_rules": asset.get("assembly_rules", {}),
            "shape_mode": asset.get("build", {}).get("shape", {}).get("mode", "generate"),
            "objectives": objectives,
            "self_reliant_target": family in {"brassbound_chest", "industrial_crate", "mechanical_door", "console_terminal", "service_cabinet", "control_pedestal", "supply_container", "sci_fi_wall_panel", "courier_drone"},
        },
    )
