"""Lathe CLI package.

Exposes the ``python -m lathe.cli`` entry point and the individual
``*_cmd`` modules that implement each subcommand.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from collections.abc import Callable
from typing import Any

from ..errors import BuildError, LatheError, LatheParseError, RuntimeConfigError
from ._common import _emit_error

__all__ = ["collect_doctor_report", "dump_doctor_json", "format_doctor_report", "main"]

SUPPORTED_SHELLS = ("bash", "zsh", "powershell")


def collect_doctor_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Lazy compatibility wrapper for callers importing from ``lathe.cli``."""
    from ..doctor import collect_doctor_report as _collect_doctor_report

    return _collect_doctor_report(*args, **kwargs)


def dump_doctor_json(*args: Any, **kwargs: Any) -> str:
    """Lazy compatibility wrapper for callers importing from ``lathe.cli``."""
    from ..doctor import dump_doctor_json as _dump_doctor_json

    return _dump_doctor_json(*args, **kwargs)


def format_doctor_report(*args: Any, **kwargs: Any) -> str:
    """Lazy compatibility wrapper for callers importing from ``lathe.cli``."""
    from ..doctor import format_doctor_report as _format_doctor_report

    return _format_doctor_report(*args, **kwargs)


def _run_register(module_name: str, sub: argparse._SubParsersAction) -> None:
    module = importlib.import_module(f".{module_name}", package=__package__)
    module.register(sub)


def _wants_json_error(args: argparse.Namespace) -> bool:
    return getattr(args, "report", None) == "json"


def _source_path_for_error(args: argparse.Namespace, exc: BaseException) -> str | None:
    if isinstance(exc, RuntimeConfigError):
        runtime_config = getattr(args, "runtime_config", None)
        return str(runtime_config) if runtime_config else None
    source_file = getattr(args, "file", None)
    return str(source_file) if source_file else None


def _lathe_error_code(exc: LatheError) -> str:
    if isinstance(exc, RuntimeConfigError):
        return "lathe.cli.runtime_config_error"
    if isinstance(exc, LatheParseError):
        return "lathe.cli.parse_error"
    if isinstance(exc, BuildError) and exc.diagnostics:
        code = exc.diagnostics[0].get("code")
        if isinstance(code, str) and code:
            return code
    return "lathe.cli.error"


