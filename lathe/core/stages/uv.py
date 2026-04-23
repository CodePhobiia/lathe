"""UV stage step body.

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ...capabilities import probe_uv_backend
from ...uv_runtime import derive_uv_semantics
from ..common import dump_json, relpath
from ..errors import runtime_stage_error
from ..io import export_glb
from ..mesh import RuntimeMesh
from ..uv_ops import apply_box_uv, apply_xatlas_uv


def run(executor: Any, topology_bundle: dict[str, Any]) -> dict[str, Any]:
    backend = executor.selected_backends["uv"]
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    adapter_report = probe_uv_backend(executor.runtime_config)
    strict = bool(adapter_report.get("strict", False))
    if adapter_report["requested_adapter"] == "xatlas" and not adapter_report["real_adapter_available"] and strict:
        raise runtime_stage_error(
            executor.asset_name,
            "uv",
            backend["id"],
            "Requested xatlas UV adapter is unavailable and strict mode is enabled",
            details=adapter_report,
        )
    try:
        if adapter_report["selected_adapter"] == "xatlas":
            uv_mesh, uv_meta, execution = apply_xatlas_uv(topology_runtime, executor.asset, executor.runtime_config)
            adapter_report["status"] = "success"
        else:
            uv_mesh, uv_meta = apply_box_uv(topology_runtime, executor.asset)
            execution = {"mode": "reference_box"}
            adapter_report["status"] = "forced" if adapter_report["requested_adapter"] in {"box", "reference_box"} else "fallback"
            if not adapter_report["real_adapter_available"]:
                adapter_report["fallback_reason"] = adapter_report["probe"].get("message", "xatlas unavailable")
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise runtime_stage_error(
                executor.asset_name,
                "uv",
                backend["id"],
                f"UV adapter failed in strict mode: {exc}",
                details={"adapter_report": adapter_report, "error_type": type(exc).__name__},
            ) from exc
        uv_mesh, uv_meta = apply_box_uv(topology_runtime, executor.asset)
        execution = {"mode": "reference_box"}
        adapter_report["status"] = "fallback"
        adapter_report["fallback_reason"] = str(exc)
        adapter_report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    actual_adapter = execution.get("mode", adapter_report["selected_adapter"])
    uv_path = executor.stage_dirs["uv"] / "uv.glb"
    export_glb(uv_mesh.mesh, uv_path)
    uv_semantics = derive_uv_semantics(executor.runtime["topology"]["bundle"], executor.runtime["shape"]["bundle"])
    bundle = {
        "backend_id": backend["id"],
        "backend_version": backend["version"],
        "mesh_uri": relpath(executor.out_dir, uv_path),
        "uv_sets": uv_meta["uv_sets"],
        "packing_report": uv_meta["packing_report"],
        "texel_density": uv_meta["texel_density"],
        **uv_semantics,
        "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
        "provenance": {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "runtime_adapter": actual_adapter,
        },
    }
    executor.runtime["uv"] = {"bundle": bundle, "runtime_mesh": uv_mesh, "uv_meta": uv_meta}
    dump_json(executor.stage_dirs["uv"] / "bundle.json", bundle)
    return bundle
