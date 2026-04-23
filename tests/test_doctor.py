from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from lathe import cli
from lathe.doctor import collect_doctor_report


class LatheDoctorTests(unittest.TestCase):
    def test_collect_doctor_report_has_expected_sections(self) -> None:
        with patch(
            "lathe.doctor._shape_provider_reports",
            return_value={"importable": True, "reports": [], "error": None},
        ):
            report = collect_doctor_report({"shape": {"providers": {"hunyuan2_1_http": {"base_url": "http://127.0.0.1:9"}}}})
        self.assertIn("environment", report)
        self.assertIn("lathe", report)
        self.assertIn("packages", report)
        self.assertIn("deterministic_backends", report)
        self.assertIn("remediation", report)

    def test_doctor_cli_json_mode_is_machine_readable(self) -> None:
        buffer = io.StringIO()
        with patch("lathe.cli.collect_doctor_report", return_value={"ok": True, "doctor": "test"}):
            with patch("sys.argv", ["lathe", "doctor", "--json"]):
                with redirect_stdout(buffer):
                    cli.main()
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["doctor"], "test")


if __name__ == "__main__":
    unittest.main()
