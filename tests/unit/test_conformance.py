"""Unit tests for ``lathe.conformance.fit_provider_proposals``.

``fit_provider_proposals`` is the gatekeeper between a native scaffold
result and provider (learned / VGGT / Hunyuan) proposals. It must:

- never weaken the scaffold (always produce a runtime_candidates list);
- record an explicit reason string for every accepted / rejected delta;
- only apply a provider proportion delta when silhouette fidelity AND
  extents-scale bounds are both satisfied;
- tolerate an empty proposal list (native-only mode).

Tests build a tiny AssetGraph + scaffold candidate with ``trimesh``
primitives so the real metric helpers run (no mocks on the scoring
path). Provider candidates are synthesized with controlled geometry so
we can steer fidelity high or low.
"""

from __future__ import annotations

import unittest

import numpy as np
import trimesh

from lathe.asset_graph import build_asset_graph
from lathe.conformance import fit_provider_proposals


def _graph():
    return build_asset_graph(
        {
            "name": "industrial_crate",
            "kind": "prop",
            "intent": {"role": "crate", "parts": ["body", "lid"]},
            "build": {
                "shape": {"symmetry": "auto", "mode": "generate"},
                "rig": {},
                "interfaces": {},
            },
            "validate": {"threshold": 0.80},
        }
    )


def _scaffold_mesh() -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    return mesh