class _LatheArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with Lathe's actionable error footer."""

    def add_subparsers(self, *args, **kwargs):
        kwargs.setdefault("parser_class", type(self))
        return super().add_subparsers(*args, **kwargs)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"lathe usage error [lathe.cli.usage]: {message}", file=sys.stderr)
        print(
            f"  Next step: Run `{self.prog} --help` for the supported arguments.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _build_parser() -> argparse.ArgumentParser:
    parser = _LatheArgumentParser(prog="lathe", description="Lathe 3D asset compiler/runtime")
    parser.add_argument(
        "--debug-traceback",
        action="store_true",
        help="Show Python tracebacks for unexpected CLI failures. Also settable via LATHE_DEBUG_TRACEBACK=1.",
    )
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
    p_fmt.add_argument(
        "files",
        nargs="*",
        help="Files or glob patterns (default: examples/*.lth)",
    )
    p_fmt.add_argument(
        "--check",
        action="store_true",
        help="Don't write; exit non-zero if any file would change",
    )
    p_fmt.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print a unified diff without writing",
    )
    p_fmt.add_argument(
        "--stdout",
        action="store_true",
        help="Read a single file (or stdin) and write canonical output to stdout",
    )

    sub.add_parser("schema", help="Emit the normalized AST JSON schema")
    sub.add_parser("backends", help="List builtin backend contracts and stacks")
    sub.add_parser("shape-providers", help="List available shape provider adapters")

    p_completions = sub.add_parser(
        "completions",
        help="Emit static shell completion scripts",
    )
    p_completions.add_argument(
        "shell",
        choices=SUPPORTED_SHELLS,
        help="Shell completion format to emit",
    )
    p_completions.add_argument(
        "--program",
        default="lathe",
        help="Command name to register in the generated script (default: lathe)",
    )
    p_completions.set_defaults(_completion_parser=parser)

    p_probe = sub.add_parser(
        "probe-providers",
        help="Probe shape provider availability in the current runtime",
    )
    p_probe.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")

    p_doctor = sub.add_parser(
        "doctor",
        help="Inspect the local Lathe environment and backend/provider availability",
    )
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
    p_plan.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved V1.3 execution profile",
    )

    p_mat = sub.add_parser("materialize", help="Materialize one asset or variant after uses and patches")
    p_mat.add_argument("file")
    p_mat.add_argument("name")
    p_mat.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved V1.3 execution profile",
    )

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
    p_build.add_argument(
        "--shape-provider",
        default=None,
        help="Override the shape provider adapter (for example: hunyuan2_1_http or vggt_local)",
    )
    p_build.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of falling back when the selected shape provider is unavailable or errors.",
    )
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
    p_build.add_argument(
        "--codex-imagegen",
        choices=["auto", "fallback", "emit", "consume"],
        default=None,
        help="Codex-operated imagegen handoff mode for V1.2 surfaces",
    )
    p_build.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved V1.3 execution profile",
    )
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

    p_probe_blender = sub.add_parser(
        "probe-blender",
        help="Probe Blender availability and V1.3 execution capabilities",
    )
    p_probe_blender.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")

    p_export_blend = sub.add_parser(
        "export-blend",
        help="Report or copy the retained .blend artifact for a completed build",
    )
    p_export_blend.add_argument("build_dir")
    p_export_blend.add_argument(
        "--out",
        default=None,
        help="Optional destination path for the exported .blend",
    )

    p_inspect_blend = sub.add_parser(
        "inspect-blend",
        help="Inspect the retained V1.3 .blend artifact summary for a completed build",
    )
    p_inspect_blend.add_argument("build_dir")

    p_render_eval = sub.add_parser("render-eval", help="Build an asset and emit V1.3 render-eval evidence")
    p_render_eval.add_argument("file")
    p_render_eval.add_argument("name")
    p_render_eval.add_argument("--out", default="dist")
    p_render_eval.add_argument("--runtime-config", default=None)
    p_render_eval.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved V1.3 execution profile",
    )

    p_bridge = sub.add_parser("bridge", help="Operate on V1.3.1 Lathe-Blender bridge plans and diagnostics")
    bridge_sub = p_bridge.add_subparsers(dest="bridge_cmd", required=True)
    p_bridge_doctor = bridge_sub.add_parser("doctor", help="Probe V1.3.1 bridge/tool-plane readiness")
    p_bridge_doctor.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_bridge_plan = bridge_sub.add_parser("plan", help="Emit a V1.3.1 typed bridge plan for an asset")
    p_bridge_plan.add_argument("file")
    p_bridge_plan.add_argument("name")
    p_bridge_plan.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p_bridge_plan.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved execution profile",
    )

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

    p_render_fixture = sub.add_parser(
        "render-fixture",
        help="Report render-fixture evidence from a completed build",
    )
    p_render_fixture.add_argument("build_dir")

    p_bake_audit = sub.add_parser(
        "bake-audit",
        help="Report bake evidence and missing bake diagnostics from a completed build",
    )
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
    p_surface_build.add_argument(
        "--codex-imagegen",
        choices=["auto", "fallback", "emit", "consume"],
        default=None,
    )

    p_surface_validate = sub.add_parser("surface-validate", help="Evaluate only V1.2 surface outputs")
    p_surface_validate.add_argument("file")
    p_surface_validate.add_argument("name")
    p_surface_validate.add_argument("--out", default="dist")
    p_surface_validate.add_argument("--runtime-config", default=None)
    p_surface_validate.add_argument(
        "--codex-imagegen",
        choices=["auto", "fallback", "emit", "consume"],
        default=None,
    )

    p_surface_repair = sub.add_parser("surface-repair", help="Attempt V1.2 zone-local surface repair")
    p_surface_repair.add_argument("file")
    p_surface_repair.add_argument("name")
    p_surface_repair.add_argument("--out", default="dist")
    p_surface_repair.add_argument("--runtime-config", default=None)
    p_surface_repair.add_argument(
        "--codex-imagegen",
        choices=["auto", "fallback", "emit", "consume"],
        default=None,
    )

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

    p_audit = sub.add_parser(
        "audit",
        help="Run benchmark/style of workspace audit for the current Lathe repo",
    )
    p_audit.add_argument("--root", default=".", help="Workspace root (default: current directory)")

    p_explain = sub.add_parser("explain", help="Explain why a build passed, failed, or selected a candidate")
    p_explain.add_argument("build_dir", help="Build directory containing build_report.json and stage outputs")

    p_explain_fit = sub.add_parser(
        "explain-fit",
        help="Explain fit/reference/transfer inputs for a completed build",
    )
    p_explain_fit.add_argument("build_dir")

    p_diff_asset = sub.add_parser("diff-asset", help="Diff two materialized assets")
    p_diff_asset.add_argument("file_a")
    p_diff_asset.add_argument("name_a")
    p_diff_asset.add_argument("file_b")
    p_diff_asset.add_argument("name_b")

    p_patch = sub.add_parser("patch", help="Apply a semantic patch operation and emit normalized JSON")
    p_patch.add_argument("file")
    p_patch.add_argument(
        "--op",
        required=True,
        choices=[
            "add_component_to_family",
            "change_repair_policy",
            "update_material_palette",
            "widen_search_bounds",
            "freeze_dimension",
            "add_benchmark_fixture",
        ],
    )
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
        description=("Exit codes: 0 = ok (JSON on stdout); 2 = bad token (parse error); 3 = unresolved ref."),
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

    _run_register("cache_cmd", sub)
    _run_register("diff_cmd", sub)
    _run_register("publish_cmd", sub)
    _run_register("snapshot_cmd", sub)
    _run_register("telemetry_cmd", sub)
    _run_register("asset_quality_cmd", sub)
    _run_register("scene_cmd", sub)
    _run_register("wonder_cmd", sub)

    return parser


