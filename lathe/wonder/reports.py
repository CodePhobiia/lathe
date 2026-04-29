"""Final Wonder readiness report helpers."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

WONDER_BENCHMARK_REPORT_VERSION = "lathe.wonder_benchmark_report.v1"
WONDER_SECURITY_REPORT_VERSION = "lathe.wonder_security_report.v1"
WONDER_PERFORMANCE_REPORT_VERSION = "lathe.wonder_performance_report.v1"
WONDER_CONTRACT_CATALOG_VERSION = "lathe.wonder_contract_catalog.v1"
WONDER_CLI_CATALOG_VERSION = "lathe.wonder_cli_catalog.v1"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _repo_relative(root: Path, path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return str(path)


def _markdown_text(value: object) -> str:
    return str(value).replace("<", "&lt;").replace(">", "&gt;")


def _lane_summary(alpha_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    lanes = alpha_report.get("lanes", [])
    if not isinstance(lanes, list):
        return []
    return [
        {
            "id": str(lane.get("id", "unknown")),
            "status": str(lane.get("status", "unknown")),
            "blocking": bool(lane.get("blocking", False)),
            "diagnostics": len(lane.get("diagnostics", [])) if isinstance(lane.get("diagnostics"), list) else 0,
        }
        for lane in lanes
        if isinstance(lane, Mapping)
    ]


def build_benchmark_report(alpha_report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a truthful benchmark summary from deterministic gate data."""
    return {
        "schema_version": WONDER_BENCHMARK_REPORT_VERSION,
        "status": "recorded",
        "measurement_mode": "deterministic_gate_summary",
        "core_alpha_gate": alpha_report.get("core_alpha_gate", "unknown"),
        "measured_timings": [],
        "reason": (
            "Wave 6 records deterministic core gate status here. It does not claim fresh "
            "wall-clock benchmark measurements unless a separate benchmark command records them."
        ),
        "core_lane_summary": _lane_summary(alpha_report),
    }


