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
from ..stage_contracts import assert_supported_backend_contract_version, supported_backend_contract_versions
from .geometry.conditioning import collect_shape_conditioning
from .mesh_program_path import compile_mesh_program_candidate, mesh_program_ast_from_asset
from .procedural_program_path import (
    compile_procedural_program_candidate,
    synthesizer_eligible,
)

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
    backend_version: str | None = None,
) -> dict[str, Any]:
    """Run shape backend.

    Args:
        backend_id: backend_id argument.
        asset: asset argument.
        source_root: source_root argument.
        seed: seed argument.
        candidates_count: candidates_count argument.
        conditioning: conditioning argument.
        work_dir: work_dir argument.
        runtime_config: runtime_config argument.
        backend_version: Backend contract version selected by the planner.

    Returns:
        The result.
    """
    if backend_id != "lathe.shape.intent_mesh_handoff_v1":
        raise ValueError(f"Unsupported runnable shape backend '{backend_id}'")
    selected_version = backend_version
    if selected_version is None:
        supported_versions = supported_backend_contract_versions(backend_id)
        selected_version = supported_versions[0] if supported_versions else None
    assert_supported_backend_contract_version(
        backend_id,
        selected_version,
        context="shape handoff contract",
    )

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
    # Shape backend dispatch — three arms in priority order:
    #
    #   1. Authored mesh_program{} in source (Phase 1 §5.1d):
    #      the explicit procedural authoring path. The mesh_program AST
    #      lowers to deterministic ShapePrimitives and feeds the
    #      exact-solid + post-boolean-polybevel chain.
    #
    #   2. Procedural synthesizer (Cycle 1 of the northstar implementation
    #      plan + procedural-synthesizer-architecture-correction.md):
    #      the automatic procedural path. The asset's construction graph
    #      drives a 8-stage compiler pipeline that produces a ShapeIR v2
    #      ShapeProgram; the program lowers through the same kernel.
    #      Triggered by the synthesizer_eligible() predicate (no
    #      mesh_program block, but a construction graph is present).
    #      family_dispatch_used: false is enforced by construction.
    #
    #   3. Legacy compile_scaffold_candidates: family-aware blueprint
    #      path. Targeted for migration to the procedural synthesizer
    #      family-by-family as Cycle 3 of the plan progresses.
    mesh_program_ast = mesh_program_ast_from_asset(asset)
    synth_active = mesh_program_ast is None and synthesizer_eligible(
        asset, runtime_config
    )
    if mesh_program_ast is not None:
        scaffold_result = compile_mesh_program_candidate(
            asset_graph,
            mesh_program_ast,
            mode=mode,
            conditioning=conditioning,
            runtime_config=runtime_config,
            work_dir=work_dir,
        )
    elif synth_active:
        # Procedural synthesizer path — lazy import to avoid a
        # synthesizer-startup cost on assets that don't use it.
        from ..asset_quality.procedural_synthesizer import synthesize_procedural_program
        from .procedural_program_path import runtime_from_asset

        synth_runtime = runtime_from_asset(asset)
        synth_result = synthesize_procedural_program(asset, synth_runtime)
        if synth_result.shape_program.ops:
            scaffold_result = compile_procedural_program_candidate(
                asset_graph,
                synth_result,
                mode=mode,
                conditioning=conditioning,
                runtime_config=runtime_config,
                work_dir=work_dir,
            )
        else:
            # Synthesizer ran but produced zero ops — fall through to
            # the legacy scaffold path. The trace records why.
            synth_active = False
            scaffold_result = compile_scaffold_candidates(
                asset_graph,
                seed=seed,
                candidates_count=candidates_count,
                conditioning=conditioning,
                mode=mode,
                runtime_config=runtime_config,
            )
    else:
        scaffold_result = compile_scaffold_candidates(
            asset_graph,
            seed=seed,
            candidates_count=candidates_count,
            conditioning=conditioning,
            mode=mode,
            runtime_config=runtime_config,
        )
    # `self_reliant_target` is true by default for every asset (Phase 0 §4.8:
    # Lathe is a standalone procedural compiler). An explicit non-"auto"
    # provider in the runtime config overrides this gate.
    # Authored ``mesh_program{}`` AND the procedural synthesizer path
    # always pin to native-only: both produce authoritative geometry,
    # so a learned proposal would be discarded by conformance fit anyway.
    if mesh_program_ast is not None or synth_active or (
        asset_graph.authoring.get("self_reliant_target")
        and mode in {"generate", "assemble", "adapt"}
        and not explicit_provider
    ):
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
                "probe": {
                    "available": True,
                    "provider_id": "lathe.provider.shape.reference_conditioned_v1",
                    "details": {},
                },
                "config": {},
                "fallback_reason": "V0.9 self-reliant compiler policy removes asset-generation AI from the critical path for this asset.",
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
