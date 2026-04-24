"""Lathe CLI package.

Exposes the ``python -m lathe.cli`` entry point and the individual
``*_cmd`` modules that implement each subcommand.
"""

from __future__ import annotations

import argparse

from ..doctor import collect_doctor_report, dump_doctor_json, format_doctor_report
from .bridge_cmd import run_bridge
from .build_cmd import run_build, run_mode_build, run_render_eval
from .cache_cmd import register as _register_cache, run_cache
from .check_cmd import run_check
from .diff_cmd import register as _register_diff, run_diff
from .doctor_cmd import (
    run_backends,
    run_doctor,
    run_probe_blender,
    run_probe_providers,
    run_shape_providers,
)
from .inspect_cmd import (
    run_bake_audit,
    run_explain,
    run_explain_fit,
    run_export_blend,
    run_inspect,
    run_inspect_blend,
    run_render_fixture,
    run_serve,
)
from .library_cmd import run_library
from .materialize_cmd import run_diff_asset, run_materialize
from .fmt_cmd import run_fmt
from .parse_cmd import run_normalize, run_parse, run_schema
from .patch_cmd import run_patch
from .plan_cmd import run_fit, run_plan, run_surface_plan
from .publish_cmd import register as _register_publish, run_publish
from .ref_cmd import run_ref
from .ref_copy_cmd import run_ref_copy
from .ref_diff_cmd import run_ref_diff
from .ref_inspect_cmd import run_ref_inspect
from .ref_planes_cmd import run_ref_planes
from .snapshot_cmd import register as _register_snapshot, run_snapshot
from .surface_cmd import run_surface
from .telemetry_cmd import register as _register_telemetry, run_telemetry
from .test_cmd import run_audit, run_bench, run_test

