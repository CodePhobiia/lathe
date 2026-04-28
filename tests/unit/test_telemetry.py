"""Unit tests for :mod:`lathe.telemetry`.

Plan 09 Phase 10b. Covers:
- Default-disabled invariant.
- enable / disable / clear config lifecycle.
- emit_build_ping is a no-op when disabled.
- emit_build_ping constructs an allow-listed payload when enabled.
- emit_build_ping swallows network failures.
- Payload never includes asset content, paths, or env.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from lathe import telemetry

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "telemetry"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


class _TelemetryTestBase(unittest.TestCase):
    """Redirect telemetry config to a tmp dir for every test."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = mock.patch.object(
            telemetry, "_user_config_dir", return_value=__import__("pathlib").Path(self._tmp.name) / "lathe"
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)


class DefaultStateTests(_TelemetryTestBase):
    def test_default_state_is_unset_treated_as_disabled(self) -> None:
        st = telemetry.status()
        self.assertEqual(st["state"], "unset")
        self.assertFalse(st["enabled"])
        self.assertIsNone(st["salt_prefix"])
        self.assertFalse(telemetry.is_enabled())


class ConfigLifecycleTests(_TelemetryTestBase):
    def test_enable_writes_config_and_returns_salt(self) -> None:
        cfg = telemetry.enable()
        self.assertTrue(cfg["enabled"])
        self.assertIn("user_salt", cfg)
        self.assertEqual(len(cfg["user_salt"]), 32)  # 16 bytes hex
        self.assertTrue(telemetry.is_enabled())

    def test_disable_preserves_salt(self) -> None:
        enabled = telemetry.enable()
        disabled = telemetry.disable()
        self.assertFalse(disabled["enabled"])
        self.assertEqual(enabled["user_salt"], disabled["user_salt"])
        self.assertFalse(telemetry.is_enabled())

    def test_clear_deletes_config(self) -> None:
        telemetry.enable()
        self.assertTrue(telemetry._config_path().exists())
        self.assertTrue(telemetry.clear())
        self.assertFalse(telemetry._config_path().exists())
        self.assertEqual(telemetry.status()["state"], "unset")

    def test_clear_when_absent_returns_false(self) -> None:
        self.assertFalse(telemetry.clear())

    def test_status_salt_prefix_is_first_four_chars(self) -> None:
        telemetry.enable(user_salt="abcdef0123456789abcdef0123456789")
        st = telemetry.status()
        self.assertEqual(st["salt_prefix"], "abcd")
        self.assertEqual(st["state"], "enabled")

    def test_write_config_failure_does_not_corrupt_existing_config(self) -> None:
        telemetry.enable(user_salt="abcdef0123456789abcdef0123456789")
        path = telemetry._config_path()
        before = path.read_text(encoding="utf-8")

        with mock.patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                telemetry.disable()

        self.assertEqual(path.read_text(encoding="utf-8"), before)


class EmitBuildPingDisabledTests(_TelemetryTestBase):
    def test_emit_returns_false_when_unset(self) -> None:
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            ok = telemetry.emit_build_ping({"build_id": "x", "stack_id": "s", "wall_ms": 1})
        self.assertFalse(ok)
        mock_net.assert_not_called()

    def test_emit_returns_false_when_disabled(self) -> None:
        telemetry.enable()
        telemetry.disable()
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            ok = telemetry.emit_build_ping({"build_id": "x", "stack_id": "s", "wall_ms": 1})
        self.assertFalse(ok)
        mock_net.assert_not_called()


class EmitBuildPingEnabledTests(_TelemetryTestBase):
    def test_emit_when_enabled_posts_expected_payload(self) -> None:
        telemetry.enable(user_salt="00112233445566778899aabbccddeeff")
        fake_response = mock.MagicMock()
        with mock.patch("lathe.net.safe_urlopen", return_value=fake_response) as mock_net:
            ok = telemetry.emit_build_ping(
                {
                    "build_id": "cache-key-abc",
                    "stack_id": "lathe.stack.hard_surface_game_asset_v1",
                    "ok": True,
                    "wall_ms": 4321,
                }
            )

        self.assertTrue(ok)
        mock_net.assert_called_once()
        _, kwargs = mock_net.call_args
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["timeout_s"], 2.0)
        self.assertEqual(kwargs["allowlist"], ["telemetry.lathe.dev"])
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

        body = json.loads(kwargs["data"].decode("utf-8"))
        self.assertEqual(body["stack_id"], "lathe.stack.hard_surface_game_asset_v1")
        self.assertEqual(body["build_kind"], "")
        self.assertTrue(body["certified"])
        self.assertEqual(body["exit_code"], 0)
        self.assertEqual(body["wall_ms"], 4321)
        self.assertEqual(len(body["build_id_hash"]), 16)
        self.assertIn("lathe_version", body)
        self.assertNotIn("salt", body)

    def test_emit_handles_network_failure_silently(self) -> None:
        telemetry.enable()
        with mock.patch("lathe.net.safe_urlopen", side_effect=RuntimeError("network down")):
            ok = telemetry.emit_build_ping({"build_id": "x", "stack_id": "s", "wall_ms": 1})
        self.assertFalse(ok)  # did not raise

    def test_emit_handles_netguard_failure_silently(self) -> None:
        from lathe.net import NetGuardError

        telemetry.enable()
        with mock.patch(
            "lathe.net.safe_urlopen",
            side_effect=NetGuardError("private_ip_rejected", "blocked"),
        ):
            ok = telemetry.emit_build_ping({"build_id": "x", "stack_id": "s", "wall_ms": 1})
        self.assertFalse(ok)

    def test_emit_never_raises_on_malformed_report(self) -> None:
        telemetry.enable()
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            ok = telemetry.emit_build_ping({})  # empty report
        self.assertIsInstance(ok, bool)
        # Even with empty report, we still attempt to emit (enabled == true).
        mock_net.assert_called_once()


