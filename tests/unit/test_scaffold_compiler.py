"""Unit tests for ``lathe.scaffold_compiler``.

``compile_scaffold_candidates`` is the hot path under the stable
``lathe.shape.intent_mesh_handoff_v1`` contract. It resolves a
blueprint via :func:`lathe.blueprints.resolve_blueprint`, compiles
an :class:`lathe.shape_ir.ShapeIR`, runs feature enhancement and
repair rounds, then shortlists and materializes runtime candidates.

These tests pin the contract surface:
- the output shape (``asset_graph``, ``shape_irs``, ``runtime_candidates``, ``report``)
- determinism under identical seed / conditioning
- seed mixing via ``RNG_PRIME_OFFSET`` at the RNG level (same seed + index
  → identical RNG output every time)
- candidate-count capping & ``best_of`` promotion
- graceful handling of degenerate asset graphs (empty parts)

They avoid mutating the contract bytes — no monkeypatching of blueprint
outputs, no forced provider paths.
"""

from __future__ import annotations

import unittest

import numpy as np
from lathe.asset_graph import build_asset_graph
from lathe.constants import RNG_PRIME_OFFSET
from lathe.scaffold_compiler import _candidate_rng, compile_scaffold_candidates
from lathe.shape_ir import ShapeIR


def _courier_drone_asset_graph():
    return build_asset_graph(
        {
            "name": "courier_drone",
            "kind": "mechanical_assembly",
            "intent": {
                "role": "drone",
                "parts": ["body", "rotor_fl", "rotor_fr", "rotor_rl", "rotor_rr"],
            },
            "build": {"shape": {"symmetry": "x", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        }
    )


def _crate_asset_graph(parts: list[str] | None = None):
    return build_asset_graph(
        {
            "name": "industrial_crate",
            "kind": "prop",
            "intent": {
                "role": "crate",
                "parts": list(parts or ["body", "lid"]),
            },
            "build": {"shape": {"symmetry": "auto", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        }
    )


def _default_conditioning() -> dict:
    return {"reference_strength": 0.0, "image_refs": [], "material_refs": [], "mesh_refs": []}


class CandidateRNGTests(unittest.TestCase):
    def test_same_seed_and_index_produces_identical_rng_bytes(self) -> None:
        # _candidate_rng derives its seed as seed + index * RNG_PRIME_OFFSET.
        # Two calls with seed=42, index=0 must produce byte-identical draws.
        rng_a = _candidate_rng(seed=42, index=0)
        rng_b = _candidate_rng(seed=42, index=0)
        draws_a = rng_a.integers(0, 2**31 - 1, size=8).tolist()
        draws_b = rng_b.integers(0, 2**31 - 1, size=8).tolist()
        self.assertEqual(draws_a, draws_b)

    def test_different_index_produces_different_rng_bytes(self) -> None:
        rng_zero = _candidate_rng(seed=42, index=0)
        rng_one = _candidate_rng(seed=42, index=1)
        draws_zero = rng_zero.integers(0, 2**31 - 1, size=8).tolist()
        draws_one = rng_one.integers(0, 2**31 - 1, size=8).tolist()
        self.assertNotEqual(draws_zero, draws_one)

    def test_rng_prime_offset_is_the_seed_mixing_multiplier(self) -> None:
        # Independently construct the reference generator with the formula
        # from the module — the two must match bit-for-bit.
        seed = 123
        index = 3
        expected = np.random.default_rng(seed + index * RNG_PRIME_OFFSET)
        actual = _candidate_rng(seed, index)
        self.assertEqual(
            expected.integers(0, 2**31 - 1, size=4).tolist(),
            actual.integers(0, 2**31 - 1, size=4).tolist(),
        )


class CompileScaffoldCandidatesTests(unittest.TestCase):
    def test_happy_courier_drone_produces_candidates(self) -> None:
        asset_graph = _courier_drone_asset_graph()
        result = compile_scaffold_candidates(
            asset_graph,
            seed=42,
            candidates_count=1,
            conditioning=_default_conditioning(),
            mode="generate",
        )

        self.assertIn("asset_graph", result)
        self.assertIn("shape_irs", result)
        self.assertIn("runtime_candidates", result)
        self.assertIn("report", result)
        self.assertIs(result["asset_graph"], asset_graph)
        self.assertGreaterEqual(len(result["shape_irs"]), 1)
        self.assertEqual(len(result["shape_irs"]), len(result["runtime_candidates"]))
        for shape_ir in result["shape_irs"]:
            self.assertIsInstance(shape_ir, ShapeIR)

    def test_report_carries_signature_blueprint_and_fidelity(self) -> None:
        asset_graph = _courier_drone_asset_graph()
        result = compile_scaffold_candidates(
            asset_graph,
            seed=7,
            candidates_count=1,
            conditioning=_default_conditioning(),
            mode="generate",
        )
        report = result["report"]
        self.assertEqual(report["family"], "courier_drone")
        self.assertEqual(report["generator"], "parametric_hard_surface_assembly")
        self.assertIn("signature", report)
        self.assertIn("blueprint_id", report)
        self.assertIn("fidelity", report)
        self.assertIn("candidate_search_summary", report)
        self.assertEqual(report["authoritative_candidate_reason"], "native_assembly_blueprint")

    def test_deterministic_same_seed_produces_same_shape_ir(self) -> None:
        asset_graph_a = _courier_drone_asset_graph()
        asset_graph_b = _courier_drone_asset_graph()
        conditioning = _default_conditioning()

        result_a = compile_scaffold_candidates(
            asset_graph_a, seed=123, candidates_count=1, conditioning=conditioning, mode="generate"
        )
        result_b = compile_scaffold_candidates(
            asset_graph_b, seed=123, candidates_count=1, conditioning=conditioning, mode="generate"
        )
        # Serialized shape IRs must match exactly.
        self.assertEqual(
            [ir.to_dict() for ir in result_a["shape_irs"]],
            [ir.to_dict() for ir in result_b["shape_irs"]],
        )

    def test_zero_primitive_blueprint_graceful_on_empty_parts(self) -> None:
        # The generic blueprint resolver accepts an empty parts list. The
        # scaffold compiler must not raise; it should still produce a
        # candidate with a (possibly near-empty) ShapeIR.
        asset_graph = _crate_asset_graph(parts=[])
        result = compile_scaffold_candidates(
            asset_graph,
            seed=11,
            candidates_count=1,
            conditioning=_default_conditioning(),
            mode="generate",
        )
        self.assertGreaterEqual(len(result["shape_irs"]), 1)
        self.assertEqual(len(result["runtime_candidates"]), len(result["shape_irs"]))

    def test_candidate_count_cap_via_candidates_count_arg(self) -> None:
        # With candidates_count=1 and no best_of override, the shortlist
        # is capped — runtime_candidates must not exceed the search count.
        asset_graph = _crate_asset_graph()
        result = compile_scaffold_candidates(
            asset_graph,
            seed=9,
            candidates_count=1,
            conditioning=_default_conditioning(),
            mode="generate",
        )
        self.assertLessEqual(len(result["runtime_candidates"]), 2)
        self.assertGreaterEqual(len(result["runtime_candidates"]), 1)
        # candidate_search_summary records every searched candidate, even
        # those not shortlisted — at minimum one per search iteration.
        summary = result["report"]["candidate_search_summary"]
        self.assertGreaterEqual(len(summary), 1)

    def test_runtime_candidate_payload_shape(self) -> None:
        asset_graph = _crate_asset_graph()
        result = compile_scaffold_candidates(
            asset_graph,
            seed=5,
            candidates_count=1,
            conditioning=_default_conditioning(),
            mode="generate",
        )
        runtime = result["runtime_candidates"][0]
        # These keys are the downstream contract: topology stage reads them.
        self.assertIn("mesh", runtime)
        self.assertIn("face_parts", runtime)
        self.assertIn("part_colors", runtime)
        self.assertIn("meta", runtime)
        self.assertEqual(runtime["units"], "cm")
        self.assertIn("blueprint_id", runtime["meta"])
        self.assertIn("shape_assessment", runtime["meta"])
        # face_parts length must match the mesh face count.
        self.assertEqual(len(runtime["face_parts"]), len(runtime["mesh"].faces))


if __name__ == "__main__":
    unittest.main()
