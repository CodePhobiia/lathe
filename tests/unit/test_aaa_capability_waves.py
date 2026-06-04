"""AAA capability-wave generation controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from lathe.asset_graph import build_asset_graph
from lathe.core.mesh import RuntimeMesh
from lathe.core.stages.optimize import _resolve_lod_ratios
from lathe.core.stages.physics import _collision_proxy_mesh, _resolve_collision_proxy_mode
from lathe.geometry_detail import geometry_detail_controls_from_authoring
from lathe.materials import surface_with_style_pack_defaults
from lathe.parser import parse_text
from lathe.resolver import materialize_asset
from lathe.scaffold_compiler import compile_scaffold_candidates
from lathe.stages import lod as lod_mod
from lathe.surface_runtime import build_surface_bundle
from PIL import Image


def _conditioning() -> dict[str, Any]:
    return {"reference_strength": 0.0, "image_refs": [], "material_refs": [], "mesh_refs": []}


def _asset(shape_controls: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "capability_probe",
        "kind": "hard_surface_prop",
        "intent": {
            "role": "console terminal AAA capability probe",
            "parts": ["body", "console_panel", "socket_plate", "screen_panel", "stand_base"],
            "materials": ["painted_steel", "bare_metal", "signal_glass"],
        },
        "features": {},
        "surface": {},
        "build": {
            "shape": {"mode": "generate", "symmetry": "x", **shape_controls},
            "rig": {"type": "none", "joints": []},
            "interfaces": {},
            "physics": {"collision": "convex_decomp", "max_hulls": 6},
            "optimize": {"lods": 3, "atlas": True},
        },
        "validate": {"threshold": 0.80},
        "package": {"formats": ["glb", "usd"]},
        "experimental": {},
    }


def _compile(shape_controls: dict[str, Any]) -> dict[str, Any]:
    return compile_scaffold_candidates(
        build_asset_graph(_asset(shape_controls)),
        seed=271,
        candidates_count=1,
        conditioning=_conditioning(),
        mode="generate",
    )


def test_wave_a_edge_arrays_and_surface_operators_change_geometry() -> None:
    baseline = _compile({"detail_density": "off", "edge_complexity": 0})
    rich = _compile(
        {
            "detail_density": "hero",
            "detail_motifs": [
                "panel_seam",
                "groove_channel",
                "raised_ridge",
                "inset_panel",
                "outset_panel",
                "trim_strip",
                "bolt_grid",
                "socket_point",
                "linear_detail_array",
                "radial_detail_array",
            ],
            "edge_complexity": "high",
            "edge_treatment": "chamfered",
            "edge_hardness": "hard",
            "bevel_width": 0.35,
            "chamfer_width": 0.25,
            "panelization": "high",
            "groove_density": "high",
            "ridge_density": "high",
            "trim_density": "high",
            "inset_depth": "high",
            "outset_depth": "high",
            "greeble_density": "high",
            "surface_layer_count": 3,
            "modular_attachment_points": 4,
            "linear_detail_repeats": 5,
            "radial_detail_repeats": 8,
            "detail_array_axis": "x",
            "detail_zones": ["body", "console_panel", "socket_plate"],
        }
    )

    baseline_ir = baseline["shape_irs"][0]
    rich_ir = rich["shape_irs"][0]
    operators = rich_ir.assessment["geometry_detail_operator_counts"]
    assert rich_ir.assessment["primitive_count"] > baseline_ir.assessment["primitive_count"]
    assert len(rich["runtime_candidates"][0]["mesh"].faces) > len(baseline["runtime_candidates"][0]["mesh"].faces)
    assert {
        "bolt_grid",
        "corner_guard",
        "groove_channel",
        "inset_panel",
        "linear_detail_array",
        "outset_panel",
        "panel_seam",
        "radial_detail_array",
        "raised_ridge",
        "socket_point",
        "trim_strip",
    }.issubset(set(operators))
    assert "edge_treatment_chamfered" in rich_ir.assessment["geometry_detail_edge_metadata"]
    assert "edge_hardness_hard" in rich_ir.assessment["geometry_detail_edge_metadata"]


def test_wave_b_c_f_g_zone_style_module_and_pipeline_controls_reach_runtime() -> None:
    controls = {
        "detail_density": "high",
        "style_modifiers": ["brutalist", "modular"],
        "module_sockets": ["power_bus", "side_rail"],
        "lod_levels": 4,
        "collision_proxy": "convex_hull",
        "export_profiles": ["glb", "usd", "godot"],
        "detail_zones": ["body", "console_panel", "socket_plate"],
        "zone_body_density": "hero",
        "zone_body_motifs": ["panel_seam", "outset_panel", "corner_guard"],
        "zone_body_falloff": "edges",
        "zone_console_panel_density": "high",
        "zone_console_panel_motifs": ["groove_channel", "raised_ridge", "linear_detail_array"],
        "zone_console_panel_linear_detail_repeats": 4,
        "zone_socket_plate_density": "high",
        "zone_socket_plate_motifs": ["socket_point", "bolt_grid", "radial_detail_array"],
        "zone_socket_plate_modular_attachment_points": 6,
        "zone_socket_plate_radial_detail_repeats": 6,
    }

    graph = build_asset_graph(_asset(controls))
    parsed_controls = geometry_detail_controls_from_authoring(graph.authoring)
    assert [zone.name for zone in parsed_controls.zones] == ["body", "console_panel", "socket_plate"]
    assert parsed_controls.style_modifiers == ("brutalist", "modular")

    result = compile_scaffold_candidates(
        graph,
        seed=313,
        candidates_count=1,
        conditioning=_conditioning(),
        mode="generate",
    )
    ir = result["shape_irs"][0]
    report = result["runtime_candidates"][0]["meta"]["feature_report"]
    hints = result["runtime_candidates"][0]["meta"]["game_pipeline_hints"]

    assert ir.assessment["geometry_detail_zone_count"] == 3
    assert set(ir.assessment["geometry_detail_zones"]) == {"body", "console_panel", "socket_plate"}
    assert set(ir.assessment["geometry_detail_style_modifiers"]) == {"brutalist", "modular"}
    assert set(ir.assessment["geometry_detail_module_sockets"]) == {"power_bus", "side_rail"}
    assert len(report["geometry_detail_zones_applied"]) >= 3
    assert hints["lod_levels_requested"] == 4
    assert hints["collision_proxy"] == "convex_hull"
    assert hints["material_id_strategy"] == "zone_and_part_material_ids"
    assert set(hints["export_profiles"]) == {"glb", "godot", "usd"}


def test_wave_c_style_modifiers_change_candidate_proportions_and_mesh_bounds() -> None:
    plain = _compile({"detail_density": "low"})
    brutalist = _compile(
        {
            "detail_density": "low",
            "style_modifiers": ["brutalist", "industrial"],
            "detail_motifs": ["panel_seam", "trim_strip"],
        }
    )

    plain_params = plain["runtime_candidates"][0]["meta"]["candidate_params"]
    styled_params = brutalist["runtime_candidates"][0]["meta"]["candidate_params"]
    assert styled_params["silhouette_bias"] > plain_params["silhouette_bias"]
    assert styled_params["panel_depth"] > plain_params["panel_depth"]
    assert styled_params["edge_weight"] > plain_params["edge_weight"]

    plain_bounds = plain["runtime_candidates"][0]["mesh"].bounds
    styled_bounds = brutalist["runtime_candidates"][0]["mesh"].bounds
    plain_extents = plain_bounds[1] - plain_bounds[0]
    styled_extents = styled_bounds[1] - styled_bounds[0]
    assert styled_extents[0] > plain_extents[0] * 1.03
    assert styled_extents[2] > plain_extents[2] * 1.03
    assert "brutalist" in brutalist["shape_irs"][0].assessment["geometry_detail_style_modifiers"]


def test_wave_c_style_pack_expands_into_geometry_modules_and_surface_defaults(tmp_path: Path) -> None:
    baseline = _compile({"detail_density": "low", "style_pack": []})
    styled_controls = {
        "style_pack": "industrial_hero",
        "style_intensity": "hero",
        "detail_zones": ["body", "console_panel"],
        "zone_console_panel_density": "high",
    }
    graph = build_asset_graph(_asset(styled_controls))
    controls = geometry_detail_controls_from_authoring(graph.authoring)

    assert controls.style_packs == ("industrial_hero",)
    assert {"industrial", "brutalist", "modular"}.issubset(set(controls.style_modifiers))
    assert {"panel_seam", "groove_channel", "bolt_grid", "socket_point"}.issubset(set(controls.detail_motifs))
    assert {"power_cell", "shield_plate", "antenna"}.issubset(set(controls.module_categories))
    assert controls.module_count >= 3

    styled = _compile(styled_controls)
    styled_ir = styled["shape_irs"][0]
    baseline_ir = baseline["shape_irs"][0]
    report = styled["runtime_candidates"][0]["meta"]["feature_report"]
    hints = styled["runtime_candidates"][0]["meta"]["game_pipeline_hints"]

    assert styled_ir.assessment["primitive_count"] > baseline_ir.assessment["primitive_count"]
    assert len(styled["runtime_candidates"][0]["mesh"].faces) > len(baseline["runtime_candidates"][0]["mesh"].faces)
    assert styled_ir.assessment["geometry_detail_style_packs"] == ["industrial_hero"]
    assert "industrial_hero" in report["geometry_detail_style_packs"]
    assert "industrial_hero" in hints["style_packs"]
    assert {"module_power_cell", "module_shield_plate", "module_antenna"} <= set(
        styled_ir.assessment["geometry_detail_operator_counts"]
    )

    surface_asset = _surface_asset({})
    surface_asset["build"]["shape"] = styled_controls
    surface_defaults = surface_with_style_pack_defaults(surface_asset)
    assert surface_defaults["material_layers"] == ["painted_steel", "bare_metal", "rubber"]
    assert surface_defaults["wear_story"] == "field_used"
    assert set(surface_defaults["story_decals"]) >= {"service_number", "hazard_stripe"}

    surface_bundle = build_surface_bundle(
        asset=surface_asset,
        out_dir=tmp_path,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )
    manifest = surface_bundle["surface_manifest"]
    assert manifest["procedural_material_layers"] == ["painted_steel", "bare_metal", "rubber"]
    assert manifest["surface_story"]["wear_story"] == "field_used"
    assert set(manifest["decals"]) >= {"service_number", "hazard_stripe", "edge_rub"}


def test_wave_c_silhouette_profile_controls_change_structure_and_bounds() -> None:
    baseline = _compile({"detail_density": "low"})
    controls = {
        "detail_density": "high",
        "silhouette_profile": "sleek_winged",
        "silhouette_motifs": ["wing", "spine", "tower", "outrigger", "blade", "handle", "guard_cowl"],
        "silhouette_intensity": "hero",
        "detail_zones": ["body", "console_panel", "socket_plate"],
    }
    parsed = geometry_detail_controls_from_authoring(build_asset_graph(_asset(controls)).authoring)
    assert parsed.silhouette_profile == "sleek_winged"
    assert {"wing", "spine", "tower", "outrigger", "blade", "handle", "guard_cowl"} <= set(
        parsed.silhouette_motifs
    )

    sculpted = _compile(controls)
    baseline_ir = baseline["shape_irs"][0]
    sculpted_ir = sculpted["shape_irs"][0]
    operators = sculpted_ir.assessment["geometry_detail_operator_counts"]

    assert sculpted_ir.assessment["primitive_count"] > baseline_ir.assessment["primitive_count"]
    assert len(sculpted["runtime_candidates"][0]["mesh"].faces) > len(baseline["runtime_candidates"][0]["mesh"].faces)
    assert {
        "silhouette_blade",
        "silhouette_guard_cowl",
        "silhouette_handle",
        "silhouette_outrigger",
        "silhouette_spine",
        "silhouette_tower",
        "silhouette_wing",
    }.issubset(set(operators))
    assert sculpted_ir.assessment["geometry_detail_silhouette_profiles"] == ["sleek_winged"]
    assert {"wing", "spine", "tower", "outrigger", "blade", "handle", "guard_cowl"} <= set(
        sculpted_ir.assessment["geometry_detail_silhouette_motifs"]
    )

    baseline_params = baseline["runtime_candidates"][0]["meta"]["candidate_params"]
    sculpted_params = sculpted["runtime_candidates"][0]["meta"]["candidate_params"]
    assert sculpted_params["width_scale"] > baseline_params["width_scale"]
    assert sculpted_params["height_scale"] > baseline_params["height_scale"]
    assert sculpted_params["attachment_spread"] > baseline_params["attachment_spread"]

    baseline_extents = baseline["runtime_candidates"][0]["mesh"].bounds[1] - baseline["runtime_candidates"][0]["mesh"].bounds[0]
    sculpted_extents = sculpted["runtime_candidates"][0]["mesh"].bounds[1] - sculpted["runtime_candidates"][0]["mesh"].bounds[0]
    assert sculpted_extents[0] > baseline_extents[0] * 1.08
    assert sculpted_extents[1] > baseline_extents[1] * 1.02
    assert "sleek_winged" in sculpted["runtime_candidates"][0]["meta"]["game_pipeline_hints"]["silhouette_profiles"]
    assert "wing" in sculpted["runtime_candidates"][0]["meta"]["feature_report"]["geometry_detail_silhouette_motifs"]


def test_wave3_attachment_motifs_create_visible_modular_geometry() -> None:
    baseline = _compile({"detail_density": "low", "attachment_motifs": []})
    motif_result = _compile(
        {
            "detail_density": "hero",
            "attachment_motifs": [
                "rail",
                "fin",
                "strap",
                "cable",
                "vent_stack",
                "handle_bar",
                "guard_bar",
                "ornament",
            ],
            "attachment_count": 5,
            "detail_zones": ["body", "console_panel", "socket_plate"],
            "zone_console_panel_attachment_motifs": ["rail", "cable", "vent_stack"],
            "zone_console_panel_attachment_count": 4,
            "zone_socket_plate_attachment_motifs": ["handle_bar", "guard_bar", "ornament"],
            "zone_socket_plate_attachment_count": 6,
        }
    )

    baseline_ir = baseline["shape_irs"][0]
    motif_ir = motif_result["shape_irs"][0]
    operators = motif_ir.assessment["geometry_detail_operator_counts"]
    assert motif_ir.assessment["primitive_count"] > baseline_ir.assessment["primitive_count"]
    assert {
        "attachment_cable",
        "attachment_fin",
        "attachment_guard_bar",
        "attachment_handle_bar",
        "attachment_ornament",
        "attachment_rail",
        "attachment_strap",
        "attachment_vent_stack",
    }.issubset(set(operators))
    assert set(motif_ir.assessment["geometry_detail_attachment_motifs"]) == {
        "cable",
        "fin",
        "guard",
        "handle",
        "ornament",
        "rail",
        "strap",
        "vent_stack",
    }
    feature_report = motif_result["runtime_candidates"][0]["meta"]["feature_report"]
    assert set(feature_report["geometry_detail_attachment_motifs"]) >= {"rail", "cable", "guard"}
    assert "attachment_motifs" in motif_result["runtime_candidates"][0]["meta"]["game_pipeline_hints"]


def test_wave_f_module_categories_generate_swappable_module_groups() -> None:
    baseline = _compile({"detail_density": "low", "module_categories": []})
    controls = {
        "detail_density": "hero",
        "module_categories": [
            "sensor_pod",
            "power_cell",
            "barrel",
            "blade",
            "wing",
            "leg",
            "shield_plate",
            "antenna",
        ],
        "module_count": 3,
        "detail_zones": ["body", "console_panel", "socket_plate"],
        "zone_console_panel_module_categories": ["sensor", "battery", "antenna"],
        "zone_console_panel_module_count": 2,
        "zone_socket_plate_module_categories": ["barrel", "blade", "shield", "leg"],
        "zone_socket_plate_module_count": 3,
    }
    parsed = geometry_detail_controls_from_authoring(build_asset_graph(_asset(controls)).authoring)
    assert set(parsed.module_categories) == {
        "sensor_pod",
        "power_cell",
        "barrel",
        "blade",
        "wing",
        "leg",
        "shield_plate",
        "antenna",
    }
    assert parsed.module_count == 3
    assert any(zone.module_categories for zone in parsed.zones)

    modular = _compile(controls)
    modular_ir = modular["shape_irs"][0]
    baseline_ir = baseline["shape_irs"][0]
    operators = modular_ir.assessment["geometry_detail_operator_counts"]
    assert modular_ir.assessment["primitive_count"] > baseline_ir.assessment["primitive_count"]
    assert {
        "module_antenna",
        "module_barrel",
        "module_blade",
        "module_leg",
        "module_power_cell",
        "module_sensor_pod",
        "module_shield_plate",
        "module_wing",
    }.issubset(set(operators))
    assert set(modular_ir.assessment["geometry_detail_module_categories"]) == {
        "antenna",
        "barrel",
        "blade",
        "leg",
        "power_cell",
        "sensor_pod",
        "shield_plate",
        "wing",
    }
    report = modular["runtime_candidates"][0]["meta"]["feature_report"]
    hints = modular["runtime_candidates"][0]["meta"]["game_pipeline_hints"]
    assert set(report["geometry_detail_module_categories"]) >= {"sensor_pod", "barrel", "wing"}
    assert set(hints["module_categories"]) >= {"sensor_pod", "barrel", "wing"}


def test_wave_g_shape_lod_controls_drive_actual_lod_generation() -> None:
    default_ratios = _resolve_lod_ratios({"lods": 1}, {}, {})
    authored_ratios = _resolve_lod_ratios({"lods": 1}, {}, {"lod_levels": 4})
    assert default_ratios == [1.0]
    assert authored_ratios == [1.0, 0.5, 0.25, 0.1]

    mesh = trimesh.creation.icosphere(subdivisions=2)
    default_lods = lod_mod.build_lods(mesh, default_ratios)
    authored_lods = lod_mod.build_lods(mesh, authored_ratios)
    assert len(default_lods) == 1
    assert len(authored_lods) == 4
    assert authored_lods[-1].tris < authored_lods[0].tris
    assert authored_lods[-1].distance_max is None


def test_wave_g_highlow_lod_pair_controls_reach_scaffold_hints() -> None:
    controls = {
        "detail_density": "hero",
        "lod_levels": 4,
        "highlow_mode": "lod_pair",
        "highlow_low_lod": 3,
        "highlow_bake_cage_offset_cm": 2.0,
        "detail_motifs": ["panel_seam", "trim_strip", "bolt_grid"],
    }
    parsed = geometry_detail_controls_from_authoring(build_asset_graph(_asset(controls)).authoring)
    assert parsed.highlow_mode == "lod_pair"
    assert parsed.highlow_low_lod == 3
    assert parsed.highlow_bake_cage_offset_cm == 2.0

    result = _compile(controls)
    hints = result["runtime_candidates"][0]["meta"]["game_pipeline_hints"]
    assert hints["lod_levels_requested"] == 4
    assert hints["bake_target"] == "high_to_low"
    assert hints["highlow_mode"] == "lod_pair"
    assert hints["highlow_low_lod"] == 3
    assert hints["highlow_bake_cage_offset_cm"] == 2.0


def test_wave_g_shape_collision_proxy_controls_create_real_proxy_mesh() -> None:
    mesh = trimesh.creation.icosphere(subdivisions=2)
    runtime = RuntimeMesh(
        mesh=mesh,
        face_parts=["body"] * len(mesh.faces),
        part_colors={"body": (120, 120, 120)},
        units="cm",
    )
    assert _resolve_collision_proxy_mode({"collision": "none"}, {"collision_proxy": "convex_hull"}) == "convex_hull"
    assert _resolve_collision_proxy_mode({"collision": "none"}, {"collision_proxy": "convex_decomp"}) == "per_part_hulls"

    box_mesh, box_mode = _collision_proxy_mesh(runtime, "box")
    hull_mesh, hull_mode = _collision_proxy_mesh(runtime, "convex_hull")
    parts_mesh, parts_mode = _collision_proxy_mesh(runtime, "per_part_hulls")

    assert box_mode == "box"
    assert hull_mode == "convex_hull"
    assert parts_mode == "per_part_hulls"
    assert len(hull_mesh.faces) > len(box_mesh.faces)
    assert len(parts_mesh.faces) >= len(hull_mesh.faces)


def _surface_asset(surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "build": {
            "surface": {
                "workflow": "metallic_roughness",
                "resolution": 128,
                "maps": ["basecolor", "normal"],
                "bakes": [],
                "decals": [],
            }
        },
        "surface": surface,
        "intent": {"parts": ["body", "trim_panel"], "materials": ["painted_steel"]},
        "assembly": {"resolved_components": []},
    }


def _runtime_mesh() -> RuntimeMesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    uv = np.zeros((len(mesh.vertices), 2), dtype=np.float64)
    for index in range(len(mesh.vertices)):
        uv[index, 0] = (index % 4) / 3.0
        uv[index, 1] = ((index // 4) % 2) / 1.0
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv)
    return RuntimeMesh(mesh=mesh, face_parts=["body"] * len(mesh.faces), part_colors={"body": (120, 120, 120)}, units="cm")


def _shape_bundle(family: str = "generic_widget") -> dict[str, Any]:
    return {
        "asset_graph": {"family": family},
        "selected_candidate_id": "cand_00",
        "candidates": [
            {
                "candidate_id": "cand_00",
                "mesh_uri": "stages\\shape\\cand_00.glb",
                "mesh_stats": {"triangle_count": 100},
                "mesh_ir": {"bake_groups": [{"part": "body", "bake_group": "bg_body"}]},
            }
        ],
    }


def _topology_bundle() -> dict[str, Any]:
    return {
        "mesh_uri": "stages\\topology\\topology.glb",
        "mesh_stats": {"triangle_count": 64},
        "part_groups": [{"name": "body"}, {"name": "trim_panel"}],
    }


def test_wave_d_e_material_layers_and_story_controls_change_surface_manifest(tmp_path: Path) -> None:
    result = build_surface_bundle(
        asset=_surface_asset(
            {
                "materials": ["painted_steel", "bare_metal", "signal_glass"],
                "material_layers": ["painted_steel", "bare_metal", "hazard_paint"],
                "wear_story": "battle_worn",
                "wear_level": "high",
                "story_decals": ["unit_17", "scrape_cluster"],
                "faction_marks": ["red_bar"],
            }
        ),
        out_dir=tmp_path,
        shape_bundle=_shape_bundle(),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )

    manifest = result["surface_manifest"]
    zones = result["material_zones"]
    assert manifest["procedural_material_layers"] == ["painted_steel", "bare_metal", "hazard_paint"]
    assert manifest["surface_story"]["wear_story"] == "battle_worn"
    assert set(manifest["decals"]) >= {"unit_17", "scrape_cluster", "red_bar"}
    assert all(zone["procedural_layers"] == ["painted_steel", "bare_metal", "hazard_paint"] for zone in zones)
    assert all(zone["wear_story"] == "battle_worn" for zone in zones)
    assert max(float(zone["wear"]) for zone in zones) > 0.35


def _output_image(out_dir: Path, result: dict[str, Any], name: str) -> np.ndarray:
    uri = str(result["outputs"][name]["uri"]).replace("\\", "/")
    with Image.open(out_dir / Path(uri)) as image:
        return np.asarray(image.convert("RGB" if image.mode != "L" else "L"), dtype=np.int16)


def test_wave_d_e_material_story_drives_actual_surface_maps(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    rich_dir = tmp_path / "rich"
    baseline = build_surface_bundle(
        asset=_surface_asset(
            {
                "materials": ["painted_steel"],
                "wear_story": "factory_new",
                "wear_level": "none",
            }
        ),
        out_dir=baseline_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )
    rich = build_surface_bundle(
        asset=_surface_asset(
            {
                "materials": ["painted_steel", "bare_metal", "hazard_paint"],
                "material_layers": ["painted_steel", "bare_metal", "hazard_paint"],
                "wear_story": "battle_worn",
                "wear_level": "high",
                "story_decals": ["unit_17", "scrape_cluster"],
            }
        ),
        out_dir=rich_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )

    assert rich["surface_manifest"]["material_wear_graph_hooks"]["mask_textures_generated"] is True
    assert (
        rich["surface_manifest"]["material_wear_graph_hooks"][
            "surface_maps_driven_by_material_wear_graph"
        ]
        is True
    )
    assert {"wear_mask", "material_layer_mask"}.issubset(set(rich["outputs"]))
    assert {"wear_mask", "material_layer_mask"}.issubset(set(rich["surface_control_pack"]["images"]))

    base_delta = np.mean(
        np.abs(_output_image(rich_dir, rich, "basecolor") - _output_image(baseline_dir, baseline, "basecolor"))
    )
    rough_delta = np.mean(
        np.abs(_output_image(rich_dir, rich, "roughness") - _output_image(baseline_dir, baseline, "roughness"))
    )
    normal_delta = np.mean(
        np.abs(_output_image(rich_dir, rich, "normal") - _output_image(baseline_dir, baseline, "normal"))
    )
    wear_mask = _output_image(rich_dir, rich, "wear_mask")
    layer_mask = _output_image(rich_dir, rich, "material_layer_mask")

    assert base_delta > 4.0
    assert rough_delta > 2.0
    assert normal_delta > 0.5
    assert int(wear_mask.max()) > 0
    assert int(layer_mask.max()) > 0


def test_wave_e_story_decals_paint_visible_surface_marks(tmp_path: Path) -> None:
    plain_dir = tmp_path / "plain_decals"
    marked_dir = tmp_path / "marked_decals"
    plain = build_surface_bundle(
        asset=_surface_asset({"materials": ["painted_steel"]}),
        out_dir=plain_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )
    marked = build_surface_bundle(
        asset=_surface_asset(
            {
                "materials": ["painted_steel"],
                "story_decals": [
                    "unit_17",
                    "scrape_cluster",
                    "etched_runes",
                    "red_bar",
                    "handled_edges",
                    "heat_warning",
                    "calibration_stripe",
                ],
            }
        ),
        out_dir=marked_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )

    assert set(marked["surface_manifest"]["decals"]) >= {
        "unit_17",
        "scrape_cluster",
        "etched_runes",
        "red_bar",
        "handled_edges",
        "heat_warning",
        "calibration_stripe",
    }
    base_delta = np.mean(
        np.abs(_output_image(marked_dir, marked, "basecolor") - _output_image(plain_dir, plain, "basecolor"))
    )
    rough_delta = np.mean(
        np.abs(_output_image(marked_dir, marked, "roughness") - _output_image(plain_dir, plain, "roughness"))
    )
    emissive_delta = np.mean(
        np.abs(_output_image(marked_dir, marked, "emissive") - _output_image(plain_dir, plain, "emissive"))
    )
    assert base_delta > 1.0
    assert rough_delta > 0.5
    assert emissive_delta > 0.02


def test_wave_g_surface_libraries_drive_visible_trim_and_decal_maps(tmp_path: Path) -> None:
    plain_dir = tmp_path / "plain_libraries"
    library_dir = tmp_path / "library_libraries"
    plain = build_surface_bundle(
        asset=_surface_asset({"materials": ["painted_steel"]}),
        out_dir=plain_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )
    authored = build_surface_bundle(
        asset=_surface_asset(
            {
                "materials": ["painted_steel", "bare_metal"],
                "decal_libraries": [
                    "std.surface.decal_library.industrial_v1",
                    "std.surface.decal_library.prototype_v1",
                ],
                "trim_sheets": [
                    "std.surface.trim.metal_strips_v1",
                    "std.surface.trim.panel_bands_v1",
                ],
            }
        ),
        out_dir=library_dir,
        shape_bundle=_shape_bundle("console_terminal"),
        shape_runtime_mesh=_runtime_mesh(),
        topology_bundle=_topology_bundle(),
        uv_runtime_mesh=_runtime_mesh(),
    )

    manifest = authored["surface_manifest"]
    assert set(manifest["library_driven_decals"]) >= {
        "hazard_stripe",
        "service_number",
        "calibration_id",
        "trim_sheet_metal_strips",
        "trim_sheet_panel_bands",
    }
    assert any(pattern.startswith("decal_library_std_surface_decal_library_industrial") for pattern in authored["patterns"])
    assert any(pattern.startswith("trim_sheet_std_surface_trim_metal_strips") for pattern in authored["patterns"])

    base_delta = np.mean(
        np.abs(_output_image(library_dir, authored, "basecolor") - _output_image(plain_dir, plain, "basecolor"))
    )
    rough_delta = np.mean(
        np.abs(_output_image(library_dir, authored, "roughness") - _output_image(plain_dir, plain, "roughness"))
    )
    emissive_delta = np.mean(
        np.abs(_output_image(library_dir, authored, "emissive") - _output_image(plain_dir, plain, "emissive"))
    )
    assert base_delta > 1.0
    assert rough_delta > 0.5
    assert emissive_delta > 0.02


def test_wave_h_examples_parse_and_use_multi_wave_controls() -> None:
    examples = sorted(Path("examples").glob("geometry_wave2_*.lth"))
    assert len(examples) >= 8
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        assert len(program["assets"]) == 1
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        assert "detail_density" in shape
        assert any(key.startswith("zone_") for key in shape) or "detail_motifs" in shape
        assert (
            "style_modifiers" in shape
            or asset.get("surface", {}).get("material_layers")
            or asset.get("build", {}).get("optimize", {}).get("lods")
        )


def test_wave3_examples_parse_and_use_attachment_motifs() -> None:
    examples = sorted(Path("examples").glob("geometry_wave3_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        assert "attachment_motifs" in shape or any(
            key.endswith("_attachment_motifs") for key in shape
        )


def test_wave4_examples_parse_and_use_material_story_maps() -> None:
    examples = sorted(Path("examples").glob("geometry_wave4_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        surface = asset.get("surface", {})
        assert surface.get("material_layers")
        assert surface.get("wear_story")
        assert surface.get("story_decals")


def test_wave5_examples_parse_and_use_module_categories() -> None:
    examples = sorted(Path("examples").glob("geometry_wave5_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        assert shape.get("module_categories")
        assert "module_count" in shape
        assert any(key.endswith("_module_categories") for key in shape)


def test_wave6_examples_parse_and_use_style_packs() -> None:
    examples = sorted(Path("examples").glob("geometry_wave6_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        surface = surface_with_style_pack_defaults(asset)
        assert shape.get("style_pack")
        assert "style_intensity" in shape
        assert surface.get("material_layers")
        assert surface.get("wear_story")
        assert surface.get("story_decals")


def test_wave7_examples_parse_and_use_silhouette_profiles() -> None:
    examples = sorted(Path("examples").glob("geometry_wave7_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        assert shape.get("silhouette_profile")
        assert shape.get("silhouette_motifs")
        assert "silhouette_intensity" in shape


def test_wave8_examples_parse_and_use_surface_libraries() -> None:
    examples = sorted(Path("examples").glob("geometry_wave8_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        surface = asset.get("surface", {})
        shape = asset["build"]["shape"]
        assert surface.get("decal_libraries")
        assert surface.get("trim_sheets")
        assert shape.get("silhouette_profile") or shape.get("style_pack")


def test_wave9_examples_parse_and_use_highlow_lod_pairs() -> None:
    examples = sorted(Path("examples").glob("geometry_wave9_*.lth"))
    assert len(examples) >= 4
    for path in examples:
        program = parse_text(path.read_text(encoding="utf-8"))
        asset = materialize_asset(program, program["assets"][0]["name"])
        shape = asset["build"]["shape"]
        assert shape.get("lod_levels", 0) >= 4
        assert shape.get("highlow_mode") == "lod_pair"
        assert shape.get("highlow_low_lod", 0) >= 2
        assert "highlow_bake_cage_offset_cm" in shape
