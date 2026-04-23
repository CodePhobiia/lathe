from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from .doctor import collect_doctor_report, dump_doctor_json, format_doctor_report
from .runtime_config import apply_cli_overrides, load_runtime_config


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def _expand_files(patterns: list[str] | None) -> list[str]:
    if not patterns:
        return []
    expanded: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(pattern)
    seen: set[str] = set()
    out: list[str] = []
    for item in expanded:
        resolved = str(Path(item).resolve())
        if resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def _diff_objects(left: Any, right: Any, path: str = "") -> dict[str, Any]:
    if type(left) is not type(right):
        return {"path": path or "$", "left": left, "right": right}
    if isinstance(left, dict):
        diffs = []
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                diffs.append({"path": f"{path}.{key}" if path else key, "left": left.get(key), "right": right.get(key)})
            else:
                child = _diff_objects(left[key], right[key], f"{path}.{key}" if path else key)
                if child:
                    if isinstance(child, list):
                        diffs.extend(child)
                    else:
                        diffs.append(child)
        return diffs
    if isinstance(left, list):
        if left != right:
            return {"path": path or "$", "left": left, "right": right}
        return {}
    if left != right:
        return {"path": path or "$", "left": left, "right": right}
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(prog="lathe", description="Lathe language reference scaffold")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="Parse a .lth file to raw AST JSON")
    p_parse.add_argument("file")

    p_norm = sub.add_parser("normalize", help="Normalize a .lth file to canonical JSON")
    p_norm.add_argument("file")

    p_fmt = sub.add_parser("fmt", help="Check Lathe sources for canonical parse/normalize stability")
    p_fmt.add_argument("files", nargs="*", help="Files or glob patterns (default: examples/*.lth)")
    p_fmt.add_argument("--check", action="store_true", help="Validate parse/normalize stability without rewriting files")

    sub.add_parser("schema", help="Emit the normalized AST JSON schema")
    sub.add_parser("backends", help="List builtin backend contracts and stacks")
    sub.add_parser("shape-providers", help="List available shape provider adapters")

    p_probe = sub.add_parser("probe-providers", help="Probe shape provider availability in the current runtime")
    p_probe.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")

    p_doctor = sub.add_parser("doctor", help="Inspect the local Lathe environment and backend/provider availability")
    p_doctor.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_check = sub.add_parser("check", help="Run semantic checks")
    p_check.add_argument("file")

    p_plan = sub.add_parser("plan", help="Emit the effective build plan for an asset or variant")
    p_plan.add_argument("file")
    p_plan.add_argument("name")
    p_plan.add_argument("--execution-profile", default=None, help="Override the resolved V1.3 execution profile")

    p_mat = sub.add_parser("materialize", help="Materialize one asset or variant after uses and patches")
    p_mat.add_argument("file")
    p_mat.add_argument("name")
    p_mat.add_argument("--execution-profile", default=None, help="Override the resolved V1.3 execution profile")

    p_build = sub.add_parser("build", help="Execute the first runnable backend stack and package outputs")
    p_build.add_argument("file")
    p_build.add_argument("name")
    p_build.add_argument("--out", default="dist", help="Output directory root (default: ./dist)")
    p_build.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_build.add_argument("--shape-provider", default=None, help="Override the shape provider adapter (for example: hunyuan2_1_http or vggt_local)")
    p_build.add_argument("--strict-shape-provider", action="store_true", help="Fail instead of falling back when the selected shape provider is unavailable or errors")
    p_build.add_argument("--codex-imagegen", choices=["auto", "fallback", "emit", "consume"], default=None, help="Codex-operated imagegen handoff mode for V1.2 surfaces")
    p_build.add_argument("--execution-profile", default=None, help="Override the resolved V1.3 execution profile")

    p_probe_blender = sub.add_parser("probe-blender", help="Probe Blender availability and V1.3 execution capabilities")
    p_probe_blender.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")

    p_export_blend = sub.add_parser("export-blend", help="Report or copy the retained .blend artifact for a completed build")
    p_export_blend.add_argument("build_dir")
    p_export_blend.add_argument("--out", default=None, help="Optional destination path for the exported .blend")

    p_inspect_blend = sub.add_parser("inspect-blend", help="Inspect the retained V1.3 .blend artifact summary for a completed build")
    p_inspect_blend.add_argument("build_dir")

    p_render_eval = sub.add_parser("render-eval", help="Build an asset and emit V1.3 render-eval evidence")
    p_render_eval.add_argument("file")
    p_render_eval.add_argument("name")
    p_render_eval.add_argument("--out", default="dist")
    p_render_eval.add_argument("--runtime-config", default=None)
    p_render_eval.add_argument("--execution-profile", default=None, help="Override the resolved V1.3 execution profile")

    p_bridge = sub.add_parser("bridge", help="Operate on V1.3.1 Lathe-Blender bridge plans and diagnostics")
    bridge_sub = p_bridge.add_subparsers(dest="bridge_cmd", required=True)
    p_bridge_doctor = bridge_sub.add_parser("doctor", help="Probe V1.3.1 bridge/tool-plane readiness")
    p_bridge_doctor.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_bridge_plan = bridge_sub.add_parser("plan", help="Emit a V1.3.1 typed bridge plan for an asset")
    p_bridge_plan.add_argument("file")
    p_bridge_plan.add_argument("name")
    p_bridge_plan.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_bridge_plan.add_argument("--execution-profile", default=None, help="Override the resolved execution profile")

    p_inspect = sub.add_parser("inspect", help="Inspect V1.3.1 evidence from a completed build")
    p_inspect.add_argument("build_dir")

    p_render_fixture = sub.add_parser("render-fixture", help="Report render-fixture evidence from a completed build")
    p_render_fixture.add_argument("build_dir")

    p_bake_audit = sub.add_parser("bake-audit", help="Report bake evidence and missing bake diagnostics from a completed build")
    p_bake_audit.add_argument("build_dir")

    p_library = sub.add_parser("library", help="Operate on V1.3 library bindings")
    library_sub = p_library.add_subparsers(dest="library_cmd", required=True)
    p_library_sync = library_sub.add_parser("sync", help="Materialize a V1.3 library binding sync manifest")
    p_library_sync.add_argument("file")
    p_library_sync.add_argument("--out", default="dist", help="Output directory root (default: ./dist)")

    p_surface_plan = sub.add_parser("surface-plan", help="Explain V1.2 surface authoring for an asset")
    p_surface_plan.add_argument("file")
    p_surface_plan.add_argument("name")

    p_surface_build = sub.add_parser("surface-build", help="Run the V1.2 surface stage with required upstream prerequisites")
    p_surface_build.add_argument("file")
    p_surface_build.add_argument("name")
    p_surface_build.add_argument("--out", default="dist")
    p_surface_build.add_argument("--runtime-config", default=None)
    p_surface_build.add_argument("--codex-imagegen", choices=["auto", "fallback", "emit", "consume"], default=None)

    p_surface_validate = sub.add_parser("surface-validate", help="Evaluate only V1.2 surface outputs")
    p_surface_validate.add_argument("file")
    p_surface_validate.add_argument("name")
    p_surface_validate.add_argument("--out", default="dist")
    p_surface_validate.add_argument("--runtime-config", default=None)
    p_surface_validate.add_argument("--codex-imagegen", choices=["auto", "fallback", "emit", "consume"], default=None)

    p_surface_repair = sub.add_parser("surface-repair", help="Attempt V1.2 zone-local surface repair")
    p_surface_repair.add_argument("file")
    p_surface_repair.add_argument("name")
    p_surface_repair.add_argument("--out", default="dist")
    p_surface_repair.add_argument("--runtime-config", default=None)
    p_surface_repair.add_argument("--codex-imagegen", choices=["auto", "fallback", "emit", "consume"], default=None)

    p_fit = sub.add_parser("fit", help="Explain deterministic fit/reference inputs for an asset")
    p_fit.add_argument("file")
    p_fit.add_argument("name")

    p_adapt = sub.add_parser("adapt", help="Build an asset in adapt mode")
    p_adapt.add_argument("file")
    p_adapt.add_argument("name")
    p_adapt.add_argument("--out", default="dist")
    p_adapt.add_argument("--runtime-config", default=None)

    p_assemble = sub.add_parser("assemble", help="Build an asset in assemble mode")
    p_assemble.add_argument("file")
    p_assemble.add_argument("name")
    p_assemble.add_argument("--out", default="dist")
    p_assemble.add_argument("--runtime-config", default=None)

    p_reconstruct = sub.add_parser("reconstruct", help="Build an asset in reconstruct mode")
    p_reconstruct.add_argument("file")
    p_reconstruct.add_argument("name")
    p_reconstruct.add_argument("--out", default="dist")
    p_reconstruct.add_argument("--runtime-config", default=None)

    p_test = sub.add_parser("test", help="Execute Lathe-defined source tests")
    p_test.add_argument("files", nargs="*", help="Files or glob patterns (default: examples/*.lth)")

    p_bench = sub.add_parser("bench", help="Execute Lathe-defined source benchmarks")
    p_bench.add_argument("files", nargs="*", help="Files or glob patterns (default: examples/*.lth)")

    p_audit = sub.add_parser("audit", help="Run benchmark/style of workspace audit for the current Lathe repo")
    p_audit.add_argument("--root", default=".", help="Workspace root (default: current directory)")

    p_explain = sub.add_parser("explain", help="Explain why a build passed, failed, or selected a candidate")
    p_explain.add_argument("build_dir", help="Build directory containing build_report.json and stage outputs")

    p_explain_fit = sub.add_parser("explain-fit", help="Explain fit/reference/transfer inputs for a completed build")
    p_explain_fit.add_argument("build_dir")

    p_diff_asset = sub.add_parser("diff-asset", help="Diff two materialized assets")
    p_diff_asset.add_argument("file_a")
    p_diff_asset.add_argument("name_a")
    p_diff_asset.add_argument("file_b")
    p_diff_asset.add_argument("name_b")

    p_patch = sub.add_parser("patch", help="Apply a semantic patch operation and emit normalized JSON")
    p_patch.add_argument("file")
    p_patch.add_argument("--op", required=True, choices=[
        "add_component_to_family",
        "change_repair_policy",
        "update_material_palette",
        "widen_search_bounds",
        "freeze_dimension",
        "add_benchmark_fixture",
    ])
    p_patch.add_argument("--target", required=True, help="Target declaration name")
    p_patch.add_argument("--value", required=True, help="Primary value for the selected patch operation")
    p_patch.add_argument("--value2", default=None, help="Secondary value for operations that need two values")

    args = parser.parse_args()

    if args.cmd == "doctor":
        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        report = collect_doctor_report(runtime_config)
        print(dump_doctor_json(report) if args.json else format_doctor_report(report))
        return

    if args.cmd == "schema":
        from .schema import get_schema

        _dump(get_schema())
        return
    if args.cmd == "fmt":
        from .normalizer import normalize_program
        from .schema import get_schema
        from jsonschema import Draft202012Validator
        from .parser import parse_file

        files = _expand_files(args.files) or _expand_files(["examples/*.lth"])
        results = []
        ok = True
        validator = Draft202012Validator(get_schema())
        for file_name in files:
            try:
                normalized = normalize_program(parse_file(Path(file_name)))
                validator.validate(normalized)
                results.append({"file": file_name, "ok": True})
            except Exception as exc:  # noqa: BLE001
                ok = False
                results.append({"file": file_name, "ok": False, "message": str(exc)})
        _dump({"ok": ok, "mode": "check" if args.check else "scaffold", "results": results})
        raise SystemExit(0 if ok else 1)
    if args.cmd == "backends":
        from .backends import list_backends, list_stacks

        _dump({"stacks": list_stacks(), "backends": list_backends()})
        return
    if args.cmd == "shape-providers":
        from .shape_providers import list_shape_providers

        _dump({"shape_providers": list_shape_providers()})
        return
    if args.cmd == "probe-providers":
        from .shape_providers import probe_all_shape_providers

        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        _dump({"shape_providers": probe_all_shape_providers(runtime_config)})
        return
    if args.cmd == "probe-blender":
        from .capabilities import probe_blender

        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        _dump(probe_blender(runtime_config))
        return
    if args.cmd == "bridge":
        from .bridge.blender_plan import build_bridge_doctor, build_bridge_plan

        runtime_config = load_runtime_config(args.runtime_config) if getattr(args, "runtime_config", None) else load_runtime_config(None)
        if args.bridge_cmd == "doctor":
            _dump(build_bridge_doctor(runtime_config))
            return
        if args.bridge_cmd == "plan":
            from .parser import parse_file as _parse_file
            from .resolver import materialize_asset as _materialize_asset

            program = _parse_file(Path(args.file))
            asset = _materialize_asset(program, args.name, execution_profile_override=args.execution_profile)
            _dump(build_bridge_plan(asset, runtime_config))
            return
        raise SystemExit(2)
    if args.cmd == "test":
        from .test_runtime import run_lathe_tests

        result = run_lathe_tests(_expand_files(args.files) or None)
        _dump(result)
        raise SystemExit(0 if result["ok"] else 1)
    if args.cmd == "bench":
        from .bench_runtime import run_lathe_benchmarks

        result = run_lathe_benchmarks(_expand_files(args.files) or None)
        _dump(result)
        raise SystemExit(0 if result["ok"] else 1)
    if args.cmd == "audit":
        from .eval_harness import run_benchmark_suite

        root = Path(args.root).resolve()
        _dump(run_benchmark_suite(root))
        return
    if args.cmd == "explain":
        build_dir = Path(args.build_dir).resolve()
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
        return
    if args.cmd == "explain-fit":
        build_dir = Path(args.build_dir).resolve()
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
        return
    if args.cmd == "inspect-blend":
        from .blender_execution import inspect_blend_artifact

        _dump(inspect_blend_artifact(Path(args.build_dir).resolve()))
        return
    if args.cmd == "inspect":
        from .bridge.blender_plan import inspect_completed_build

        _dump(inspect_completed_build(Path(args.build_dir).resolve()))
        return
    if args.cmd == "render-fixture":
        from .bridge.blender_plan import build_render_fixture_report

        _dump(build_render_fixture_report(Path(args.build_dir).resolve()))
        return
    if args.cmd == "bake-audit":
        from .bridge.blender_plan import build_bake_audit

        _dump(build_bake_audit(Path(args.build_dir).resolve()))
        return
    if args.cmd == "export-blend":
        from .blender_execution import export_blend_artifact

        destination = Path(args.out).resolve() if args.out else None
        _dump(export_blend_artifact(Path(args.build_dir).resolve(), destination))
        return
    if args.cmd == "diff-asset":
        from .parser import parse_file as _parse_file
        from .resolver import materialize_asset as _materialize_asset

        asset_a = _materialize_asset(_parse_file(Path(args.file_a)), args.name_a)
        asset_b = _materialize_asset(_parse_file(Path(args.file_b)), args.name_b)
        _dump(_diff_objects(asset_a, asset_b))
        return
    if args.cmd == "library":
        from .blender_execution import build_library_sync_manifest
        from .parser import parse_file as _parse_file

        if args.library_cmd == "sync":
            program = _parse_file(Path(args.file))
            out_root = Path(args.out)
            out_dir = out_root / "library_sync"
            _dump(build_library_sync_manifest(program, out_dir))
            return
        raise SystemExit(2)
    if args.cmd == "patch":
        from .parser import parse_file
        from .patch_api import (
            add_benchmark_fixture,
            add_component_to_family,
            change_repair_policy,
            freeze_dimension,
            update_material_palette,
            widen_search_bounds,
        )

        program = parse_file(Path(args.file))
        if args.op == "add_component_to_family":
            payload = add_component_to_family(program, args.target, args.value)
        elif args.op == "change_repair_policy":
            payload = change_repair_policy(program, args.target, args.value)
        elif args.op == "update_material_palette":
            payload = update_material_palette(program, args.target, args.value)
        elif args.op == "widen_search_bounds":
            if args.value2 is None:
                raise SystemExit("--value2 is required for widen_search_bounds")
            if ":" not in args.value2:
                raise SystemExit("--value2 must be LOWER:UPPER for widen_search_bounds")
            lower_text, upper_text = args.value2.split(":", 1)
            payload = widen_search_bounds(program, args.target, args.value, float(lower_text), float(upper_text))
        elif args.op == "freeze_dimension":
            payload = freeze_dimension(program, args.target, args.value)
        elif args.op == "add_benchmark_fixture":
            payload = add_benchmark_fixture(program, args.target, args.value)
        else:
            raise SystemExit(2)
        _dump(payload)
        return

    from .parser import parse_file

    program = parse_file(Path(args.file))

    if args.cmd == "parse":
        _dump(program)
    elif args.cmd == "normalize":
        from .normalizer import normalize_program

        _dump(normalize_program(program))
    elif args.cmd == "fit":
        from .resolver import materialize_asset

        asset = materialize_asset(program, args.name)
        _dump(
            {
                "asset": args.name,
                "mode": asset.get("build", {}).get("shape", {}).get("mode"),
                "refs": asset.get("refs", {}),
                "fit": asset.get("fit", {}),
                "transfer": asset.get("transfer", {}),
                "reuse": asset.get("reuse", {}),
                "constraints": asset.get("constraints", {}),
                "assembly": asset.get("assembly", {}),
            }
        )
    elif args.cmd == "check":
        from .checker import check_program

        diagnostics = check_program(program)
        _dump({"ok": not any(d["severity"] == "error" for d in diagnostics), "diagnostics": diagnostics})
    elif args.cmd == "plan":
        from .planner import build_plan

        _dump(build_plan(program, args.name, execution_profile_override=args.execution_profile))
    elif args.cmd == "surface-plan":
        from .planner import build_plan
        from .resolver import materialize_asset

        asset = materialize_asset(program, args.name)
        plan = build_plan(program, args.name)
        surface = asset.get("surface", {})
        build_surface = asset.get("build", {}).get("surface", {})
        authoring = surface.get("authoring", {}) if isinstance(surface.get("authoring"), dict) else {}
        policy_values = surface.get("resolved_surface_policy", {}).get("values", {})
        _dump(
            {
                "asset": args.name,
                "backend": authoring.get("backend") or surface.get("backend") or build_surface.get("authoring_backend") or build_surface.get("backend"),
                "resolved_backend_id": surface.get("resolved_surface_backend", {}).get("values", {}).get("id", ""),
                "policy": surface.get("policy", ""),
                "resolved_policy": plan["v1_2_surface"].get("resolved_surface_policy", ""),
                "zones": list(surface.get("material_zones", [])),
                "maps_to_generate": list(authoring.get("generate", [])),
                "maps_to_derive": list(authoring.get("derive", [])),
                "required_maps": list(policy_values.get("maps", build_surface.get("maps", []))),
                "control_images": ["uv_layout", "padded_island_mask", "material_zone_mask", "ao", "curvature", "normal_reference", "preview"],
                "validation_gates": [
                    "surface_authoring_quality",
                    "material_zone_coherence",
                    "seam_continuity",
                    "padding_safety",
                    "normal_richness",
                    "roughness_variation",
                    "texture_entropy",
                    "decal_coherence",
                    "trim_coherence",
                    "mip_safety",
                    "bake_alignment_quality",
                    "surface_render_plausibility",
                ],
                "v1_2_surface": plan["v1_2_surface"],
            }
        )
    elif args.cmd == "materialize":
        from .resolver import materialize_asset

        _dump(materialize_asset(program, args.name, execution_profile_override=args.execution_profile))
    elif args.cmd in {"surface-build", "surface-validate", "surface-repair"}:
        from .executor import BuildError, build_surface_stage, repair_surface_stage, validate_surface_stage

        out_root = Path(args.out)
        out_dir = out_root / args.name
        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        runtime_config = apply_cli_overrides(runtime_config, codex_imagegen=args.codex_imagegen)
        try:
            if args.cmd == "surface-build":
                _dump(build_surface_stage(program, args.name, out_dir, runtime_config=runtime_config))
            elif args.cmd == "surface-validate":
                result = validate_surface_stage(program, args.name, out_dir, runtime_config=runtime_config)
                _dump(result)
                raise SystemExit(0 if result["ok"] else 1)
            else:
                result = repair_surface_stage(program, args.name, out_dir, runtime_config=runtime_config)
                _dump(result)
                raise SystemExit(0 if result["ok"] else 1)
        except BuildError as exc:
            payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
            _dump(payload)
            raise SystemExit(1) from exc
    elif args.cmd == "build":
        from .executor import BuildError, build_asset

        out_root = Path(args.out)
        out_dir = out_root / args.name
        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        runtime_config = apply_cli_overrides(
            runtime_config,
            shape_provider=args.shape_provider,
            shape_strict=True if args.strict_shape_provider else None,
            codex_imagegen=args.codex_imagegen,
        )
        try:
            _dump(
                build_asset(
                    program,
                    args.name,
                    out_dir,
                    runtime_config=runtime_config,
                    execution_profile_override=args.execution_profile,
                )
            )
        except BuildError as exc:
            payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
            _dump(payload)
            raise SystemExit(1) from exc
    elif args.cmd == "render-eval":
        from .executor import BuildError, build_asset

        out_root = Path(args.out)
        out_dir = out_root / args.name
        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        try:
            build_asset(
                program,
                args.name,
                out_dir,
                runtime_config=runtime_config,
                execution_profile_override=args.execution_profile,
            )
            bundle = json.loads((out_dir / "stages" / "execution" / "bundle.json").read_text(encoding="utf-8"))
            _dump(
                {
                    "asset": args.name,
                    "out_dir": str(out_dir),
                    "backend_id": bundle.get("backend_id"),
                    "probe": bundle.get("probe", {}),
                    "render_eval_ir": bundle.get("render_eval_ir", {}),
                    "blend_artifact_ir": bundle.get("blend_artifact_ir", {}),
                    "diagnostics": bundle.get("diagnostics", []),
                }
            )
        except BuildError as exc:
            payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
            _dump(payload)
            raise SystemExit(1) from exc
    elif args.cmd in {"adapt", "assemble", "reconstruct"}:
        from .executor import BuildError, build_asset
        from .resolver import materialize_asset

        effective = materialize_asset(program, args.name)
        expected_mode = args.cmd
        actual_mode = str(effective.get("build", {}).get("shape", {}).get("mode", "generate"))
        if actual_mode != expected_mode:
            raise SystemExit(f"Asset '{args.name}' is configured for shape.mode={actual_mode}, not {expected_mode}")
        out_root = Path(args.out)
        out_dir = out_root / args.name
        runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
        try:
            _dump(build_asset(program, args.name, out_dir, runtime_config=runtime_config))
        except BuildError as exc:
            payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
            _dump(payload)
            raise SystemExit(1) from exc
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
