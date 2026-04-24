"""Unit tests for ``lathe.candidate_search``.

Covers the three public entry points of the candidate-search module:
``generate_candidate_params`` (seeded sample of the search space),
``apply_candidate_params`` (deterministic projection onto an
:class:`AssemblyBlueprint`), and ``objective_weights`` (normalization of
the authoring objectives block). The sampler is meant to be pure and
seed-deterministic; these tests pin that contract plus boundary
behaviors (frozen dimensions, empty objectives, large indices).
"""

from __future__ import annotations

import unittest

import numpy as np

from lathe.asset_graph import build_asset_graph
from lathe.assembly_kernel import AssemblyBlueprint, BlueprintComponent
from lathe.blueprints import resolve_blueprint
from lathe.candidate_search import (
    CandidateParams,
    apply_candidate_params,
    generate_candidate_params,
    objective_weights,
)
from lathe.fidelity import infer_fidelity_profile


def _crate_graph(**authoring_overrides):
    asset = {
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
    if authoring_overrides:
        asset.update(authoring_overrides)
    return build_asset_graph(asset)


class GenerateCandidateParamsTests(unittest.TestCase):
    def test_generate_three_distinct_indices(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        results = [
            generate_candidate_params(graph, seed=7, candidate_index=i, fidelity=fidelity)
            for i in range(3)
        ]
        # each call returns a CandidateParams dataclass with all float fields
        for params in results:
            self.assertIsInstance(params, CandidateParams)
            for field_name in (
                "width_scale", "height_scale", "depth_scale",
                "feature_density", "panel_depth", "edge_weight",
                "support_spread", "attachment_spread", "trim_scale",
                "silhouette_bias", "rotor_guard_scale",
            ):
                self.assertIsInstance(getattr(params, field_name), float)
        # distinct indices must produce distinct samples (seed + index*977)
        self.assertNotEqual(results[0], results[1])
        self.assertNotEqual(results[1], results[2])

    def test_seed_determinism(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        first = generate_candidate_params(graph, seed=123, candidate_index=4, fidelity=fidelity)
        second = generate_candidate_params(graph, seed=123, candidate_index=4, fidelity=fidelity)
        self.assertEqual(first.to_dict(), second.to_dict())
        # different seed => different params
        other = generate_candidate_params(graph, seed=124, candidate_index=4, fidelity=fidelity)
        self.assertNotEqual(first.to_dict(), other.to_dict())

    def test_large_candidate_index_does_not_crash(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        # seed + candidate_index * 977 stays inside numpy's uint64 space
        # for huge indices; verify no overflow / no exception.
        params = generate_candidate_params(
            graph, seed=1, candidate_index=1_000_000, fidelity=fidelity
        )
        self.assertIsInstance(params, CandidateParams)
        self.assertTrue(np.isfinite(params.width_scale))
        self.assertTrue(np.isfinite(params.feature_density))

    def test_frozen_paths_reset_to_defaults(self) -> None:
        # space.freeze names must be reset to the _FROZEN_DEFAULTS value
        # regardless of random sampling.
        graph = _crate_graph(
            space={
                "freeze": ["width_scale", "height_scale", "depth_scale"],
                "vary": [],
            }
        )
        fidelity = infer_fidelity_profile(graph)
        params = generate_candidate_params(graph, seed=99, candidate_index=0, fidelity=fidelity)
        self.assertEqual(params.width_scale, 1.0)
        self.assertEqual(params.height_scale, 1.0)
        self.assertEqual(params.depth_scale, 1.0)

    def test_reconstruct_mode_freezes_silhouette_dims(self) -> None:
        # shape_mode == reconstruct auto-freezes the silhouette dims so
        # width/height/depth scales collapse to 1.0.
        graph = _crate_graph()
        graph.authoring["shape_mode"] = "reconstruct"
        fidelity = infer_fidelity_profile(graph)
        params = generate_candidate_params(graph, seed=5, candidate_index=2, fidelity=fidelity)
        self.assertEqual(params.width_scale, 1.0)
        self.assertEqual(params.height_scale, 1.0)
        self.assertEqual(params.depth_scale, 1.0)


class ApplyCandidateParamsTests(unittest.TestCase):
    def _blueprint(self, graph):
        rng = np.random.default_rng(0)
        return resolve_blueprint(graph, {}, rng, 0)

    def test_apply_is_pure_projection(self) -> None:
        # Invariants: component count preserved; original blueprint is
        # not mutated; notes are appended with a candidate_search line.
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        params = generate_candidate_params(graph, seed=1, candidate_index=0, fidelity=fidelity)
        blueprint = self._blueprint(graph)
        original_count = len(blueprint.components)
        original_first_extents = blueprint.components[0].extents
        original_notes = list(blueprint.notes)

        projected = apply_candidate_params(blueprint, params, graph)

        self.assertIsInstance(projected, AssemblyBlueprint)
        self.assertEqual(len(projected.components), original_count)
        # original blueprint untouched
        self.assertEqual(blueprint.components[0].extents, original_first_extents)
        self.assertEqual(blueprint.notes, original_notes)
        # new notes appended
        self.assertGreater(len(projected.notes), len(original_notes))
        self.assertTrue(any("candidate_search" in note for note in projected.notes))

    def test_apply_is_deterministic_for_same_params(self) -> None:
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        params = generate_candidate_params(graph, seed=3, candidate_index=0, fidelity=fidelity)
        blueprint = self._blueprint(graph)
        first = apply_candidate_params(blueprint, params, graph)
        second = apply_candidate_params(blueprint, params, graph)
        self.assertEqual(
            [comp.to_dict() for comp in first.components],
            [comp.to_dict() for comp in second.components],
        )

    def test_apply_handles_unknown_component_type_via_default_branch(self) -> None:
        # The else-branch in apply_candidate_params scales extents by
        # width/height/depth_scale for unknown component types.
        graph = _crate_graph()
        fidelity = infer_fidelity_profile(graph)
        params = generate_candidate_params(graph, seed=0, candidate_index=0, fidelity=fidelity)
        blueprint = AssemblyBlueprint(
            blueprint_id="bp.unknown",
            family="hard_surface_prop_generic",
            components=[
                BlueprintComponent(
                    name="mystery",
                    component_type="__unknown_type__",
                    part="body",
                    center=(0.0, 0.0, 0.0),
                    extents=(2.0, 3.0, 4.0),
                )
            ],
        )
        projected = apply_candidate_params(blueprint, params, graph)
        extents = projected.components[0].extents
        self.assertAlmostEqual(extents[0], 2.0 * params.width_scale)
        self.assertAlmostEqual(extents[1], 3.0 * params.height_scale)
        self.assertAlmostEqual(extents[2], 4.0 * params.depth_scale)


class ObjectiveWeightsTests(unittest.TestCase):
    def test_returns_dict_and_normalizes_to_one(self) -> None:
        graph = _crate_graph(
            space={
                "objectives": [
                    {"metric": "silhouette_fidelity", "weight": 1.0},
                    {"metric": "feature_density", "weight": 3.0},
                ]
            }
        )
        weights = objective_weights(graph)
        self.assertIsInstance(weights, dict)
        self.assertEqual(set(weights), {"silhouette_fidelity", "feature_density"})
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        self.assertAlmostEqual(weights["feature_density"], 0.75, places=6)

    def test_empty_objectives_yields_empty_dict(self) -> None:
        graph = _crate_graph()
        self.assertEqual(objective_weights(graph), {})

    def test_zero_total_weight_yields_empty_dict(self) -> None:
        graph = _crate_graph(
            space={
                "objectives": [
                    {"metric": "m1", "weight": 0.0},
                    {"metric": "m2"},  # no weight => 0
                ]
            }
        )
        self.assertEqual(objective_weights(graph), {})

    def test_objectives_read_from_top_level_then_fallback_to_space(self) -> None:
        # authoring.objectives is populated from the asset.space
        # objectives (see build_asset_graph). We also accept the same
        # block on the authoring.space fallback.
        graph = _crate_graph(
            space={
                "objectives": [
                    {"metric": "space_metric", "weight": 2.0},
                ]
            }
        )
        weights = objective_weights(graph)
        # top-level objectives pulled from the space block take priority
        self.assertIn("space_metric", weights)
        self.assertAlmostEqual(weights["space_metric"], 1.0)


if __name__ == "__main__":
    unittest.main()
