"""``lathe surface`` subcommand: V1.2 surface-stage helpers."""

from __future__ import annotations

from pathlib import Path

from ..providers.errors import ShapeProviderError
from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump


def run_surface(args) -> None:
    """Run surface.

    Args:
        args: args argument.
    """
    from ..executor import BuildError, build_surface_stage, repair_surface_stage, validate_surface_stage
    from ..parser import parse_file

    program = parse_file(Path(args.file))
    out_root = Path(args.out)
    out_dir = out_root / args.name
    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    runtime_config = apply_cli_overrides(
        runtime_config,
        allow_fallback=True if getattr(args, "allow_fallback", False) else None,
        codex_imagegen=args.codex_imagegen,
    )
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
