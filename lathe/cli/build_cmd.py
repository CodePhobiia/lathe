"""``lathe build`` subcommand: run the full pipeline and emit a bundle."""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

from ..paths import PathGuardError, safe_resolve
from ..providers.errors import ShapeProviderError
from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump, _emit_error


def _guarded_out_root(raw_out: str | Path) -> Path:
    """Apply ``safe_resolve`` to a user-supplied ``--out`` target (SEC-1).

    Bypassed when ``LATHE_ALLOW_EXTERNAL_OUT=1`` — the escape hatch for
    CI / tooling that legitimately writes outside cwd. Emits a CLI
    error (exit code 2) when rejected.
    """
    if os.environ.get("LATHE_ALLOW_EXTERNAL_OUT") == "1":
        return Path(raw_out)
    try:
        return safe_resolve(Path.cwd(), raw_out)
    except PathGuardError as exc:
        _emit_error(
            "lathe.cli.build.unsafe_out_path",
            f"--out rejected by path guard: {exc}",
            "Pick a path under the current working directory, or set "
            "LATHE_ALLOW_EXTERNAL_OUT=1 to bypass.",
            exit_code=2,
        )
        raise SystemExit(2) from exc


def _resolve_report_format(args) -> str:
    """Resolve ``--report`` or pick a default based on TTY status."""

    explicit = getattr(args, "report", None)
    if explicit:
        return str(explicit).lower()
    return "terminal" if sys.stdout.isatty() else "json"


def _emit_report(report: dict, out_dir: Path, fmt: str, *, deterministic: bool = False) -> None:
    """Render the resolved report format after a successful build."""

    from ..reports import (
        canonicalize_report,
        render_html_report,
        render_terminal_report,
        write_report,
    )

    payload = canonicalize_report(report) if deterministic else report

    if fmt == "json":
        if deterministic:
            write_report(report, out_dir, "json", deterministic=True)
            print(json.dumps(payload, sort_keys=True, separators=(",", ": "), ensure_ascii=False))
        else:
            _dump(payload)
        return
    if fmt == "html":
        path = write_report(report, out_dir, "html", deterministic=deterministic)
        if deterministic:
            print(json.dumps(payload, sort_keys=True, separators=(",", ": "), ensure_ascii=False))
        else:
            _dump(payload)
        print(f"HTML report: {path}", file=sys.stderr)
        return
    if fmt == "terminal":
        print(render_terminal_report(payload))
        return
    # Unknown -- structured error via _emit_error.
    _emit_error(
        "lathe.cli.build.invalid_report_format",
        f"Unknown --report format: {fmt!r}",
        "Use one of: terminal, html, json.",
        exit_code=2,
    )
    # Unused but keeps linters happy about unused import
    _ = render_html_report


def _resolve_strict_flag(args) -> bool | None:
    """BL-37 (Plan 08 Phase 8): normalize ``--strict-shape-provider`` (deprecated)
    and any future ``--strict`` flag into a single strict override.

    ``--strict-shape-provider`` is preserved as a back-compat alias and emits
    a ``DeprecationWarning`` when used; callers should migrate to the Phase 11
    V0.2.0 default flip path (where strict becomes the default for learned
    providers).
    """
    if getattr(args, "strict_shape_provider", False):
        warnings.warn(
            "--strict-shape-provider is a back-compat alias; pass --strict in V0.2+.",
            DeprecationWarning,
            stacklevel=2,
        )
        return True
    return None


def run_build(args) -> None:
    """Run build.

    Args:
        args: args argument.
    """
    from ..executor import BuildError, build_asset
    from ..parser import parse_file

    program = parse_file(Path(args.file))
    out_root = _guarded_out_root(args.out)
    out_dir = out_root / args.name
    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    runtime_config = apply_cli_overrides(
        runtime_config,
        shape_provider=args.shape_provider,
        shape_strict=_resolve_strict_flag(args),
        allow_fallback=True if getattr(args, "allow_fallback", False) else None,
        codex_imagegen=args.codex_imagegen,
    )
    try:
        report = build_asset(
            program,
            args.name,
            out_dir,
            runtime_config=runtime_config,
            execution_profile_override=args.execution_profile,
        )
        # BL-33 (Plan 08 Phase 3): ``report["repair_rounds"]`` is populated
        # by BuildExecutor.build via run_repair_loop() when the validate
        # stage did not certify on the first pass. Empty list on hero
        # short-circuit paths.
        report.setdefault("repair_rounds", [])
        publish_target = getattr(args, "publish", None)
        if publish_target:
            from ..publish import get_driver as _get_publish_driver

            publish_cfg = dict((runtime_config or {}).get("publish") or {})
            publish_cfg["target"] = publish_target
            try:
                driver = _get_publish_driver(str(publish_target))
                publish_result = driver.publish(out_dir, publish_cfg)
                report = dict(report)
                report["publish"] = {
                    "ok": True,
                    "driver": publish_result.get("driver", str(publish_target)),
                    "manifest_uri": publish_result.get("manifest_uri"),
                    "signature_uri": publish_result.get("signature_uri"),
                }
            except (ValueError, RuntimeError) as publish_exc:
                report = dict(report)
                report["publish"] = {
                    "ok": False,
                    "driver": str(publish_target),
                    "message": str(publish_exc),
                }
        _emit_report(
            report,
            out_dir,
            _resolve_report_format(args),
            deterministic=bool(getattr(args, "deterministic", False)),
        )
        try:
            from .. import telemetry as _telemetry

            _telemetry.emit_build_ping(report)
        except Exception:
            pass
    except BuildError as exc:
        payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
        _dump(payload)
        raise SystemExit(1) from exc
    except ShapeProviderError as exc:
        # BL-37 (Plan 08 Phase 8) exit-code contract: strict-mode provider
        # blocks fallback -> non-zero exit with diagnostic
        # ``provider_fallback_blocked`` visible on stdout.
        payload = {
            "ok": False,
            "message": str(exc),
            "diagnostics": [
                {
                    "code": exc.code,
                    "provider_id": exc.provider_id,
                    "details": exc.details,
                }
            ],
        }
        _dump(payload)
        raise SystemExit(1) from exc


def run_render_eval(args) -> None:
    """Run render eval.

    Args:
        args: args argument.
    """
    from ..executor import BuildError, build_asset
    from ..parser import parse_file

    program = parse_file(Path(args.file))
    out_root = _guarded_out_root(args.out)
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
        # JSON ingress — internal controlled payload from our own execution stage bundle just emitted by build_asset above; safe without schema validation.
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


def run_mode_build(args) -> None:
    """Run mode build.

    Args:
        args: args argument.
    """
    from ..executor import BuildError, build_asset
    from ..parser import parse_file
    from ..resolver import materialize_asset

    program = parse_file(Path(args.file))
    effective = materialize_asset(program, args.name)
    expected_mode = args.cmd
    actual_mode = str(effective.get("build", {}).get("shape", {}).get("mode", "generate"))
    if actual_mode != expected_mode:
        raise SystemExit(f"Asset '{args.name}' is configured for shape.mode={actual_mode}, not {expected_mode}")
    out_root = _guarded_out_root(args.out)
    out_dir = out_root / args.name
    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    try:
        _dump(build_asset(program, args.name, out_dir, runtime_config=runtime_config))
    except BuildError as exc:
        payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
        _dump(payload)
        raise SystemExit(1) from exc
