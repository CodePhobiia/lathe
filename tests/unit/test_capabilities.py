"""Unit tests for ``lathe.capabilities``.

Covers the environment-probe helpers (``probe_blender``, ``probe_xatlas``,
``probe_torch``, ``probe_hunyuan_endpoint``) under both available and absent
configurations via monkeypatching, plus the backend-report shape for
unknown/graceful inputs.
"""

from __future__ import annotations

import unittest
from unittest import mock

from lathe import capabilities
from lathe.net import NetGuardError


class ProbeBlenderTests(unittest.TestCase):
    def test_probe_blender_available_when_candidate_exists(self) -> None:
        fake_candidates = [mock.MagicMock()]
        fake_candidates[0].exists.return_value = True
        fake_candidates[0].__str__ = lambda self: "/fake/blender"
        with mock.patch.object(capabilities, "_candidate_blender_paths", return_value=fake_candidates), \
             mock.patch.object(
                 capabilities,
                 "_run_command",
                 return_value={"ok": True, "returncode": 0, "stdout": "Blender 4.5.0\n", "stderr": ""},
             ):
            report = capabilities.probe_blender()
        self.assertTrue(report["available"])
        self.assertEqual(report["code"], "ok")
        self.assertEqual(report["version"], "4.5.0")

    def test_probe_blender_absent(self) -> None:
        with mock.patch.object(capabilities, "_candidate_blender_paths", return_value=[]):
            report = capabilities.probe_blender()
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "not_found")
        self.assertIsNone(report["path"])


class ProbeXatlasTests(unittest.TestCase):
    def test_probe_xatlas_available(self) -> None:
        with mock.patch.object(
            capabilities,
            "package_report",
            return_value={"import_name": "xatlas", "distribution_name": "xatlas", "available": True, "version": "0.0.9"},
        ):
            report = capabilities.probe_xatlas()
        self.assertTrue(report["available"])
        self.assertEqual(report["code"], "ok")
        self.assertEqual(report["version"], "0.0.9")

    def test_probe_xatlas_absent(self) -> None:
        with mock.patch.object(
            capabilities,
            "package_report",
            return_value={"import_name": "xatlas", "distribution_name": "xatlas", "available": False, "version": None},
        ):
            report = capabilities.probe_xatlas()
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "not_installed")
        self.assertIn("build_tools", report)


class ProbeTorchTests(unittest.TestCase):
    def test_probe_torch_absent(self) -> None:
        with mock.patch.object(capabilities, "_module_available", return_value=False):
            report = capabilities.probe_torch()
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "not_installed")
        self.assertFalse(report["cuda_available"])
        self.assertEqual(report["devices"], [])

    def test_probe_torch_available_reports_shape(self) -> None:
        fake_torch = mock.MagicMock()
        fake_torch.__version__ = "2.1.0"
        fake_torch.cuda.is_available.return_value = False
        fake_torch.version.cuda = None
        with mock.patch.object(capabilities, "_module_available", return_value=True), \
             mock.patch.dict("sys.modules", {"torch": fake_torch}):
            report = capabilities.probe_torch()
        self.assertTrue(report["available"])
        self.assertEqual(report["code"], "ok")
        self.assertFalse(report["cuda_available"])
        self.assertEqual(report["devices"], [])


class ProbeHunyuanEndpointTests(unittest.TestCase):
    def test_non_loopback_http_is_rejected(self) -> None:
        rc = {"shape": {"providers": {"hunyuan2_1_http": {"base_url": "http://example.com"}}}}
        with mock.patch.object(
            capabilities,
            "safe_urlopen",
            side_effect=NetGuardError("scheme_insecure", "http only allowed for loopback"),
        ):
            report = capabilities.probe_hunyuan_endpoint(rc)
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "scheme_insecure")

    def test_link_local_address_rejected(self) -> None:
        rc = {"shape": {"providers": {"hunyuan2_1_http": {"base_url": "http://169.254.169.254"}}}}
        with mock.patch.object(
            capabilities,
            "safe_urlopen",
            side_effect=NetGuardError("private_ip_rejected", "link-local address rejected"),
        ):
            report = capabilities.probe_hunyuan_endpoint(rc)
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "private_ip_rejected")

    def test_configured_flag_false_when_base_url_missing(self) -> None:
        rc = {"shape": {"providers": {"hunyuan2_1_http": {"base_url": ""}}}}
        report = capabilities.probe_hunyuan_endpoint(rc)
        self.assertFalse(report["configured"])
        self.assertFalse(report["available"])
        self.assertEqual(report["code"], "missing_base_url")


class DeterministicBackendReportsTests(unittest.TestCase):
    def test_unknown_backend_config_gracefully_falls_back(self) -> None:
        with mock.patch.object(
            capabilities,
            "probe_blender",
            return_value={"available": False, "code": "not_found", "python_module_available": False,
                          "supported_modes": [], "asset_libraries": [], "addons": []},
        ), mock.patch.object(
            capabilities,
            "probe_xatlas",
            return_value={"available": False, "code": "not_installed", "version": None,
                          "build_tools": {}},
        ):
            reports = capabilities.deterministic_backend_reports({"topology": {"adapter": "weird_unknown"}})
        self.assertEqual(len(reports), 3)
        ids = [r["backend_id"] for r in reports]
        self.assertIn("lathe.topology.blender_hard_surface_v1", ids)
        self.assertIn("lathe.uv.xatlas_v1", ids)
        self.assertIn("lathe.package.openusd_gltf_v1", ids)

    def test_capability_report_shape_has_required_keys(self) -> None:
        with mock.patch.object(
            capabilities,
            "probe_blender",
            return_value={"available": True, "code": "ok", "path": "/fake",
                          "python_module_available": False, "supported_modes": ["background_cli"],
                          "asset_libraries": [], "addons": []},
        ), mock.patch.object(
            capabilities,
            "probe_xatlas",
            return_value={"available": True, "code": "ok", "version": "0.0.9"},
        ):
            reports = capabilities.deterministic_backend_reports({})
        for report in reports:
            for key in (
                "backend_id",
                "requested_adapter",
                "selected_adapter",
                "strict",
                "available",
                "real_adapter_available",
                "fallback_available",
                "probe",
            ):
                self.assertIn(key, report)


if __name__ == "__main__":
    unittest.main()
