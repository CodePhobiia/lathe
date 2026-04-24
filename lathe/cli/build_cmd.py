from __future__ import annotations

import json
from pathlib import Path

from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump


def run_build(args) -> None:
    from ..executor import BuildError, build_asset
    from ..parser import parse_file

    program = parse_file(Path(args.file))
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


def run_render_eval(args) -> None:
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
