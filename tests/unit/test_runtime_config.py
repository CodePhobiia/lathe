"""Unit tests for ``lathe.runtime_config`` (BL-22e Tranche C tail).

Integration tests already exercise ``--runtime-config`` end-to-end through the
CLI. This file covers the loader, merger, and env-overlay APIs at unit level:

* ``load_runtime_config`` — JSON parse, schema validation, size cap, unknown-key
  warning.
* ``merge_runtime_config`` — base / override layering on top of defaults.
* ``apply_env_overrides`` — ``LATHE_*`` env-var overlay.
"""

from __future__ import annotations

import json
import os
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from lathe.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RuntimeConfigError,
    apply_env_overrides,
    load_runtime_config,
    merge_runtime_config,
)


class _TempConfigMixin:
    def _write_config(self, name: str, contents: str) -> Path:
        path = Path(self._tempdir.name) / name
        path.write_text(contents, encoding="utf-8")
        return path

    def setUp(self) -> None:  # type: ignore[override]
        self._tempdir = TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)


class LoadRuntimeConfigTests(_TempConfigMixin, unittest.TestCase):
    def test_load_valid_runtime_config_validates_against_schema(self) -> None:
        path = self._write_config(
            "valid.json",
            json.dumps(
                {
                    "shape": {"provider": "auto", "strict": True},
                    "uv": {"adapter": "auto", "xatlas": {"resolution": 1024}},
                }
            ),
        )
        config = load_runtime_config(path)
        self.assertEqual(config["shape"]["provider"], "auto")
        self.assertTrue(config["shape"]["strict"])
        self.assertEqual(config["uv"]["xatlas"]["resolution"], 1024)
        # Unspecified blocks remain at defaults (deep merge over DEFAULT_RUNTIME_CONFIG).
        self.assertEqual(
            config["topology"]["blender"]["timeout_s"],
            DEFAULT_RUNTIME_CONFIG["topology"]["blender"]["timeout_s"],
        )

    def test_invalid_json_raises_runtime_config_error(self) -> None:
        path = self._write_config("invalid.json", "{not valid json,,,")
        with self.assertRaises(RuntimeConfigError) as ctx:
            load_runtime_config(path)
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_size_cap_over_256_kib_raises(self) -> None:
        # 256 KiB + 1 byte: write a JSON object with a single key whose value
        # is a long string padding the file past the cap.
        cap = 256 * 1024
        padding = "x" * (cap + 1024)
        payload = json.dumps({"shape": {"provider": padding}})
        # Confirm the payload actually exceeds the cap before asserting the error.
        self.assertGreater(len(payload.encode("utf-8")), cap)
        path = self._write_config("oversized.json", payload)
        with self.assertRaises(RuntimeConfigError) as ctx:
            load_runtime_config(path)
        self.assertIn("256 KiB", str(ctx.exception))

    def test_unknown_keys_emit_warning(self) -> None:
        path = self._write_config(
            "unknown.json",
            json.dumps({"shape": {"provider": "auto", "totally_made_up_key": 42}}),
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            config = load_runtime_config(path)
        unknown_warnings = [
            w for w in caught if "unknown keys" in str(w.message)
        ]
        self.assertTrue(unknown_warnings, msg=f"expected an unknown-keys warning, got: {[str(w.message) for w in caught]}")
        # Despite the warning, load still succeeds and the unknown key is preserved.
        self.assertEqual(config["shape"]["totally_made_up_key"], 42)

    def test_root_must_be_object(self) -> None:
        path = self._write_config("array.json", json.dumps(["not", "an", "object"]))
        with self.assertRaises(RuntimeConfigError) as ctx:
            load_runtime_config(path)
        self.assertIn("must be a JSON object", str(ctx.exception))

    def test_missing_file_raises(self) -> None:
        path = Path(self._tempdir.name) / "does_not_exist.json"
        with self.assertRaises(RuntimeConfigError) as ctx:
            load_runtime_config(path)
        self.assertIn("not found", str(ctx.exception))

    def test_load_with_no_path_returns_defaults_with_env_overlay(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in [k for k in os.environ if k.startswith("LATHE_")]:
                os.environ.pop(var, None)
            config = load_runtime_config(None)
        self.assertEqual(
            config["shape"]["provider"],
            DEFAULT_RUNTIME_CONFIG["shape"]["provider"],
        )


class MergeRuntimeConfigTests(unittest.TestCase):
    def test_merge_layers_overrides_correctly(self) -> None:
        base = {"shape": {"provider": "hunyuan2_1_http", "strict": True}}
        override = {"shape": {"strict": False}, "uv": {"xatlas": {"resolution": 4096}}}
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in [k for k in os.environ if k.startswith("LATHE_")]:
                os.environ.pop(var, None)
            merged = merge_runtime_config(base, override)
        # Override wins over base for shape.strict.
        self.assertFalse(merged["shape"]["strict"])
        # Base value preserved when not overridden.
        self.assertEqual(merged["shape"]["provider"], "hunyuan2_1_http")
        # New override block added.
        self.assertEqual(merged["uv"]["xatlas"]["resolution"], 4096)
        # Default block untouched.
        self.assertIn("blender", merged["topology"])

    def test_merge_with_none_base_and_none_override_returns_defaults(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in [k for k in os.environ if k.startswith("LATHE_")]:
                os.environ.pop(var, None)
            merged = merge_runtime_config(None, None)
        self.assertEqual(merged["shape"]["provider"], DEFAULT_RUNTIME_CONFIG["shape"]["provider"])
        # Returned dict is independent of DEFAULT_RUNTIME_CONFIG.
        merged["shape"]["provider"] = "MUTATED"
        self.assertNotEqual(DEFAULT_RUNTIME_CONFIG["shape"]["provider"], "MUTATED")


class ApplyEnvOverridesTests(unittest.TestCase):
    def _isolated_env(self, overrides: dict[str, str]):
        # Strip any pre-existing LATHE_* vars so the test sees only `overrides`.
        clean: dict[str, str] = {}
        for var in os.environ:
            if not var.startswith("LATHE_"):
                clean[var] = os.environ[var]
        clean.update(overrides)
        return mock.patch.dict(os.environ, clean, clear=True)

    def test_lathe_shape_provider_env_overrides_provider(self) -> None:
        base = {"shape": {"provider": "auto", "strict": False}}
        with self._isolated_env({"LATHE_SHAPE_PROVIDER": "hunyuan2_1_http"}):
            result = apply_env_overrides(base)
        self.assertEqual(result["shape"]["provider"], "hunyuan2_1_http")

    def test_lathe_shape_strict_env_truthy_values_set_strict_true(self) -> None:
        for truthy in ("1", "true", "True", "YES", "on"):
            base = {"shape": {"provider": "auto", "strict": False}}
            with self._isolated_env({"LATHE_SHAPE_STRICT": truthy}):
                result = apply_env_overrides(base)
            self.assertTrue(
                result["shape"]["strict"],
                msg=f"LATHE_SHAPE_STRICT={truthy!r} should be truthy",
            )

    def test_lathe_hunyuan_base_url_env_seeds_provider_config(self) -> None:
        base = {"shape": {"provider": "auto", "providers": {}}}
        with self._isolated_env({"LATHE_HUNYUAN_BASE_URL": "http://example.invalid:9000"}):
            result = apply_env_overrides(base)
        self.assertEqual(
            result["shape"]["providers"]["hunyuan2_1_http"]["base_url"],
            "http://example.invalid:9000",
        )

    def test_lathe_xatlas_resolution_env_must_parse_as_int(self) -> None:
        base = {"uv": {"xatlas": {"resolution": 2048}}}
        with self._isolated_env({"LATHE_XATLAS_RESOLUTION": "8192"}):
            result = apply_env_overrides(base)
        self.assertEqual(result["uv"]["xatlas"]["resolution"], 8192)
        # Bad value silently ignored — original survives.
        with self._isolated_env({"LATHE_XATLAS_RESOLUTION": "not_an_int"}):
            result = apply_env_overrides(base)
        self.assertEqual(result["uv"]["xatlas"]["resolution"], 2048)

    def test_apply_env_overrides_does_not_mutate_input(self) -> None:
        base = {"shape": {"provider": "auto", "strict": False}}
        original_provider = base["shape"]["provider"]
        with self._isolated_env({"LATHE_SHAPE_PROVIDER": "vggt_local"}):
            apply_env_overrides(base)
        self.assertEqual(base["shape"]["provider"], original_provider)

    def test_no_env_overrides_returns_equivalent_config(self) -> None:
        base = {"shape": {"provider": "reference_conditioned", "strict": True}}
        with self._isolated_env({}):
            result = apply_env_overrides(base)
        self.assertEqual(result["shape"]["provider"], "reference_conditioned")
        self.assertTrue(result["shape"]["strict"])


if __name__ == "__main__":
    unittest.main()
