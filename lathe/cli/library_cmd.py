from __future__ import annotations

from pathlib import Path

from ._common import _dump


def run_library(args) -> None:
    from ..blender_execution import build_library_sync_manifest
    from ..parser import parse_file as _parse_file

    if args.library_cmd == "sync":
        program = _parse_file(Path(args.file))
        out_root = Path(args.out)
        out_dir = out_root / "library_sync"
        _dump(build_library_sync_manifest(program, out_dir))
        return
    raise SystemExit(2)