__all__ = ["main", "collect_doctor_report", "dump_doctor_json", "format_doctor_report"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lathe", description="Lathe language reference scaffold")
    parser.add_argument(
        "--strict-prompt-injection",
        action="store_true",
        help=(
            "SEC-8: promote prompt-injection scanner warnings (L7001-L7005) to "
            "errors. Also settable via LATHE_STRICT_PROMPT_INJECTION=1."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="Parse a .lth file to raw AST JSON")
    p_parse.add_argument("file")

    p_norm = sub.add_parser("normalize", help="Normalize a .lth file to canonical JSON")
    p_norm.add_argument("file")

    p_fmt = sub.add_parser(
        "fmt",
        help="Rewrite Lathe sources in canonical form",
        description=(
            "Rewrite Lathe sources in canonical form. By default, files are "
            "rewritten in place; use --check to report without writing, "
            "--dry-run to print a unified diff, or --stdout to read a single "
            "file (or stdin) and write the canonical form to stdout."
        ),
    )
    p_fmt.add_argument("files", nargs="*", help="Files or glob patterns (default: examples/*.lth)")
    p_fmt.add_argument("--check", action="store_true", help="Don't write; exit non-zero if any file would change")
    p_fmt.add_argument("--dry-run", dest="dry_run", action="store_true", help="Print a unified diff without writing")
    p_fmt.add_argument("--stdout", action="store_true", help="Read a single file (or stdin) and write canonical output to stdout")

    sub.add_parser("schema", help="Emit the normalized AST JSON schema")
    sub.add_parser("backends", help="List builtin backend contracts and stacks")
    sub.add_parser("shape-providers", help="List available shape provider adapters")

    p_probe = sub.add_parser("probe-providers", help="Probe shape provider availability in the current runtime")
    p_probe.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")

    p_doctor = sub.add_parser("doctor", help="Inspect the local Lathe environment and backend/provider availability")
    p_doctor.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p_doctor.add_argument(
        "--plugins",
        action="store_true",
        help=(
            "Plan 03 Phase 2: list backends, stacks, shape providers, and "
            "validators discovered via the ``lathe.*`` entry-point groups, "
            "with their resolvable status. Also runs under --json."
        ),
    )

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

    p_build = sub.add_parser(
        "build",
        help="Execute the first runnable backend stack and package outputs",
        description=(
            "Execute the first runnable backend stack and package outputs. "
            "Exit codes: 0 = ok; 1 = build or provider error (including "
            "'provider_fallback_blocked' under strict shape-provider mode); "
            "2 = CLI usage error."
        ),
    )
    p_build.add_argument("file")
    p_build.add_argument("name")
    p_build.add_argument("--out", default="dist", help="Output directory root (default: ./dist)")
    p_build.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_build.add_argument("--shape-provider", default=None, help="Override the shape provider adapter (for example: hunyuan2_1_http or vggt_local)")
    p_build.add_argument(
        "--strict-shape-provider",
        action="store_true",
        help=(
            "[DEPRECATED] Back-compat alias: fail instead of falling back when "
            "the selected shape provider is unavailable or errors. Emits a "
            "DeprecationWarning; use --strict (V0.2+) or set shape.strict=true "
            "in runtime_config."
        ),
    )
    p_build.add_argument(
        "--allow-fallback",
        action="store_true",
        help=(
            "BL-37 (Plan 08 Phase 8): explicitly opt into the legacy "
            "'fall back to reference_conditioned on learned-provider error' "
            "behavior, silencing the V0.1.x DeprecationWarning. In V0.2 this "
            "becomes the sole non-strict opt-out."
        ),
    )
    p_build.add_argument("--codex-imagegen", choices=["auto", "fallback", "emit", "consume"], default=None, help="Codex-operated imagegen handoff mode for V1.2 surfaces")
    p_build.add_argument("--execution-profile", default=None, help="Override the resolved V1.3 execution profile")
    p_build.add_argument(
        "--publish",
        default=None,
        help=(
            "BL-31 (Plan 08 Phase 1): after a successful build, publish the "
            "output via the named driver (e.g. local_fs, s3, supabase, git_lfs). "
            "Driver-specific settings come from --runtime-config."
        ),
    )
    p_build.add_argument(
        "--report",
        choices=["terminal", "html", "json"],
        default=None,
        help=(
            "BL-36 (Plan 08 Phase 6): select the build-report output style. "
            "Default: 'terminal' if stdout is a TTY, else 'json'. "
            "'html' also writes report.html next to build_report.json."
        ),
    )
    p_build.add_argument(
        "--deterministic",
        action="store_true",
        help=(
            "RPT-3 (V0.2 E4): emit reports with zeroed timestamps, "
            "forward-slash paths, collapsed $HOME, runtime_ms rounded "
            "to the nearest ms, and diagnostics sorted by code. Two "
            "cache-cleared builds produce byte-identical JSON reports."
        ),
    )

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
    p_inspect.add_argument(
        "--view",
        action="store_true",
        help=(
            "BL-36 (Plan 08 Phase 7): open the build's packaged .glb in a "
            "trimesh Scene viewer. Requires the optional 'trimesh' extra."
        ),
    )

    p_serve = sub.add_parser(
        "serve",
        help="Serve a completed build's .glb via a local <model-viewer> page",
        description=(
            "BL-36 (Plan 08 Phase 7): start a local HTTP server that pairs the "
            "vendored <model-viewer> viewer with a completed build's .glb. "
            "Exit codes: 0 = clean shutdown; 2 = CLI usage error (missing dir)."
        ),
    )
    p_serve.add_argument("build_dir")
    p_serve.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")

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

    p_surface_build = sub.add_parser(
        "surface-build",
        help="Run the V1.2 surface stage with required upstream prerequisites",
        description=(
            "Run the V1.2 surface stage. Exit codes: 0 = ok; 1 = build or "
            "provider error (including 'provider_fallback_blocked' under "
            "strict shape-provider mode); 2 = CLI usage error."
        ),
    )
    p_surface_build.add_argument("file")
    p_surface_build.add_argument("name")
    p_surface_build.add_argument("--out", default="dist")
    p_surface_build.add_argument("--runtime-config", default=None)
    p_surface_build.add_argument(
        "--allow-fallback",
        action="store_true",
        help=(
            "BL-37 (Plan 08 Phase 8): opt into legacy learned-provider "
            "fallback behavior, silencing the V0.1.x DeprecationWarning."
        ),
    )
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

    p_ref = sub.add_parser(
        "ref",
        help="Operate on @lathe[...] semantic references (Phase 1: non-geometric)",
        description=(
            "REF-1/2/3/4/8/14 (V0.2 E1 Phase 1). Parse, validate, and (later) "
            "resolve @lathe[...] reference tokens. See docs/refs.md. "
            "Exit codes: 0 = ok; 2 = bad token or usage error."
        ),
    )
    ref_sub = p_ref.add_subparsers(dest="ref_cmd", required=True)
    p_ref_parse = ref_sub.add_parser("parse", help="Parse an @lathe[...] token and print it as JSON")
    p_ref_parse.add_argument("token", help="The @lathe[...] token to parse, quoted")

    p_ref_inspect = ref_sub.add_parser(
        "inspect",
        help="Parse, resolve, and print JSON facts for an @lathe[...] token (REF-9)",
        description=(
            "Exit codes: 0 = ok (JSON on stdout); 2 = bad token (parse error); "
            "3 = unresolved ref."
        ),
    )
    p_ref_inspect.add_argument("token", help="The @lathe[...] token to inspect, quoted")
    p_ref_inspect.add_argument("--repo-root", default=None, help="Override repo root for resolution")

    p_ref_planes = ref_sub.add_parser(
        "planes",
        help="List cardinal axis-aligned planes for each part's bbox (REF-10)",
    )
    p_ref_planes.add_argument("build_dir", help="Completed build directory")
    p_ref_planes.add_argument("--part", default=None, help="Restrict to a single part id")

    p_ref_diff = ref_sub.add_parser(
        "diff",
        help="Structural diff between two selector manifests (REF-11)",
    )
    p_ref_diff.add_argument("build_a", help="First build directory")
    p_ref_diff.add_argument("build_b", help="Second build directory")

    p_ref_copy = ref_sub.add_parser(
        "copy",
        help="Copy the referenced artifact to a target path (REF-12)",
    )
    p_ref_copy.add_argument("token", help="The @lathe[...] token to resolve and copy, quoted")
    p_ref_copy.add_argument("target_path", help="Destination file (or directory) path")
    p_ref_copy.add_argument("--repo-root", default=None, help="Override repo root for resolution")

    _register_cache(sub)
    _register_diff(sub)
    _register_publish(sub)
    _register_snapshot(sub)
    _register_telemetry(sub)

    return parser


_DISPATCH = {
    "doctor": run_doctor,
    "schema": run_schema,
    "fmt": run_fmt,
    "backends": run_backends,
    "shape-providers": run_shape_providers,
    "probe-providers": run_probe_providers,
    "probe-blender": run_probe_blender,
    "bridge": run_bridge,
    "test": run_test,
    "bench": run_bench,
    "audit": run_audit,
    "explain": run_explain,
    "explain-fit": run_explain_fit,
    "inspect-blend": run_inspect_blend,
    "inspect": run_inspect,
    "serve": run_serve,
    "render-fixture": run_render_fixture,
    "bake-audit": run_bake_audit,
    "export-blend": run_export_blend,
    "diff-asset": run_diff_asset,
    "library": run_library,
    "patch": run_patch,
    "parse": run_parse,
    "normalize": run_normalize,
    "fit": run_fit,
    "check": run_check,
    "plan": run_plan,
    "surface-plan": run_surface_plan,
    "materialize": run_materialize,
    "surface-build": run_surface,
    "surface-validate": run_surface,
    "surface-repair": run_surface,
    "build": run_build,
    "cache": run_cache,
    "diff": run_diff,
    "ref": run_ref,
    "snapshot": run_snapshot,
    "publish": run_publish,
    "telemetry": run_telemetry,
    "render-eval": run_render_eval,
    "adapt": run_mode_build,
    "assemble": run_mode_build,
    "reconstruct": run_mode_build,
}


def main() -> None:
    """Main.
    """
    import os as _os

    parser = _build_parser()
    args = parser.parse_args()
    if getattr(args, "strict_prompt_injection", False):
        _os.environ["LATHE_STRICT_PROMPT_INJECTION"] = "1"
    handler = _DISPATCH.get(args.cmd)
    if handler is None:
        raise SystemExit(2)
    handler(args)


if __name__ == "__main__":
    main()
