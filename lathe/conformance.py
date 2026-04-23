from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
import trimesh

from .asset_graph import AssetGraph
from .proposals import ProposalBank, ProposalDelta, ShapeProposal


def _ratio_signature(extents: list[float]) -> list[float]:
    largest = max(1e-6, max(extents))
    return [float(value) / largest for value in extents]


def _actual_part_labels(candidate: dict[str, Any]) -> set[str]:
    face_parts = [str(item) for item in candidate.get("face_parts", []) if item is not None]
    if face_parts:
        return set(face_parts)
    return {str(item) for item in candidate.get("meta", {}).get("parts", [])}


def _symmetry_score(mesh: trimesh.Trimesh, axis: str | None) -> float:
    if axis not in {"x", "z"}:
        return 1.0
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0
    axis_index = 0 if axis == "x" else 2
    spread = max(1e-6, float(mesh.extents[axis_index]))
    return max(0.0, 1.0 - abs(float(center[axis_index])) / spread)


def _proposal_metrics(asset_graph: AssetGraph, scaffold_signature: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    mesh = candidate["mesh"]
    stats_extents = [float(value) for value in mesh.extents]
    scaffold_extents = scaffold_signature.get("expected_extents", stats_extents)
    expected_ratio = scaffold_signature.get("projected_ratio", _ratio_signature(stats_extents))
    actual_ratio = _ratio_signature(stats_extents)
    silhouette_fidelity = max(0.0, 1.0 - sum(abs(left - right) for left, right in zip(expected_ratio, actual_ratio)) / 1.1)
    expected_parts = {part.name for part in asset_graph.parts}
    actual_parts = _actual_part_labels(candidate)
    part_coverage = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    structural_richness = min(1.0, len(mesh.faces) / max(1.0, 220.0 * max(1, len(expected_parts))))
    symmetry_score = _symmetry_score(mesh, asset_graph.symmetry_axis)
    extents_scale = [max(0.84, min(1.18, stats_extents[idx] / max(1e-6, float(scaffold_extents[idx])))) for idx in range(3)]
    proposal_score = round((0.32 * silhouette_fidelity) + (0.24 * structural_richness) + (0.24 * symmetry_score) + (0.20 * part_coverage), 6)
    return {
        "part_coverage": round(part_coverage, 6),
        "silhouette_fidelity": round(silhouette_fidelity, 6),
        "structural_richness": round(structural_richness, 6),
        "symmetry_score": round(symmetry_score, 6),
        "proposal_score": proposal_score,
        "extents_scale": [round(value, 6) for value in extents_scale],
    }


def _region_deltas(asset_graph: AssetGraph, source_id: str, candidate_index: int, metrics: dict[str, Any], actual_parts: set[str]) -> list[ProposalDelta]:
    deltas: list[ProposalDelta] = []
    deltas.append(
        ProposalDelta(
            delta_id=f"{candidate_index}:proportion_shift",
            kind="proportion_shift",
            target_region="global",
            source=source_id,
            accepted=metrics["silhouette_fidelity"] >= 0.70 and max(abs(scale - 1.0) for scale in metrics["extents_scale"]) <= 0.12,
            reason="global proportions stay within blueprint bounds" if metrics["silhouette_fidelity"] >= 0.70 else "provider proportions drift too far from the blueprint silhouette",
            metrics={"silhouette_fidelity": metrics["silhouette_fidelity"], "extents_scale": metrics["extents_scale"]},
        )
    )
    deltas.append(
        ProposalDelta(
            delta_id=f"{candidate_index}:detail_hint",
            kind="detail_hint",
            target_region="global",
            source=source_id,
            accepted=metrics["structural_richness"] >= 0.58,
            reason="provider contributes enough structural detail to be a useful hint" if metrics["structural_richness"] >= 0.58 else "provider detail is too coarse to improve the scaffold truthfully",
            metrics={"structural_richness": metrics["structural_richness"]},
        )
    )
    for part in asset_graph.parts:
        deltas.append(
            ProposalDelta(
                delta_id=f"{candidate_index}:region:{part.name}",
                kind="region_detail",
                target_region=part.name,
                source=source_id,
                accepted=part.name in actual_parts,
                reason="proposal exposes an explicit semantic region" if part.name in actual_parts else "proposal lacks an explicit semantic region label",
                metrics={"part_present": part.name in actual_parts},
            )
        )
    return deltas


def _bank_from_provider(asset_graph: AssetGraph, scaffold_signature: dict[str, Any], provider_result: dict[str, Any]) -> ProposalBank:
    provider_candidates = provider_result.get("runtime_candidates") or []
    provider_report = provider_result.get("provider_report", {})
    source_id = provider_report.get("actual_provider_id") or provider_report.get("selected_provider_id") or "native"
    proposals: list[ShapeProposal] = []
    for index, candidate in enumerate(provider_candidates):
        metrics = _proposal_metrics(asset_graph, scaffold_signature, candidate)
        deltas = _region_deltas(asset_graph, source_id, index, metrics, _actual_part_labels(candidate))
        proposals.append(
            ShapeProposal(
                proposal_id=f"{source_id}:{index}",
                source_id=source_id,
                candidate_index=index,
                score=metrics["proposal_score"],
                deltas=deltas,
                assessment=metrics,
            )
        )
    attempted = [item for item in {provider_report.get("selected_provider_id"), provider_report.get("actual_provider_id")} if item]
    return ProposalBank(attempted_sources=attempted, proposals=proposals)


def _scale_runtime_candidate(candidate: dict[str, Any], scale_factors: list[float], source_id: str, notes: list[str]) -> dict[str, Any]:
    scaled = deepcopy(candidate)
    mesh = candidate["mesh"].copy()
    transform = np.eye(4)
    transform[0, 0] = scale_factors[0]
    transform[1, 1] = scale_factors[1]
    transform[2, 2] = scale_factors[2]
    mesh.apply_transform(transform)
    scaled["mesh"] = mesh
    scaled.setdefault("meta", {})
    scaled["meta"].setdefault("selection_notes", []).extend(notes)
    scaled["meta"]["accepted_provider_delta_source"] = source_id
    scaled["meta"]["accepted_provider_scale"] = scale_factors
    return scaled


def fit_provider_proposals(
    asset_graph: AssetGraph,
    scaffold_result: dict[str, Any],
    provider_result: dict[str, Any],
) -> dict[str, Any]:
    scaffold_candidates = list(scaffold_result["runtime_candidates"])
    scaffold_signature = scaffold_result["shape_irs"][0].signature if scaffold_result.get("shape_irs") else {}
    bank = _bank_from_provider(asset_graph, scaffold_signature, provider_result)
    accepted_deltas: list[dict[str, Any]] = []
    rejected_deltas: list[dict[str, Any]] = []
    proposal_sources_used: list[str] = []
    authoritative_reason = "native_assembly_blueprint"
    runtime_candidates = scaffold_candidates

    best_proposal: ShapeProposal | None = None
    for proposal in bank.proposals:
        if best_proposal is None or proposal.score > best_proposal.score:
            best_proposal = proposal
        for delta in proposal.deltas:
            (accepted_deltas if delta.accepted else rejected_deltas).append(delta.to_dict())
    if best_proposal is not None:
        proportion_delta = next((delta for delta in best_proposal.deltas if delta.kind == "proportion_shift" and delta.accepted), None)
        if proportion_delta is not None:
            scale_factors = list(proportion_delta.metrics.get("extents_scale", [1.0, 1.0, 1.0]))
            runtime_candidates = [
                _scale_runtime_candidate(
                    candidate,
                    scale_factors,
                    best_proposal.source_id,
                    [f"accepted provider proportion delta from {best_proposal.source_id}", f"proposal_score={best_proposal.score}"],
                )
                for candidate in scaffold_candidates
            ]
            proposal_sources_used.append(best_proposal.source_id)
            authoritative_reason = "native_assembly_blueprint_with_provider_proportion_delta"

    conformance_failures = [delta["reason"] for delta in rejected_deltas if delta["kind"] in {"proportion_shift", "region_detail"}]
    report: dict[str, Any] = {
        "mode": "native_scaffold_only" if not bank.proposals else ("provider_deltas_applied" if proposal_sources_used else "provider_deltas_rejected"),
        "proposal_bank": bank.to_dict(),
        "proposal_sources_attempted": list(bank.attempted_sources),
        "proposal_sources_used": proposal_sources_used,
        "accepted_deltas": accepted_deltas,
        "rejected_deltas": rejected_deltas,
        "conformance_failures": conformance_failures,
        "authoritative_candidate_reason": authoritative_reason,
        "shape_assessment": scaffold_result["report"].get("shape_assessment", {}),
    }
    return {"runtime_candidates": runtime_candidates, "report": report}
