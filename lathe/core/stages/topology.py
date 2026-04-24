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

import subprocess
from pathlib import Path
from typing import Any

from ...blender_execution import BlenderExecutionError
from ...capabilities import probe_blender
from ...subproc import DEFAULT_STDERR_DENY_PATTERNS, run_sandboxed
from ...topology_runtime import derive_topology_semantics, should_preserve_integrated_shape
from ..common import dump_json, relpath
from ..errors import runtime_stage_error
from ..geometry import (
    load_runtime_mesh_from_scene,
    mesh_stats,
    part_groups_from_face_parts,
    run_reference_topology_cleanup,
)
from ..io import export_glb, export_runtime_scene_glb
from ..mesh import RuntimeMesh


def run_blender_topology(runtime_mesh: RuntimeMesh, stage_dir: Path, runtime_config: dict[str, Any] | None) -> tuple[RuntimeMesh, dict[str, Any]]:
    """Invoke Blender as a subprocess to re-topologize ``runtime_mesh``.

    Stage 2.IV + Plan 07 Phase 4: delegates to :func:`lathe.subproc.run_sandboxed`
    for env-allowlist scrubbing and stderr deny-pattern scanning. A returncode-0
    run that matches a deny pattern is still treated as failure; failures raise
    :class:`BlenderExecutionError` rather than a bare :class:`RuntimeError`.
    """
    blender = probe_blender(runtime_config)
    if not blender["available"]:
        raise RuntimeError(blender.get("message", "Blender is unavailable"))
    input_path = stage_dir / "blender_input.glb"
    output_path = stage_dir / "blender_output.glb"
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "blender_topology_adapter.py"
    export_runtime_scene_glb(runtime_mesh, input_path)
    timeout_s = int(((runtime_config or {}).get("topology", {}).get("blender", {}) or {}).get("timeout_s", 300))
    result = run_sandboxed(
        [
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
        ],
        timeout_s=timeout_s,
        cwd=stage_dir,
        extra_env={"LATHE_BLENDER_PATH": str(blender["path"])},
        expect_files=[output_path],
        stderr_deny_patterns=DEFAULT_STDERR_DENY_PATTERNS,
    )
    stderr_tail = result.stderr_tail or None
    if result.timed_out or result.returncode != 0 or result.stderr_signaled_error:
        fallback_message = (result.stderr_tail or result.stdout or "").strip()[-500:] or "Blender topology subprocess failed"
        raise BlenderExecutionError(
            fallback_message,
            blender_path=blender.get("path"),
            returncode=result.returncode,
            stderr_tail=stderr_tail,
            matched_patterns=list(result.matched_stderr_patterns),
        )
    topology_runtime = load_runtime_mesh_from_scene(output_path, runtime_mesh)
    if topology_runtime is None or len(topology_runtime.mesh.faces) == 0:
        # Defense-in-depth: Blender exited cleanly but didn't produce a usable mesh.
        raise BlenderExecutionError(
            "Blender topology subprocess did not produce a valid mesh",
            blender_path=blender.get("path"),
            returncode=result.returncode,
            stderr_tail=stderr_tail,
            matched_patterns=list(result.matched_stderr_patterns),
        )
    return (
        topology_runtime,
        {
            "mode": "blender_subprocess",
            "blender_path": blender["path"],
            "blender_version": blender.get("version"),
            "input_artifact": input_path.name,
            "output_artifact": output_path.name,
            "stdout_tail": result.stdout.strip()[-500:] or None,
            "stderr_tail": (result.stderr_tail or "").strip()[-500:] or None,
            "matched_stderr_patterns": list(result.matched_stderr_patterns),
        },
    )


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
    runtime_mesh: RuntimeMesh = executor.runtime["shape"]["runtime_mesh"]
    adapter_report = probe_topology_backend(executor.runtime_config)
    strict = bool(adapter_report.get("strict", False))
    preserve_integrated = should_preserve_integrated_shape(executor.runtime["shape"]["bundle"], executor.runtime_config)
    if adapter_report["requested_adapter"] == "blender" and not adapter_report["real_adapter_available"] and strict:
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
            topology_runtime, execution = _run_blender_topology(runtime_mesh, executor.stage_dirs["topology"], executor.runtime_config)
            blender_stats = mesh_stats(topology_runtime.mesh)
            if not blender_stats["watertight"]:
                message = "Blender topology adapter produced a non-watertight mesh"
                if strict:
                    raise RuntimeError(message)
                topology_runtime, fallback_execution = run_reference_topology_cleanup(runtime_mesh, executor.asset)
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
            adapter_report["status"] = "forced" if adapter_report["requested_adapter"] in {"cleanup", "reference_cleanup"} else "fallback"
            if not adapter_report["real_adapter_available"]:
                adapter_report["fallback_reason"] = adapter_report["probe"].get("message", "Blender unavailable")
    except (OSError, ValueError, RuntimeError, AttributeError, IndexError, TypeError, subprocess.SubprocessError, BlenderExecutionError) as exc:
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
    topology_path = executor.stage_dirs["topology"] / "topology.glb"
    export_glb(topology_runtime.mesh, topology_path)
    part_groups = part_groups_from_face_parts(topology_runtime.mesh, topology_runtime.face_parts)
    topology_semantics = derive_topology_semantics(executor.runtime["shape"]["bundle"])
    bundle = {
        "backend_id": backend["id"],
        "backend_version": backend["version"],
        "mesh_uri": relpath(executor.out_dir, topology_path),
        "mesh_stats": mesh_stats(topology_runtime.mesh),
        "normals": {"mode": "face", "count": int(len(topology_runtime.mesh.face_normals))},
        "part_groups": part_groups,
        **topology_semantics,
        "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
        "provenance": {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "runtime_adapter": actual_adapter,
        },
    }
    executor.runtime["topology"] = {"bundle": bundle, "runtime_mesh": topology_runtime}
    dump_json(executor.stage_dirs["topology"] / "bundle.json", bundle)
    return bundle
