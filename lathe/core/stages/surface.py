"""Surface stage step body.

Extracted from ``lathe/executor.py`` during Stage 2.IV. Delegates to the
existing ``lathe.surface_runtime.build_surface_bundle`` without modification.
"""

from __future__ import annotations

from typing import Any

from ...surface_runtime import build_surface_bundle
from ..common import dump_json


def run(executor: Any, uv_bundle: dict[str, Any], *, repair_mode: str | None = None) -> dict[str, Any]:
    stage_dir = executor.stage_dirs["surface"]
    bundle = build_surface_bundle(
        asset=executor.asset,
        out_dir=stage_dir,
        shape_bundle=executor.runtime["shape"]["bundle"],
        shape_runtime_mesh=executor.runtime["shape"]["runtime_mesh"],
        topology_bundle=executor.runtime["topology"]["bundle"],
        uv_runtime_mesh=executor.runtime["uv"]["runtime_mesh"],
        repair_mode=repair_mode,
        runtime_config=executor.runtime_config,
    )
    executor.runtime["surface"] = {"bundle": bundle, "stage_dir": stage_dir}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