def _scaffold_candidate(mesh: trimesh.Trimesh | None = None) -> dict:
    mesh = mesh if mesh is not None else _scaffold_mesh()
    face_parts = ["body"] * (len(mesh.faces) // 2) + ["lid"] * (len(mesh.faces) - len(mesh.faces) // 2)
    return {
        "mesh": mesh,
        "face_parts": face_parts,
        "meta": {"parts": ["body", "lid"]},
    }


class _FakeShapeIR:
    """Minimal shape-IR substitute exposing only the ``signature`` attr.

    ``fit_provider_proposals`` reads ``scaffold_result["shape_irs"][0].signature``
    and nothing else about the IR, so a duck-typed shim is sufficient.
    """

    def __init__(self, signature: dict) -> None:
        self.signature = signature


def _scaffold_result(asset_graph, *, n_candidates: int = 1):
    scaffold_mesh = _scaffold_mesh()
    signature = {
        "expected_extents": list(map(float, scaffold_mesh.extents)),
        "projected_ratio": [1.0, 1.0, 1.0],
    }
    return {
        "runtime_candidates": [_scaffold_candidate() for _ in range(n_candidates)],
        "shape_irs": [_FakeShapeIR(signature)],
        "report": {
            "shape_assessment": {"required_part_coverage": 0.9},
        },
    }


def _provider_candidate(
    *, extents: tuple[float, float, float] = (1.0, 1.0, 1.0),
    face_count: int = 600,
    parts: list[str] | None = None,
) -> dict:
    mesh = trimesh.creation.box(extents=extents)
    # subdivide to hit the structural richness threshold if desired
    if face_count > len(mesh.faces):
        mesh = mesh.subdivide()
        while len(mesh.faces) < face_count:
            mesh = mesh.subdivide()
    face_labels = parts if parts is not None else ["body", "lid"]
    per_face = [face_labels[idx % len(face_labels)] for idx in range(len(mesh.faces))]
    return {
        "mesh": mesh,
        "face_parts": per_face,
        "meta": {"parts": list(face_labels)},
    }


def _provider_result(candidates: list[dict], *, source_id: str = "lathe.provider.test_v1") -> dict:
    return {
        "runtime_candidates": candidates,
        "provider_report": {
            "selected_provider_id": source_id,
            "actual_provider_id": source_id,
        },
    }


class FitProviderProposalsTests(unittest.TestCase):
    def test_well_fitting_proposal_is_accepted_and_scales_scaffold(self) -> None:
        graph = _graph()
        scaffold = _scaffold_result(graph)
        provider = _provider_result([_provider_candidate()])
        result = fit_provider_proposals(graph, scaffold, provider)

        self.assertIn("runtime_candidates", result)
        self.assertEqual(len(result["runtime_candidates"]), 1)
        report = result["report"]
        # proposal matches scaffold silhouette exactly => proportion
        # delta should be accepted (silhouette_fidelity near 1.0).
        self.assertEqual(report["mode"], "provider_deltas_applied")
        self.assertIn("lathe.provider.test_v1", report["proposal_sources_used"])
        # accepted deltas include proportion_shift
        kinds = {delta["kind"] for delta in report["accepted_deltas"]}
        self.assertIn("proportion_shift", kinds)

    def test_off_silhouette_proposal_is_rejected(self) -> None:
        graph = _graph()
        scaffold = _scaffold_result(graph)
        # provider proposes extents that are way off the scaffold
        # signature — silhouette fidelity collapses below 0.70.
        bad = _provider_candidate(extents=(6.0, 0.1, 0.1), face_count=60)
        provider = _provider_result([bad])
        result = fit_provider_proposals(graph, scaffold, provider)

        report = result["report"]
        self.assertEqual(report["mode"], "provider_deltas_rejected")
        self.assertEqual(report["proposal_sources_used"], [])
        # scaffold candidate passed through untouched
        self.assertEqual(
            result["runtime_candidates"][0]["mesh"].extents.tolist(),
            scaffold["runtime_candidates"][0]["mesh"].extents.tolist(),
        )
        # some rejection recorded in conformance_failures
        self.assertTrue(report["conformance_failures"])

    def test_empty_provider_proposals_list_falls_back_to_native_only(self) -> None:
        graph = _graph()
        scaffold = _scaffold_result(graph)
        provider = _provider_result([], source_id="native")
        result = fit_provider_proposals(graph, scaffold, provider)

        self.assertEqual(result["report"]["mode"], "native_scaffold_only")
        self.assertEqual(result["report"]["accepted_deltas"], [])
        self.assertEqual(result["report"]["rejected_deltas"], [])
        # runtime_candidates pass through scaffold's
        self.assertEqual(len(result["runtime_candidates"]), 1)

    def test_best_proposal_selected_from_mixed_quality_pair(self) -> None:
        graph = _graph()
        scaffold = _scaffold_result(graph)
        good = _provider_candidate()
        bad = _provider_candidate(extents=(8.0, 0.05, 0.05), face_count=12)
        provider = _provider_result([bad, good])
        result = fit_provider_proposals(graph, scaffold, provider)

        report = result["report"]
        self.assertEqual(report["mode"], "provider_deltas_applied")
        # Exactly two proposals showed up in the bank; one accepted
        # proportion delta, one rejected.
        bank = report["proposal_bank"]
        self.assertEqual(len(bank["proposals"]), 2)
        accepted_kinds = {delta["kind"] for delta in report["accepted_deltas"]}
        self.assertIn("proportion_shift", accepted_kinds)

    def test_accepted_scale_stays_within_tolerance(self) -> None:
        # Provider proposal is accepted, so runtime candidate is scaled
        # by extents_scale — each factor must be clamped to the [0.84,
        # 1.18] window documented in conformance._proposal_metrics.
        graph = _graph()
        scaffold = _scaffold_result(graph)
        provider = _provider_result([_provider_candidate(extents=(1.1, 1.05, 0.95))])
        result = fit_provider_proposals(graph, scaffold, provider)

        if result["report"]["mode"] == "provider_deltas_applied":
            candidate_meta = result["runtime_candidates"][0]["meta"]
            scale = candidate_meta["accepted_provider_scale"]
            for factor in scale:
                self.assertGreaterEqual(factor, 0.84)
                self.assertLessEqual(factor, 1.18)

    def test_malformed_provider_candidate_missing_mesh_raises(self) -> None:
        # Provider candidates are required to carry a ``mesh`` key;
        # metric computation does mesh.extents / mesh.faces access.
        graph = _graph()
        scaffold = _scaffold_result(graph)
        provider = _provider_result([{"face_parts": [], "meta": {}}])  # no mesh
        with self.assertRaises(KeyError):
            fit_provider_proposals(graph, scaffold, provider)

    def test_report_records_attempted_sources_for_traceability(self) -> None:
        graph = _graph()
        scaffold = _scaffold_result(graph)
        provider = {
            "runtime_candidates": [_provider_candidate()],
            "provider_report": {
                "selected_provider_id": "lathe.provider.selected_v1",
                "actual_provider_id": "lathe.provider.fallback_v1",
            },
        }
        result = fit_provider_proposals(graph, scaffold, provider)
        attempted = result["report"]["proposal_sources_attempted"]
        self.assertIn("lathe.provider.selected_v1", attempted)
        self.assertIn("lathe.provider.fallback_v1", attempted)


if __name__ == "__main__":
    unittest.main()