class GoldenPayloadFixtureTests(_TelemetryTestBase):
    def test_all_supported_emit_events_have_golden_payload_fixtures(self) -> None:
        supported_events = {
            name.removeprefix("emit_")
            for name, value in vars(telemetry).items()
            if name.startswith("emit_") and callable(value)
        }
        fixture_events = {_load_fixture(path.name)["event"] for path in _FIXTURES_DIR.glob("*_payload.json")}

        self.assertEqual(fixture_events, supported_events)

    def test_build_ping_emits_checked_in_golden_payload(self) -> None:
        fixture = _load_fixture("build_ping_payload.json")
        self.assertEqual(fixture["event"], "build_ping")

        telemetry.enable(user_salt=fixture["salt"])
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            ok = telemetry.emit_build_ping(fixture["build_report"])

        self.assertTrue(ok)
        mock_net.assert_called_once()
        raw = mock_net.call_args.kwargs["data"].decode("utf-8")
        body = json.loads(raw)
        self.assertEqual(body, fixture["expected_payload"])

        self.assertEqual(set(body), PayloadHygieneTests._ALLOWED)
        for key in fixture["forbidden_payload_keys"]:
            self.assertNotIn(key, body)
        for needle in fixture["forbidden_payload_strings"]:
            self.assertNotIn(needle, raw)


class PayloadHygieneTests(_TelemetryTestBase):
    _FORBIDDEN = {
        "asset_path",
        "asset_content",
        "file",
        "files",
        "out_dir",
        "source_path",
        "env",
        "environment",
        "cwd",
        "home",
        "username",
        "user",
        "hostname",
        "ip",
        "api_key",
        "token",
        "secret",
        "repo_root",
        "runtime_config",
        "diagnostics",
        "logs",
        "stdout",
        "stderr",
    }

    _ALLOWED = {
        "lathe_version",
        "build_id_hash",
        "build_kind",
        "stack_id",
        "certified",
        "exit_code",
        "wall_ms",
    }

    def test_payload_contains_only_allowed_fields(self) -> None:
        telemetry.enable(user_salt="deadbeefcafefeed0123456789abcdef")
        poisoned_report = {
            "build_id": "b1",
            "stack_id": "stack",
            "wall_ms": 10,
            "ok": True,
            "asset_path": "/home/alice/secrets/asset.lth",
            "env": {"API_KEY": "hunter2"},
            "diagnostics": [{"msg": "very secret"}],
            "runtime_config": {"shape": {"strict": True}},
            "stdout": "build log",
        }
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            telemetry.emit_build_ping(poisoned_report)

        body = json.loads(mock_net.call_args.kwargs["data"].decode("utf-8"))
        self.assertEqual(set(body.keys()), self._ALLOWED)
        # Serialized body must literally not contain any forbidden strings
        # from the poisoned report.
        raw = mock_net.call_args.kwargs["data"].decode("utf-8")
        self.assertNotIn("/home/alice", raw)
        self.assertNotIn("API_KEY", raw)
        self.assertNotIn("hunter2", raw)
        self.assertNotIn("very secret", raw)
        self.assertNotIn("build log", raw)
        self.assertNotIn("deadbeefcafefeed0123456789abcdef", raw)

    def test_payload_extracts_current_build_metadata(self) -> None:
        telemetry.enable(user_salt="00112233445566778899aabbccddeeff")
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            telemetry.emit_build_ping(
                {
                    "asset": "secret_local_asset_name",
                    "kind": "hard_surface_prop",
                    "out_dir": "C:/Users/alice/private/build",
                    "certified": False,
                    "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
                    "cache_key": "cache-key-123",
                    "duration_ms": 99,
                }
            )

        raw = mock_net.call_args.kwargs["data"].decode("utf-8")
        body = json.loads(raw)
        self.assertEqual(body["build_kind"], "hard_surface_prop")
        self.assertEqual(body["stack_id"], "lathe.stack.hard_surface_game_asset_v1")
        self.assertFalse(body["certified"])
        self.assertEqual(body["wall_ms"], 99)
        self.assertNotIn("secret_local_asset_name", raw)
        self.assertNotIn("C:/Users/alice", raw)

    def test_payload_derives_identity_from_normal_build_report_without_paths(self) -> None:
        telemetry.enable(user_salt="00112233445566778899aabbccddeeff")
        with mock.patch("lathe.net.safe_urlopen") as mock_net:
            telemetry.emit_build_ping(
                {
                    "asset": "local_asset_name",
                    "kind": "mechanical_assembly",
                    "out_dir": "D:/private/build",
                    "certified": True,
                    "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
                    "outputs": [
                        {
                            "format": "glb",
                            "uri": "stages/package/asset.glb",
                            "sha256": "a" * 64,
                            "size_bytes": 10,
                        }
                    ],
                }
            )

        raw = mock_net.call_args.kwargs["data"].decode("utf-8")
        body = json.loads(raw)
        self.assertEqual(len(body["build_id_hash"]), 16)
        self.assertNotIn("local_asset_name", raw)
        self.assertNotIn("D:/private", raw)
        self.assertNotIn("stages/package/asset.glb", raw)
        self.assertNotIn("a" * 64, raw)

    def test_build_id_hash_is_salted(self) -> None:
        # Same build_id + different salts => different hashes.
        h1 = telemetry._hash_build_id("salt-a", "build-1")
        h2 = telemetry._hash_build_id("salt-b", "build-1")
        self.assertNotEqual(h1, h2)
        self.assertEqual(len(h1), 16)


if __name__ == "__main__":
    unittest.main()
