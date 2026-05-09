"""``lathe quick`` subcommand: 30-60s preview build (no bakes, no LODs, no validation).

Runs the minimal subset ``shape -> topology -> uv -> surface(skip_bakes) ->
multi-part GLB``. Targets ``<60s`` on hero assets vs. ~25 min for the full
``lathe build`` pipeline. Inspired by ForgeCAD's ``forgecad render`` workflow.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..errors import ShapeProviderError
from ..runtime_config import apply_cli_overrides, load_runtime_config
from ._common import _dump, _emit_error
from .build_cmd import _build_failed_payload, _guarded_out_root

_LOG = logging.getLogger(__name__)


def register(sub: Any) -> None:
    """Register the ``quick`` subcommand with the CLI argument parser."""
    parser = sub.add_parser(
        "quick",
        help="Fast-preview build: shape -> topology -> uv -> surface (no bakes) -> GLB",
        description=(
            "Run the minimal pipeline subset and emit a multi-part .glb. "
            "Skips execution, rig, interfaces, physics, optimize, validate, "
            "package, and repair. Targets <60s wall-clock vs. the full "
            "build's ~25 min."
        ),
    )
    parser.add_argument("file")
    parser.add_argument("name")
    parser.add_argument(
        "--out",
        required=True,
        help="Path to write the preview .glb (e.g. chest_preview.glb)",
    )
    parser.add_argument(
        "--render",
        default=None,
        help=(
            "Optional path for a turntable preview .png. Best-effort: "
            "skips silently if no GL stack is available."
        ),
    )
    parser.add_argument(
        "--runtime-config",
        default=None,
        help="Optional runtime config JSON file (same schema as `lathe build`)",
    )
    parser.add_argument(
        "--shape-provider",
        default=None,
        help="Override the shape provider adapter",
    )
    parser.add_argument(
        "--execution-profile",
        default=None,
        help="Override the resolved V1.3 execution profile",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help=(
            "Bypass the quick-preview cache: run every stage even when the "
            "source + runtime config are unchanged."
        ),
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help=(
            "Clear every cached quick-preview entry (across all assets) "
            "before running. Useful after a parser/normalizer change you "
            "expect the cache key not to capture."
        ),
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=None,
        help=(
            "Override build.shape.candidates for this run (transient). "
            "Forces a smaller candidate-search width than the asset declares; "
            "trades quality for cold-build wall-clock. Use '--candidates 1' "
            "for the fastest cold preview."
        ),
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help=(
            "Zero out space.select.best_of for this run (transient). Combined "
            "with --candidates 1, collapses the shape candidate sweep to a "
            "single first-emitted candidate. Lower quality, fastest cold loop."
        ),
    )


def run_quick(args: Any) -> None:
    """Execute the ``lathe quick`` subcommand."""
    from ..executor import BuildError, clear_quick_cache, quick_build_asset
    from ..parser import parse_file

    out_glb = Path(args.out).resolve()
    if out_glb.suffix.lower() != ".glb":
        _emit_error(
            "lathe.cli.quick.invalid_out",
            f"--out must end in .glb (got {out_glb.name!r})",
            "Pass a path ending in .glb, e.g. --out chest_preview.glb",
            exit_code=2,
            source_path=str(out_glb),
        )

    candidates_override = getattr(args, "candidates", None)
    no_search = bool(getattr(args, "no_search", False))
    if candidates_override is not None and candidates_override < 1:
        _emit_error(
            "lathe.cli.quick.invalid_candidates",
            f"--candidates must be >= 1 (got {candidates_override})",
            "Pass an integer >= 1, e.g. --candidates 1 for fastest cold preview.",
            exit_code=2,
            source_path=str(out_glb),
        )
    shape_overrides: dict[str, Any] = {}
    if candidates_override is not None:
        shape_overrides["candidates"] = int(candidates_override)
    if no_search:
        shape_overrides["no_search"] = True
    if candidates_override is not None and candidates_override < 3:
        print(
            f"lathe quick: WARN running with --candidates {candidates_override}, "
            "output may be lower quality (search-width sacrificed for speed).",
            file=sys.stderr,
        )

    cleared_count: int | None = None
    if getattr(args, "clear_cache", False):
        cleared_count = clear_quick_cache()

    # Quick stage directory lives next to the output GLB. We feed the
    # path-guard a relative form (it rejects absolute strings) and
    # join the asset name as the build's per-asset out_dir.
    stage_root_rel = f".{out_glb.stem}_quick_stage"
    stage_root_arg = _guarded_out_root(stage_root_rel)
    stage_out_dir = stage_root_arg / args.name

    program = parse_file(Path(args.file))
    runtime_config = (
        load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    )
    runtime_config = apply_cli_overrides(
        runtime_config,
        shape_provider=args.shape_provider,
    )

    use_cache = not getattr(args, "no_cache", False)
    wall_t0 = time.monotonic()
    try:
        report = quick_build_asset(
            program,
            args.name,
            stage_out_dir,
            glb_path=out_glb,
            runtime_config=runtime_config,
            execution_profile_override=args.execution_profile,
            use_cache=use_cache,
            shape_overrides=shape_overrides or None,
        )
    except BuildError as exc:
        _dump(_build_failed_payload("lathe.cli.quick.build_failed", str(exc), exc.diagnostics))
        raise SystemExit(1) from exc
    except ShapeProviderError as exc:
        _dump(
            _build_failed_payload(
                "lathe.cli.quick.provider_failed",
                str(exc),
                [
                    {
                        "code": exc.code,
                        "severity": "error",
                        "message": str(exc),
                        "provider_id": exc.provider_id,
                        "details": exc.details,
                    }
                ],
            )
        )
        raise SystemExit(1) from exc

    wall_clock_s = round(time.monotonic() - wall_t0, 3)

    render_status: dict[str, Any] = {"requested": False, "ok": False, "path": None}
    if args.render:
        from ._quick_render import render_turntable

        render_status["requested"] = True
        png_path = Path(args.render).resolve()
        try:
            ok = render_turntable(out_glb, png_path)
        except Exception as exc:
            _LOG.info("lathe.cli.quick.render.unexpected_error: %s", exc)
            ok = False
        render_status["ok"] = bool(ok)
        render_status["path"] = str(png_path) if ok else None
        if not ok:
            print(
                "lathe quick: render skipped (no GL backend available); GLB only.",
                file=sys.stderr,
            )

    payload = {
        "ok": True,
        "asset": report["asset"],
        "glb_path": report["glb_path"],
        "part_count": report["part_count"],
        "face_count": report["face_count"],
        "vertex_count": report["vertex_count"],
        "stage_timings_s": report["stage_timings_s"],
        "wall_clock_s": wall_clock_s,
        "cache": {
            "enabled": use_cache,
            "hit": bool(report.get("cache_hit", False)),
            "cleared_entries": cleared_count,
        },
        "render": render_status,
        "stage_dir": report["out_dir"],
        "stage_bundles": report["stage_bundles"],
    }
    print(json.dumps(payload, indent=2, sort_keys=False))
