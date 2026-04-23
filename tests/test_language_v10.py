from __future__ import annotations

import unittest
from pathlib import Path

from lathe.normalizer import normalize_program
from lathe.parser import parse_file


ROOT = Path(__file__).resolve().parents[1]


class LatheV10StdlibTests(unittest.TestCase):
    def test_stdlib_now_exposes_v10_family_floor(self) -> None:
        family_files = sorted((ROOT / "std" / "families").glob("*.lth"))
        self.assertGreaterEqual(len(family_files), 8)

    def test_new_v10_examples_parse_with_from_and_surface_programs(self) -> None:
        for example_name, family_name, surface_program in (
            ("service_cabinet.lth", "service_cabinet_family", "service_cabinet_hero"),
            ("control_pedestal.lth", "control_pedestal_family", "control_pedestal_hero"),
            ("supply_container.lth", "supply_container_family", "supply_container_hero"),
        ):
            program = parse_file(ROOT / "examples" / example_name)
            normalized = normalize_program(program)
            asset = next(item for item in normalized["assets"] if item["from"] == family_name)
            self.assertEqual(asset["surface"]["program"], surface_program)
            self.assertTrue(asset["repair_policy"]["use"])


if __name__ == "__main__":
    unittest.main()
