from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import trimesh
from lathe.executor import RuntimeMesh, _run_reference_topology_cleanup, build_asset
from lathe.parser import parse_file
from lathe.resolver import materialize_asset

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"
RECONSTRUCT_VIEWS_EXAMPLE = ROOT / "examples" / "reconstruct_courier_from_views.lth"
CHEST_EXAMPLE = ROOT / "examples" / "brassbound_chest.lth"
WALL_PANEL_EXAMPLE = ROOT / "examples" / "sci_fi_wall_panel.lth"
CRATE_EXAMPLE = ROOT / "examples" / "industrial_crate.lth"
DOOR_EXAMPLE = ROOT / "examples" / "mechanical_door.lth"
CONSOLE_EXAMPLE = ROOT / "examples" / "console_terminal.lth"
CABINET_EXAMPLE = ROOT / "examples" / "service_cabinet.lth"
PEDESTAL_EXAMPLE = ROOT / "examples" / "control_pedestal.lth"
SUPPLY_EXAMPLE = ROOT / "examples" / "supply_container.lth"
ADAPT_EXAMPLE = ROOT / "examples" / "console_terminal_mobile_adapt.lth"
ASSEMBLE_EXAMPLE = ROOT / "examples" / "service_corridor_wall.lth"


class LatheBuildTests(unittest.TestCase):
    def test_example_builds_and_packages(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            report = build_asset(program, "courier_drone", out_dir)
            self.assertTrue(report["certified"])
            self.assertGreaterEqual(report["score"], report["threshold"])
            self.assertTrue((out_dir / "stages" / "shape" / "bundle.json").exists())
            self.assertTrue((out_dir / "stages" / "topology" / "bundle.json").exists())
            self.assertTrue((out_dir / "stages" / "uv" / "bundle.json").exists())
            self.assertTrue((out_dir / "stages" / "package" / "package_manifest.json").exists())
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.hero_pbr_v1")
            self.assertIn("highlow_relation", surface_bundle)
            self.assertTrue((out_dir / "stages" / "surface" / "maps" / "basecolor.png").exists())
            formats = {item["format"] for item in report["outputs"]}
            self.assertGreaterEqual(formats, {"usd", "glb"})

    def test_build_report_redacts_runtime_config_secrets(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            report = build_asset(
                program,
                "courier_drone",
                out_dir,
                runtime_config={
                    "publish": {"service_key": "sk-build-secret"},
                    "shape": {"providers": {"reference_conditioned": {"api_token": "provider-token"}}},
                },
            )
            report_text = (out_dir / "build_report.json").read_text(encoding="utf-8")

        self.assertNotIn("sk-build-secret", report_text)
        self.assertNotIn("provider-token", report_text)
        self.assertEqual(report["runtime_config"]["publish"]["service_key"], "[redacted]")

    def test_variant_builds(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone_mobile"
            report = build_asset(program, "courier_drone_mobile", out_dir)
            self.assertTrue(report["certified"])
            self.assertTrue((out_dir / "stages" / "package" / "courier_drone_mobile.glb").exists())

    def test_shape_bundle_records_reference_conditioning(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            build_asset(program, "courier_drone", out_dir)
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(bundle["conditioning_report"]["image_refs"]), 2)
            self.assertGreaterEqual(
                sum(1 for item in bundle["provenance"]["consumed_refs"] if item.get("exists")), 3
            )

    def test_reconstruct_mode_uses_mesh_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_mesh = trimesh.creation.box(extents=[90.0, 28.0, 120.0])
            source_mesh.export(tmp / "source.obj")
            source = EXAMPLE.read_text(encoding="utf-8")
            source = source.replace(
                'refs {\n    images = [\n      "refs/courier_front.png",\n      "refs/courier_side.png",\n      "refs/materials.jpg",\n    ]\n  }',
                'refs {\n    meshes = ["source.obj"]\n  }',
            )
            source = source.replace("mode = generate", "mode = reconstruct", 1)
            source_path = tmp / "reconstruct_drone.lth"
            source_path.write_text(source, encoding="utf-8")
            program = parse_file(source_path)
            out_dir = tmp / "dist" / "courier_drone"
            report = build_asset(program, "courier_drone", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(bundle["conditioning_report"]["mesh_refs"]), 1)
            selected_id = bundle["selected_candidate_id"]
            selected = next(item for item in bundle["candidates"] if item["candidate_id"] == selected_id)
            joined = " ".join(selected["selection_notes"]).lower()
            self.assertIn("mesh-conditioned assembly blueprint", joined)

    def test_reconstruct_views_example_builds_with_fallbacks(self) -> None:
        program = parse_file(RECONSTRUCT_VIEWS_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "reconstruct_courier_from_views"
            report = build_asset(program, "reconstruct_courier_from_views", out_dir)
            self.assertTrue(report["certified"])
            shape_bundle = json.loads(
                (out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                shape_bundle["provenance"]["shape_provider_id"],
                "lathe.provider.shape.reference_conditioned_v1",
            )
            self.assertTrue(shape_bundle["reference_ir"]["resolved_reference_sets"])
            self.assertTrue(shape_bundle["fit_ir"]["fit_profile"])
            self.assertTrue(shape_bundle["fit_ir"]["reconstruct_policy"])

    def test_chest_example_builds(self) -> None:
        program = parse_file(CHEST_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "brassbound_chest"
            report = build_asset(program, "brassbound_chest", out_dir)
            self.assertTrue(report["certified"])
            self.assertTrue((out_dir / "stages" / "package" / "brassbound_chest.glb").exists())
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.hero_pbr_v1")
            self.assertTrue((out_dir / "stages" / "surface" / "maps" / "normal.png").exists())

    def test_wall_panel_example_builds(self) -> None:
        program = parse_file(WALL_PANEL_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "sci_fi_wall_panel"
            report = build_asset(program, "sci_fi_wall_panel", out_dir)
            self.assertTrue(report["certified"])
            self.assertTrue((out_dir / "stages" / "package" / "sci_fi_wall_panel.glb").exists())
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.semantic_passthrough_v1")

    def test_crate_example_builds(self) -> None:
        program = parse_file(CRATE_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "industrial_crate"
            report = build_asset(program, "industrial_crate", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.hard_surface_crate_v2")
            self.assertIn("shell", bundle["primitives_used"])
            self.assertIn("frame", bundle["primitives_used"])
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.hero_pbr_v1")

    def test_door_example_builds(self) -> None:
        program = parse_file(DOOR_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "mechanical_door"
            report = build_asset(program, "mechanical_door", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.env_mechanical_door_v2")
            self.assertIn("hinge", bundle["primitives_used"])
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.hero_pbr_v1")

    def test_console_example_builds(self) -> None:
        program = parse_file(CONSOLE_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "console_terminal"
            report = build_asset(program, "console_terminal", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.hard_surface_console_terminal_v2")
            self.assertIn("bezel", bundle["primitives_used"])
            surface_bundle = json.loads(
                (out_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(surface_bundle["backend_id"], "lathe.surface.hero_pbr_v1")
            self.assertTrue((out_dir / "stages" / "surface" / "maps" / "emissive.png").exists())

    def test_service_cabinet_example_builds(self) -> None:
        program = parse_file(CABINET_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "service_cabinet"
            report = build_asset(program, "service_cabinet", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.hard_surface_service_cabinet_v1")
            self.assertIn("door", bundle["primitives_used"])
            self.assertIn("vent", bundle["primitives_used"])

    def test_control_pedestal_example_builds(self) -> None:
        program = parse_file(PEDESTAL_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "control_pedestal"
            report = build_asset(program, "control_pedestal", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.hard_surface_control_pedestal_v1")
            self.assertIn("bezel", bundle["primitives_used"])
            self.assertIn("stand", bundle["primitives_used"])

    def test_supply_container_example_builds(self) -> None:
        program = parse_file(SUPPLY_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "supply_container"
            report = build_asset(program, "supply_container", out_dir)
            self.assertTrue(report["certified"])
            bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["blueprint_id"], "lathe.blueprint.hard_surface_supply_container_v1")
            self.assertIn("lid", bundle["primitives_used"])
            self.assertIn("frame", bundle["primitives_used"])

    def test_console_terminal_mobile_adapt_builds(self) -> None:
        program = parse_file(ADAPT_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "console_terminal_mobile"
            report = build_asset(program, "console_terminal_mobile", out_dir)
            self.assertTrue(report["certified"])
            shape_bundle = json.loads(
                (out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(shape_bundle["fit_ir"]["fit_profile"], {})
            self.assertTrue(shape_bundle["transfer_ir"]["adapt_policy"])
            self.assertEqual(shape_bundle["asset_graph"]["authoring"]["shape_mode"], "adapt")
            validate = json.loads(
                (out_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate["flow_quality"]["mode"], "adapt")
            self.assertIn("semantic_preservation_quality", validate["flow_quality"]["metrics"])
            trace = json.loads(
                (out_dir / "stages" / "package" / "trace_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(trace["stage_execution"]["flow_quality"]["mode"], "adapt")

    def test_service_corridor_wall_assemble_builds(self) -> None:
        program = parse_file(ASSEMBLE_EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "service_corridor_wall"
            report = build_asset(program, "service_corridor_wall", out_dir)
            self.assertTrue(report["certified"])
            shape_bundle = json.loads(
                (out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertTrue(shape_bundle["kit_ir"]["kit_name"])
            self.assertTrue(shape_bundle["kit_ir"]["values"])
            self.assertEqual(shape_bundle["asset_graph"]["authoring"]["shape_mode"], "assemble")
            validate = json.loads(
                (out_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate["flow_quality"]["mode"], "assemble")
            self.assertIn("join_legality", validate["flow_quality"]["metrics"])

    def test_topology_quality_gate_falls_back_from_blender(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            broken = trimesh.creation.box(extents=[20.0, 20.0, 20.0])
            broken.update_faces(list(range(len(broken.faces) - 1)))
            broken.remove_unreferenced_vertices()
            bad_runtime = RuntimeMesh(
                mesh=broken,
                face_parts=["body"] * len(broken.faces),
                part_colors={"body": (120, 120, 120)},
                units="cm",
            )
            with (
                patch(
                    "lathe.executor.probe_topology_backend",
                    return_value={
                        "backend_id": "lathe.topology.blender_hard_surface_v1",
                        "requested_adapter": "auto",
                        "selected_adapter": "blender_subprocess",
                        "strict": False,
                        "available": True,
                        "real_adapter_available": True,
                        "fallback_available": True,
                        "probe": {"available": True, "path": "mock-blender", "version": "mock", "code": "ok"},
                    },
                ),
                patch(
                    "lathe.executor._run_blender_topology",
                    return_value=(
                        bad_runtime,
                        {"mode": "blender_subprocess", "blender_path": "mock-blender"},
                    ),
                ),
            ):
                report = build_asset(
                    program,
                    "courier_drone",
                    out_dir,
                    runtime_config={"topology": {"adapter": "auto", "strict": False}},
                )

            self.assertTrue(report["certified"])
            topology_bundle = json.loads(
                (out_dir / "stages" / "topology" / "bundle.json").read_text(encoding="utf-8")
            )
            self.assertIn(topology_bundle["adapter_report"]["status"], {"fallback", "preserved"})
            self.assertIn(
                topology_bundle["adapter_report"]["actual_adapter"],
                {"reference_cleanup", "integrated_preserve_cleanup"},
            )
            trace = json.loads(
                (out_dir / "stages" / "package" / "trace_manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                trace["stage_execution"]["topology"]["actual_adapter"],
                {"reference_cleanup", "integrated_preserve_cleanup"},
            )

    def test_uv_fallback_records_reference_box_adapter(self) -> None:
        program = parse_file(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "courier_drone"
            report = build_asset(
                program,
                "courier_drone",
                out_dir,
                runtime_config={"topology": {"adapter": "cleanup"}, "uv": {"adapter": "box"}},
            )
            self.assertTrue(report["certified"])
            uv_bundle = json.loads((out_dir / "stages" / "uv" / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(uv_bundle["adapter_report"]["actual_adapter"], "reference_box")
            self.assertIn(uv_bundle["adapter_report"]["status"], {"forced", "fallback"})

    def test_reference_topology_cleanup_seals_and_infers_parts(self) -> None:
        program = parse_file(EXAMPLE)
        asset = materialize_asset(program, "courier_drone")
        broken = trimesh.creation.box(extents=[40.0, 20.0, 80.0])
        broken.update_faces(list(range(len(broken.faces) - 1)))
        broken.remove_unreferenced_vertices()
        runtime = RuntimeMesh(
            mesh=broken,
            face_parts=["body"] * len(broken.faces),
            part_colors={part: (120, 120, 120) for part in asset["intent"]["parts"]},
            units="cm",
        )
        repaired, execution = _run_reference_topology_cleanup(runtime, asset)
        self.assertTrue(repaired.mesh.is_watertight)
        self.assertIn(execution["seal_strategy"], {"fill_holes", "convex_hull"})
        self.assertIn("rotor_fl", set(repaired.face_parts))
        self.assertIn("cargo_door", set(repaired.face_parts))


if __name__ == "__main__":
    unittest.main()
