"""Package stage step body (USD/glTF/OBJ serialization + manifest + trace).

Extracted from ``lathe/executor.py`` during Stage 2.IV. The trace manifest
construction lives inside this module so the package stage owns the whole
build_trace pipeline (including stage-execution telemetry collation).
"""

from __future__ import annotations

from typing import Any

from ..common import dump_json, hash_obj, hash_ref, output_entry, relpath
from ..io import export_glb, export_gltf, export_obj, write_usda
from ..mesh import RuntimeMesh
from ..rendering import render_lod_sheet, render_mesh_preview, render_uv_layout
from ...engine_manifests import ADAPTERS as _ENGINE_ADAPTERS, manifest_filename as _engine_manifest_filename
from ...selector_manifest import build_selector_manifest, write_selector_manifest


STAGE_ORDER_FOR_TRACE = [
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
]


def run(executor: Any, optimize_bundle: dict[str, Any], validate_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        optimize_bundle: optimize_bundle argument.
        validate_bundle: validate_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["package"]
    package_cfg = executor.asset["package"]
    optimize_runtime: RuntimeMesh = executor.runtime["optimize"]["runtime_mesh"]
    mesh = optimize_runtime.mesh.copy()
    outputs: list[dict[str, Any]] = []
    if "usd" in package_cfg.get("formats", []):
        usd_path = stage_dir / f"{executor.asset_name}.usda"
        write_usda(mesh, usd_path, asset_name=executor.asset_name)
        outputs.append(output_entry(executor.out_dir, usd_path, "usd"))
    if "glb" in package_cfg.get("formats", []):
        glb_path = stage_dir / f"{executor.asset_name}.glb"
        export_glb(mesh, glb_path)
        outputs.append(output_entry(executor.out_dir, glb_path, "glb"))
    if "gltf" in package_cfg.get("formats", []):
        gltf_paths = export_gltf(mesh, stage_dir, executor.asset_name)
        for path in gltf_paths:
            outputs.append(output_entry(executor.out_dir, path, "gltf" if path.suffix == ".gltf" else "gltf_resource"))
    if "obj" in package_cfg.get("formats", []):
        obj_path = stage_dir / f"{executor.asset_name}.obj"
        export_obj(mesh, obj_path)
        outputs.append(output_entry(executor.out_dir, obj_path, "obj"))

    # Copy LOD + collision artifacts into the packaged asset dir so they live
    # alongside the main glb as the shipping asset package.
    optimize_bundle_local = executor.runtime.get("optimize", {}).get("bundle", optimize_bundle)
    for entry in optimize_bundle_local.get("lods") or []:
        src_uri = entry.get("mesh_uri")
        if not src_uri:
            continue
        src = executor.out_dir / src_uri
        if not src.exists():
            continue
        dst = stage_dir / src.name
        dst.write_bytes(src.read_bytes())
        outputs.append(output_entry(executor.out_dir, dst, "lod_glb"))
    collision_info = optimize_bundle_local.get("collision") or {}
    for kind_key, kind_name in (("hull_uri", "collision_hull"), ("parts_uri", "collision_parts")):
        src_rel = collision_info.get(kind_key)
        if not src_rel:
            continue
        src = executor.out_dir / src_rel
        if not src.exists():
            continue
        dst = stage_dir / src.name
        dst.write_bytes(src.read_bytes())
        outputs.append(output_entry(executor.out_dir, dst, kind_name))

    # STAGE-10: engine-specific manifests (godot/unity/unreal). Emitted at the
    # executor.out_dir root — NOT inside stages/package/ — so they sit next to
    # the copied lod_{0..3}.glb + collision_*.glb / main <asset>.glb bundle
    # that engine importers actually consume. Only runs on glb-packaged builds
    # (engine importers expect a glb alongside).
    engine_manifest_entries: dict[str, Any] = {}
    if "glb" in package_cfg.get("formats", []):
        engine_context = _build_engine_context(
            executor=executor,
            outputs=outputs,
            optimize_bundle=optimize_bundle_local,
        )
        for engine_id, emit_fn in _ENGINE_ADAPTERS.items():
            try:
                payload = emit_fn(engine_context, executor.asset_name)
            except Exception:  # noqa: BLE001 — best-effort sidecar, never fail the build
                continue
            filename = _engine_manifest_filename(engine_id, executor.asset_name)
            target = executor.out_dir / filename
            target.write_text(payload, encoding="utf-8")
            import hashlib as _hashlib

            engine_manifest_entries[engine_id] = {
                "path": relpath(executor.out_dir, target),
                "sha256": _hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "format": "yaml" if filename.endswith(".yaml") else "json",
            }

    previews = []
    preview_dir = stage_dir / "previews"
    preview_dir.mkdir(exist_ok=True)
    requested_previews = package_cfg.get("previews", [])
    if "turntable" in requested_previews:
        path = preview_dir / "turntable.png"
        render_mesh_preview(optimize_runtime, path, mode="shaded")
        previews.append(relpath(executor.out_dir, path))
    if "wireframe" in requested_previews:
        path = preview_dir / "wireframe.png"
        render_mesh_preview(optimize_runtime, path, mode="wireframe")
        previews.append(relpath(executor.out_dir, path))
    if "material_ids" in requested_previews:
        path = preview_dir / "material_ids.png"
        render_mesh_preview(optimize_runtime, path, mode="material_ids")
        previews.append(relpath(executor.out_dir, path))
    if "uv_layout" in requested_previews:
        path = preview_dir / "uv_layout.png"
        render_uv_layout(executor.runtime["uv"]["runtime_mesh"], path)
        previews.append(relpath(executor.out_dir, path))
    if "collision" in requested_previews:
        path = preview_dir / "collision.png"
        collision_mesh = RuntimeMesh(
            mesh=executor.runtime["physics"]["collision_mesh"],
            face_parts=["collision"] * int(len(executor.runtime["physics"]["collision_mesh"].faces)),
            part_colors={"collision": (220, 92, 60)},
            units="cm",
        )
        render_mesh_preview(collision_mesh, path, mode="wireframe")
        previews.append(relpath(executor.out_dir, path))
    if "lod_sheet" in requested_previews:
        path = preview_dir / "lod_sheet.png"
        render_lod_sheet(optimize_runtime, int(len(optimize_bundle["lods"])), path)
        previews.append(relpath(executor.out_dir, path))

    manifest = {
        "asset_id": executor.asset_name,
        "kind": executor.asset["kind"],
        "contracts": list(executor.asset.get("uses", [])),
        "profiles": executor._resolved_profile_names(),
        "version": executor.asset["publish"].get("version"),
        "formats": list(package_cfg.get("formats", [])),
        "outputs": outputs,
        "output_hashes": {entry["uri"]: entry["sha256"] for entry in outputs},
        "previews": previews,
        "trace_path": None,
        "normalized_source_path": relpath(executor.out_dir, executor.normalized_asset_path),
        "build_timestamp": None,
    }
    trace_path = None
    if package_cfg.get("include_trace", True):
        trace_path = stage_dir / "trace_manifest.json"
        trace = _build_trace(executor, outputs, previews, validate_bundle)
        dump_json(trace_path, trace)
        manifest["trace_path"] = relpath(executor.out_dir, trace_path)
    manifest_path = stage_dir / "package_manifest.json"
    dump_json(manifest_path, manifest)
    bundle = {
        "backend_id": executor.selected_backends["package"]["id"],
        "outputs": outputs,
        "manifest_path": relpath(executor.out_dir, manifest_path),
        "trace_path": relpath(executor.out_dir, trace_path) if trace_path else None,
        "normalized_source_path": relpath(executor.out_dir, executor.normalized_asset_path),
        "previews": previews,
        "engine_manifests": engine_manifest_entries,
    }
    executor.runtime["package"] = {"bundle": bundle}
    dump_json(stage_dir / "bundle.json", bundle)
    selector_manifest_path = _write_selector_manifest(executor, validate_bundle)
    if selector_manifest_path is not None:
        bundle["selector_manifest_path"] = relpath(executor.out_dir, selector_manifest_path)
        dump_json(stage_dir / "bundle.json", bundle)
    return bundle


def _build_engine_context(
    *,
    executor: Any,
    outputs: list[dict[str, Any]],
    optimize_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the small context dict passed to each engine adapter.

    Keeps adapter inputs free of executor-specific types — every value is
    JSON-serialisable. Resolves the main glb uri from ``outputs``.
    """

    main_glb = next(
        (entry.get("uri") for entry in outputs if entry.get("format") == "glb"),
        None,
    )
    lods_ctx: list[dict[str, Any]] = []
    for lod in optimize_bundle.get("lods") or []:
        if not isinstance(lod, dict):
            continue
        name = str(lod.get("name") or "lod0")
        try:
            level = int(name.replace("lod", ""))
        except (TypeError, ValueError):
            level = 0
        lods_ctx.append(
            {
                "level": level,
                "mesh_uri": lod.get("mesh_uri"),
                "triangle_count": lod.get("triangle_count"),
                "distance_min": lod.get("distance_min"),
                "distance_max": lod.get("distance_max"),
                "screen_coverage": lod.get("screen_coverage"),
            }
        )
    interfaces = (executor.runtime.get("interfaces") or {}).get("bundle") or {}
    sockets = [
        {
            "id": sock.get("id") or sock.get("name"),
            "origin": sock.get("origin") or sock.get("position") or [0.0, 0.0, 0.0],
            "axis": sock.get("axis") or [0.0, 1.0, 0.0],
            "socket_type": sock.get("socket_type")
            or sock.get("socketType")
            or sock.get("kind")
            or "attach",
            "kind": sock.get("kind"),
            "parent_part_id": sock.get("parent_part_id") or sock.get("parentPartId"),
        }
        for sock in interfaces.get("sockets", []) or []
        if isinstance(sock, dict) and (sock.get("id") or sock.get("name"))
    ]
    pivots = [
        {
            "id": piv.get("id") or piv.get("name"),
            "origin": piv.get("origin") or piv.get("position") or [0.0, 0.0, 0.0],
            "axis": piv.get("axis") or [0.0, 1.0, 0.0],
            "pivot_type": piv.get("pivot_type") or piv.get("pivotType") or "center",
        }
        for piv in interfaces.get("pivots", []) or []
        if isinstance(piv, dict) and (piv.get("id") or piv.get("name"))
    ]
    collisions: list[dict[str, Any]] = []
    collision_info = optimize_bundle.get("collision") or {}
    if collision_info.get("hull_uri"):
        collisions.append(
            {
                "id": "hull",
                "kind": "hull",
                "uri": collision_info.get("hull_uri"),
                "parent_part_id": None,
            }
        )
    if collision_info.get("parts_uri"):
        collisions.append(
            {
                "id": "parts",
                "kind": "hull",
                "uri": collision_info.get("parts_uri"),
                "parent_part_id": None,
            }
        )
    surface = (executor.runtime.get("surface") or {}).get("bundle") or {}
    mats_raw = surface.get("materials") or []
    materials: list[dict[str, Any]] = []
    if isinstance(mats_raw, list) and mats_raw:
        for mat in mats_raw:
            if not isinstance(mat, dict):
                continue
            mid = mat.get("id") or mat.get("name")
            if not mid:
                continue
            materials.append(
                {
                    "id": str(mid),
                    "display_name": mat.get("display_name") or mat.get("displayName") or str(mid),
                }
            )
    if not materials:
        # Fall back to material_zones.
        seen: set[str] = set()
        for zone in surface.get("material_zones", []) or []:
            if not isinstance(zone, dict):
                continue
            name = zone.get("material") or zone.get("name")
            if not isinstance(name, str) or not name or name in seen:
                continue
            seen.add(name)
            materials.append({"id": name, "display_name": name})
    publish = executor.asset.get("publish") or {}
    raw_tags = publish.get("tags") or []
    from ...selector_manifest import GAMEPLAY_TAG_CATALOG

    gameplay_tags = [t for t in raw_tags if isinstance(t, str) and t in GAMEPLAY_TAG_CATALOG]
    return {
        "main_glb_uri": main_glb,
        "lods": lods_ctx,
        "sockets": sockets,
        "pivots": pivots,
        "collisions": collisions,
        "materials": materials,
        "gameplay_tags": gameplay_tags,
    }


def _write_selector_manifest(executor: Any, validate_bundle: dict[str, Any]) -> Any:
    """Assemble + write ``selector_manifest.json`` alongside the build outputs.

    Keeps the package stage resilient: a schema/IO failure surfaces a warning
    rather than aborting an otherwise-certified build.
    """

    try:
        source_path = executor.program.get("_source_path") or ""
        variant_name = None
        asset_name = executor.asset_name
        for variant in executor.program.get("variants", []) or []:
            if variant.get("name") == asset_name:
                variant_name = asset_name
                break
        manifest = build_selector_manifest(
            asset_name=asset_name,
            variant_name=variant_name,
            source_path=source_path,
            build_hash=executor.cache_key,
            runtime=executor.runtime,
            validate_report=validate_bundle,
            asset=executor.asset,
            build_dir=executor.out_dir,
            repo_root=None,
        )
        return write_selector_manifest(manifest, executor.out_dir)
    except Exception as exc:  # noqa: BLE001 — best-effort sidecar
        import warnings

        warnings.warn(
            f"selector_manifest.json could not be written for asset "
            f"'{executor.asset_name}': {exc}",
            stacklevel=2,
        )
        return None


def _build_trace(executor: Any, outputs: list[dict[str, Any]], previews: list[str], validate_bundle: dict[str, Any]) -> dict[str, Any]:
    refs = []
    for group_name, group_values in executor.asset.get("refs", {}).items():
        if not isinstance(group_values, list):
            continue
        for value in group_values:
            refs.append({
                "group": group_name,
                "value": value,
                "sha256": hash_ref(value),
            })
    return {
        "asset_id": executor.asset_name,
        "source_hash": hash_obj(executor.program),
        "normalized_hash": hash_obj(executor.normalized_program),
        "compiler_version": "0.1.0",
        "backend_versions": {stage: data["id"] + "@" + data["version"] for stage, data in executor.selected_backends.items()},
        "determinism_by_stage": {stage: data["determinism_class"] for stage, data in executor.selected_backends.items()},
        "refs_with_hashes": refs,
        "uses": list(executor.asset.get("uses", [])),
        "stage_configs": {
            "shape": executor.asset["build"]["shape"],
            "topology": executor.asset["build"]["topology"],
            "uv": executor.asset["build"]["uv"],
            "surface": executor.asset["build"]["surface"],
            "execution": executor.asset.get("execution", {}),
            "rig": executor.asset["build"]["rig"],
            "interfaces": executor.asset["build"]["interfaces"],
            "physics": executor.asset["build"]["physics"],
            "optimize": executor.asset["build"]["optimize"],
            "package": executor.asset["package"],
            "publish": executor.asset["publish"],
        },
        "stage_outputs": {
            stage: relpath(executor.out_dir, executor.stage_dirs[stage] / ("report.json" if stage == "validate" else "bundle.json"))
            for stage in STAGE_ORDER_FOR_TRACE
        },
        "stage_execution": {
            "shape": {
                "provider_report": executor.runtime["shape"]["bundle"].get("provider_report"),
                "blueprint_id": executor.runtime["shape"]["bundle"].get("blueprint_id"),
                "primitives_used": executor.runtime["shape"]["bundle"].get("primitives_used", []),
                "proposal_sources_attempted": executor.runtime["shape"]["bundle"].get("proposal_sources_attempted", []),
                "proposal_sources_used": executor.runtime["shape"]["bundle"].get("proposal_sources_used", []),
                "accepted_deltas": executor.runtime["shape"]["bundle"].get("accepted_deltas", []),
                "rejected_deltas": executor.runtime["shape"]["bundle"].get("rejected_deltas", []),
                "conformance_failures": executor.runtime["shape"]["bundle"].get("conformance_failures", []),
                "authoritative_candidate_reason": executor.runtime["shape"]["bundle"].get("authoritative_candidate_reason"),
                "shape_assessment": executor.runtime["shape"]["bundle"].get("shape_assessment", {}),
                "reference_ir": executor.runtime["shape"]["bundle"].get("reference_ir", {}),
                "fit_ir": executor.runtime["shape"]["bundle"].get("fit_ir", {}),
                "transfer_ir": executor.runtime["shape"]["bundle"].get("transfer_ir", {}),
                "kit_ir": executor.runtime["shape"]["bundle"].get("kit_ir", {}),
            },
            "topology": executor.runtime["topology"]["bundle"].get("adapter_report"),
            "uv": executor.runtime["uv"]["bundle"].get("adapter_report"),
            "surface": {
                "surface_backend_report": executor.runtime["surface"]["bundle"].get("surface_backend_report", {}),
                "surface_control_pack": executor.runtime["surface"]["bundle"].get("surface_control_pack", {}),
                "codex_imagegen_requests": executor.runtime["surface"]["bundle"].get("codex_imagegen_requests", {}),
                "codex_imagegen_outputs": executor.runtime["surface"]["bundle"].get("codex_imagegen_outputs", {}),
                "atlas_assembly_ir": executor.runtime["surface"]["bundle"].get("atlas_assembly_ir", {}),
                "surface_validation_ir": executor.runtime["surface"]["bundle"].get("surface_validation_ir", {}),
                "surface_repair_ir": executor.runtime["surface"]["bundle"].get("surface_repair_ir", {}),
            },
            "execution": executor.runtime.get("execution", {}).get("bundle", {}),
            "flow_quality": executor.runtime.get("flow_quality", {}),
            "package": {"adapter": "reference_package"},
        },
        "candidate_selection": executor.runtime["shape"]["bundle"],
        "repairs_applied": executor.runtime["validate"]["bundle"].get("semantic_repairs_applied", []),
        "diagnostics": validate_bundle["diagnostics"],
        "package_outputs": outputs,
        "previews": previews,
        "approval_state": "pending_required_approval" if executor.asset["publish"].get("approval") == "required" else "not_required",
    }
