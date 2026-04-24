"""Blender driver scripts.

Python entry points Blender runs on startup to realize a Lathe
execution plan inside ``bpy``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..sandbox.blender import DEFAULT_BLENDER_TIMEOUT_S, run_blender_sandboxed


BACKEND_IDS = {
    "exec": "lathe.exec.blender_v1",
    "geometry_backend": {
        "blender_gnodes": "lathe.geometry.blender_gnodes_v1",
        "blender_modstack": "lathe.geometry.blender_modstack_v1",
    },
    "topology_backend": "lathe.topology.blender_mesh_v1",
    "uv_backend": {
        "blender_uv": "lathe.uv.blender_uv_v1",
    },
    "bake_backend": {
        "blender_cycles": "lathe.bake.blender_cycles_v1",
    },
    "surface_backend": {
        "blender_materials": "lathe.surface.blender_materials_v1",
    },
    "render_backend": {
        "blender_eval": "lathe.render.blender_eval_v1",
    },
    "package_backend": {
        "blender_export": "lathe.package.blender_export_v1",
    },
    "library_backend": {
        "blender_assets": "lathe.library.blender_assets_v1",
    },
}


def _export_blend_artifact(blender: dict[str, Any], input_glb: Path, output_blend: Path, summary_path: Path) -> dict[str, Any]:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "blender_export_blend.py"
    work_dir = output_blend.parent
    result = run_blender_sandboxed(
        [
            blender["path"],
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
            "--",
            "--input",
            str(input_glb),
            "--output",
            str(output_blend),
            "--summary",
            str(summary_path),
        ],
        cwd=work_dir,
        extra_env={"LATHE_BLENDER_PATH": str(blender["path"])},
        expect_files=[output_blend, summary_path],
        timeout_s=DEFAULT_BLENDER_TIMEOUT_S,
        log_dir=work_dir,
        log_prefix="export_blend",
    )
    stderr_tail = result.stderr_tail or None
    return {
        "ok": result.ok,
        "stdout_tail": result.stdout_tail.strip()[-800:] or None,
        "stderr_tail": stderr_tail,
        "returncode": result.exit_code,
        "duration_s": result.duration_s,
        "blender_path": blender.get("path"),
        "stderr_signaled_error": result.stderr_signaled_error,
        "matched_stderr_patterns": list(result.raw.matched_stderr_patterns),
        "timed_out": result.timed_out,
        "expected_files_missing": [str(p) for p in result.raw.expected_files_missing],
        "stdout_log": str(result.stdout_log_path) if result.stdout_log_path else None,
        "stderr_log": str(result.stderr_log_path) if result.stderr_log_path else None,
        "sandbox": "lathe.sandbox.blender",
    }
