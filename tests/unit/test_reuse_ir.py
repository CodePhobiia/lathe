"""Unit tests for ``lathe.reuse_ir.ReuseIR``.

``ReuseIR`` lifts the asset's ``reuse`` block plus the
``assembly.resolved_kit`` bundle. It's a thin extractor — no validation
lives in the IR itself — so tests cover extraction correctness,
defaulting, dict round-tripping, and one end-to-end case through a real
``.lth`` example that exercises the V1.1 ``library`` / ``kit`` assemble
flow.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.reuse_ir import ReuseIR

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLE_EXAMPLE = ROOT / "examples" / "service_corridor_wall.lth"


class ReuseIRTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        ir = ReuseIR(
            values={"source": "industrial_hardsurface_library", "components": ["c1"]},
            resolved_kit={"name": "industrial_wall_kit", "values": {"family": "fam"}},
        )
        self.assertEqual(ir.values["source"], "industrial_hardsurface_library")
        self.assertEqual(ir.resolved_kit["name"], "industrial_wall_kit")

    def test_to_dict_round_trip(self) -> None:
        ir = ReuseIR(
            values={"source": "lib", "components": ["a", "b"]},
            resolved_kit={"name": "k", "values": {"modules": ["a", "b"]}},
        )
        payload = ir.to_dict()
        restored = ReuseIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(set(payload), {"values", "resolved_kit"})

    def test_from_asset_empty_defaults(self) -> None:
        # No reuse block, no assembly block — IR falls back to empty dicts
        # rather than raising. The resolver/checker gate required-field
        # errors upstream.
        ir = ReuseIR.from_asset({})
        self.assertEqual(ir.values, {})
        self.assertEqual(ir.resolved_kit, {})

    def test_from_asset_preserves_reuse_fields(self) -> None:
        asset = {
            "reuse": {
                "source": "industrial_hardsurface_library",
                "components": ["wall_panel_shell", "wall_screen_bezel"],
                "materials": ["painted_steel_body"],
            },
            "assembly": {},
        }
        ir = ReuseIR.from_asset(asset)
        self.assertEqual(ir.values["source"], "industrial_hardsurface_library")
        self.assertEqual(ir.values["components"], ["wall_panel_shell", "wall_screen_bezel"])
        self.assertEqual(ir.values["materials"], ["painted_steel_body"])
        self.assertEqual(ir.resolved_kit, {})

    def test_from_asset_tracks_resolved_kit_from_real_example(self) -> None:
        # ``service_corridor_wall.lth`` resolves the industrial_wall_kit
        # even though it doesn't declare an explicit ``reuse`` block, so
        # ReuseIR captures the assembly-side resolved_kit bundle.
        asset = materialize_asset(parse_file(ASSEMBLE_EXAMPLE), "service_corridor_wall")
        ir = ReuseIR.from_asset(asset)
        self.assertEqual(ir.resolved_kit.get("name"), "industrial_wall_kit")
        self.assertIn("values", ir.resolved_kit)
        self.assertIn("modules", ir.resolved_kit["values"])

    def test_empty_components_list_handled(self) -> None:
        asset = {"reuse": {"source": "lib", "components": []}}
        ir = ReuseIR.from_asset(asset)
        self.assertEqual(ir.values["components"], [])
        # to_dict still round-trips cleanly with an empty list.
        self.assertEqual(ir.to_dict()["values"]["components"], [])

    def test_from_asset_does_not_alias_top_level_dicts(self) -> None:
        src = {
            "reuse": {"source": "lib"},
            "assembly": {"resolved_kit": {"name": "k"}},
        }
        ir = ReuseIR.from_asset(src)
        ir.values["extra"] = 1
        ir.resolved_kit["extra"] = 1
        # ``from_asset`` copies at the top level via dict(...); the source
        # must not pick up the IR's mutations.
        self.assertNotIn("extra", src["reuse"])
        self.assertNotIn("extra", src["assembly"]["resolved_kit"])


if __name__ == "__main__":
    unittest.main()
