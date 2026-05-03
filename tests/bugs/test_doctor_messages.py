"""Regression tests for the doctor ok/fail message split (C3).

Before the fix every check entry had a single ``message`` string written
for the failure case, so a passing check rendered as e.g.
``pip_available: ok (pip was not found on PATH.)``. After the fix
``_setup_checks`` emits both ``ok_message`` and ``fail_message`` and
``format_doctor_report`` picks the right one.
"""

from __future__ import annotations

from lathe.doctor import collect_doctor_report, format_doctor_report


def test_setup_checks_have_ok_and_fail_messages() -> None:
    report = collect_doctor_report()
    checks = report["setup_checks"]
    assert checks
    for check in checks:
        assert "ok_message" in check, check["id"]
        assert "fail_message" in check, check["id"]
        assert check["ok_message"]
        assert check["fail_message"]
        assert check["ok_message"] != check["fail_message"]


def test_format_doctor_report_uses_ok_message_when_check_passed() -> None:
    report = collect_doctor_report()
    formatted = format_doctor_report(report)
    for check in report["setup_checks"]:
        if not check.get("ok"):
            continue
        line = next(
            line
            for line in formatted.splitlines()
            if line.startswith(f"- {check['id']}:")
        )
        assert check["ok_message"] in line, line
        assert check["fail_message"] not in line, line


def test_format_doctor_report_uses_fail_message_when_check_failed() -> None:
    report = collect_doctor_report()
    # Inject a synthetic failing check so we can exercise the failure branch
    # without depending on a host that happens to be missing something.
    report["setup_checks"].append(
        {
            "id": "synthetic_failing_check",
            "ok": False,
            "severity": "error",
            "ok_message": "synthetic-ok",
            "fail_message": "synthetic-fail",
            "remediation": "do the thing",
        }
    )
    formatted = format_doctor_report(report)
    line = next(
        line for line in formatted.splitlines() if line.startswith("- synthetic_failing_check:")
    )
    assert "synthetic-fail" in line
    assert "synthetic-ok" not in line
