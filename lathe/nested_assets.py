"""Nested asset source emission for socketed procedural modules."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

NESTED_ASSET_MANIFEST_VERSION = "lathe.nested_asset_sources.v1"
NESTED_BUILD_GRAPH_VERSION = "lathe.nested_asset_build_graph.v1"

_NON_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")

_KIND_BY_FAMILY: dict[str, str] = {
    "procedural_vehicle": "mechanical_assembly",
    "procedural_machine": "mechanical_assembly",
    "procedural_boat": "env_module",
    "procedural_interior": "env_module",
    "procedural_furniture": "hard_surface_prop",
    "procedural_foliage": "env_module",
    "procedural_urban_prop": "env_module",
}

_MATERIALS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "procedural_vehicle": ("painted_metal", "rubber", "glass", "warning_paint"),
    "procedural_boat": ("marine_paint", "deck_wood", "weathered_steel", "canvas"),
    "procedural_machine": ("industrial_steel", "rubber_tread", "warning_paint", "oil_stain"),
    "procedural_interior": ("painted_plaster", "finished_wood", "emissive_panel", "glass"),
    "procedural_furniture": ("finished_wood", "fabric", "painted_metal", "emissive_panel"),
    "procedural_foliage": ("moss", "bark", "leaf_litter", "stone"),
    "procedural_urban_prop": ("painted_metal", "concrete", "warning_paint"),
}

_PARTS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "procedural_vehicle": ("chassis", "cabin", "wheel", "rotor_pod", "cargo_module", "turret"),
    "procedural_boat": ("hull", "deck", "engine", "pontoon", "sail", "cargo_hold"),
    "procedural_machine": ("machine_base", "machine_column", "hydraulic_piston", "conveyor", "gear", "crane_boom"),
    "procedural_interior": ("room_cell", "partition", "ceiling_light", "alcove"),
    "procedural_furniture": ("furniture_base", "table_top", "chair_seat", "chair_back", "shelf_unit", "lamp"),
    "procedural_foliage": ("foliage_ground", "tree_trunk", "leaf_cluster", "bush", "grass_clump", "natural_rock", "flower"),
    "procedural_urban_prop": ("urban_base", "socket_plate", "street_crate", "sign_post"),
}


def nested_assets_from_child_layout(
    *,
    parent_asset_name: str,
    parent_family: str,
    parent_kind: str,
    child_module_layout: Mapping[str, Any] | None,
    source_module: str | None = None,
    parent_materials: Sequence[str] | None = None,
    parent_styles: Sequence[str] | None = None,
    parent_surface: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create linked child asset source payloads from a child-module layout."""
    layout = child_module_layout if isinstance(child_module_layout, Mapping) else {}
    slots = [slot for slot in layout.get("slots", []) if isinstance(slot, Mapping)]
    slots_by_id = {str(slot.get("id") or ""): slot for slot in slots}
    assets: list[dict[str, Any]] = []
    for instance in layout.get("instances", []) or []:
        if not isinstance(instance, Mapping):
            continue
        slot_id = str(instance.get("slot_id") or "")
        slot = slots_by_id.get(slot_id, {})
        family = str(instance.get("family") or "procedural_urban_prop")
        asset_name = _nested_asset_name(parent_asset_name, str(instance.get("instance_id") or slot_id))
        placement = _placement_for_slot(
            asset_name=asset_name,
            parent_asset_name=parent_asset_name,
            instance=instance,
            slot=slot,
        )
        dependency = _dependency_for_slot(
            asset_name=asset_name,
            parent_asset_name=parent_asset_name,
            instance=instance,
            slot=slot,
        )
        package = _package_plan_for_asset(asset_name=asset_name, parent_asset_name=parent_asset_name)
        surface_inheritance = _surface_inheritance(
            family=family,
            parent_materials=parent_materials,
            parent_styles=parent_styles,
            parent_surface=parent_surface,
        )
        materials = _materials_for_child(family, surface_inheritance)
        style_tags = _style_tags_for_child(instance, parent_styles=parent_styles, surface=surface_inheritance)
        source_text = _source_text(
            asset_name=asset_name,
            parent_asset_name=parent_asset_name,
            parent_family=parent_family,
            parent_kind=parent_kind,
            source_module=source_module or f"lathe.generated_nested.{_slug(parent_asset_name, fallback='asset')}",
            instance=instance,
            slot=slot,
            family=family,
            materials=materials,
            style_tags=style_tags,
            surface_inheritance=surface_inheritance,
        )
        assets.append(
            {
                "asset_name": asset_name,
                "asset_kind": _KIND_BY_FAMILY.get(family, "env_module"),
                "family": family,
                "blueprint_id": str(instance.get("blueprint_id") or ""),
                "instance_id": str(instance.get("instance_id") or asset_name),
                "slot_id": slot_id,
                "slot_kind": str(slot.get("kind") or instance.get("kind") or ""),
                "socket": str(slot.get("socket") or ""),
                "anchor": str(slot.get("anchor") or ""),
                "mount": str(slot.get("mount") or ""),
                "template": str(instance.get("template") or ""),
                "archetype": str(instance.get("archetype") or ""),
                "source_filename": f"{asset_name}.lth",
                "source_text": source_text,
                "shape_controls": _shape_controls(instance, slot, parent_asset_name=parent_asset_name),
                "parts": _parts_for_instance(instance, family),
                "materials": materials,
                "style_tags": style_tags,
                "surface_inheritance": surface_inheritance,
                "placement": placement,
                "dependency": dependency,
                "package": package,
            }
        )
    summary = {
        "nested_asset_count": len(assets),
        "families": _counts(asset.get("family") for asset in assets),
        "templates": _counts(asset.get("template") for asset in assets),
        "slot_kinds": _counts(asset.get("slot_kind") for asset in assets),
        "asset_names": [asset["asset_name"] for asset in assets],
        "build_node_count": len(assets) + (1 if assets else 0),
        "build_edge_count": len(assets),
        "placement_count": len(assets),
    }
    build_graph = _build_graph(
        parent_asset_name=parent_asset_name,
        parent_family=parent_family,
        parent_kind=parent_kind,
        assets=assets,
    )
    return {
        "schema_version": NESTED_ASSET_MANIFEST_VERSION,
        "parent_asset_name": parent_asset_name,
        "parent_family": parent_family,
        "parent_kind": parent_kind,
        "summary": summary,
        "assets": assets,
        "build_graph": build_graph,
    }


