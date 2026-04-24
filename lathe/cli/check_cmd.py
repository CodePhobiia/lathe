from __future__ import annotations

from pathlib import Path

from ._common import _dump


def run_check(args) -> None:
    from ..checker import check_program
    from ..parser import parse_file

    program = parse_file(Path(args.file))
    diagnostics = check_program(program)
    _dump({"ok": not any(d["severity"] == "error" for d in diagnostics), "diagnostics": diagnostics})
