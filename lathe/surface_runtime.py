from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .atlas_assembler import build_atlas_assembly_ir
from .bake_runtime import (
    _uv_image_size,
    apply_decal_overlays,
    bake_ao_map,
    bake_basecolor_map,
    bake_curvature_map,
    bake_emissive_map,
    bake_id_map,
    bake_metallic_map,
    bake_normal_map,
    bake_roughness_map,
    enhance_normal_map,
)
from .codex_imagegen_bridge import (
    codex_imagegen_mode,
    consume_codex_imagegen_outputs,
    emit_codex_imagegen_requests,
    resolve_surface_backend_report,
)
from .highlow import HighLowRelation
from .materials import assign_material_zones
from .pbr_deriver import derive_orm_map
from .repair.surface_repair import build_surface_repair_ir
from .texture_control_pack import relative_uri, write_image, write_surface_control_pack
from .validators.surface_quality import build_surface_validation_ir


HERO_FAMILIES = {"brassbound_chest", "courier_drone", "console_terminal"}
V09_HERO_FAMILIES = {"brassbound_chest", "industrial_crate", "mechanical_door", "console_terminal", "service_cabinet", "control_pedestal", "supply_container"}


def _hero_surface_enabled(shape_bundle: dict[str, Any]) -> bool:
    asset_graph = shape_bundle.get("asset_graph", {})
    family = asset_graph.get("family")
    return family in V09_HERO_FAMILIES or family in HERO_FAMILIES


def _write_image(image: Image.Image, path: Path) -> dict[str, Any]:
    return write_image(image, path)


def _surface_manifest(surface_cfg: dict[str, Any], material_zones: list[dict[str, Any]], material_slots: int, hero_mode: bool) -> dict[str, Any]:
    return {
        "workflow": surface_cfg.get("workflow"),
        "maps": list(surface_cfg.get("maps", [])),
        "resolution": surface_cfg.get("resolution"),
        "semantic_materials": [entry["material"] for entry in material_zones],
        "material_slots": material_slots,
        "decals": list(surface_cfg.get("decals", [])),
        "hero_surface": hero_mode,
    }


def _rel(root: Path, path: Path) -> str:
    return relative_uri(root, path)


def _surface_backend_report(source_surface: dict[str, Any], surface_cfg: dict[str, Any], hero_mode: bool) -> dict[str, Any]:
    return resolve_surface_backend_report(source_surface, surface_cfg, hero_mode)


def _write_surface_control_pack(
    *,
    out_dir: Path,
    size: int,
    material_zones: list[dict[str, Any]],
    surface_cfg: dict[str, Any],
    source_surface: dict[str, Any],
    ao: Image.Image,
    curvature: Image.Image,
    normal: Image.Image,
    id_map: Image.Image,
) -> dict[str, Any]:
    return write_surface_control_pack(
        out_dir=out_dir,
        size=size,
        material_zones=material_zones,
        surface_cfg=surface_cfg,
        source_surface=source_surface,
        ao=ao,
        curvature=curvature,
        normal=normal,
        id_map=id_map,
    )


