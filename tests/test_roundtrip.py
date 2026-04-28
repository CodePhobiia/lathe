from __future__ import annotations

import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from lathe.checker import check_program
from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.schema import get_schema

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


class LatheRoundtripTest(unittest.TestCase):
    def test_parse_normalize_validate(self) -> None:
        program = parse_file(EXAMPLE)
        normalized = normalize_program(program)
        Draft202012Validator(get_schema()).validate(normalized)
        diags = check_program(program)
        self.assertEqual(diags, [])


if __name__ == "__main__":
    unittest.main()
