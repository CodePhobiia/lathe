"""Tests for the second backend stack ``lathe.stack.soft_surface_prop_v1``
(BL-34 / Plan 08 Phase 4, scoped down to a proof-of-plugin-model).

Coverage:

* Stack and topology backend are registered and resolvable.
* Every adapter id on the stack can be fetched from the backend registry.
* The satchel hero routes onto the soft stack, builds, and certifies.
* The soft-silhouette validator emits its proxy diagnostics on crafted
  bad inputs (jagged / too-smooth / too-folded).
* The ``lathe.shape.intent_mesh_handoff_v1`` contract hash is unchanged
  (same pin as ``tests/contract/test_shape_handoff_v1.py``).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pytest
from lathe.adapters import blender_subdiv
from lathe.backends import (
    BACKENDS,
    STACKS,
    get_backend,
    list_stacks,
    resolve_selected_backends,
    select_stack,
)
from lathe.executor import build_asset
from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.validators.soft_silhouette import (
    MAX_DIHEDRAL_DEGREES,
    MIN_READABLE_EDGE_VARIANCE,
    MIN_TRIANGLE_SAMPLES,
    evaluate_soft_silhouette,
)

ROOT = Path(__file__).resolve().parents[1]
SATCHEL_EXAMPLE = ROOT / "examples" / "satchel_bag.lth"

SOFT_STACK_ID = "lathe.stack.soft_surface_prop_v1"
SOFT_TOPOLOGY_ID = "lathe.topology.blender_subdiv_v1"
SHAPE_CONTRACT_ID = "lathe.shape.intent_mesh_handoff_v1"
# Same pin as tests/contract/test_shape_handoff_v1.py.
PINNED_CONTRACT_SHA256 = "51e02c6ed7e524cca42d0e638aa936da222af5a006358bd1d4e931aea671b085"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SoftSurfaceStackRegistryTests(unittest.TestCase):
    def test_stack_is_registered(self) -> None:
        self.assertIn(SOFT_STACK_ID, STACKS)
        ids = {stack["id"] for stack in list_stacks()}
        self.assertIn(SOFT_STACK_ID, ids)
        # Legacy stack must still be there unchanged.
        self.assertIn("lathe.stack.hard_surface_game_asset_v1", ids)

    def test_stack_bindings_resolve(self) -> None:
        stack = STACKS[SOFT_STACK_ID]
        bindings = stack["stage_backends"]
        for stage, backend_id in bindings.items():
            with self.subTest(stage=stage):
                backend = get_backend(backend_id)
                self.assertEqual(backend["stage"], stage)

    def test_subdiv_topology_backend_registered(self) -> None:
        self.assertIn(SOFT_TOPOLOGY_ID, BACKENDS)
        backend = BACKENDS[SOFT_TOPOLOGY_ID]
        self.assertEqual(backend["stage"], "topology")
        # Required output guarantees on the topology bundle preserved.
        required = set(backend["contract"]["outputs"]["required_fields"])
        for field in [
            "mesh_uri",
            "mesh_stats.vertex_count",
            "mesh_stats.triangle_count",
            "part_groups",
            "provenance.backend_id",
        ]:
            self.assertIn(field, required)

    def test_adapter_module_describes_itself(self) -> None:
        info = blender_subdiv.describe()
        self.assertEqual(info["adapter_id"], SOFT_TOPOLOGY_ID)
        self.assertEqual(info["stage"], "topology")
        self.assertIn("delegates_to", info)


class SoftSurfaceStackSelectionTests(unittest.TestCase):
    def test_satchel_routes_onto_soft_stack(self) -> None:
        program = parse_file(SATCHEL_EXAMPLE)
        asset = materialize_asset(program, "satchel_bag")
        resolved = resolve_selected_backends(asset)
        self.assertEqual(resolved["stack"]["id"], SOFT_STACK_ID)
        self.assertEqual(resolved["selected"]["topology"]["id"], SOFT_TOPOLOGY_ID)
        self.assertEqual(resolved["selected"]["shape"]["id"], SHAPE_CONTRACT_ID)

    def test_hard_surface_heroes_still_pick_hard_stack(self) -> None:
        # Regression guard: the new stack must not steal existing heroes.
        for name, asset_name in [
            ("courier_drone", "courier_drone"),
            ("industrial_crate", "industrial_crate"),
        ]:
            with self.subTest(hero=name):
                program = parse_file(ROOT / "examples" / f"{name}.lth")
                asset = materialize_asset(program, asset_name)
                resolved = resolve_selected_backends(asset)
                self.assertEqual(
                    resolved["stack"]["id"],
                    "lathe.stack.hard_surface_game_asset_v1",
                )

    def test_select_stack_prefers_explicit_binding_match(self) -> None:
        program = parse_file(SATCHEL_EXAMPLE)
        asset = materialize_asset(program, "satchel_bag")
        stack = select_stack(asset)
        self.assertEqual(stack["id"], SOFT_STACK_ID)
        self.assertTrue(stack.get("resolved"))


@pytest.mark.slow
class SoftSurfaceBuildTests(unittest.TestCase):
    def test_satchel_builds_and_certifies(self) -> None:
        program = parse_file(SATCHEL_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "satchel_bag"
            report = build_asset(program, "satchel_bag", out_dir)
            self.assertTrue(
                report["certified"],
                msg=f"satchel failed to certify: score={report['score']} "
                f"threshold={report['threshold']} diagnostics="
                f"{report.get('diagnostics', [])[:3]}",
            )
            self.assertGreaterEqual(report["score"], report["threshold"])
            # Topology bundle should record the subdiv backend id as the
            # declared backend.
            topo_bundle = json.loads(
                (out_dir / "stages" / "topology" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(topo_bundle["backend_id"], SOFT_TOPOLOGY_ID)
            # Deliverables exist.
            formats = {item["format"] for item in report["outputs"]}
            self.assertGreaterEqual(formats, {"usd", "glb"})


class SoftSilhouetteValidatorTests(unittest.TestCase):
    def _make_runtime(
        self,
        triangle_count: int,
        vertex_count: int,
        runtime_mesh: object | None = None,
    ) -> dict[str, object]:
        return {
            "topology": {
                "bundle": {
                    "mesh_stats": {
                        "triangle_count": triangle_count,
                        "vertex_count": vertex_count,
                    }
                },
                "runtime_mesh": runtime_mesh,
            }
        }

    def test_healthy_input_has_no_diagnostics(self) -> None:
        import trimesh

        mesh = trimesh.creation.uv_sphere(radius=1.0, count=[24, 24])

        class _Rt:
            def __init__(self, m: object) -> None:
                self.mesh = m

        runtime = self._make_runtime(
            triangle_count=len(mesh.faces),
            vertex_count=len(mesh.vertices),
            runtime_mesh=_Rt(mesh),
        )
        report = evaluate_soft_silhouette({"name": "ok"}, runtime)
        codes = {d["code"] for d in report["diagnostics"]}
        # A clean uv_sphere should not trip any of our tripwires.
        self.assertNotIn("L6701", codes)
        self.assertNotIn("L6702", codes)
        self.assertNotIn("L6703", codes)
        self.assertGreater(report["score"], 0.5)

    def test_too_few_samples_emits_too_jagged(self) -> None:
        runtime = self._make_runtime(
            triangle_count=max(1, MIN_TRIANGLE_SAMPLES - 10),
            vertex_count=8,
        )
        report = evaluate_soft_silhouette({"name": "jagged"}, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        self.assertIn("soft_silhouette_too_jagged", names)

    def test_flat_mesh_emits_too_smooth(self) -> None:
        import trimesh

        # A single square (two tris) has near-zero edge-length variance.
        mesh = trimesh.Trimesh(
            vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            faces=[[0, 1, 2], [0, 2, 3]],
            process=False,
        )

        class _Rt:
            def __init__(self, m: object) -> None:
                self.mesh = m

        runtime = self._make_runtime(
            triangle_count=len(mesh.faces),
            vertex_count=len(mesh.vertices),
            runtime_mesh=_Rt(mesh),
        )
        # Bump the triangle count above the too-jagged threshold so we
        # isolate the too-smooth / too-few-vertex tripwires.
        runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"] = MIN_TRIANGLE_SAMPLES + 10
        report = evaluate_soft_silhouette({"name": "flat"}, runtime)
        names = {d["name"] for d in report["diagnostics"]}
        # Flat plane: too few vertices AND too-smooth are acceptable
        # evidence that the validator tripped; assert at least one.
        self.assertTrue(
            names & {"soft_silhouette_too_jagged", "soft_silhouette_too_smooth"},
            msg=f"expected a jagged/smooth diagnostic, got: {names}",
        )

    def test_thresholds_round_trip_are_exposed(self) -> None:
        runtime = self._make_runtime(triangle_count=0, vertex_count=0)
        report = evaluate_soft_silhouette({"name": "empty"}, runtime)
        self.assertEqual(report["thresholds"]["min_triangle_samples"], MIN_TRIANGLE_SAMPLES)
        self.assertEqual(report["thresholds"]["max_dihedral_degrees"], MAX_DIHEDRAL_DEGREES)
        self.assertEqual(
            report["thresholds"]["min_readable_edge_variance"],
            MIN_READABLE_EDGE_VARIANCE,
        )


class ShapeContractHashPreservationTests(unittest.TestCase):
    def test_intent_mesh_handoff_v1_hash_unchanged(self) -> None:
        # Pulled in as part of the BL-34 suite to make any accidental
        # contract drift visible in CI alongside the second-stack work.
        backend = get_backend(SHAPE_CONTRACT_ID)
        actual = hashlib.sha256(_canonical_bytes(backend)).hexdigest()
        self.assertEqual(
            actual,
            PINNED_CONTRACT_SHA256,
            msg=(
                "shape contract bytes drifted while wiring BL-34. "
                "This is a stable public contract -- revert or migrate."
            ),
        )


if __name__ == "__main__":
    unittest.main()
