"""Unit tests for ``lathe.reference_ir.ReferenceIR``.

``ReferenceIR`` captures the ``refs`` block from a materialized asset:
raw image / mesh / asset / material paths, plus the V1.1
``reference_sets`` names and the resolver-produced
``resolved_reference_sets`` bundles. The IR is a pure extractor — path
validation / format checks are the resolver's responsibility — so these
tests focus on extraction, defaulting, list ordering, and an
end-to-end case through the reconstruct flow.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from lathe.parser import parse_file
from lathe.reference_ir import ReferenceIR
from lathe.resolver import materialize_asset

ROOT = Path(__file__).resolve().parents[2]
RECONSTRUCT_EXAMPLE = ROOT / "examples" / "reconstruct_courier_from_views.lth"


class ReferenceIRTests(unittest.TestCase):
    def test_from_asset_with_mesh_refs(self) -> None:
        asset = {
            "refs": {
                "meshes": ["refs/source_block.obj", "refs/hero.fbx"],
                "materials": ["refs/painted_steel.mat"],
            }
        }
        ir = ReferenceIR.from_asset(asset)
        self.assertEqual(ir.meshes, ["refs/source_block.obj", "refs/hero.fbx"])
        self.assertEqual(ir.materials, ["refs/painted_steel.mat"])
        self.assertEqual(ir.images, [])
        self.assertEqual(ir.reference_sets, [])

    def test_from_asset_with_image_refs_and_reference_sets(self) -> None:
        asset = {
            "refs": {
                "images": ["refs/front.png", "refs/side.png"],
                "reference_sets": ["courier_views"],
                "resolved_reference_sets": [
                    {"name": "courier_views", "images": ["refs/front.png", "refs/side.png"]}
                ],
            }
        }
        ir = ReferenceIR.from_asset(asset)
        self.assertEqual(ir.images, ["refs/front.png", "refs/side.png"])
        self.assertEqual(ir.reference_sets, ["courier_views"])
        self.assertEqual(len(ir.resolved_reference_sets), 1)
        self.assertEqual(ir.resolved_reference_sets[0]["name"], "courier_views")

    def test_from_asset_empty_refs_defaults(self) -> None:
        # All six buckets must default to empty lists so downstream
        # consumers can iterate without None checks.
        ir = ReferenceIR.from_asset({})
        self.assertEqual(ir.images, [])
        self.assertEqual(ir.meshes, [])
        self.assertEqual(ir.assets, [])
        self.assertEqual(ir.materials, [])
        self.assertEqual(ir.reference_sets, [])
        self.assertEqual(ir.resolved_reference_sets, [])

    def test_to_dict_round_trip(self) -> None:
        ir = ReferenceIR(
            images=["a.png"],
            meshes=["m.obj"],
            assets=["x.usd"],
            materials=["y.mat"],
            reference_sets=["rs1"],
            resolved_reference_sets=[{"name": "rs1"}],
        )
        payload = ir.to_dict()
        restored = ReferenceIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(
            set(payload),
            {"images", "meshes", "assets", "materials", "reference_sets", "resolved_reference_sets"},
        )

    def test_list_ordering_preserved(self) -> None:
        # Path ordering is semantically meaningful (e.g. first image is
        # the canonical hero view). The IR must preserve insertion
        # order across all list buckets.
        images = [f"refs/img_{i}.png" for i in range(5)]
        meshes = [f"refs/mesh_{i}.obj" for i in range(3)]
        ir = ReferenceIR.from_asset({"refs": {"images": images, "meshes": meshes}})
        self.assertEqual(ir.images, images)
        self.assertEqual(ir.meshes, meshes)

    def test_from_asset_copies_top_level_lists(self) -> None:
        # ``from_asset`` wraps each bucket with ``list(...)``, so
        # appending to the IR's lists must not mutate the source asset.
        src_images = ["a.png"]
        src_sets = [{"name": "rs"}]
        asset = {
            "refs": {
                "images": src_images,
                "resolved_reference_sets": src_sets,
            }
        }
        ir = ReferenceIR.from_asset(asset)
        ir.images.append("b.png")
        ir.resolved_reference_sets.append({"name": "rs2"})
        self.assertEqual(src_images, ["a.png"])
        self.assertEqual(src_sets, [{"name": "rs"}])

    def test_reconstruct_policy_references_preserved_end_to_end(self) -> None:
        # Real-example drive-through: the reconstruct example declares
        # ``reference_set courier_views`` + ``reference_sets = [courier_views]``.
        # After materialization both the authoring-side name list and the
        # resolver-expanded bundle must be present on the IR.
        asset = materialize_asset(parse_file(RECONSTRUCT_EXAMPLE), "reconstruct_courier_from_views")
        ir = ReferenceIR.from_asset(asset)
        self.assertEqual(ir.reference_sets, ["courier_views"])
        resolved_names = [entry.get("name") for entry in ir.resolved_reference_sets]
        self.assertEqual(resolved_names, ["courier_views"])
        # The resolved bundle carries the raw image paths from the
        # ``reference_set courier_views`` declaration under its ``values``
        # sub-dict (the resolver preserves the declaration structure
        # verbatim so downstream stages see the original field layout).
        resolved_values = ir.resolved_reference_sets[0].get("values", {})
        resolved_images = resolved_values.get("images", [])
        self.assertIn("refs/courier_front.png", resolved_images)
        self.assertIn("refs/courier_side.png", resolved_images)


if __name__ == "__main__":
    unittest.main()
