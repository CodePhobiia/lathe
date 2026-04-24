"""Unit tests for ``lathe.defaults`` (and ``DEFAULT_RUNTIME_CONFIG``).

The module exposes a family of ``*_DEFAULTS`` dicts plus
``BUILD_STAGES``. These are the canonical fill-in values used by the
normalizer and resolver, so they're effectively part of the language
surface. We verify:

* the canonical ``*_DEFAULTS`` constants exist with expected types
* ``deep_copy`` returns an independent copy (mutation resistance)
* ``BUILD_STAGES`` matches the BUILD_STAGE_DEFAULTS keys
* the ``build`` stage defaults wire the ``shape`` slot correctly
* ``DEFAULT_RUNTIME_CONFIG`` validates against
  ``schema/runtime_config.schema.json`` (the doc string of that schema
  literally says "Mirrors DEFAULT_RUNTIME_CONFIG")
* hero-asset-defaults are present and reachable from ``ASSET_DEFAULTS``
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from lathe.defaults import (
    ASSET_DEFAULTS,
    ASSET_PACKAGE_DEFAULTS,
    ASSET_VALIDATE_DEFAULTS,
    BUILD_STAGE_DEFAULTS,
    BUILD_STAGES,
    PROGRAM_DEFAULTS,
    SET_LIKE_PATHS,
    deep_copy,
)
from lathe.runtime_config import DEFAULT_RUNTIME_CONFIG

REPO_ROOT = Path(__file__).resolve().parents[2]


class DefaultsConstantsTests(unittest.TestCase):
    def test_program_defaults_is_a_dict_with_assets_key(self) -> None:
        self.assertIsInstance(PROGRAM_DEFAULTS, dict)
        self.assertIn("assets", PROGRAM_DEFAULTS)
        self.assertEqual(PROGRAM_DEFAULTS["assets"], [])
        self.assertIsNone(PROGRAM_DEFAULTS["module"])

    def test_asset_defaults_includes_hero_subblocks(self) -> None:
        for key in ("refs", "intent", "build", "validate", "package", "publish"):
            self.assertIn(key, ASSET_DEFAULTS, msg=f"ASSET_DEFAULTS missing {key}")

    def test_validate_threshold_is_080(self) -> None:
        self.assertEqual(ASSET_VALIDATE_DEFAULTS["threshold"], 0.80)

    def test_set_like_paths_is_a_set_of_strings(self) -> None:
        self.assertIsInstance(SET_LIKE_PATHS, set)
        self.assertTrue(SET_LIKE_PATHS)
        self.assertTrue(all(isinstance(p, str) for p in SET_LIKE_PATHS))


class DeepCopyAndMutationTests(unittest.TestCase):
    def test_deep_copy_returns_independent_object(self) -> None:
        copied = deep_copy(ASSET_DEFAULTS)
        copied["intent"]["style"].append("mutated")
        self.assertNotIn("mutated", ASSET_DEFAULTS["intent"]["style"])

    def test_program_defaults_lists_are_not_aliased_after_deepcopy(self) -> None:
        copy_a = deep_copy(PROGRAM_DEFAULTS)
        copy_b = deep_copy(PROGRAM_DEFAULTS)
        copy_a["assets"].append({"name": "x"})
        self.assertEqual(copy_b["assets"], [])

    def test_asset_package_defaults_has_expected_shape(self) -> None:
        self.assertEqual(ASSET_PACKAGE_DEFAULTS["backend"], "auto")
        self.assertTrue(ASSET_PACKAGE_DEFAULTS["manifest"])
        self.assertIsInstance(ASSET_PACKAGE_DEFAULTS["formats"], list)


class BuildStagesTests(unittest.TestCase):
    def test_build_stages_matches_build_stage_defaults_keys(self) -> None:
        self.assertEqual(set(BUILD_STAGES), set(BUILD_STAGE_DEFAULTS))

    def test_shape_stage_defaults_have_auto_backend(self) -> None:
        self.assertEqual(BUILD_STAGE_DEFAULTS["shape"]["backend"], "auto")
        self.assertEqual(BUILD_STAGE_DEFAULTS["shape"]["mode"], "generate")
        self.assertGreaterEqual(BUILD_STAGE_DEFAULTS["shape"]["candidates"], 1)


class RuntimeConfigDefaultsTests(unittest.TestCase):
    def test_default_runtime_config_validates_against_schema(self) -> None:
        schema_path = REPO_ROOT / "schema" / "runtime_config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(DEFAULT_RUNTIME_CONFIG))
        self.assertEqual(errors, [], msg=f"runtime defaults invalid: {[e.message for e in errors[:3]]}")

    def test_default_runtime_config_has_expected_top_level_sections(self) -> None:
        for section in ("shape", "topology", "uv", "surface", "execution"):
            self.assertIn(section, DEFAULT_RUNTIME_CONFIG)


if __name__ == "__main__":
    unittest.main()
