"""Wonder alpha-gate readiness report assembly."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .env import probe_wonder_environment
from .evidence import build_evidence_trace
from .reports import write_final_report_bundle

WONDER_ALPHA_GATE_REPORT_VERSION = "lathe.wonder_alpha_gate_report.v1"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "wonder-tasks.md").exists() and (parent / "lathe").exists():
            return parent
    return Path.cwd()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _lane(
    lane_id: str,
    status: str,
    *,
    blocking: bool = True,
    diagnostics: list[dict[str, Any]] | None = None,
    artifacts: dict[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": lane_id,
        "status": status,
        "blocking": blocking,
        "diagnostics": diagnostics or [],
    }
    if artifacts:
        payload["artifacts"] = artifacts
    if details:
        payload["details"] = details
    return payload


def _run_lane(lane_id: str, callback: Callable[[], list[dict[str, Any]]]) -> dict[str, Any]:
    diagnostics = callback()
    return _lane(lane_id, "failed" if diagnostics else "passed", diagnostics=diagnostics)


def _contract_lane(contract_id: str, path: Path) -> Callable[[], list[dict[str, Any]]]:
    def run() -> list[dict[str, Any]]:
        from .contracts import load_and_validate_contract

        _payload, diagnostics = load_and_validate_contract(contract_id, path)
        return diagnostics

    return run


def _brief_scene_lane(brief_path: Path, scene_path: Path) -> list[dict[str, Any]]:
    from .brief import load_and_check_brief_scene

    _brief, _scene, diagnostics = load_and_check_brief_scene(brief_path, scene_path)
    return diagnostics


def _scene_semantics_lane(scene_path: Path) -> list[dict[str, Any]]:
    from lathe.scene import load_and_check_scene_graph

    _scene, diagnostics = load_and_check_scene_graph(scene_path)
    return diagnostics


def _world_memory_lane(memory_path: Path, scene_path: Path) -> list[dict[str, Any]]:
    from lathe.scene.memory import load_and_validate_world_memory

    _memory, diagnostics = load_and_validate_world_memory(memory_path, scene_graph=scene_path)
    return diagnostics


def _scene_plan_lane(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    from lathe.scene import plan_scene, validate_scene_plan_payload

    return validate_scene_plan_payload(plan_scene(scene_graph, mode="preview"))


def _scene_assembly_lane(scene_graph: Mapping[str, Any], example_dir: Path) -> list[dict[str, Any]]:
    from lathe.scene import assemble_scene, validate_scene_assembly_payload

    return validate_scene_assembly_payload(assemble_scene(scene_graph), package_root=example_dir)


def _scene_quality_lane(scene_graph: Mapping[str, Any], example_dir: Path) -> list[dict[str, Any]]:
    from lathe.scene import run_scene_validators

    report = run_scene_validators(scene_graph, root=example_dir)
    diagnostics = report.get("diagnostics", [])
    return diagnostics if isinstance(diagnostics, list) else []


def _optional_lane_summary(env_probe: Mapping[str, Any]) -> dict[str, str]:
    optional_lanes = env_probe.get("optional_lanes", {})
    if not isinstance(optional_lanes, Mapping):
        return {}
    summary: dict[str, str] = {}
    for lane_id, payload in optional_lanes.items():
        if isinstance(payload, Mapping):
            summary[str(lane_id)] = str(payload.get("status", "unknown"))
    return summary


def build_alpha_gate_report(
    example_dir: str | Path,
    out_dir: str | Path,
    *,
    tasks_path: str | Path | None = None,
    evidence_path: str | Path | None = None,
    mode: str = "core",
) -> dict[str, Any]:
    """Run the deterministic Wonder alpha-gate skeleton and write reports."""
    root = _repo_root()
    example_root = Path(example_dir)
    if not example_root.is_absolute():
        example_root = root / example_root
    output_root = Path(out_dir)
    reports_dir = output_root / "reports"
    for folder_name in ("before", "after", "comparisons", "history"):
        (output_root / folder_name).mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    task_file = Path(tasks_path) if tasks_path is not None else root / "wonder-tasks.md"
    evidence_file = (
        Path(evidence_path)
        if evidence_path is not None
        else root / "docs" / "wonder-readiness" / "evidence.md"
    )

    env_probe = probe_wonder_environment(mode=mode)
    _write_json(reports_dir / "env_probe.json", env_probe)

    evidence_trace = build_evidence_trace(task_file, evidence_file, repo_root=root)
    _write_json(reports_dir / "evidence_traceability.json", evidence_trace)

    brief_path = example_root / "dream_brief.json"
    scene_path = example_root / "scene_graph.json"
    patch_path = example_root / "scene_patch.example.json"
    if not patch_path.exists():
        patch_path = example_root / "scene_patch_more_sacred.json"
    render_inspection_path = example_root / "render_inspection.example.json"
    memory_path = example_root / "world_memory.json"
    scene_graph = _load_json(scene_path)

    lanes: list[dict[str, Any]] = [
        _lane(
            "env_probe",
            "passed" if env_probe.get("ok") else "failed",
            diagnostics=[],
            artifacts={"report": str(reports_dir / "env_probe.json")},
            details={
                "blocking_missing": list(env_probe.get("blocking_missing", [])),
                "optional_missing": list(env_probe.get("optional_missing", [])),
            },
        ),
        _lane(
            "evidence_traceability",
            "passed" if evidence_trace.get("ok") else "failed",
            diagnostics=list(evidence_trace.get("diagnostics", [])),
            artifacts={"report": str(reports_dir / "evidence_traceability.json")},
        ),
        _run_lane("dream_brief_contract", _contract_lane("dream_brief", brief_path)),
        _run_lane("scene_graph_contract", _contract_lane("scene_graph", scene_path)),
        _run_lane("brief_scene_consistency", lambda: _brief_scene_lane(brief_path, scene_path)),
        _run_lane("scene_graph_semantics", lambda: _scene_semantics_lane(scene_path)),
        _run_lane("scene_patch_contract", _contract_lane("scene_patch", patch_path)),
        _run_lane("render_inspection_contract", _contract_lane("render_inspection", render_inspection_path)),
        _run_lane("world_memory_contract", lambda: _world_memory_lane(memory_path, scene_path)),
        _run_lane("scene_plan_contract", lambda: _scene_plan_lane(scene_graph)),
        _run_lane("scene_assembly_contract", lambda: _scene_assembly_lane(scene_graph, example_root)),
        _run_lane("scene_quality_validators", lambda: _scene_quality_lane(scene_graph, example_root)),
    ]

    blocking_failures = [
        lane
        for lane in lanes
        if lane.get("blocking") is True and lane.get("status") != "passed"
    ]
    core_passed = not blocking_failures
    report: dict[str, Any] = {
        "schema_version": WONDER_ALPHA_GATE_REPORT_VERSION,
        "ok": core_passed,
        "core_alpha_gate": "passed" if core_passed else "failed",
        "mode": mode,
        "example": str(example_root),
        "reports_dir": str(reports_dir),
        "blocking_missing_runtimes": list(env_probe.get("blocking_missing", [])),
        "optional_lanes": _optional_lane_summary(env_probe),
        "alpha_decision_ready": core_passed,
        "remaining_human_decision": "Approve Project Wonder alpha gate.",
        "summary": {
            "lanes": len(lanes),
            "passed": sum(1 for lane in lanes if lane.get("status") == "passed"),
            "failed": len(blocking_failures),
            "optional_missing": len(env_probe.get("optional_missing", [])),
        },
        "lanes": lanes,
    }
    report = write_final_report_bundle(
        root=root,
        example_root=example_root,
        reports_dir=reports_dir,
        alpha_report=report,
        env_probe=env_probe,
        evidence_trace=evidence_trace,
    )
    _write_json(reports_dir / "final_readiness_report.json", report)
    return report


__all__ = [
    "WONDER_ALPHA_GATE_REPORT_VERSION",
    "build_alpha_gate_report",
]