_DISPATCH: dict[str, str] = {
    "doctor": "doctor_cmd:run_doctor",
    "schema": "parse_cmd:run_schema",
    "fmt": "fmt_cmd:run_fmt",
    "backends": "doctor_cmd:run_backends",
    "shape-providers": "doctor_cmd:run_shape_providers",
    "completions": "completions_cmd:run_completions",
    "probe-providers": "doctor_cmd:run_probe_providers",
    "probe-blender": "doctor_cmd:run_probe_blender",
    "bridge": "bridge_cmd:run_bridge",
    "test": "test_cmd:run_test",
    "bench": "test_cmd:run_bench",
    "audit": "test_cmd:run_audit",
    "explain": "inspect_cmd:run_explain",
    "explain-fit": "inspect_cmd:run_explain_fit",
    "inspect-blend": "inspect_cmd:run_inspect_blend",
    "inspect": "inspect_cmd:run_inspect",
    "serve": "inspect_cmd:run_serve",
    "render-fixture": "inspect_cmd:run_render_fixture",
    "bake-audit": "inspect_cmd:run_bake_audit",
    "export-blend": "inspect_cmd:run_export_blend",
    "diff-asset": "materialize_cmd:run_diff_asset",
    "library": "library_cmd:run_library",
    "patch": "patch_cmd:run_patch",
    "parse": "parse_cmd:run_parse",
    "normalize": "parse_cmd:run_normalize",
    "fit": "plan_cmd:run_fit",
    "check": "check_cmd:run_check",
    "plan": "plan_cmd:run_plan",
    "surface-plan": "plan_cmd:run_surface_plan",
    "materialize": "materialize_cmd:run_materialize",
    "surface-build": "surface_cmd:run_surface",
    "surface-validate": "surface_cmd:run_surface",
    "surface-repair": "surface_cmd:run_surface",
    "build": "build_cmd:run_build",
    "cache": "cache_cmd:run_cache",
    "diff": "diff_cmd:run_diff",
    "ref": "ref_cmd:run_ref",
    "snapshot": "snapshot_cmd:run_snapshot",
    "publish": "publish_cmd:run_publish",
    "telemetry": "telemetry_cmd:run_telemetry",
    "asset-quality": "asset_quality_cmd:run_asset_quality",
    "scene": "scene_cmd:run_scene",
    "wonder": "wonder_cmd:run_wonder",
    "render-eval": "build_cmd:run_render_eval",
    "adapt": "build_cmd:run_mode_build",
    "assemble": "build_cmd:run_mode_build",
    "reconstruct": "build_cmd:run_mode_build",
}


def _load_handler(spec: str) -> Callable[[argparse.Namespace], None]:
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(f".{module_name}", package=__package__)
    return getattr(module, function_name)


def main() -> None:
    """Run the Lathe command-line entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    if getattr(args, "strict_prompt_injection", False):
        os.environ["LATHE_STRICT_PROMPT_INJECTION"] = "1"
    handler_spec = _DISPATCH.get(args.cmd)
    if handler_spec is None:
        raise SystemExit(2)
    debug_traceback = (
        getattr(args, "debug_traceback", False) or os.environ.get("LATHE_DEBUG_TRACEBACK") == "1"
    )
    try:
        handler = _load_handler(handler_spec)
        handler(args)
    except FileNotFoundError as exc:
        if debug_traceback:
            raise
        missing = str(exc.filename or exc)
        _emit_error(
            "lathe.cli.file_not_found",
            f"File not found: {missing}",
            "Check the path and rerun the command from the repository root.",
            exit_code=2,
            source_path=missing,
            json_mode=_wants_json_error(args),
        )
    except IsADirectoryError as exc:
        if debug_traceback:
            raise
        target = str(exc.filename or exc)
        _emit_error(
            "lathe.cli.expected_file",
            f"Expected a file but got a directory: {target}",
            "Pass a .lth source file or a supported JSON sidecar path.",
            exit_code=2,
            source_path=target,
            json_mode=_wants_json_error(args),
        )
    except PermissionError as exc:
        if debug_traceback:
            raise
        target = str(exc.filename or exc)
        _emit_error(
            "lathe.cli.permission_denied",
            f"Permission denied: {target}",
            "Check file permissions or choose an output/cache directory you can read and write.",
            exit_code=2,
            source_path=target,
            json_mode=_wants_json_error(args),
        )
    except LatheError as exc:
        if debug_traceback:
            raise
        _emit_error(
            _lathe_error_code(exc),
            str(exc),
            "Fix the reported Lathe input or configuration issue and rerun the command.",
            exit_code=1,
            source_path=_source_path_for_error(args, exc),
            json_mode=_wants_json_error(args),
        )
    except OSError as exc:
        if debug_traceback:
            raise
        output_path = getattr(args, "out", None) if getattr(args, "cmd", None) == "build" else None
        target = str(output_path or getattr(exc, "filename", None) or exc)
        _emit_error(
            "lathe.cli.io_error",
            str(exc),
            "Check the referenced path, filesystem permissions, and available disk space.",
            exit_code=1,
            source_path=target,
            json_mode=_wants_json_error(args),
        )


if __name__ == "__main__":
    main()
