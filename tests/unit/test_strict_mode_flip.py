"""BL-37 Wave 4.IV.a — strict-mode opt-in + V0.1.x deprecation warning.

Covers the Plan 08 Phase 8 amended rollout:

* ``shape.strict=True`` with a learned provider whose probe fails raises
  ``ShapeProviderExecutionError`` with code ``provider_fallback_blocked``.
* ``shape.strict=True`` with a learned provider whose execution fails raises
  the same typed error, preserving the underlying code under ``details``.
* ``shape.strict=False`` with a learned provider emits a
  ``DeprecationWarning`` (V0.1.x rollout) when ``allow_fallback`` is unset.
* ``shape.allow_fallback=True`` (CLI: ``--allow-fallback``) silences the
  warning and keeps legacy fallback behavior.
* The ``build`` CLI exits non-zero when the provider raises
  ``provider_fallback_blocked``.
* The ``--strict-shape-provider`` CLI flag still works but emits a
  ``DeprecationWarning`` (back-compat alias).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import unittest
import warnings
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from lathe.providers.errors import ShapeProviderExecutionError
from lathe.providers.selection import maybe_run_shape_provider
from lathe.runtime_config import DEFAULT_RUNTIME_CONFIG, apply_cli_overrides


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


def _load_courier_asset() -> dict:
    from lathe.parser import parse_file

    program = parse_file(EXAMPLE)
    return next(item for item in program["assets"] if item["name"] == "courier_drone")


class StrictModeMechanismTests(unittest.TestCase):
    """The strict-mode wiring: deprecation warning + provider_fallback_blocked."""

    def setUp(self) -> None:
        self.asset = _load_courier_asset()
        self.conditioning = {"image_refs": [{"kind": "front", "path": "front.png"}]}

    def _run(self, runtime_config: dict, *, work_dir: Path):
        return maybe_run_shape_provider(
            self.asset,
            source_root=EXAMPLE.parent,
            seed=0,
            candidates_count=1,
            conditioning=self.conditioning,
            work_dir=work_dir,
            runtime_config=runtime_config,
        )

    def test_default_runtime_config_does_not_set_strict_true(self) -> None:
        # Wave 4.IV.a hard rule: factory default must NOT flip to True yet.
        self.assertFalse(DEFAULT_RUNTIME_CONFIG["shape"]["strict"])
        self.assertFalse(DEFAULT_RUNTIME_CONFIG["shape"]["allow_fallback"])

    def test_strict_true_learned_provider_probe_fail_raises_provider_fallback_blocked(self) -> None:
        runtime_config = {
            "shape": {
                "provider": "hunyuan2_1_http",
                "strict": True,
                "providers": {
                    "hunyuan2_1_http": {
                        # Point at a blackhole port that will not accept connections
                        # so the probe returns available=False.
                        "base_url": "http://127.0.0.1:1",
                        "health_timeout_s": 1,
                    }
                },
            }
        }
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            with self.assertRaises(ShapeProviderExecutionError) as ctx:
                self._run(runtime_config, work_dir=work)
        self.assertEqual(ctx.exception.code, "provider_fallback_blocked")
        self.assertEqual(ctx.exception.provider_id, "lathe.provider.shape.hunyuan2_1_http_v1")
        self.assertEqual(ctx.exception.details.get("reason"), "probe_unavailable")

    def test_strict_true_learned_provider_exec_error_raises_provider_fallback_blocked(self) -> None:
        # Patch the probe to return available so we reach the execution branch,
        # then patch the hunyuan adapter to raise an execution error.
        runtime_config = {
            "shape": {
                "provider": "hunyuan2_1_http",
                "strict": True,
                "providers": {"hunyuan2_1_http": {"base_url": "http://example.invalid"}},
            }
        }
        from lathe.providers.errors import ShapeProviderExecutionError as Exec

        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            with (
                mock.patch(
                    "lathe.providers.selection.probe_shape_provider",
                    return_value={
                        "available": True,
                        "provider_id": "lathe.provider.shape.hunyuan2_1_http_v1",
                        "details": {},
                    },
                ),
                mock.patch(
                    "lathe.providers.selection._run_hunyuan_http_provider",
                    side_effect=Exec(
                        "lathe.provider.shape.hunyuan2_1_http_v1",
                        "boom",
                        code="request_failed",
                    ),
                ),
                self.assertRaises(ShapeProviderExecutionError) as ctx,
            ):
                self._run(runtime_config, work_dir=work)
        self.assertEqual(ctx.exception.code, "provider_fallback_blocked")
        self.assertEqual(ctx.exception.details.get("reason"), "execution_error")
        self.assertEqual(ctx.exception.details.get("underlying_code"), "request_failed")

    def test_strict_false_learned_provider_emits_deprecation_warning(self) -> None:
        runtime_config = {
            "shape": {
                "provider": "hunyuan2_1_http",
                "strict": False,
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "http://127.0.0.1:1",
                        "health_timeout_s": 1,
                    }
                },
            }
        }
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self._run(runtime_config, work_dir=work)
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertTrue(
            dep,
            msg=f"expected DeprecationWarning, saw: {[str(w.message) for w in caught]}",
        )
        msg = str(dep[0].message)
        self.assertIn("V0.1.x deprecation", msg)
        self.assertIn("allow_fallback", msg)

    def test_allow_fallback_true_silences_deprecation_warning(self) -> None:
        runtime_config = {
            "shape": {
                "provider": "hunyuan2_1_http",
                "strict": False,
                "allow_fallback": True,
                "providers": {
                    "hunyuan2_1_http": {
                        "base_url": "http://127.0.0.1:1",
                        "health_timeout_s": 1,
                    }
                },
            }
        }
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self._run(runtime_config, work_dir=work)
        dep = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning) and "V0.1.x deprecation" in str(w.message)
        ]
        self.assertFalse(dep, msg=f"expected no V0.1.x DeprecationWarning, got: {[str(w.message) for w in dep]}")

    def test_native_path_does_not_emit_deprecation_warning(self) -> None:
        # No configured learned providers => reference_conditioned native path.
        runtime_config = {"shape": {"provider": "auto", "strict": False}}
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self._run(runtime_config, work_dir=work)
        dep = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning) and "V0.1.x deprecation" in str(w.message)
        ]
        self.assertFalse(dep, msg="native path must not emit the V0.1.x strict deprecation warning")


class CLIAllowFallbackTests(unittest.TestCase):
    """--allow-fallback flag + --strict-shape-provider deprecation alias."""

    def test_apply_cli_overrides_sets_allow_fallback_true(self) -> None:
        merged = apply_cli_overrides({}, allow_fallback=True)
        self.assertTrue(merged["shape"]["allow_fallback"])

    def test_apply_cli_overrides_allow_fallback_none_preserves_config(self) -> None:
        base = {"shape": {"provider": "auto", "allow_fallback": True}}
        merged = apply_cli_overrides(base, allow_fallback=None)
        self.assertTrue(merged["shape"]["allow_fallback"])

    def test_resolve_strict_flag_deprecated_alias_emits_warning(self) -> None:
        from lathe.cli.build_cmd import _resolve_strict_flag

        args = argparse.Namespace(strict_shape_provider=True)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _resolve_strict_flag(args)
        self.assertTrue(result)
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertTrue(dep, msg="--strict-shape-provider must emit DeprecationWarning")

    def test_resolve_strict_flag_absent_returns_none(self) -> None:
        from lathe.cli.build_cmd import _resolve_strict_flag

        args = argparse.Namespace(strict_shape_provider=False)
        self.assertIsNone(_resolve_strict_flag(args))


class CLIExitCodeContractTests(unittest.TestCase):
    """Strict + fallback path exits non-zero on the CLI."""

    def test_build_cli_exits_non_zero_on_provider_fallback_blocked(self) -> None:
        from lathe.cli.build_cmd import run_build

        with TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                file=str(EXAMPLE),
                name="courier_drone",
                out=tmp,
                runtime_config=None,
                shape_provider="hunyuan2_1_http",
                strict_shape_provider=True,
                allow_fallback=False,
                codex_imagegen=None,
                execution_profile=None,
            )
            buf = io.StringIO()
            with (
                mock.patch.dict(
                    sys.modules,
                    {},  # allow real imports
                ),
                mock.patch.dict(os.environ, {"LATHE_ALLOW_EXTERNAL_OUT": "1"}),
                warnings.catch_warnings(),
                redirect_stdout(buf),
            ):
                warnings.simplefilter("ignore", DeprecationWarning)
                # Patch probe to unavailable so the strict path triggers.
                with mock.patch(
                    "lathe.providers.selection.probe_shape_provider",
                    return_value={
                        "available": False,
                        "provider_id": "lathe.provider.shape.hunyuan2_1_http_v1",
                        "code": "probe_failed",
                        "message": "synthetic probe failure",
                        "details": {},
                    },
                ):
                    with self.assertRaises(SystemExit) as ctx:
                        run_build(args)
            self.assertEqual(ctx.exception.code, 1)
            output = buf.getvalue()
            self.assertIn("provider_fallback_blocked", output)
            # Output should parse as JSON with a diagnostics entry containing the code.
            payload = json.loads(output)
            self.assertFalse(payload["ok"])
            codes = [d.get("code") for d in payload.get("diagnostics", [])]
            self.assertIn("provider_fallback_blocked", codes)


if __name__ == "__main__":
    unittest.main()