def nested_asset_manifest_for_signature(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return nested-asset metadata without source text for signatures/manifests."""
    if not isinstance(manifest, Mapping):
        return {}
    assets = [
        {key: value for key, value in asset.items() if key != "source_text"}
        for asset in manifest.get("assets", [])
        if isinstance(asset, Mapping)
    ]
    parent_asset_name = str(manifest.get("parent_asset_name") or "")
    parent_family = str(manifest.get("parent_family") or "")
    parent_kind = str(manifest.get("parent_kind") or "")
    build_graph = _build_graph(
        parent_asset_name=parent_asset_name,
        parent_family=parent_family,
        parent_kind=parent_kind,
        assets=assets,
    )
    out = {
        "schema_version": str(manifest.get("schema_version") or NESTED_ASSET_MANIFEST_VERSION),
        "parent_asset_name": parent_asset_name,
        "parent_family": parent_family,
        "parent_kind": parent_kind,
        "summary": dict(manifest.get("summary") or {}),
        "assets": assets,
        "build_graph": build_graph,
    }
    diagnostics = manifest.get("diagnostics")
    if isinstance(diagnostics, list):
        out["diagnostics"] = list(diagnostics)
    assembly = manifest.get("assembly")
    if isinstance(assembly, Mapping):
        out["assembly"] = dict(assembly)
    return out


def nested_build_graph_from_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return only the parent/child dependency graph for a nested asset manifest."""
    clean = nested_asset_manifest_for_signature(manifest)
    return dict(clean.get("build_graph") or {})


def _build_graph(
    *,
    parent_asset_name: str,
    parent_family: str,
    parent_kind: str,
    assets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not assets:
        return {
            "schema_version": NESTED_BUILD_GRAPH_VERSION,
            "parent_asset_name": parent_asset_name,
            "nodes": [],
            "edges": [],
            "placements": [],
            "package_plan": {},
            "summary": {"node_count": 0, "edge_count": 0, "placement_count": 0},
        }
    nodes: list[dict[str, Any]] = [
        {
            "id": parent_asset_name,
            "role": "parent",
            "asset_name": parent_asset_name,
            "family": parent_family,
            "kind": parent_kind,
        }
    ]
    edges: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []
    for asset in assets:
        asset_name = str(asset.get("asset_name") or "")
        if not asset_name:
            continue
        build_payload = asset.get("build") if isinstance(asset.get("build"), Mapping) else {}
        package_payload = asset.get("package") if isinstance(asset.get("package"), Mapping) else {}
        node = {
            "id": asset_name,
            "role": "nested_child",
            "asset_name": asset_name,
            "family": str(asset.get("family") or ""),
            "kind": str(asset.get("asset_kind") or ""),
            "source_path": str(asset.get("source_path") or asset.get("source_filename") or ""),
            "build_root": str(build_payload.get("out_dir") or package_payload.get("build_root") or ""),
        }
        if build_payload:
            node["build"] = dict(build_payload)
        nodes.append(node)
        dependency = asset.get("dependency") if isinstance(asset.get("dependency"), Mapping) else {}
        edge = dict(dependency)
        edge.setdefault("id", f"{parent_asset_name}_contains_{asset_name}")
        edge.setdefault("from", parent_asset_name)
        edge.setdefault("to", asset_name)
        edge.setdefault("edge_type", "nested_child")
        edge.setdefault("relation", "attached_to")
        edge.setdefault("requires", ["source", "check", "plan"])
        if build_payload:
            edge["build_status"] = "built" if build_payload.get("ok") else "failed"
        edges.append(edge)
        placement = asset.get("placement")
        if isinstance(placement, Mapping):
            placements.append(dict(placement))
    return {
        "schema_version": NESTED_BUILD_GRAPH_VERSION,
        "parent_asset_name": parent_asset_name,
        "nodes": nodes,
        "edges": edges,
        "placements": placements,
        "package_plan": {
            "child_source_root": f"assets/{parent_asset_name}/children",
            "child_build_root": f"builds/{parent_asset_name}/children",
            "aggregate_metadata_path": f"assets/{parent_asset_name}/metadata.json",
            "child_count": len([node for node in nodes if node.get("role") == "nested_child"]),
        },
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "placement_count": len(placements),
        },
    }


def _placement_for_slot(
    *,
    asset_name: str,
    parent_asset_name: str,
    instance: Mapping[str, Any],
    slot: Mapping[str, Any],
) -> dict[str, Any]:
    position = _vec3(slot.get("normalized_position"))
    facing = float(slot.get("facing_degrees") or 0.0)
    socket = str(slot.get("socket") or f"module_socket_{slot.get('id') or 'child'}")
    anchor = str(slot.get("anchor") or f"{slot.get('kind') or 'module'}_mount")
    return {
        "id": f"{asset_name}_placement",
        "parent_asset_name": parent_asset_name,
        "child_asset_name": asset_name,
        "slot_id": str(slot.get("id") or instance.get("slot_id") or "slot"),
        "slot_kind": str(slot.get("kind") or instance.get("kind") or "module"),
        "socket": socket,
        "anchor": anchor,
        "mount": str(slot.get("mount") or "module_mount"),
        "relation": "attached_to",
        "normalized_position": position,
        "local_position": position,
        "local_rotation_degrees": [0.0, round(facing, 6), 0.0],
        "local_scale": [1.0, 1.0, 1.0],
        "local_transform": _yaw_translation_transform(position, facing),
        "snap": {
            "grid": str(slot.get("snap_grid") or "setpiece_child_module_grid"),
            "clearance": float(slot.get("clearance") or 0.12),
            "socket_type": str(slot.get("kind") or instance.get("kind") or "module"),
            "compat_kind": str(instance.get("kind") or slot.get("kind") or "module"),
        },
        "attach": {
            "parent_endpoint": anchor,
            "child_endpoint": socket,
            "parent_path": f"{parent_asset_name}.{anchor}",
            "child_path": f"{asset_name}.{socket}",
        },
    }


def _dependency_for_slot(
    *,
    asset_name: str,
    parent_asset_name: str,
    instance: Mapping[str, Any],
    slot: Mapping[str, Any],
) -> dict[str, Any]:
    slot_id = str(slot.get("id") or instance.get("slot_id") or "slot")
    return {
        "id": f"{parent_asset_name}_requires_{asset_name}",
        "from": parent_asset_name,
        "to": asset_name,
        "edge_type": "nested_child",
        "relation": "attached_to",
        "slot_id": slot_id,
        "slot_kind": str(slot.get("kind") or instance.get("kind") or "module"),
        "socket": str(slot.get("socket") or ""),
        "anchor": str(slot.get("anchor") or ""),
        "requires": ["source", "check", "plan"],
        "build_after": parent_asset_name,
        "package_under": f"assets/{parent_asset_name}/children/{asset_name}",
    }


def _package_plan_for_asset(*, asset_name: str, parent_asset_name: str) -> dict[str, Any]:
    return {
        "source_root": f"assets/{parent_asset_name}/children/{asset_name}",
        "source_path": f"assets/{parent_asset_name}/children/{asset_name}/{asset_name}.lth",
        "build_root": f"builds/{parent_asset_name}/children/{asset_name}",
        "metadata_path": f"assets/{parent_asset_name}/children/{asset_name}/metadata.json",
        "package_manifest_path": f"builds/{parent_asset_name}/children/{asset_name}/stages/package/package_manifest.json",
        "selector_manifest_path": f"builds/{parent_asset_name}/children/{asset_name}/selector_manifest.json",
    }


def _vec3(value: Any) -> list[float]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and len(value) >= 3:
        return [round(float(value[0]), 6), round(float(value[1]), 6), round(float(value[2]), 6)]
    return [0.0, 0.0, 0.0]


def _yaw_translation_transform(position: Sequence[float], facing_degrees: float) -> list[list[float]]:
    yaw = math.radians(float(facing_degrees))
    c = round(math.cos(yaw), 6)
    s = round(math.sin(yaw), 6)
    x, y, z = _vec3(position)
    return [
        [c, 0.0, s, x],
        [0.0, 1.0, 0.0, y],
        [-s, 0.0, c, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _source_text(
    *,
    asset_name: str,
    parent_asset_name: str,
    parent_family: str,
    parent_kind: str,
    source_module: str,
    instance: Mapping[str, Any],
    slot: Mapping[str, Any],
    family: str,
    materials: Sequence[str],
    style_tags: Sequence[str],
    surface_inheritance: Mapping[str, Any],
) -> str:
    asset_kind = _KIND_BY_FAMILY.get(family, "env_module")
    controls = _shape_controls(instance, slot, parent_asset_name=parent_asset_name)
    parts = _parts_for_instance(instance, family)
    role = " ".join(
        item
        for item in (
            str(instance.get("template") or "nested_module").replace("_", " "),
            "child module for",
            parent_asset_name.replace("_", " "),
        )
        if item
    )
    socket = str(slot.get("socket") or f"module_socket_{slot.get('id') or 'child'}")
    anchor = str(slot.get("anchor") or f"{slot.get('kind') or 'module'}_mount")
    tags = _dedupe(
        [
            "nested",
            "child_module",
            str(instance.get("kind") or ""),
            str(instance.get("template") or ""),
            str(instance.get("archetype") or ""),
            *[str(item) for item in style_tags],
            *[str(item) for item in instance.get("tags", [])],
        ]
    )
    lines = [
        f"module {source_module}.children",
        "",
        f"asset {asset_name}: {asset_kind} {{",
        "  intent {",
        f"    role = {_source_string(role)}",
        f"    style = {_source_array(tags, identifiers=True)}",
        f"    parts = {_source_array(parts, identifiers=True)}",
        f"    materials = {_source_array(materials, identifiers=True)}",
        "    negatives = [unmounted, unscaled]",
        "    scale = 0.45m",
        "    interactions = [attachable, socketed]",
        "  }",
        "",
        "  assembly {",
        f"    runtime_family = {family}",
        "  }",
        "",
    ]
    surface_lines = _surface_block_lines(surface_inheritance)
    if surface_lines:
        lines.extend(surface_lines)
        lines.append("")
    lines.extend(
        [
            "  build {",
            "    shape {",
            "      mode = generate",
            "      candidates = 1",
            f"      seed = {_seed(asset_name)}",
        ]
    )
    for key, value in sorted(controls.items()):
        lines.append(f"      {key} = {_source_value(value, identifiers=True)}")
    lines.extend(
        [
            "    }",
            "    interfaces {",
            f"      sockets = {_source_array([socket], identifiers=True)}",
            f"      anchors = {_source_array([anchor], identifiers=True)}",
            "      connections = ["
            + _connection_call(
                {
                    "id": f"{asset_name}_to_parent_slot",
                    "source": socket,
                    "target": f"parent.{anchor}",
                    "relation": "attached_to",
                    "socket_type": str(slot.get("kind") or instance.get("kind") or "module"),
                    "compat_kind": str(instance.get("kind") or slot.get("kind") or "module"),
                    "clearance": slot.get("clearance", 0.12),
                    "snap_grid": slot.get("snap_grid", "setpiece_child_module_grid"),
                }
            )
            + "]",
            "    }",
            "  }",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _surface_inheritance(
    *,
    family: str,
    parent_materials: Sequence[str] | None,
    parent_styles: Sequence[str] | None,
    parent_surface: Mapping[str, Any] | None,
) -> dict[str, Any]:
    surface: dict[str, Any] = {
        "materials": list(_MATERIALS_BY_FAMILY.get(family, ("mat_scene_default",))),
        "inheritance": "parent_scene_surface",
    }
    parent_surface = parent_surface if isinstance(parent_surface, Mapping) else {}
    inherited_materials = _string_sequence(parent_materials)
    if inherited_materials:
        surface["materials"] = _dedupe([*surface["materials"], *inherited_materials])
    for key in (
        "materials",
        "material_layers",
        "layers",
        "story_decals",
        "faction_marks",
        "markings",
        "decals",
        "decal_targets",
        "story_targets",
        "story_regions",
        "patterns",
        "mask_programs",
        "trim_sheets",
    ):
        values = _string_sequence(parent_surface.get(key))
        if values:
            existing = _string_sequence(surface.get(key))
            surface[key] = _dedupe([*existing, *values])
    for key in (
        "wear_story",
        "usage_history",
        "story",
        "wear_level",
        "edge_wear",
        "damage_level",
        "story_density",
        "story_asymmetry",
        "asymmetry",
    ):
        value = parent_surface.get(key)
        if isinstance(value, str | int | float | bool):
            surface[key] = value
    zones = parent_surface.get("zones") if isinstance(parent_surface.get("zones"), Mapping) else {}
    if zones:
        surface["zones"] = {
            _slug(str(zone), fallback="zone"): str(material)
            for zone, material in zones.items()
            if isinstance(zone, str) and material not in {None, ""}
        }
    parent_style_tags = _string_sequence(parent_styles)
    if parent_style_tags:
        surface["parent_styles"] = parent_style_tags
    return surface


def _materials_for_child(family: str, surface: Mapping[str, Any]) -> list[str]:
    defaults = list(_MATERIALS_BY_FAMILY.get(family, ("mat_scene_default",)))
    materials = _string_sequence(surface.get("materials"))
    zones = surface.get("zones") if isinstance(surface.get("zones"), Mapping) else {}
    zone_materials = [str(value) for value in zones.values() if value is not None and value != ""]
    return _dedupe([*defaults, *materials, *zone_materials])[:16]


def _style_tags_for_child(
    instance: Mapping[str, Any],
    *,
    parent_styles: Sequence[str] | None,
    surface: Mapping[str, Any],
) -> list[str]:
    tags = [
        *[str(item) for item in parent_styles or [] if item],
        *[str(item) for item in surface.get("parent_styles", []) if item],
        *[str(item) for item in surface.get("faction_marks", []) if item],
        *[str(item) for item in surface.get("markings", []) if item],
        str(surface.get("wear_story") or ""),
        str(instance.get("template") or ""),
        str(instance.get("archetype") or ""),
    ]
    return [_slug(item, fallback="style") for item in _dedupe(tags) if item]


def _surface_block_lines(surface: Mapping[str, Any]) -> list[str]:
    body: list[str] = []
    for key in (
        "materials",
        "material_layers",
        "layers",
        "story_decals",
        "faction_marks",
        "markings",
        "decals",
        "decal_targets",
        "story_targets",
        "story_regions",
        "patterns",
        "mask_programs",
        "trim_sheets",
    ):
        values = _string_sequence(surface.get(key))
        if values:
            body.append(f"    {key} = {_source_array(values, identifiers=True)}")
    for key in (
        "wear_story",
        "usage_history",
        "story",
        "wear_level",
        "edge_wear",
        "damage_level",
        "story_density",
        "story_asymmetry",
        "asymmetry",
    ):
        if key in surface:
            body.append(f"    {key} = {_source_value(surface[key], identifiers=True)}")
    zones = surface.get("zones") if isinstance(surface.get("zones"), Mapping) else {}
    for zone, material in sorted(zones.items(), key=lambda item: str(item[0])):
        zone_id = _slug(str(zone), fallback="zone")
        body.append(f"    zones.{zone_id} = {_source_value(material, identifiers=True)}")
    if not body:
        return []
    return ["  surface {", *body, "  }"]


def _shape_controls(
    instance: Mapping[str, Any],
    slot: Mapping[str, Any],
    *,
    parent_asset_name: str,
) -> dict[str, Any]:
    controls = dict(instance.get("controls") or {})
    position = slot.get("normalized_position")
    if isinstance(position, Sequence) and not isinstance(position, str | bytes | bytearray) and len(position) >= 3:
        controls.setdefault("slot_position_x", round(float(position[0]), 6))
        controls.setdefault("slot_position_y", round(float(position[1]), 6))
        controls.setdefault("slot_position_z", round(float(position[2]), 6))
    controls.setdefault("nested_asset", True)
    controls.setdefault("nested_parent_asset", parent_asset_name)
    controls.setdefault("nested_slot_id", str(slot.get("id") or instance.get("slot_id") or "slot"))
    controls.setdefault("nested_socket", str(slot.get("socket") or "module_socket"))
    controls.setdefault("nested_anchor", str(slot.get("anchor") or "module_anchor"))
    controls.setdefault("nested_mount", str(slot.get("mount") or "module_mount"))
    controls.setdefault("nested_template", str(instance.get("template") or "module"))
    controls.setdefault("nested_family", str(instance.get("family") or "procedural_urban_prop"))
    controls.setdefault("slot_clearance", float(slot.get("clearance") or 0.12))
    controls.setdefault("slot_facing_degrees", float(slot.get("facing_degrees") or 0.0))
    return _source_safe_controls(controls)


def _parts_for_instance(instance: Mapping[str, Any], family: str) -> list[str]:
    parts = [str(item) for item in instance.get("components", []) if item]
    parts.extend(_PARTS_BY_FAMILY.get(family, ()))
    return _dedupe([_slug(part, fallback="part") for part in parts if part])


def _source_safe_controls(controls: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in controls.items():
        if not isinstance(key, str) or not key:
            continue
        safe_key = _slug(key, fallback="control")
        if isinstance(value, bool | int | float | str):
            out[safe_key] = value
        elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
            items = [item for item in value if isinstance(item, bool | int | float | str)]
            if items:
                out[safe_key] = [str(item) if not isinstance(item, bool | int | float) else item for item in items]
    return out


def _connection_call(value: Mapping[str, Any]) -> str:
    args: list[str] = []
    for key in ("id", "source", "target", "relation", "socket_type", "compat_kind", "clearance", "snap_grid"):
        item = value.get(key)
        if item is None or item == "":
            continue
        args.append(f"{key}: {_source_value(item, identifiers=True)}")
    return f"connection({', '.join(args)})"


def _source_value(value: Any, *, identifiers: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return _source_array(value, identifiers=identifiers)
    if identifiers and isinstance(value, str) and _IDENTIFIER_RE.match(value):
        return value
    return json.dumps(str(value), ensure_ascii=True)


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _source_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _source_array(values: Sequence[Any], *, identifiers: bool = False) -> str:
    items: list[str] = []
    for value in values:
        if identifiers and isinstance(value, str) and _IDENTIFIER_RE.match(value):
            items.append(value)
        else:
            items.append(json.dumps(value, ensure_ascii=True))
    return "[" + ", ".join(items) + "]"


def _string_sequence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value if item is not None and item != ""]
    return [str(value)]


def _nested_asset_name(parent_asset_name: str, instance_id: str) -> str:
    return _slug(f"{parent_asset_name}_{instance_id}", fallback="nested_asset")[:64].rstrip("_")


def _slug(value: str, *, fallback: str) -> str:
    slug = _NON_IDENTIFIER_RE.sub("_", str(value).lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    return slug[:96].rstrip("_") or fallback


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:8], 16)


def _counts(values: Sequence[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        text = str(value or "")
        if not text:
            continue
        out[text] = out.get(text, 0) + 1
    return dict(sorted(out.items()))


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
