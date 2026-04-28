"""Unit tests for ``lathe.schema`` + ``schema/lathe.schema.json``.

Complements ``tests/test_roundtrip.py`` (which tests parse->normalize->
validate end-to-end) by exercising the schema *as a schema*: load,
required fields, type checks, ``additionalProperties: false`` policy
on the program root, JSON-pointer location of errors, and a sanity
round-trip of every hero ``.lth`` source through the validator.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import jsonschema
from lathe.normalizer import normalize_program
from lathe.parser import parse_file
from lathe.schema import SCHEMA_PATH, get_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
HERO_NAMES = [
    "brassbound_chest",
    "courier_drone",
    "industrial_crate",
    "mechanical_door",
    "console_terminal",
    "sci_fi_wall_panel",
    "service_cabinet",
    "control_pedestal",
    "supply_container",
]


def _minimal_program() -> dict:
    program = {
        key: []
        for key in [
            "imports",
            "profiles",
            "contracts",
            "critics",
            "libraries",
            "kits",
            "patterns",
            "families",
            "components",
            "assemblies",
            "traits",
            "mechanisms",
            "materials",
            "surface_programs",
            "surface_backends",
            "surface_policies",
            "decal_libraries",
            "mask_programs",
            "trim_sheets",
            "palettes",
            "reference_sets",
            "reconstruct_policies",
            "adapt_policies",
            "assembly_policies",
            "fit_profiles",
            "transfer_rules",
            "execution_profiles",
            "render_fixtures",
            "bake_profiles",
            "library_bindings",
            "material_graphs",
            "inspection_policies",
            "repair_policies",
            "fixtures",
            "tests",
            "benchmarks",
            "spaces",
            "assets",
            "variants",
        ]
    }
    program["module"] = None
    return program


class SchemaLoadTests(unittest.TestCase):
    def test_get_schema_returns_dict_with_root_object(self) -> None:
        schema = get_schema()
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema.get("type"), "object")
        self.assertIn("required", schema)
        self.assertIn("properties", schema)

    def test_schema_path_exists_and_is_under_repo(self) -> None:
        self.assertTrue(SCHEMA_PATH.exists(), f"schema not found at {SCHEMA_PATH}")
        self.assertEqual(SCHEMA_PATH.name, "lathe.schema.json")


class SchemaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = get_schema()
        self.validator = jsonschema.Draft202012Validator(self.schema)

    def test_minimal_program_validates(self) -> None:
        errors = list(self.validator.iter_errors(_minimal_program()))
        self.assertEqual(errors, [], msg=f"unexpected errors: {[e.message for e in errors]}")

    def test_missing_required_field_rejected(self) -> None:
        program = _minimal_program()
        program.pop("assets")
        errors = list(self.validator.iter_errors(program))
        self.assertTrue(any("assets" in err.message for err in errors))

    def test_wrong_type_rejected(self) -> None:
        program = _minimal_program()
        program["imports"] = "not-a-list"
        errors = list(self.validator.iter_errors(program))
        self.assertTrue(errors)
        self.assertTrue(any("array" in err.message or "list" in err.message for err in errors))

    def test_unknown_top_level_declaration_rejected(self) -> None:
        program = _minimal_program()
        program["bogus_decl"] = []
        errors = list(self.validator.iter_errors(program))
        # schema declares additionalProperties: false at the root
        self.assertTrue(
            any("bogus_decl" in err.message or "additional" in err.message.lower() for err in errors)
        )

    def test_error_pointer_locates_path(self) -> None:
        program = _minimal_program()
        program["imports"] = [42]  # items must be string
        errors = list(self.validator.iter_errors(program))
        self.assertTrue(errors)
        first = errors[0]
        self.assertIn("imports", list(first.absolute_path))

    def test_all_hero_examples_round_trip_through_schema(self) -> None:
        examples_dir = REPO_ROOT / "examples"
        for hero in HERO_NAMES:
            with self.subTest(hero=hero):
                src = examples_dir / f"{hero}.lth"
                self.assertTrue(src.exists(), f"missing hero example {src}")
                ast = parse_file(str(src))
                normalized = normalize_program(ast)
                errors = list(self.validator.iter_errors(normalized))
                self.assertEqual(errors, [], msg=f"{hero}: {[e.message for e in errors[:3]]}")


if __name__ == "__main__":
    unittest.main()
