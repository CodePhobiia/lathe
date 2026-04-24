from __future__ import annotations

from pathlib import Path

from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump


def run_surface(args) -> None:
    from ..executor import BuildError, build_surface_stage, repair_surface_stage, validate_surface_stage
    from ..parser import parse_file

    program = parse_file(Path(args.file))
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
