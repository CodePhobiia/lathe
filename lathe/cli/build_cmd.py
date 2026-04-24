"""``lathe build`` subcommand: run the full pipeline and emit a bundle."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from ..providers.errors import ShapeProviderError
from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump


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
    out_root = Path(args.out)
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
        _dump(report)
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
    out_root = Path(args.out)
    out_dir = out_root / args.name
    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    try:
        _dump(build_asset(program, args.name, out_dir, runtime_config=runtime_config))
    except BuildError as exc:
        payload = {"ok": False, "message": str(exc), "diagnostics": exc.diagnostics}
        _dump(payload)
        raise SystemExit(1) from exc
