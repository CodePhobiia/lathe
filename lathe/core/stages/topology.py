"""Topology stage step body, including the Blender subprocess adapter.

Extracted from ``lathe/executor.py`` during Stage 2.IV. The Blender
subprocess helper ``run_blender_topology`` applies the Plan 07 M4 / Plan 10
M4b hardening pattern already present on
``blender_execution._export_blend_artifact``:

* scan ``stderr`` for known fatal-error substrings,
* treat a returncode-0 run that matched any of those as a failure,
* raise :class:`BlenderExecutionError` with matched patterns and the last
  2000 chars of stderr rather than a generic ``RuntimeError``.

``BlenderExecutionError`` itself lives in ``lathe.blender_execution``; we
reuse that class rather than defining a new one.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any

import trimesh

from ...backends import stage_bundle_contract_version_issue
from ...blender_execution import BlenderExecutionError
from ...capabilities import probe_blender
from ...sandbox.blender import run_blender_sandboxed
from ...style_presets import stage_axis
from ...topology_runtime import (
    MultiPartScene,
    build_part_tag_index,
    derive_topology_semantics,
    export_multi_part_scene_glb,
    manifest_from_part_index,
    semantic_preservation_report,
    should_preserve_integrated_shape,
)
from ..common import dump_json, relpath
from ..errors import contract_version_stage_error, runtime_stage_error
from ..geometry import (
    load_runtime_mesh_from_scene,
    load_runtime_scene_from_glb,
    mesh_stats,
    part_groups_from_face_parts,
    run_reference_topology_cleanup,
)
from ..io import export_runtime_scene_glb
from ..mesh import RuntimeMesh

# Fidelity-tier defaults for the Subsurf+Bevel+Decimate stack.
#
# Each tier maps to a (subsurf_level, bevel_segments) pair plus a default
# bevel width in cm that fires when seam groups are present but no width
# was authored. blockout/game stay flat (no subsurf) since their budget
# can't absorb the 4x face growth; hero gets one level of Catmull-Clark
# for organic curvature; cinematic doubles down for full DCC quality.
_TIER_PIPELINE_DEFAULTS: dict[str, dict[str, float | int]] = {
    "blockout": {"subsurf_level": 0, "bevel_segments": 1, "bevel_width_cm": 0.1},
    "game": {"subsurf_level": 0, "bevel_segments": 1, "bevel_width_cm": 0.15},
    "hero": {"subsurf_level": 1, "bevel_segments": 2, "bevel_width_cm": 0.2},
    "cinematic": {"subsurf_level": 2, "bevel_segments": 3, "bevel_width_cm": 0.3},
}


def _infer_fidelity_tier_from_asset(asset: dict[str, Any]) -> str:
    """Mirror ``infer_fidelity_profile`` thresholds without an AssetGraph.

    The topology stage runs on the materialized asset dict, not the asset
    graph, so this duplicates the threshold logic from
    ``lathe.surface_grammar._infer_fidelity_tier_from_asset`` to avoid a
    cross-stage import.
    """
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    asset_class = str((intent or {}).get("asset_class") or "").strip().lower()
    if asset_class == "aaa_hero":
        return "cinematic"
    if asset_class == "hero":
        return "hero"
    if asset_class in {"background", "mobile", "web", "roblox"}:
        return "blockout"
    if asset_class == "mid_ground":
        return "game"
    validate = asset.get("validate") if isinstance(asset.get("validate"), dict) else {}
    critic_name = str((validate or {}).get("score") or "").lower()
    try:
        threshold = float((validate or {}).get("threshold", 0.80) or 0.80)
    except (TypeError, ValueError):
        threshold = 0.80
    if "cinematic" in critic_name or threshold >= 0.92:
        return "cinematic"
    if "hero" in critic_name or threshold >= 0.86:
        return "hero"
    if threshold <= 0.78:
        return "blockout"
    return "game"


def _asset_class_budget_target_quads(asset: dict[str, Any]) -> int:
    """Resolve a quad-equivalent face budget from ``intent.asset_class``.

    Mirrors the optimize-stage cascade: builtin profile ``poly_budget``
    drives the budget when no explicit ``build.topology.target_quads`` /
    ``build.optimize.lods.lod_0.target_face_count`` is declared. The
    return value is a quad count -- the adapter doubles it to a tri
    target when computing the decimate ratio.
    """
    try:
        from ...asset_class_profiles import get_builtin_profile
    except Exception:  # pragma: no cover - defensive import
        return 0
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    asset_class = str((intent or {}).get("asset_class") or "").strip().lower()
    if not asset_class or asset_class == "generic":
        return 0
    profile = get_builtin_profile(asset_class)
    if not isinstance(profile, dict):
        return 0
    poly_budget = profile.get("poly_budget", {}) if isinstance(profile.get("poly_budget"), dict) else {}
    quads_target = poly_budget.get("quads_target")
    if isinstance(quads_target, (int, float)) and quads_target > 0:
        return int(quads_target)
    tris_max = poly_budget.get("tris_max")
    if isinstance(tris_max, (int, float)) and tris_max > 0:
        return max(1, int(tris_max) // 2)
    return 0


def _shape_bundle_has_terrain_heightfield(shape_bundle: dict[str, Any]) -> bool:
    """Detect whether the shape stage emitted a terrain heightfield.

    The terrain primitive lowering stamps ``primitive_type="heightfield"``
    on the ShapeIR record. When detected we tell the adapter to skip
    subsurf for this asset (an N=64 grid is already a smooth, regular
    triangulation; subdividing 4x just inflates the face count without
    adding curvature).
    """
    selected_shape_ir = shape_bundle.get("selected_shape_ir")
    shape_ir = [selected_shape_ir] if isinstance(selected_shape_ir, dict) else shape_bundle.get("shape_ir") or []
    if not isinstance(shape_ir, list):
        return False
    for entry in shape_ir:
        if not isinstance(entry, dict):
            continue
        primitives = entry.get("primitives") or []
        if not isinstance(primitives, list):
            continue
        for prim in primitives:
            if isinstance(prim, dict) and str(prim.get("primitive_type", "")).lower() == "heightfield":
                return True
    return False


def _build_topology_adapter_config(
    runtime_mesh: RuntimeMesh,
    shape_bundle: dict[str, Any],
    asset: dict[str, Any],
    runtime_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the §5.6 modifier-stack config for the Blender adapter.

    Resolution order for each axis (highest precedence first):

      1. Runtime-config override (``runtime_config.topology.*``).
      2. Asset-declared override (``build.topology.*`` / ``build.shape.*``).
      3. Fidelity-tier default from
         :data:`_TIER_PIPELINE_DEFAULTS` (subsurf level, bevel segments,
         default bevel width). Tier is inferred from
         ``intent.asset_class`` + ``validate.threshold``.
      4. Asset-class ``poly_budget`` from
         :mod:`lathe.asset_class_profiles` for ``decimate_target_quads``
         when no explicit budget was declared.

    Returns ``{}`` when nothing actionable is present and the asset has
    no fidelity bias (legacy cleanup path).
    """
    integration = shape_bundle.get("integration_report") or {}
    runtime_topology_cfg = ((runtime_config or {}).get("topology") or {}) if runtime_config else {}
    build_topology_cfg = (asset.get("build", {}) or {}).get("topology", {}) or {}
    build_shape_cfg = (asset.get("build", {}) or {}).get("shape", {}) or {}
    build_optimize_cfg = (asset.get("build", {}) or {}).get("optimize", {}) or {}

    tier = _infer_fidelity_tier_from_asset(asset)
    tier_defaults = _TIER_PIPELINE_DEFAULTS.get(tier, _TIER_PIPELINE_DEFAULTS["game"])

    config: dict[str, Any] = {}

    # Subsurf level: explicit override > tier default. Authors get a
    # smoother shading bump for free at hero/cinematic without
    # touching their .lth source.
    subsurf_level_override = (
        runtime_topology_cfg.get("subsurf_level")
        if runtime_topology_cfg.get("subsurf_level") is not None
        else build_topology_cfg.get("subsurf_level")
    )
    if subsurf_level_override is not None:
        try:
            subsurf_level = int(subsurf_level_override)
        except (TypeError, ValueError):
            subsurf_level = 0
    else:
        subsurf_level = int(tier_defaults["subsurf_level"])
    if subsurf_level > 0:
        config["subsurf_level"] = subsurf_level

    # Decimate budget: explicit target_quads > lod_0.target_face_count >
    # asset_class poly_budget. The adapter no-ops when the mesh is
    # already under budget (and reports the reason).
    target_quads = 0
    for source in (build_topology_cfg, build_shape_cfg):
        try:
            value = int(source.get("target_quads", 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            target_quads = value
            break
    if target_quads <= 0:
        lods_cfg = build_optimize_cfg.get("lods") if isinstance(build_optimize_cfg, dict) else None
        if isinstance(lods_cfg, dict):
            lod0 = lods_cfg.get("lod_0") or lods_cfg.get(0)
            if isinstance(lod0, dict):
                try:
                    target_face_count = int(lod0.get("target_face_count", 0) or 0)
                except (TypeError, ValueError):
                    target_face_count = 0
                if target_face_count > 0:
                    target_quads = max(1, target_face_count // 2)
    if target_quads <= 0:
        target_quads = _asset_class_budget_target_quads(asset)
    if target_quads > 0:
        config["decimate_target_quads"] = target_quads

    # Bevel segments: explicit > tier default.
    bevel_segments_override = (
        runtime_topology_cfg.get("bevel_segments")
        if runtime_topology_cfg.get("bevel_segments") is not None
        else build_topology_cfg.get("bevel_segments")
    )
    if bevel_segments_override is not None:
        try:
            bevel_segments = int(bevel_segments_override)
        except (TypeError, ValueError):
            bevel_segments = int(tier_defaults["bevel_segments"])
    else:
        bevel_segments = int(tier_defaults["bevel_segments"])
    if bevel_segments > 0:
        config["bevel_segments"] = bevel_segments

    seam_groups = _seam_groups_to_world_pairs(runtime_mesh, integration)
    if seam_groups:
        config["bevel_seam_groups"] = seam_groups
        widths = [g["width"] for g in seam_groups if g.get("width")]
        if widths:
            config["bevel_width"] = max(widths)
        else:
            # Tier default fires only when no per-strip width was authored;
            # this lets seam-marked-but-width-unspecified flows still get a
            # visible chamfer.
            config["bevel_width"] = float(tier_defaults["bevel_width_cm"])

    # Allow build.topology.bevel_width_cm to override regardless of seam groups.
    bevel_width_override = (
        runtime_topology_cfg.get("bevel_width_cm")
        if runtime_topology_cfg.get("bevel_width_cm") is not None
        else build_topology_cfg.get("bevel_width_cm")
    )
    if bevel_width_override is not None:
        with contextlib.suppress(TypeError, ValueError):
            config["bevel_width"] = float(bevel_width_override)

    instance_records = integration.get("instance_pattern_records") or []
    if isinstance(instance_records, list) and instance_records:
        config["instance_pattern_records"] = list(instance_records)

    # Heightfield-style terrain shouldn't be subdivided; the grid is
    # already a smooth surface. The adapter double-checks the mesh
    # signature so accidental flag drift can't blow up unrelated assets.
    if _shape_bundle_has_terrain_heightfield(shape_bundle):
        config["skip_subsurf_for_terrain"] = True

    config["fidelity_tier"] = tier

    return config


def _seam_groups_to_world_pairs(
    runtime_mesh: RuntimeMesh, integration: dict[str, Any]
) -> list[dict[str, Any]]:
    """Translate seam strip records into ``edge_world_pairs`` for bevel.

    The shape integration report stores per-strip edge vertex pairs as
    indices into the integrated mesh; we resolve them through the
    runtime mesh vertex array so the Blender adapter can match by
    coordinate (GLB round-trip preserves coords, not indices).
    """
    raw_strips = integration.get("post_boolean_polybevel_strips") or []
    if not isinstance(raw_strips, list) or not raw_strips:
        return []

    try:
        vertices = runtime_mesh.mesh.vertices
    except AttributeError:
        return []

    groups: dict[str, dict[str, Any]] = {}
    for strip in raw_strips:
        if not isinstance(strip, dict):
            continue
        name = str(strip.get("seam_name") or strip.get("name") or "post_boolean_bevel")
        width = float(strip.get("width_cm") or strip.get("width") or 0.0)
        edge_pairs_raw = (
            strip.get("edge_world_pairs")
            or strip.get("edge_vertex_pairs")
            or strip.get("edge_indices_pairs")
            or []
        )
        coord_pairs: list[list[list[float]]] = []
        for pair in edge_pairs_raw:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            a, b = pair[0], pair[1]
            if (
                isinstance(a, (list, tuple))
                and isinstance(b, (list, tuple))
                and len(a) == 3
                and len(b) == 3
            ):
                coord_pairs.append([list(map(float, a)), list(map(float, b))])
                continue
            try:
                a_idx, b_idx = int(a), int(b)
            except (TypeError, ValueError):
                continue
            if 0 <= a_idx < len(vertices) and 0 <= b_idx < len(vertices):
                coord_pairs.append(
                    [
                        list(map(float, vertices[a_idx])),
                        list(map(float, vertices[b_idx])),
                    ]
                )

        if not coord_pairs:
            continue
        bucket = groups.setdefault(name, {"name": name, "width": width, "edge_world_pairs": []})
        bucket["width"] = max(float(bucket.get("width", 0.0)), width)
        bucket["edge_world_pairs"].extend(coord_pairs)

    return [group for group in groups.values() if group["edge_world_pairs"]]


def run_blender_topology(
    runtime_mesh: RuntimeMesh,
    stage_dir: Path,
    runtime_config: dict[str, Any] | None,
    *,
    adapter_config: dict[str, Any] | None = None,
) -> tuple[RuntimeMesh, dict[str, Any]]:
    """Invoke Blender as a subprocess to re-topologize ``runtime_mesh``.

    Stage 2.IV + Plan 07 Phase 4: delegates to
    :func:`lathe.sandbox.blender.run_blender_sandboxed` for env-allowlist
    scrubbing, resource limits, and stderr deny-pattern scanning. A returncode-0
    run that matches a deny pattern is still treated as failure; failures raise
    :class:`BlenderExecutionError` rather than a bare :class:`RuntimeError`.
    """
    blender = probe_blender(runtime_config)
    if not blender["available"]:
        raise RuntimeError(blender.get("message", "Blender is unavailable"))
    input_path = stage_dir / "blender_input.glb"
    output_path = stage_dir / "blender_output.glb"
    config_path = stage_dir / "blender_topology_config.json"
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "blender_topology_adapter.py"
    export_runtime_scene_glb(runtime_mesh, input_path)
    timeout_s = int(
        ((runtime_config or {}).get("topology", {}).get("blender", {}) or {}).get("timeout_s", 300)
    )
    cli_args = [
        blender["path"],
        "--background",
        "--factory-startup",
        "--python",
        str(script_path),
        "--",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    if adapter_config:
        try:
            with Path(config_path).open("w", encoding="utf-8") as handle:
                json.dump(adapter_config, handle, indent=2)
            cli_args.extend(["--config", str(config_path)])
        except OSError:
            pass
    result = run_blender_sandboxed(
        cli_args,
        timeout_s=timeout_s,
        cwd=stage_dir,
        extra_env={"LATHE_BLENDER_PATH": str(blender["path"])},
        expect_files=[output_path],
        log_dir=stage_dir,
        log_prefix="blender_topology",
    )
    stderr_tail = result.stderr_tail or None
    if result.timed_out or result.exit_code != 0 or result.stderr_signaled_error:
        fallback_message = (result.stderr_tail or result.stdout_tail or "").strip()[
            -500:
        ] or "Blender topology subprocess failed"
        raise BlenderExecutionError(
            fallback_message,
            blender_path=blender.get("path"),
            returncode=result.exit_code,
            stderr_tail=stderr_tail,
            matched_patterns=list(result.raw.matched_stderr_patterns),
        )
    topology_runtime = load_runtime_mesh_from_scene(output_path, runtime_mesh)
    if topology_runtime is None or len(topology_runtime.mesh.faces) == 0:
        # Defense-in-depth: Blender exited cleanly but didn't produce a usable mesh.
        raise BlenderExecutionError(
            "Blender topology subprocess did not produce a valid mesh",
            blender_path=blender.get("path"),
            returncode=result.exit_code,
            stderr_tail=stderr_tail,
            matched_patterns=list(result.raw.matched_stderr_patterns),
        )
    adapter_report_summary = {
        "subsurf_level": int((adapter_config or {}).get("subsurf_level", 0) or 0),
        "decimate_target_quads": int(
            (adapter_config or {}).get("decimate_target_quads", 0) or 0
        ),
        "bevel_seam_group_count": len((adapter_config or {}).get("bevel_seam_groups", []) or []),
        "bevel_segments": int((adapter_config or {}).get("bevel_segments", 0) or 0),
        "bevel_width": float((adapter_config or {}).get("bevel_width", 0.0) or 0.0),
        "instance_pattern_record_count": len(
            (adapter_config or {}).get("instance_pattern_records", []) or []
        ),
        "fidelity_tier": (adapter_config or {}).get("fidelity_tier"),
        "skip_subsurf_for_terrain": bool(
            (adapter_config or {}).get("skip_subsurf_for_terrain", False)
        ),
    }
    return (
        topology_runtime,
        {
            "mode": "blender_subprocess",
            "blender_path": blender["path"],
            "blender_version": blender.get("version"),
            "input_artifact": input_path.name,
            "output_artifact": output_path.name,
            "config_artifact": config_path.name if adapter_config else None,
            "adapter_config_summary": adapter_report_summary,
            "stdout_tail": result.stdout_tail.strip()[-500:] or None,
            "stderr_tail": (result.stderr_tail or "").strip()[-500:] or None,
            "matched_stderr_patterns": list(result.raw.matched_stderr_patterns),
        },
    )


def _multi_part_scene_from_runtime_mesh(
    runtime_mesh: RuntimeMesh,
    part_index: dict[str, dict[str, Any]],
) -> MultiPartScene:
    """Build a multi-part scene from a single ``RuntimeMesh`` + face_parts.

    Used as the fallback path when Blender is unavailable or returned
    only a single fused mesh — we slice the runtime mesh by face_parts
    so downstream stages still get a multi-part contract instead of
    silently regressing.
    """
    from ..geometry import runtime_scene_parts

    scene = trimesh.Scene()
    names: list[str] = []
    face_counts: list[int] = []
    vertex_counts: list[int] = []
    for part_name, submesh in runtime_scene_parts(runtime_mesh):
        scene.add_geometry(submesh, geom_name=part_name, node_name=part_name)
        names.append(part_name)
        face_counts.append(len(submesh.faces))
        vertex_counts.append(len(submesh.vertices))
    manifest = manifest_from_part_index(names, face_counts, vertex_counts, part_index)
    return MultiPartScene(scene=scene, manifest=manifest, units=runtime_mesh.units)


def run(executor: Any, shape_bundle: dict[str, Any]) -> dict[str, Any]:
    # Look up ``probe_topology_backend`` and ``_run_blender_topology`` through the
    # ``lathe.executor`` module so test suites that patch those attributes on
    # ``lathe.executor`` continue to see their mocks applied at call time
    # (Stage 2.IV backward compat).
    """Run.

    Args:
        executor: executor argument.
        shape_bundle: shape_bundle argument.

    Returns:
        The result.
    """
    from lathe import executor as _executor_module

    probe_topology_backend = _executor_module.probe_topology_backend
    _run_blender_topology = _executor_module._run_blender_topology

    backend = executor.selected_backends["topology"]
    shape_version_issue = stage_bundle_contract_version_issue("shape", shape_bundle)
    if shape_version_issue is not None:
        raise contract_version_stage_error(
            executor.asset_name,
            "shape",
            str(shape_bundle.get("backend_id") or ""),
            shape_version_issue,
            details={
                "consumer_stage": "topology",
                "backend_version": shape_bundle.get("backend_version"),
            },
        )
    runtime_mesh: RuntimeMesh = executor.runtime["shape"]["runtime_mesh"]
    adapter_report = probe_topology_backend(executor.runtime_config)
    strict = bool(adapter_report.get("strict", False))
    preserve_integrated = should_preserve_integrated_shape(
        executor.runtime["shape"]["bundle"], executor.runtime_config
    )
    if (
        adapter_report["requested_adapter"] == "blender"
        and not adapter_report["real_adapter_available"]
        and strict
    ):
        raise runtime_stage_error(
            executor.asset_name,
            "topology",
            backend["id"],
            "Requested Blender topology adapter is unavailable and strict mode is enabled",
            details=adapter_report,
        )
    try:
        if preserve_integrated:
            topology_runtime, execution = run_reference_topology_cleanup(runtime_mesh, executor.asset)
            execution["mode"] = "integrated_preserve_cleanup"
            adapter_report["status"] = "preserved"
            adapter_report["selected_adapter"] = "integrated_preserve_cleanup"
            adapter_report["fallback_reason"] = None
        elif adapter_report["selected_adapter"] == "blender_subprocess":
            adapter_config = _build_topology_adapter_config(
                runtime_mesh,
                executor.runtime["shape"]["bundle"],
                executor.asset,
                executor.runtime_config,
            )
            try:
                topology_runtime, execution = _run_blender_topology(
                    runtime_mesh,
                    executor.stage_dirs["topology"],
                    executor.runtime_config,
                    adapter_config=adapter_config,
                )
            except TypeError:
                # Backward compat: tests patching ``_run_blender_topology``
                # may use the legacy 3-arg signature without the
                # ``adapter_config`` kwarg.
                topology_runtime, execution = _run_blender_topology(
                    runtime_mesh, executor.stage_dirs["topology"], executor.runtime_config
                )
            blender_stats = mesh_stats(topology_runtime.mesh)
            if not blender_stats["watertight"]:
                message = "Blender topology adapter produced a non-watertight mesh"
                if strict:
                    raise RuntimeError(message)
                topology_runtime, fallback_execution = run_reference_topology_cleanup(
                    runtime_mesh, executor.asset
                )
                execution = {
                    "mode": "reference_cleanup",
                    "fallback_from": "blender_subprocess",
                    "reason": message,
                    "blender_execution": execution,
                    "blender_mesh_stats": blender_stats,
                    "fallback_execution": fallback_execution,
                }
                adapter_report["status"] = "fallback"
                adapter_report["fallback_reason"] = message
                adapter_report["error"] = {"type": "quality_gate", "message": message}
            else:
                adapter_report["status"] = "success"
        else:
            topology_runtime, execution = run_reference_topology_cleanup(runtime_mesh, executor.asset)
            adapter_report["status"] = (
                "forced"
                if adapter_report["requested_adapter"] in {"cleanup", "reference_cleanup"}
                else "fallback"
            )
            if not adapter_report["real_adapter_available"]:
                adapter_report["fallback_reason"] = adapter_report["probe"].get(
                    "message", "Blender unavailable"
                )
    except (
        OSError,
        ValueError,
        RuntimeError,
        AttributeError,
        IndexError,
        TypeError,
        subprocess.SubprocessError,
        BlenderExecutionError,
    ) as exc:
        # The Blender topology path shells out to a headless subprocess and
        # then re-imports the emitted mesh through trimesh; failures span
        # subprocess errors, file IO, glTF parse issues, and adapter-specific
        # BlenderExecutionError. Any of those should degrade to the
        # deterministic reference cleanup path in non-strict mode.
        if strict:
            raise runtime_stage_error(
                executor.asset_name,
                "topology",
                backend["id"],
                f"Topology adapter failed in strict mode: {exc}",
                details={"adapter_report": adapter_report, "error_type": type(exc).__name__},
            ) from exc
        topology_runtime, execution = run_reference_topology_cleanup(runtime_mesh, executor.asset)
        adapter_report["status"] = "fallback"
        adapter_report["fallback_reason"] = str(exc)
        adapter_report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    actual_adapter = execution.get("mode", adapter_report["selected_adapter"])

    # Multi-part contract preservation step 1/2 — re-anchor before
    # subdivision finishing. When Blender ran and produced a multi-part
    # ``blender_output.glb``, we override any watertight-fallback collapse
    # so the subdivision pass and downstream stages all operate on the
    # 18-part scene rather than a 1-part convex-hull result. Triggers
    # whenever the file exists and Blender wrote >1 geometry — this also
    # covers the ``fallback_from=blender_subprocess`` case where trimesh
    # rejected the Blender output as non-watertight.
    blender_output_path = executor.stage_dirs["topology"] / "blender_output.glb"
    multi_part_override_applied = False
    if blender_output_path.exists():
        loaded = load_runtime_scene_from_glb(blender_output_path, topology_runtime)
        if loaded is not None:
            scene_payload, names, face_counts = loaded
            if len(names) > 1:
                fused_meshes = [scene_payload.geometry[name] for name in names]
                fused_face_parts: list[str] = []
                for name, count in zip(names, face_counts, strict=False):
                    fused_face_parts.extend([name] * int(count))
                if len(fused_meshes) == 1:
                    fused_mesh = fused_meshes[0].copy()
                else:
                    fused_mesh = trimesh.util.concatenate(fused_meshes)
                if len(fused_mesh.faces) > 0:
                    topology_runtime = RuntimeMesh(
                        mesh=fused_mesh,
                        face_parts=fused_face_parts,
                        part_colors=dict(topology_runtime.part_colors),
                        units=topology_runtime.units,
                    )
                    multi_part_override_applied = True
                    if execution.get("mode") == "reference_cleanup" and (
                        execution.get("fallback_from") == "blender_subprocess"
                    ):
                        execution["mode"] = "blender_subprocess_multi_part_recovered"
                        execution["multi_part_override"] = {
                            "source": "blender_output_glb",
                            "part_count": len(names),
                            "face_count": int(sum(face_counts)),
                            "note": (
                                "Watertight fallback was discarded in favour of "
                                "preserving Blender's 18-part scene; downstream "
                                "stages operate on the multi-part topology."
                            ),
                        }
                        actual_adapter = "blender_subprocess_multi_part_recovered"
                        adapter_report["status"] = "success_multi_part_recovered"
                        adapter_report["fallback_reason"] = None
                        adapter_report["error"] = None

    topology_semantics = derive_topology_semantics(executor.runtime["shape"]["bundle"])
    # Roadmap §6.8: read shading + material axes. anime_cel/npr_cel triggers
    # ``artist_edited_normals`` so downstream subdivision and shading code
    # bias face normals for cel shadow falloff. Flat-shaded routes skip
    # smoothing-group merging entirely.
    style_shading = stage_axis(executor.asset, "shading_model")
    style_material = stage_axis(executor.asset, "material_model")
    style_outline = stage_axis(executor.asset, "outline_mode")
    style_lighting = stage_axis(executor.asset, "lighting_strategy")
    style_routing = {
        "shading_model": style_shading,
        "material_model": style_material,
        "outline_mode": style_outline,
        "lighting_strategy": style_lighting,
        "artist_edited_normals": style_shading == "ramp_outline" or style_material == "npr_cel",
        "preserve_flat_shading": style_shading == "flat_shaded",
        "needs_inverted_hull_pass": style_outline in {"inverted_hull", "hybrid"},
        "needs_sobel_post_pass": style_outline in {"sobel_post", "hybrid"},
    }
    # Roadmap §7.5: optional subdivision finishing pass. When the asset
    # declares an inline ``geometry.subdivision`` block, references a
    # top-level ``subdivision_finishing`` decl through
    # ``build.topology.subdivision_finishing``, or matches a hero asset
    # class default, we replace the topology runtime mesh with the
    # refined output before exporting. ``geometry-strict`` builds with
    # ``build.topology.subdivision_finishing = "disabled"`` opt out.
    selected_integration_mode = str(

            executor.runtime.get("shape", {})
            .get("selected", {})
            .get("integration_report", {})
            .get("mode", "")

    )
    selected_integration_report = (
        executor.runtime.get("shape", {})
        .get("selected", {})
        .get("integration_report", {})
    )
    if (
        selected_integration_mode == "mesh_program_explicit_surface"
        and isinstance(selected_integration_report, dict)
        and isinstance(selected_integration_report.get("exact_report"), dict)
    ):
        selected_integration_mode = str(
            selected_integration_report["exact_report"].get("mode", selected_integration_mode)
        )
    exact_boolean_preserve_modes = {
        "exact_boolean_union",
        "exact_boolean_union_clustered",
        "exact_boolean_difference",
        "exact_boolean_intersection",
        "exact_boolean_mixed",
        "exact_boolean_kernel_program",
        "exact_boolean_manifold_kernel",
    }
    if multi_part_override_applied:
        # Skip the standalone subdivision-finishing pass: Blender's
        # subsurf+bevel modifier stack already produced the refined mesh
        # we're publishing, and the standalone pass would re-pad
        # face_parts with a single fallback part name (see
        # ``_repair_face_parts``) which would collapse the 18-part
        # structure we just recovered.
        subdivision_report = {
            "applied": False,
            "reason": "skipped_for_multi_part_preservation",
            "skipped_because": "blender_subprocess_multi_part_recovered",
        }
    elif (
        actual_adapter == "integrated_preserve_cleanup"
        and selected_integration_mode in exact_boolean_preserve_modes
    ):
        subdivision_report = {
            "applied": False,
            "reason": "skipped_for_watertight_exact_boolean_preservation",
            "skipped_because": selected_integration_mode,
        }
    else:
        subdivision_report = _maybe_apply_subdivision_finishing(
            executor, topology_runtime
        )
        if subdivision_report.get("applied"):
            topology_runtime = subdivision_report.pop("_runtime_mesh")

    # Multi-part contract preservation step 2/2 — build the scene + manifest
    # for export. After step 1 above re-anchored topology_runtime to the
    # Blender multi-part output, ``runtime_scene_parts`` slices it back
    # into per-part submeshes preserving the names. This also covers the
    # paths where Blender didn't run (integrated_preserve_cleanup or
    # adapter unavailable) — we still emit a multi-part scene by slicing
    # whatever face_parts the runtime currently has.
    part_index = build_part_tag_index(executor.runtime["shape"]["bundle"])
    multi_part_scene = _multi_part_scene_from_runtime_mesh(topology_runtime, part_index)
    multi_part_source = (
        "blender_output_glb" if multi_part_override_applied else "runtime_mesh_face_parts"
    )

    topology_path = executor.stage_dirs["topology"] / "topology.glb"
    export_multi_part_scene_glb(multi_part_scene, topology_path)

    part_groups = part_groups_from_face_parts(topology_runtime.mesh, topology_runtime.face_parts)
    # Annotate the multi-part manifest with per-part bboxes so downstream
    # validators can recover bbox-based metrics (adjacency, symmetry,
    # part_coverage) even if ``part_groups`` is later mutated/collapsed in
    # the runtime dict. ``parts`` always tracks the authoritative scene
    # geometry; ``part_groups`` is recomputed from face_parts and can be
    # invalidated by length-mismatch fallbacks downstream.
    _part_group_bbox = {
        group.get("name"): (group.get("bounds_min"), group.get("bounds_max"))
        for group in part_groups
        if isinstance(group, dict)
    }
    for part in multi_part_scene.manifest:
        bmin, bmax = _part_group_bbox.get(part.name, (None, None))
        if bmin is not None and bmax is not None:
            part.bounds_min = list(bmin)
            part.bounds_max = list(bmax)
    semantic_preservation = semantic_preservation_report(
        topology_semantics,
        multi_part_scene.part_names(),
    )
    bundle = {
        "backend_id": backend["id"],
        "backend_version": backend["version"],
        "mesh_uri": relpath(executor.out_dir, topology_path),
        "mesh_stats": mesh_stats(topology_runtime.mesh),
        "normals": {"mode": "face", "count": len(topology_runtime.mesh.face_normals)},
        "part_groups": part_groups,
        "parts": multi_part_scene.manifest_as_list(),
        "part_count": len(multi_part_scene.manifest),
        "multi_part_scene_source": multi_part_source,
        **topology_semantics,
        "semantic_preservation": semantic_preservation,
        "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
        "style_routing": style_routing,
        "subdivision_finishing": subdivision_report,
        "provenance": {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "runtime_adapter": actual_adapter,
        },
    }
    # Sentinel: snapshot part_group names at topology emission so the
    # validate stage can detect any in-memory collapse of part_groups
    # (e.g. a downstream consumer rebuilding it via the
    # ``["mesh"]*N`` length-mismatch fallback in part_groups_from_face_parts).
    # This catches bugs where the on-disk bundle.json has all 18 parts but
    # the runtime dict at validate time has only 1 ("body"). See task #22.
    bundle["_part_groups_emitted"] = sorted(
        str(group.get("name", "")) for group in part_groups if isinstance(group, dict)
    )
    executor.runtime["topology"] = {
        "bundle": bundle,
        "runtime_mesh": topology_runtime,
        "multi_part_scene": multi_part_scene,
    }
    dump_json(executor.stage_dirs["topology"] / "bundle.json", bundle)
    return bundle


def _maybe_apply_subdivision_finishing(
    executor: Any,
    topology_runtime: RuntimeMesh,
) -> dict[str, Any]:
    """Resolve the subdivision finishing spec for the asset and run it."""
    try:
        from ...subdivision import from_geometry_block
        from ...subdivision.runtime_bridge import apply_finishing_to_trimesh
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "applied": False,
            "reason": f"subdivision module import failed: {exc}",
        }

    decl_lookup: dict[str, Any] = {}
    program = getattr(executor, "program", None) or {}
    for decl in program.get("subdivision_finishings") or []:
        name = decl.get("name")
        values = decl.get("values") or {}
        if name:
            decl_lookup[name] = values

    spec = from_geometry_block(executor.asset, decl_lookup=decl_lookup)
    if spec is None:
        return {"applied": False, "reason": "no subdivision spec resolved"}

    refined_mesh, report = apply_finishing_to_trimesh(topology_runtime.mesh, spec)
    if not report.get("applied"):
        return report

    refined_runtime = RuntimeMesh(
        mesh=refined_mesh,
        face_parts=_repair_face_parts(refined_mesh, topology_runtime),
        part_colors=dict(topology_runtime.part_colors),
        units=topology_runtime.units,
    )
    report["_runtime_mesh"] = refined_runtime
    report["input_face_count"] = len(topology_runtime.mesh.faces)
    report["output_face_count"] = len(refined_mesh.faces)
    return report


def _repair_face_parts(refined_mesh: Any, source: RuntimeMesh) -> list[str]:
    """Pad the face_parts list so it matches the refined face count.

    Subdivision multiplies face counts; without a true face-tracking
    table we fall back to repeating the first part label so downstream
    code that indexes ``face_parts[face_idx]`` does not blow up. Future
    work: thread through a per-face provenance table from the CC pass.
    """
    target = len(refined_mesh.faces)
    if not source.face_parts:
        return [""] * target
    if len(source.face_parts) == target:
        return list(source.face_parts)
    fallback = source.face_parts[0]
    return [fallback] * target
