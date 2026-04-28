from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from lathe import cli
from lathe.doctor import _remediation_steps, collect_doctor_report, format_doctor_report


class LatheDoctorTests(unittest.TestCase):
    def test_collect_doctor_report_has_expected_sections(self) -> None:
        with patch(
            "lathe.doctor._shape_provider_reports",
            return_value={"importable": True, "reports": [], "error": None},
        ):
            report = collect_doctor_report(
                {"shape": {"providers": {"hunyuan2_1_http": {"base_url": "http://127.0.0.1:9"}}}}
            )
        self.assertIn("environment", report)
        self.assertIn("lathe", report)
        self.assertIn("packages", report)
        self.assertIn("setup_checks", report)
        self.assertIn("deterministic_backends", report)
        self.assertIn("remediation", report)
        self.assertIn("python_version", {item["id"] for item in report["setup_checks"]})
        self.assertIn("base_dependencies", {item["id"] for item in report["setup_checks"]})

    def test_doctor_cli_json_mode_is_machine_readable(self) -> None:
        buffer = io.StringIO()
        with (
            patch("lathe.cli.collect_doctor_report", return_value={"ok": True, "doctor": "test"}),
            patch("sys.argv", ["lathe", "doctor", "--json"]),
            redirect_stdout(buffer),
        ):
            cli.main()
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["doctor"], "test")

    def test_doctor_format_includes_setup_checks(self) -> None:
        report = {
            "environment": {
                "os": {"platform": "test-os"},
                "shell": "powershell",
                "python": {"version": "3.11.0\n", "executable": "python", "venv_active": True},
            },
            "lathe": {"editable_install": {"editable": True}},
            "packages": {
                "lark": {"available": True, "version": "1"},
                "jsonschema": {"available": True, "version": "1"},
                "numpy": {"available": True, "version": "1"},
                "Pillow": {"available": True, "version": "1"},
                "trimesh": {"available": True, "version": "1"},
                "pytest": {"available": True, "version": "1"},
                "xatlas": {"available": False, "version": None},
                "torch": {"available": False, "version": None},
                "torchvision": {"available": False, "version": None},
                "vggt": {"available": False, "version": None},
            },
            "setup_checks": [
                {
                    "id": "base_dependencies",
                    "ok": True,
                    "severity": "error",
                    "message": "Required packages are present.",
                },
                {
                    "id": "virtualenv_active",
                    "ok": False,
                    "severity": "warning",
                    "message": "No virtualenv.",
                },
            ],
            "blender": {"available": False, "path": None},
            "xatlas": {"available": False, "code": "not_installed"},
            "torch": {"available": False, "cuda_available": False},
            "vggt": {"available": False, "selected_device": "cpu"},
            "hunyuan": {"available": False, "base_url": "http://localhost:8081"},
            "shape_providers": {"importable": True, "reports": [], "error": None},
            "deterministic_backends": [],
            "remediation": [],
        }

        text = format_doctor_report(report)

        self.assertIn("Setup checks:", text)
        self.assertIn("- virtualenv_active: warning", text)

    def test_remediation_steps_include_failed_setup_checks_once(self) -> None:
        base_remediation = (
            r"Install the base repo dependencies: "
            r".\.venv\Scripts\python.exe -m pip install -e ."
        )
        report = {
            "environment": {"commands": {"nmake": "nmake"}},
            "lathe": {"editable_install": {"editable": True}},
            "packages": {
                "lark": {"available": True},
                "trimesh": {"available": True},
                "numpy": {"available": True},
                "Pillow": {"available": True},
                "pytest": {"available": True},
            },
            "setup_checks": [
                {
                    "id": "base_dependencies",
                    "ok": False,
                    "remediation": base_remediation,
                },
                {
                    "id": "base_dependencies_duplicate",
                    "ok": False,
                    "remediation": base_remediation,
                },
            ],
            "blender": {"available": True},
            "xatlas": {"available": True},
            "torch": {"available": True},
            "vggt": {"available": True},
            "hunyuan": {"configured": False, "available": False},
            "shape_providers": {"importable": True},
        }

        steps = _remediation_steps(report)

        self.assertEqual(
            steps.count(base_remediation),
            1,
        )


if __name__ == "__main__":
    unittest.main()