def build_security_report(alpha_report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic security/safety readiness summary."""
    core_status = str(alpha_report.get("core_alpha_gate", "failed"))
    return {
        "schema_version": WONDER_SECURITY_REPORT_VERSION,
        "status": "passed" if core_status == "passed" else "failed",
        "scope": "deterministic_wonder_core",
        "checks": [
            {
                "id": "world_memory_redaction",
                "status": "covered",
                "evidence": "tests/unit/test_wonder_memory.py",
            },
            {
                "id": "path_safety",
                "status": "covered",
                "evidence": "tests/fuzz/test_wonder_contract_fuzz.py",
            },
            {
                "id": "llm_validator_boundary",
                "status": "covered",
                "evidence": "tests/unit/test_wonder_llm.py",
            },
            {
                "id": "optional_external_runtimes_nonblocking",
                "status": "covered",
                "evidence": "lathe/wonder/env.py",
            },
        ],
        "limitations": [
            "External Blender, Roblox, and viewer lanes are not required by the deterministic core report.",
            "The final human alpha decision remains pending.",
        ],
    }


def build_performance_report(alpha_report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic performance readiness summary."""
    return {
        "schema_version": WONDER_PERFORMANCE_REPORT_VERSION,
        "status": "recorded",
        "measurement_mode": "ci_script_and_alpha_gate_summary",
        "core_alpha_gate": alpha_report.get("core_alpha_gate", "unknown"),
        "slow_or_external_lanes": {
            "blender": "optional",
            "roblox": "optional",
            "external_viewer": "optional",
        },
        "measured_timings": [],
        "reason": (
            "Core readiness is intentionally dependency-light. Performance measurements can be "
            "attached later without making optional runtimes block core CI."
        ),
    }


def build_contract_catalog(root: Path) -> dict[str, Any]:
    """Return the committed Wonder contract catalog."""
    from .contracts import list_contract_summaries

    contracts = list_contract_summaries()
    return {
        "schema_version": WONDER_CONTRACT_CATALOG_VERSION,
        "status": "passed",
        "contracts": contracts,
        "summary": {"total": len(contracts)},
        "root": _repo_relative(root, root),
    }


def _leaf_command_paths(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
) -> set[tuple[str, ...]]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            paths: set[tuple[str, ...]] = set()
            for name, subparser in action.choices.items():
                child_paths = _leaf_command_paths(subparser, (*prefix, name))
                paths.update(child_paths or {(*prefix, name)})
            return paths
    return set()


def build_cli_catalog() -> dict[str, Any]:
    """Return the current CLI leaf-command catalog."""
    from lathe.cli import _build_parser

    commands = [" ".join(path) for path in sorted(_leaf_command_paths(_build_parser()))]
    wonder_commands = [command for command in commands if command.startswith("wonder ")]
    return {
        "schema_version": WONDER_CLI_CATALOG_VERSION,
        "status": "passed",
        "commands": commands,
        "wonder_commands": wonder_commands,
        "summary": {
            "total": len(commands),
            "wonder": len(wonder_commands),
        },
    }


def _public_example_catalog(root: Path) -> dict[str, Any]:
    from .examples import catalog_wonder_examples

    payload = catalog_wonder_examples(root / "examples" / "wonder", include_reports=False)
    return {key: value for key, value in payload.items() if key != "reports"}


def _known_deferred_lanes(
    alpha_report: Mapping[str, Any],
    env_probe: Mapping[str, Any],
    example_catalog: Mapping[str, Any],
) -> list[dict[str, Any]]:
    deferred: list[dict[str, Any]] = []
    optional_lanes = env_probe.get("optional_lanes", {})
    if isinstance(optional_lanes, Mapping):
        for lane_id, lane in sorted(optional_lanes.items()):
            if not isinstance(lane, Mapping):
                continue
            if lane.get("status") in {"skipped", "skipped_nonblocking", "failed"} and lane.get("blocking") is False:
                deferred.append(
                    {
                        "lane": str(lane_id),
                        "status": str(lane.get("status", "unknown")),
                        "blocking": False,
                        "reason": str(lane.get("reason", "optional runtime evidence not present")),
                    }
                )
    for example in example_catalog.get("examples", []):
        if not isinstance(example, Mapping):
            continue
        for lane_id in example.get("deferred_lanes", []):
            deferred.append(
                {
                    "lane": str(lane_id),
                    "status": "deferred",
                    "blocking": False,
                    "example": str(example.get("name", "unknown")),
                    "reason": "Golden fixture records this lane as truthfully deferred.",
                }
            )
    if alpha_report.get("remaining_human_decision"):
        deferred.append(
            {
                "lane": "human_alpha_decision",
                "status": "pending",
                "blocking": False,
                "reason": str(alpha_report["remaining_human_decision"]),
            }
        )
    return deferred


def render_final_readiness_markdown(report: Mapping[str, Any]) -> str:
    """Render a concise final readiness Markdown report."""
    optional = report.get("optional_lanes", {})
    if isinstance(optional, Mapping):
        optional_lines = [f"- {lane}: {status}" for lane, status in sorted(optional.items())]
    else:
        optional_lines = []
    bundle = report.get("report_bundle", {})
    bundle_lines = []
    if isinstance(bundle, Mapping):
        bundle_lines = [f"- {name}: `{path}`" for name, path in sorted(bundle.items())]
    deferred = report.get("known_deferred_lanes", [])
    deferred_lines = []
    if isinstance(deferred, list):
        for lane in deferred:
            if isinstance(lane, Mapping):
                label = lane.get("lane", "unknown")
                status = lane.get("status", "unknown")
                reason = lane.get("reason", "")
                deferred_lines.append(f"- {_markdown_text(label)}: {_markdown_text(status)}. {_markdown_text(reason)}")
    core_gate = report.get("core_alpha_gate", "unknown")
    decision = "ready for human approval" if report.get("alpha_decision_ready") else "not ready"
    lines = [
        "# Project Wonder Final Readiness Report",
        "",
        "Generated by `python -m lathe.cli wonder alpha-gate` or `wonder readiness-report`.",
        "",
        "Scope: deterministic core/proxy alpha gate. This report does not claim full final "
        "Wonder runtime readiness unless optional Blender, Roblox, POSIX, and external-viewer "
        "lanes are separately recorded as required by the release scope.",
        "",
        "## Status Summary",
        "",
        f"- Core alpha gate: {core_gate}",
        f"- Blocking missing runtimes: {report.get('blocking_missing_runtimes', [])}",
        f"- Alpha decision readiness: {decision}",
        f"- Remaining human decision: {report.get('remaining_human_decision', 'Approve Project Wonder alpha gate.')}",
        "",
        "## Core Gates",
        "",
    ]
    for lane in _lane_summary(report):
        lines.append(f"- {lane['id']}: {lane['status']}")
    lines.extend(["", "## Optional Gates", ""])
    lines.extend(optional_lines or ["- No optional lane summary was recorded."])
    lines.extend(["", "## Evidence Bundle Paths", ""])
    lines.extend(bundle_lines or ["- No report bundle paths were recorded."])
    lines.extend(["", "## Known Deferred Lanes", ""])
    lines.extend(deferred_lines or ["- None."])
    lines.extend(
        [
            "",
            "## Final Alpha Decision",
            "",
            "The deterministic core evidence can make the alpha gate decision-ready, but the human approval "
            "decision is not completed by this report.",
            "",
        ]
    )
    return "\n".join(lines)


def write_final_report_bundle(
    *,
    root: Path,
    example_root: Path,
    reports_dir: Path,
    alpha_report: dict[str, Any],
    env_probe: Mapping[str, Any],
    evidence_trace: Mapping[str, Any],
) -> dict[str, Any]:
    """Write final Wave 6 reports and return the enriched alpha report."""
    benchmark = build_benchmark_report(alpha_report)
    security = build_security_report(alpha_report)
    performance = build_performance_report(alpha_report)
    contract_catalog = build_contract_catalog(root)
    cli_catalog = build_cli_catalog()
    example_catalog = _public_example_catalog(root)

    report_paths = {
        "benchmark_report": reports_dir / "benchmark_report.json",
        "security_report": reports_dir / "security_report.json",
        "performance_report": reports_dir / "performance_report.json",
        "contract_catalog": reports_dir / "contract_catalog.json",
        "cli_catalog": reports_dir / "cli_catalog.json",
        "example_catalog": reports_dir / "example_catalog.json",
    }
    _write_json(report_paths["benchmark_report"], benchmark)
    _write_json(report_paths["security_report"], security)
    _write_json(report_paths["performance_report"], performance)
    _write_json(report_paths["contract_catalog"], contract_catalog)
    _write_json(report_paths["cli_catalog"], cli_catalog)
    _write_json(report_paths["example_catalog"], example_catalog)

    bundle_paths = {
        "final_readiness_report_json": reports_dir / "final_readiness_report.json",
        "final_readiness_report_md": reports_dir / "final_readiness_report.md",
        "env_probe": reports_dir / "env_probe.json",
        "evidence_traceability": reports_dir / "evidence_traceability.json",
        **report_paths,
    }
    alpha_report["report_bundle"] = {
        name: _repo_relative(root, path) for name, path in sorted(bundle_paths.items())
    }
    alpha_report["known_deferred_lanes"] = _known_deferred_lanes(alpha_report, env_probe, example_catalog)
    alpha_report["reports"] = {
        "benchmark": benchmark,
        "security": security,
        "performance": performance,
        "contract_catalog_summary": contract_catalog["summary"],
        "cli_catalog_summary": cli_catalog["summary"],
        "example_catalog_summary": example_catalog.get("summary", {}),
        "evidence_traceability_summary": evidence_trace.get("summary", {}),
    }
    alpha_report["example_catalog"] = {
        "path": _repo_relative(root, report_paths["example_catalog"]),
        "summary": example_catalog.get("summary", {}),
    }
    alpha_report["example"] = _repo_relative(root, example_root)

    markdown_path = reports_dir / "final_readiness_report.md"
    markdown_path.write_text(render_final_readiness_markdown(alpha_report), encoding="utf-8")
    return alpha_report


def write_readiness_report_files(
    out_path: str | Path,
    alpha_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Write Markdown plus a sibling JSON final readiness report."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    report = dict(alpha_report)
    target.write_text(render_final_readiness_markdown(report), encoding="utf-8")
    json_path = target.with_suffix(".json")
    _write_json(json_path, report)
    return {
        "ok": bool(report.get("ok", False)),
        "command": "wonder.readiness-report",
        "out": str(target),
        "json_out": str(json_path),
        "core_alpha_gate": report.get("core_alpha_gate", "unknown"),
        "alpha_decision_ready": bool(report.get("alpha_decision_ready", False)),
        "remaining_human_decision": report.get(
            "remaining_human_decision",
            "Approve Project Wonder alpha gate.",
        ),
    }


__all__ = [
    "WONDER_BENCHMARK_REPORT_VERSION",
    "WONDER_CLI_CATALOG_VERSION",
    "WONDER_CONTRACT_CATALOG_VERSION",
    "WONDER_PERFORMANCE_REPORT_VERSION",
    "WONDER_SECURITY_REPORT_VERSION",
    "build_benchmark_report",
    "build_cli_catalog",
    "build_contract_catalog",
    "build_performance_report",
    "build_security_report",
    "render_final_readiness_markdown",
    "write_final_report_bundle",
    "write_readiness_report_files",
]
