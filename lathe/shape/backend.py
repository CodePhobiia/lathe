"""Shape stage orchestrator.

Implements the stable ``lathe.shape.intent_mesh_handoff_v1`` contract:
``intent → AssetGraph → blueprint → ShapeIR → fused search geometry →
authoritative mesh → optional provider proposals → conformance fit →
deterministic downstream``. Thin by design — heavy lifting lives in the
scaffold compiler, provider mux, and conformance modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..asset_graph import build_asset_graph
from ..conformance import fit_provider_proposals
from ..scaffold_compiler import compile_scaffold_candidates
from ..shape_providers import maybe_run_shape_provider
from .geometry.conditioning import collect_shape_conditioning

__all__ = ["collect_shape_conditioning", "run_shape_backend"]


def run_shape_backend(
    backend_id: str,
    asset: dict[str, Any],
    *,
    source_root: Path,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if backend_id != "lathe.shape.intent_mesh_handoff_v1":
        raise ValueError(f"Unsupported runnable shape backend '{backend_id}'")

    asset_graph = build_asset_graph(asset)
    mode = asset.get("build", {}).get("shape", {}).get("mode", "generate")
    shape_cfg = (runtime_config or {}).get("shape", {})
    provider = shape_cfg.get("provider")
    if provider in (None, "", "auto"):
        provider = "auto"
    elif provider in ("None", "null"):
        raise ValueError(
            f"Invalid shape_cfg.provider={provider!r}: use None or 'auto' "
            f"for auto-selection, not the literal string {provider!r}."
        )
    explicit_provider = provider != "auto"
    scaffold_result = compile_scaffold_candidates(
        asset_graph,
        seed=seed,
        candidates_count=candidates_count,
        conditioning=conditioning,
        mode=mode,
    )
    if asset_graph.authoring.get("self_reliant_target") and mode in {"generate", "assemble", "adapt"} and not explicit_provider:
        provider_result = {
            "provider_report": {
                "selected_provider_id": "lathe.provider.shape.reference_conditioned_v1",
                "selected_provider_version": "1.0.0",
                "actual_provider_id": "lathe.provider.shape.reference_conditioned_v1",
                "actual_provider_version": "1.0.0",
                "selected_via": "self_reliant_native_only",
                "strict": False,
                "learned": False,
                "status": "native_only",
                "probe": {"available": True, "provider_id": "lathe.provider.shape.reference_conditioned_v1", "details": {}},
                "config": {},
                "fallback_reason": "V0.9 self-reliant compiler policy removes asset-generation AI from the critical path for this asset family.",
            },
            "runtime_candidates": None,
        }
    else:
        provider_result = maybe_run_shape_provider(
            asset,
            source_root=source_root,
            seed=seed,
            candidates_count=candidates_count,
            conditioning=conditioning,
            work_dir=work_dir,
            runtime_config=runtime_config,
        )
    conformance_result = fit_provider_proposals(asset_graph, scaffold_result, provider_result)
    provider_result["runtime_candidates"] = conformance_result["runtime_candidates"]
    provider_result["asset_graph"] = scaffold_result["asset_graph"].to_dict()
    provider_result["shape_ir"] = scaffold_result["report"]["shape_irs"]
    provider_result["scaffold_report"] = {
        **scaffold_result["report"],
        "signature": scaffold_result["shape_irs"][0].signature if scaffold_result["shape_irs"] else {},
        "blueprint_id": scaffold_result["report"].get("blueprint_id"),
        "primitives_used": scaffold_result["report"].get("primitives_used", []),
        "shape_assessment": scaffold_result["report"].get("shape_assessment", {}),
    }
    provider_result["conformance_report"] = conformance_result["report"]
    return provider_result
