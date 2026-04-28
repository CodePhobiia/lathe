"""Unit tests for the publish runner (BL-31, Plan 08 Phase 1).

Covers driver registry lookup, LocalFSDriver round-trip + signature verify,
S3/Supabase/GitLFS drivers via mocks, schema validation of manifests, and
the stage-body no-op path when no target is configured.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import jsonschema
from lathe import publish as publish_mod
from lathe.core.stages import publish as stage_publish
from lathe.publish import (
    PUBLISH_DRIVERS,
    GitLFSDriver,
    GitLFSPublishError,
    LocalFSDriver,
    PublishManifestError,
    S3Driver,
    SupabaseDriver,
    build_manifest,
    get_driver,
    register_driver,
    sign_manifest,
    verify_signature,
)

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:  # pragma: no cover - exercised only without publish extra
    ed25519 = None  # type: ignore[assignment]

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "publish_manifest.schema.json"


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class _BuildDirMixin:
    def setUp(self) -> None:  # type: ignore[override]
        self._tempdir = TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.tempdir = Path(self._tempdir.name)
        self.build_dir = self.tempdir / "build"
        self.build_dir.mkdir()
        self._seed_build_dir(self.build_dir)

    def _seed_build_dir(self, build_dir: Path) -> None:
        package_dir = build_dir / "stages" / "package"
        package_dir.mkdir(parents=True)
        glb = package_dir / "demo.glb"
        glb.write_bytes(b"GLBDEMO")
        manifest = {
            "asset_id": "demo",
            "outputs": [
                {
                    "format": "glb",
                    "uri": "stages/package/demo.glb",
                    "sha256": "",
                    "size_bytes": len(b"GLBDEMO"),
                }
            ],
        }
        (package_dir / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (build_dir / "build_report.json").write_text(
            json.dumps(
                {
                    "asset": "demo",
                    "backend_stack": "lathe.stack.hard_surface_game_asset_v1",
                    "selected_backends": {"shape": {"id": "lathe.shape.intent_mesh_handoff_v1"}},
                }
            ),
            encoding="utf-8",
        )
        validate_dir = build_dir / "stages" / "validate"
        validate_dir.mkdir(parents=True)
        (validate_dir / "report.json").write_text(
            json.dumps({"certified": True, "scores": {"silhouette": 0.9}}),
            encoding="utf-8",
        )


class GetDriverTests(unittest.TestCase):
    def test_registry_exposes_known_drivers(self) -> None:
        for key in ("local_fs", "s3", "supabase", "git_lfs"):
            self.assertIn(key, PUBLISH_DRIVERS)
            self.assertIs(get_driver(key), PUBLISH_DRIVERS[key])

    def test_unknown_driver_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_driver("nonexistent_target")

    def test_register_driver_overrides_entry(self) -> None:
        sentinel = object()
        try:
            register_driver("_test_driver", sentinel)  # type: ignore[arg-type]
            self.assertIs(get_driver("_test_driver"), sentinel)
        finally:
            PUBLISH_DRIVERS.pop("_test_driver", None)


class ManifestTests(_BuildDirMixin, unittest.TestCase):
    def test_build_manifest_matches_schema(self) -> None:
        manifest = build_manifest(self.build_dir, asset="demo")
        jsonschema.Draft202012Validator(_load_schema()).validate(manifest)
        self.assertEqual(manifest["asset"], "demo")
        self.assertEqual(manifest["shape_contract"], "lathe.shape.intent_mesh_handoff_v1")
        self.assertEqual(len(manifest["package_formats"]), 1)
        entry = manifest["package_formats"][0]
        self.assertEqual(entry["format"], "glb")
        # sha256 was empty in the seed and should now be computed.
        self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_build_manifest_rejects_traversal_package_uri(self) -> None:
        outside = self.tempdir / "outside.glb"
        outside.write_bytes(b"outside")
        package_manifest = self.build_dir / "stages" / "package" / "package_manifest.json"
        payload = json.loads(package_manifest.read_text(encoding="utf-8"))
        payload["outputs"].append({"format": "glb", "uri": "../outside.glb", "sha256": "", "size_bytes": 0})
        package_manifest.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(PublishManifestError):
            build_manifest(self.build_dir, asset="demo")

    def test_build_manifest_rejects_missing_package_artifact(self) -> None:
        package_manifest = self.build_dir / "stages" / "package" / "package_manifest.json"
        payload = json.loads(package_manifest.read_text(encoding="utf-8"))
        payload["outputs"].append({"format": "glb", "uri": "stages/package/missing.glb"})
        package_manifest.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(PublishManifestError):
            build_manifest(self.build_dir, asset="demo")

    def test_build_manifest_redacts_secret_extra_fields(self) -> None:
        manifest = build_manifest(self.build_dir, asset="demo", extra={"service_key": "sk-test"})

        self.assertEqual(manifest["service_key"], "[redacted]")


@unittest.skipUnless(publish_mod._CRYPTOGRAPHY_OK, "cryptography not installed")
class SignatureRoundTripTests(_BuildDirMixin, unittest.TestCase):
    def test_local_fs_round_trip_signature_verifies(self) -> None:
        self.assertIsNotNone(ed25519)
        private_key = ed25519.Ed25519PrivateKey.generate()
        key_path = self.tempdir / "signing.key"
        key_path.write_bytes(
            private_key.private_bytes_raw()
            if hasattr(private_key, "private_bytes_raw")
            else private_key.private_numbers().private_bytes()
        )

        target_dir = self.tempdir / "published"
        driver = LocalFSDriver()
        result = driver.publish(
            self.build_dir,
            {
                "target_dir": str(target_dir),
                "signing_key": str(key_path),
                "asset": "demo",
                "version": "1.0.0",
            },
        )

        manifest_path = Path(result["manifest_uri"])
        self.assertTrue(manifest_path.exists())
        self.assertTrue(Path(result["signature_uri"]).exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(_load_schema()).validate(manifest)
        self.assertTrue(verify_signature(manifest))

    def test_signature_fails_verify_on_tampered_manifest(self) -> None:
        self.assertIsNotNone(ed25519)
        private_key = ed25519.Ed25519PrivateKey.generate()
        key_path = self.tempdir / "signing.key"
        key_path.write_bytes(private_key.private_bytes_raw())

        manifest = build_manifest(self.build_dir, asset="demo")
        manifest = sign_manifest(manifest, signing_key_path=str(key_path))
        self.assertTrue(verify_signature(manifest))
        manifest["asset"] = "tampered"
        self.assertFalse(verify_signature(manifest))


class SignSkipTests(_BuildDirMixin, unittest.TestCase):
    def test_sign_manifest_skips_when_no_key(self) -> None:
        # Ensure env doesn't smuggle in a key.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LATHE_PUBLISH_SIGNING_KEY", None)
            manifest = build_manifest(self.build_dir, asset="demo")
            manifest = sign_manifest(manifest, signing_key_path=None)
        self.assertEqual(manifest["signature"]["algorithm"], "ed25519")
        self.assertEqual(manifest["signature"]["skipped_reason"], "no_signing_key_configured")

    def test_sign_manifest_skips_when_key_missing(self) -> None:
        manifest = build_manifest(self.build_dir, asset="demo")
        manifest = sign_manifest(manifest, signing_key_path="/nonexistent/key.bin")
        self.assertIn("signature", manifest)
        # skipped_reason will be either signing_key_missing or cryptography_not_installed
        self.assertIn("skipped_reason", manifest["signature"])
        self.assertNotIn("key_path", manifest["signature"])

    def test_missing_signing_key_log_does_not_include_path(self) -> None:
        manifest = build_manifest(self.build_dir, asset="demo")
        missing = str(self.tempdir / "secret-signing.key")
        with self.assertLogs("lathe.publish", level="WARNING") as captured:
            sign_manifest(manifest, signing_key_path=missing)

        self.assertNotIn(missing, "\n".join(captured.output))

    @unittest.skipUnless(os.name == "posix" and publish_mod._CRYPTOGRAPHY_OK, "POSIX permission check")
    def test_sign_manifest_skips_world_readable_key(self) -> None:
        self.assertIsNotNone(ed25519)
        private_key = ed25519.Ed25519PrivateKey.generate()
        key_path = self.tempdir / "signing.key"
        key_path.write_bytes(private_key.private_bytes_raw())
        key_path.chmod(0o644)

        manifest = build_manifest(self.build_dir, asset="demo")
        manifest = sign_manifest(manifest, signing_key_path=key_path)

        self.assertEqual(manifest["signature"]["skipped_reason"], "signing_key_permissions_unsafe")


class LocalFSDriverNoSigningTests(_BuildDirMixin, unittest.TestCase):
    def test_publish_without_signing_key_still_writes_manifest(self) -> None:
        target_dir = self.tempdir / "published"
        driver = LocalFSDriver()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LATHE_PUBLISH_SIGNING_KEY", None)
            result = driver.publish(
                self.build_dir,
                {"target_dir": str(target_dir), "asset": "demo", "version": "0.0.1"},
            )
        self.assertTrue(Path(result["manifest_uri"]).exists())
        self.assertIsNone(result["signature_uri"])
        self.assertEqual(result["driver"], "local_fs")
        self.assertGreaterEqual(len(result["published_files"]), 1)

    def test_publish_rejects_target_asset_traversal(self) -> None:
        target_dir = self.tempdir / "published"
        driver = LocalFSDriver()

        with self.assertRaises(ValueError):
            driver.publish(
                self.build_dir,
                {"target_dir": str(target_dir), "asset": "../escape", "version": "0.0.1"},
            )

    def test_publish_refuses_to_overwrite_existing_artifact(self) -> None:
        target_dir = self.tempdir / "published"
        existing = target_dir / "demo" / "0.0.1" / "demo.glb"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"existing")
        driver = LocalFSDriver()

        with self.assertRaises(FileExistsError):
            driver.publish(
                self.build_dir,
                {"target_dir": str(target_dir), "asset": "demo", "version": "0.0.1"},
            )


class LocalFSDriverRequiredArgsTests(_BuildDirMixin, unittest.TestCase):
    def test_missing_target_dir_raises(self) -> None:
        driver = LocalFSDriver()
        with self.assertRaises(ValueError):
            driver.publish(self.build_dir, {})


class S3DriverTests(_BuildDirMixin, unittest.TestCase):
    def test_s3_driver_calls_boto3_with_expected_args(self) -> None:
        fake_client = mock.MagicMock()
        fake_boto3 = mock.MagicMock()
        fake_boto3.client.return_value = fake_client
        with (
            mock.patch.object(publish_mod, "_boto3", fake_boto3),
            mock.patch.object(publish_mod, "_BOTO3_OK", True),
        ):
            driver = S3Driver()
            result = driver.publish(
                self.build_dir,
                {
                    "bucket": "my-bucket",
                    "prefix": "artifacts",
                    "asset": "demo",
                    "version": "1.0",
                    "url_allowlist": ["s3.amazonaws.com"],
                },
            )
        # Upload one file + one put_object for manifest.
        self.assertTrue(fake_client.upload_file.called)
        upload_args = fake_client.upload_file.call_args
        self.assertEqual(upload_args[0][1], "my-bucket")
        self.assertIn("artifacts/demo/1.0/", upload_args[0][2])
        put_calls = fake_client.put_object.call_args_list
        manifest_put = [c for c in put_calls if c.kwargs.get("Key", "").endswith("manifest.json")]
        self.assertEqual(len(manifest_put), 1)
        self.assertEqual(result["driver"], "s3")
        self.assertTrue(result["manifest_uri"].startswith("s3://my-bucket/artifacts/demo/1.0/"))

    def test_s3_driver_errors_without_boto3(self) -> None:
        with mock.patch.object(publish_mod, "_BOTO3_OK", False):
            driver = S3Driver()
            with self.assertRaises(RuntimeError):
                driver.publish(self.build_dir, {"bucket": "b"})

    def test_s3_driver_requires_bucket(self) -> None:
        with (
            mock.patch.object(publish_mod, "_BOTO3_OK", True),
            mock.patch.object(publish_mod, "_boto3", mock.MagicMock()),
        ):
            driver = S3Driver()
            with self.assertRaises(ValueError):
                driver.publish(self.build_dir, {})

    def test_s3_driver_requires_allowlisted_destination_host(self) -> None:
        with (
            mock.patch.object(publish_mod, "_BOTO3_OK", True),
            mock.patch.object(publish_mod, "_boto3", mock.MagicMock()),
        ):
            driver = S3Driver()
            with self.assertRaises(ValueError):
                driver.publish(self.build_dir, {"bucket": "b", "url_allowlist": ["example.com"]})


class SupabaseDriverTests(_BuildDirMixin, unittest.TestCase):
    def test_supabase_driver_issues_put_requests(self) -> None:
        fake_response = mock.MagicMock(status=200, content_type="application/json")
        with mock.patch.object(publish_mod, "safe_urlopen", return_value=fake_response) as fake_put:
            driver = SupabaseDriver()
            result = driver.publish(
                self.build_dir,
                {
                    "base_url": "https://example.supabase.co",
                    "url_allowlist": ["example.supabase.co"],
                    "bucket": "assets",
                    "service_key": "sk-test",
                    "asset": "demo",
                    "version": "0.1",
                },
            )
        self.assertGreaterEqual(fake_put.call_count, 2)  # at least manifest + one file
        call_args = fake_put.call_args_list[0]
        self.assertEqual(call_args.kwargs["method"], "PUT")
        self.assertEqual(call_args.kwargs["allowlist"], ["example.supabase.co"])
        self.assertIn("Authorization", call_args.kwargs["headers"])
        self.assertTrue(call_args.kwargs["headers"]["Authorization"].startswith("Bearer sk-test"))
        self.assertEqual(result["driver"], "supabase")
        self.assertIn("assets", result["manifest_uri"])

    def test_supabase_driver_requires_base_url_and_bucket(self) -> None:
        driver = SupabaseDriver()
        with self.assertRaises(ValueError):
            driver.publish(self.build_dir, {"service_key": "x"})

    def test_supabase_driver_requires_service_key(self) -> None:
        driver = SupabaseDriver()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LATHE_SUPABASE_KEY", None)
            with self.assertRaises(ValueError):
                driver.publish(
                    self.build_dir,
                    {"base_url": "https://x", "url_allowlist": ["x"], "bucket": "b"},
                )

    def test_supabase_driver_requires_url_allowlist(self) -> None:
        driver = SupabaseDriver()
        with self.assertRaises(ValueError):
            driver.publish(
                self.build_dir,
                {"base_url": "https://x", "bucket": "b", "service_key": "sk-test"},
            )

    def test_supabase_driver_rejects_non_origin_base_url(self) -> None:
        driver = SupabaseDriver()
        for base_url in ("ftp://example.supabase.co", "https://example.supabase.co/project"):
            with self.subTest(base_url=base_url), self.assertRaises(ValueError):
                driver.publish(
                    self.build_dir,
                    {
                        "base_url": base_url,
                        "url_allowlist": ["example.supabase.co"],
                        "bucket": "assets",
                        "service_key": "sk-test",
                    },
                )

    def test_supabase_driver_rejects_path_injection_characters(self) -> None:
        driver = SupabaseDriver()
        unsafe_configs = [
            {"asset": "demo?download=true", "version": "0.1"},
            {"asset": "demo#fragment", "version": "0.1"},
            {"asset": "demo%2Fescape", "version": "0.1"},
            {"asset": "demo\nbad", "version": "0.1"},
            {"asset": "demo", "version": "0.1", "bucket": "assets?bad"},
        ]
        for config in unsafe_configs:
            with self.subTest(config=config):
                payload = {
                    "base_url": "https://example.supabase.co",
                    "url_allowlist": ["example.supabase.co"],
                    "bucket": "assets",
                    "service_key": "sk-test",
                    "asset": config.get("asset", "demo"),
                    "version": config.get("version", "0.1"),
                }
                if "bucket" in config:
                    payload["bucket"] = config["bucket"]
                with self.assertRaises(ValueError):
                    driver.publish(self.build_dir, payload)

    def test_supabase_driver_quotes_each_object_key_segment(self) -> None:
        fake_response = mock.MagicMock(status=200, content_type="application/json")
        with mock.patch.object(publish_mod, "safe_urlopen", return_value=fake_response) as fake_put:
            driver = SupabaseDriver()
            driver.publish(
                self.build_dir,
                {
                    "base_url": "https://example.supabase.co",
                    "url_allowlist": ["example.supabase.co"],
                    "bucket": "asset.bucket",
                    "service_key": "sk-test",
                    "prefix": "release-v1",
                    "asset": "demo_asset",
                    "version": "0.1",
                },
            )

        urls = [call.args[0] for call in fake_put.call_args_list]
        self.assertTrue(
            all("/storage/v1/object/asset.bucket/release-v1/demo_asset/0.1/" in url for url in urls)
        )


class GitLFSDriverTests(_BuildDirMixin, unittest.TestCase):
    def test_git_lfs_driver_shells_out_expected_argv_shape(self) -> None:
        repo_dir = self.tempdir / "repo"
        repo_dir.mkdir()
        sandbox_result = mock.MagicMock(ok=True, returncode=0, stderr_tail="", stdout="abc123\n")
        with (
            mock.patch("lathe.publish.run_sandboxed", return_value=sandbox_result) as fake_run,
            mock.patch("shutil.which", return_value="/usr/bin/git"),
        ):
            driver = GitLFSDriver()
            result = driver.publish(
                self.build_dir,
                {"repo_dir": str(repo_dir), "asset": "demo", "version": "1.0"},
            )
        self.assertEqual(result["driver"], "git_lfs")
        # Expect four git lfs / publish steps plus any incidental git calls
        # (e.g. rev-parse HEAD during manifest construction).
        argvs = [call.args[0] for call in fake_run.call_args_list]
        lfs_steps = [argv for argv in argvs if len(argv) >= 2 and argv[1] in {"lfs", "add", "commit", "push"}]
        self.assertEqual(len(lfs_steps), 4)
        self.assertEqual(lfs_steps[0][:3], ["/usr/bin/git", "lfs", "track"])
        self.assertEqual(lfs_steps[1][:2], ["/usr/bin/git", "add"])
        self.assertEqual(lfs_steps[2][:2], ["/usr/bin/git", "commit"])
        self.assertEqual(lfs_steps[3][:2], ["/usr/bin/git", "push"])
        self.assertEqual(len(result["git_steps"]), 4)

    def test_git_lfs_driver_requires_repo_dir(self) -> None:
        driver = GitLFSDriver()
        with self.assertRaises(ValueError):
            driver.publish(self.build_dir, {})

    def test_git_lfs_driver_fails_closed_when_push_fails(self) -> None:
        repo_dir = self.tempdir / "repo"
        repo_dir.mkdir()
        ok = mock.MagicMock(ok=True, returncode=0, stderr_tail="", stdout="abc123\n")
        push_failed = mock.MagicMock(ok=False, returncode=128, stderr_tail="permission denied", stdout="")
        with (
            mock.patch("lathe.publish.run_sandboxed", side_effect=[ok, ok, ok, ok, push_failed]),
            mock.patch("shutil.which", return_value="/usr/bin/git"),
        ):
            driver = GitLFSDriver()
            with self.assertRaises(GitLFSPublishError) as ctx:
                driver.publish(
                    self.build_dir,
                    {"repo_dir": str(repo_dir), "asset": "demo", "version": "1.0"},
                )

        self.assertEqual(ctx.exception.returncode, 128)
        self.assertIn("permission denied", ctx.exception.stderr_tail)


class StageBodyTests(_BuildDirMixin, unittest.TestCase):
    def _make_fake_executor(self, runtime_config: dict | None):
        stage_dir = self.build_dir / "stages" / "publish"
        stage_dir.mkdir(parents=True, exist_ok=True)
        executor = mock.MagicMock()
        executor.out_dir = self.build_dir
        executor.stage_dirs = {"publish": stage_dir}
        executor.runtime_config = runtime_config or {}
        executor.runtime = {}
        return executor, stage_dir

    def test_stage_body_no_ops_when_target_unset(self) -> None:
        executor, stage_dir = self._make_fake_executor({})
        bundle = stage_publish.run(executor, {})
        self.assertFalse(bundle["published"])
        self.assertEqual(bundle["reason"], "no_publish_target_configured")
        self.assertTrue((stage_dir / "bundle.json").exists())

    def test_stage_body_no_ops_when_no_runtime_config(self) -> None:
        executor, _ = self._make_fake_executor(None)
        bundle = stage_publish.run(executor, {})
        self.assertFalse(bundle["published"])

    def test_stage_body_invokes_driver_when_configured(self) -> None:
        target_dir = self.tempdir / "staged"
        target_dir.mkdir()
        executor, stage_dir = self._make_fake_executor(
            {
                "publish": {
                    "target": "local_fs",
                    "target_dir": str(target_dir),
                    "asset": "demo",
                    "version": "9.9",
                }
            }
        )
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LATHE_PUBLISH_SIGNING_KEY", None)
            bundle = stage_publish.run(executor, {})
        self.assertTrue(bundle["published"])
        self.assertEqual(bundle["driver"], "local_fs")
        self.assertTrue((stage_dir / "manifest.json").exists())

    def test_stage_body_unknown_target_records_error(self) -> None:
        executor, _ = self._make_fake_executor({"publish": {"target": "definitely_not_a_driver"}})
        bundle = stage_publish.run(executor, {})
        self.assertFalse(bundle["published"])
        self.assertIn("error", bundle)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
