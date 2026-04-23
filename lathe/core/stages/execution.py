"""Execution stage step body (Blender plan invocation).

Extracted from ``lathe/executor.py`` during Stage 2.IV. Delegates to the
existing ``lathe.blender_execution.build_execution_bundle``, which is the
canonical site for Blender subprocess management (already hardened in
commit f9de43c).
"""

from __future__ import annotations

from typing import Any

from ...blender_execution import build_execution_bundle
from ..common import dump_json


def run(executor: Any, optimize_bundle: dict[str, Any]) -> dict[str, Any]:
    stage_dir = executor.stage_dirs["execution"]
    bundle = build_execution_bundle(
        asset=executor.asset,
        stage_dir=stage_dir,
        runtime=executor.runtime,
        runtime_config=executor.runtime_config,
        out_dir=executor.out_dir,
    )
    executor.runtime["execution"] = {"bundle": bundle, "stage_dir": stage_dir}
    render_metrics = bundle.get("render_eval_ir", {}).get("metrics", {})
    if render_metrics:
        executor.runtime["render_eval"] = {
            "report": {
                "views": bundle.get("render_eval_ir", {}).get("view_metrics", {}),
                "metrics": render_metrics,
            }
        }
    else:
        executor.runtime.pop("render_eval", None)
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
