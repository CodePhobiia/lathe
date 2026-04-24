from __future__ import annotations

import json
from pathlib import Path

from ._common import _dump


def run_inspect(args) -> None:
    from ..bridge.blender_plan import inspect_completed_build

    _dump(inspect_completed_build(Path(args.build_dir).resolve()))


def run_inspect_blend(args) -> None:
    from ..blender_execution import inspect_blend_artifact

    _dump(inspect_blend_artifact(Path(args.build_dir).resolve()))


def run_render_fixture(args) -> None:
    from ..bridge.blender_plan import build_render_fixture_report

    _dump(build_render_fixture_report(Path(args.build_dir).resolve()))


def run_bake_audit(args) -> None:
    from ..bridge.blender_plan import build_bake_audit

    _dump(build_bake_audit(Path(args.build_dir).resolve()))


def run_export_blend(args) -> None:
    from ..blender_execution import export_blend_artifact

    destination = Path(args.out).resolve() if args.out else None
    _dump(export_blend_artifact(Path(args.build_dir).resolve(), destination))


def run_explain(args) -> None:
    build_dir = Path(args.build_dir).resolve()
    # JSON ingress — internal controlled payloads from our own prior-run build artifacts (build_report.json, shape stage bundle, validate report, all emitted by this package); safe without schema validation.
    report = json.loads((build_dir / "build_report.json").read_text(encoding="utf-8"))
    shape_bundle = json.loads((build_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
    validate_report = json.loads((build_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8"))
    selected_id = shape_bundle.get("selected_candidate_id")
    selected = next((item for item in shape_bundle.get("candidates", []) if item.get("candidate_id") == selected_id), {})
    _dump(
        {
            "asset": report.get("asset"),
            "kind": report.get("kind"),
            "certified": report.get("certified"),
            "score": report.get("score"),
            "threshold": report.get("threshold"),
            "family": shape_bundle.get("asset_graph", {}).get("family"),
            "blueprint_id": shape_bundle.get("blueprint_id"),
            "authoritative_candidate_reason": shape_bundle.get("authoritative_candidate_reason"),
            "selected_candidate_id": selected_id,
            "candidate_params": selected.get("candidate_params", {}),
            "repairs_changed_result": validate_report.get("semantic_repairs_applied", []),
            "repair_suggestions": validate_report.get("repair_suggestions", []),
            "diagnostics": validate_report.get("diagnostics", []),
            "geometry_metrics": validate_report.get("visual_quality", {}).get("metrics", {}),
            "semantic_metrics": validate_report.get("semantic_quality", {}).get("metrics", {}),
        }
    )


def run_explain_fit(args) -> None:
    build_dir = Path(args.build_dir).resolve()
    # JSON ingress — internal controlled payloads from our own prior-run shape stage bundle and validate report; safe without schema validation.
    shape_bundle = json.loads((build_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
    validate_report = json.loads((build_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8"))
    _dump(
        {
            "reference_ir": shape_bundle.get("reference_ir", {}),
            "fit_ir": shape_bundle.get("fit_ir", {}),
            "transfer_ir": shape_bundle.get("transfer_ir", {}),
            "kit_ir": shape_bundle.get("kit_ir", {}),
            "conditioning_report": shape_bundle.get("conditioning_report", {}),
            "shape_assessment": shape_bundle.get("shape_assessment", {}),
            "diagnostics": validate_report.get("diagnostics", []),
        }
    )
