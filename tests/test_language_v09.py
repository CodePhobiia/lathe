from __future__ import annotations

import unittest
from pathlib import Path

from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.resolver import materialize_asset


ROOT = Path(__file__).resolve().parents[1]
CHEST_EXAMPLE = ROOT / "examples" / "brassbound_chest.lth"
CRATE_EXAMPLE = ROOT / "examples" / "industrial_crate.lth"
DOOR_EXAMPLE = ROOT / "examples" / "mechanical_door.lth"


class LatheV09LanguageTests(unittest.TestCase):
    def test_imports_expose_patterns_and_surface_programs(self) -> None:
        program = parse_file(CHEST_EXAMPLE)
        self.assertTrue(any(item["name"] == "plank_spacing_hero" for item in program["patterns"]))
        self.assertTrue(any(item["name"] == "chest_wood_brass_hero" for item in program["surface_programs"]))

    def test_materialize_asset_resolves_from_surface_program_and_patterns(self) -> None:
        program = parse_file(CRATE_EXAMPLE)
        asset = materialize_asset(program, "industrial_crate")
        self.assertEqual(asset["from"], "industrial_crate_family")
        self.assertEqual(asset["assembly"]["family"], "industrial_crate_family")
        self.assertEqual(asset["surface"]["program"], "industrial_crate_hero")
        self.assertTrue(asset["surface"]["resolved_surface_program"])
        self.assertIn("cargo_fastener_grid", asset["surface"]["patterns"])
        self.assertTrue(asset["surface"]["resolved_patterns"])
        self.assertEqual(asset["repair_policy"]["use"], "hero_hardsurface_repair")

    def test_normalized_program_contains_v09_namespaces(self) -> None:
        program = parse_file(DOOR_EXAMPLE)
        normalized = normalize_program(program)
        self.assertIn("patterns", normalized)
        self.assertIn("surface_programs", normalized)
        asset = next(item for item in normalized["assets"] if item["name"] == "mechanical_door")
        self.assertEqual(asset["from"], "mechanical_door_family")
        self.assertEqual(asset["surface"]["program"], "mechanical_door_hero")


if __name__ == "__main__":
    unittest.main()