def _atlas_assembly_ir(surface_cfg: dict[str, Any], control_pack: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    return build_atlas_assembly_ir(surface_cfg, control_pack, outputs)


def _surface_validation_ir(surface_cfg: dict[str, Any], backend_report: dict[str, Any]) -> dict[str, Any]:
    return build_surface_validation_ir(surface_cfg, backend_report)


def _surface_repair_ir(backend_report: dict[str, Any]) -> dict[str, Any]:
    return build_surface_repair_ir(backend_report)


def _enhance_surface_maps_for_repair(
    basecolor: Image.Image,
    normal: Image.Image,
    roughness: Image.Image,
    emissive: Image.Image,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    base = np.asarray(basecolor, dtype=np.float64)
    base = np.clip((base - 128.0) * 1.22 + 128.0, 0.0, 255.0)
    yy, xx = np.indices(base.shape[:2], dtype=np.float64)
    wear_mask = (np.sin(xx / 17.0) + np.cos(yy / 23.0)) * 12.0
    base[:, :, 0] = np.clip(base[:, :, 0] + wear_mask, 0.0, 255.0)
    base[:, :, 1] = np.clip(base[:, :, 1] + wear_mask * 0.75, 0.0, 255.0)

    normal_arr = np.asarray(normal, dtype=np.float64)
    normal_arr[:, :, 0] = np.clip((normal_arr[:, :, 0] - 128.0) * 1.28 + 128.0, 0.0, 255.0)
    normal_arr[:, :, 1] = np.clip((normal_arr[:, :, 1] - 128.0) * 1.28 + 128.0, 0.0, 255.0)

    rough = np.asarray(roughness, dtype=np.float64)
    rough_mean = float(np.mean(rough))
    rough = np.clip((rough - rough_mean) * 1.42 + rough_mean, 0.0, 255.0)

    emissive_arr = np.asarray(emissive, dtype=np.float64)
    if emissive_arr.max() > 0:
        emissive_arr = np.clip(emissive_arr * 1.10, 0.0, 255.0)

    return (
        Image.fromarray(base.astype(np.uint8), mode="RGB"),
        Image.fromarray(normal_arr.astype(np.uint8), mode="RGB"),
        Image.fromarray(rough.astype(np.uint8), mode="L"),
        Image.fromarray(emissive_arr.astype(np.uint8), mode="RGB"),
    )


def build_surface_bundle(
    *,
    asset: dict[str, Any],
    out_dir: Path,
    shape_bundle: dict[str, Any],
    shape_runtime_mesh,
    topology_bundle: dict[str, Any],
    uv_runtime_mesh,
    repair_mode: str | None = None,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface_cfg = dict(asset["build"]["surface"])
    source_surface = dict(asset.get("surface", {}))
    surface_program = dict(source_surface.get("resolved_surface_program", {}))
    program_values = dict(surface_program.get("values", {}))
    if program_values.get("workflow"):
        surface_cfg["workflow"] = program_values["workflow"]
    if program_values.get("resolution") and not surface_cfg.get("resolution"):
        surface_cfg["resolution"] = program_values["resolution"]
    if program_values.get("maps"):
        surface_cfg["maps"] = list(dict.fromkeys([*program_values.get("maps", []), *surface_cfg.get("maps", [])]))
    if program_values.get("bakes"):
        surface_cfg["bakes"] = list(dict.fromkeys([*program_values.get("bakes", []), *surface_cfg.get("bakes", [])]))
    if program_values.get("decals"):
        surface_cfg["decals"] = list(dict.fromkeys([*program_values.get("decals", []), *surface_cfg.get("decals", [])]))
    if source_surface.get("decals"):
        surface_cfg["decals"] = list(dict.fromkeys([*surface_cfg.get("decals", []), *source_surface.get("decals", [])]))
    if source_surface.get("bake"):
        surface_cfg["bakes"] = list(dict.fromkeys([*surface_cfg.get("bakes", []), *source_surface.get("bake", [])]))
    bake_profile_values = dict(asset.get("build", {}).get("surface", {}).get("resolved_bake_profile", {}).get("values", {}))
    if bake_profile_values.get("maps"):
        surface_cfg["bakes"] = list(dict.fromkeys([*bake_profile_values.get("maps", []), *surface_cfg.get("bakes", [])]))
    policy_values = dict(source_surface.get("resolved_surface_policy", {}).get("values", {}))
    if policy_values.get("maps"):
        surface_cfg["maps"] = list(dict.fromkeys([*policy_values.get("maps", []), *surface_cfg.get("maps", [])]))
    if policy_values.get("resolution"):
        surface_cfg["resolution"] = policy_values["resolution"]
    if repair_mode == "surface_enhance_v1":
        surface_cfg["decals"] = list(dict.fromkeys([*surface_cfg.get("decals", []), "service_label", "trim_wear", "warning_band"]))
    pattern_names = list(dict.fromkeys([*program_values.get("patterns", []), *source_surface.get("patterns", [])]))
    part_groups = topology_bundle.get("part_groups", [])
    material_zones = assign_material_zones(asset, [group["name"] for group in part_groups]) if part_groups else assign_material_zones(asset, asset.get("intent", {}).get("parts", []))
    material_slots = max(1, len({entry["material"] for entry in material_zones}))
    hero_mode = _hero_surface_enabled(shape_bundle)
    backend_report = _surface_backend_report(source_surface, surface_cfg, hero_mode)
    imagegen_mode = codex_imagegen_mode(runtime_config)
    if (
        backend_report.get("codex_imagegen_requested")
        and backend_report.get("backend_unavailable_policy") == "fail"
        and imagegen_mode not in {"emit_requests", "consume_outputs"}
    ):
        raise RuntimeError("Codex ImageGen surface backend was requested, but the reference runtime has no available governed bridge")
    manifest = _surface_manifest(surface_cfg, material_zones, material_slots, hero_mode)
    manifest["program"] = source_surface.get("program", "")
    manifest["material_graph"] = source_surface.get("material_graph", "")
    manifest["patterns"] = pattern_names
    manifest["palette"] = source_surface.get("palette", "")
    manifest["source_material_zones"] = list(source_surface.get("material_zones", []))
    manifest["source_bake"] = list(source_surface.get("bake", []))
    manifest["authoring_backend"] = backend_report["selected_backend_id"]
    manifest["authoring_mode"] = backend_report["authoring_mode"]
    manifest["surface_policy"] = source_surface.get("policy", "")
    manifest["bake_profile"] = asset.get("build", {}).get("surface", {}).get("bake_profile", "")
    manifest["render_fixture"] = asset.get("build", {}).get("surface", {}).get("render_fixture", "")
    manifest["decal_libraries"] = list(source_surface.get("decal_libraries", []))
    manifest["mask_programs"] = list(source_surface.get("mask_programs", []))
    manifest["trim_sheets"] = list(source_surface.get("trim_sheets", []))

    if not hero_mode:
        return {
            "backend_id": "lathe.surface.semantic_passthrough_v1",
            "surface_backend_report": backend_report,
            "material_slots": material_slots,
            "maps": list(surface_cfg.get("maps", [])),
            "surface_manifest": manifest,
            "material_zones": material_zones,
        }

    size = _uv_image_size(surface_cfg.get("resolution"))
    face_parts = list(getattr(uv_runtime_mesh, "face_parts", []))
    mesh = uv_runtime_mesh.mesh
    maps_dir = out_dir / "maps"
    ao = bake_ao_map(mesh, size)
    curvature = bake_curvature_map(mesh, size)
    id_map = bake_id_map(mesh, face_parts, material_zones, size)
    basecolor = bake_basecolor_map(id_map, material_zones, curvature, ao)
    normal = enhance_normal_map(bake_normal_map(mesh, size), id_map, material_zones, curvature)
    roughness = bake_roughness_map(id_map, material_zones, curvature, ao)
    metallic = bake_metallic_map(id_map, material_zones)
    emissive = bake_emissive_map(id_map, material_zones)
    basecolor, roughness, emissive = apply_decal_overlays(basecolor, roughness, emissive, list(surface_cfg.get("decals", [])))
    if repair_mode == "surface_enhance_v1":
        basecolor, normal, roughness, emissive = _enhance_surface_maps_for_repair(basecolor, normal, roughness, emissive)
    orm = derive_orm_map(ao, roughness, metallic)
    control_pack = _write_surface_control_pack(
        out_dir=out_dir,
        size=size,
        material_zones=material_zones,
        surface_cfg=surface_cfg,
        source_surface=source_surface,
        ao=ao,
        curvature=curvature,
        normal=normal,
        id_map=id_map,
    )
    codex_requests: dict[str, Any] = {}
    codex_outputs: dict[str, Any] = {}
    if backend_report.get("codex_imagegen_requested") and imagegen_mode == "emit_requests":
        codex_requests = emit_codex_imagegen_requests(
            asset=asset,
            out_dir=out_dir,
            runtime_config=runtime_config,
            surface_cfg=surface_cfg,
            source_surface=source_surface,
            material_zones=material_zones,
            control_pack=control_pack,
        )
        backend_report["codex_imagegen_pending"] = True
        backend_report["codex_imagegen_request_manifest"] = codex_requests.get("manifest_uri", "")
    elif backend_report.get("codex_imagegen_requested") and imagegen_mode == "consume_outputs":
        basecolor, codex_outputs = consume_codex_imagegen_outputs(
            out_dir=out_dir,
            runtime_config=runtime_config,
            id_map=id_map,
            basecolor=basecolor,
            material_zones=material_zones,
        )
        backend_report["codex_imagegen_ran"] = bool(codex_outputs.get("consumed"))
        backend_report["codex_imagegen_output_manifest"] = codex_outputs.get("manifest_uri", "")
        if backend_report["codex_imagegen_ran"]:
            backend_report["fallback_backend_id"] = ""
            backend_report["fallback_reason"] = ""

    outputs = {
        "basecolor": _write_image(basecolor, maps_dir / "basecolor.png"),
        "normal": _write_image(normal, maps_dir / "normal.png"),
        "ao": _write_image(ao, maps_dir / "ao.png"),
        "curvature": _write_image(curvature, maps_dir / "curvature.png"),
        "id": _write_image(id_map, maps_dir / "id.png"),
        "orm": _write_image(orm, maps_dir / "orm.png"),
        "emissive": _write_image(emissive, maps_dir / "emissive.png"),
    }

    shape_selected_id = shape_bundle.get("selected_candidate_id")
    high_mesh_uri = next((item["mesh_uri"] for item in shape_bundle.get("candidates", []) if item.get("candidate_id") == shape_selected_id), None)
    selected_candidate = next((item for item in shape_bundle.get("candidates", []) if item.get("candidate_id") == shape_selected_id), {})
    low_relation = HighLowRelation(
        high_mesh_uri=high_mesh_uri or "stages\\shape\\candidate_00.glb",
        low_mesh_uri=topology_bundle.get("mesh_uri", "stages\\topology\\topology.glb"),
        bake_cage_offset_cm=1.25,
        source="hero_surface_runtime_v1",
        high_triangle_count=int(selected_candidate.get("mesh_stats", {}).get("triangle_count", 0)),
        low_triangle_count=int(topology_bundle.get("mesh_stats", {}).get("triangle_count", 0)),
        distinction_ratio=round(
            abs(
                int(selected_candidate.get("mesh_stats", {}).get("triangle_count", 0))
                - int(topology_bundle.get("mesh_stats", {}).get("triangle_count", 0))
            )
            / max(1, int(selected_candidate.get("mesh_stats", {}).get("triangle_count", 0))),
            6,
        ),
        bake_groups=[entry.get("bake_group", entry.get("part")) for entry in selected_candidate.get("mesh_ir", {}).get("bake_groups", [])] or None,
        authoritative=True,
    )

    relative_outputs = {name: {**entry, "uri": str(Path(entry["uri"]).relative_to(out_dir)).replace("/", "\\")} for name, entry in outputs.items()}

    return {
        "backend_id": "lathe.surface.hero_pbr_v1",
        "surface_backend_report": backend_report,
        "surface_program": source_surface.get("program", ""),
        "patterns": pattern_names,
        "repair_mode": repair_mode or "",
        "material_slots": material_slots,
        "maps": list(surface_cfg.get("maps", [])),
        "surface_manifest": manifest,
        "material_zones": material_zones,
        "outputs": relative_outputs,
        "surface_control_pack": control_pack,
        "codex_imagegen_requests": codex_requests,
        "codex_imagegen_outputs": codex_outputs,
        "atlas_assembly_ir": _atlas_assembly_ir(surface_cfg, control_pack, relative_outputs),
        "surface_validation_ir": _surface_validation_ir(surface_cfg, backend_report),
        "surface_repair_ir": _surface_repair_ir(backend_report),
        "highlow_relation": low_relation.to_dict(),
        "bake_outputs": {
            "normal": relative_outputs["normal"]["uri"],
            "ao": relative_outputs["ao"]["uri"],
            "curvature": relative_outputs["curvature"]["uri"],
            "id": relative_outputs["id"]["uri"],
        },
        "decal_masks": list(surface_cfg.get("decals", [])),
    }
