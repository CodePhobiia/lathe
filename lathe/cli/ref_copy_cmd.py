"""``lathe ref copy <token> <target_path>`` — copy the referenced artifact (REF-12).

Supports:
  - whole-build or ``#asset.<id>`` / ``#variant.<id>`` → primary .glb
  - ``#part.<id>`` → part GLB fragment if one exists, else the whole-build .glb
  - ``#stage.<id>`` → that stage's bundle.json (or stage output mesh if present)

Exit 0 on success (copy performed), 2 on parse error, 3 on unresolved,
4 when the resolved entity has no copyable artifact.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from ..ref import RefParseError, parse_ref, resolve_ref


def _primary_glb(build_dir: Path) -> Path | None:
    report_path = build_dir / "build_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
        for out in report.get("outputs") or []:
            if isinstance(out, dict) and out.get("format") == "glb" and out.get("uri"):
                candidate = build_dir / str(out["uri"])
                if candidate.exists():
                    return candidate
    for candidate in (
        build_dir / "stages" / "package",
        build_dir / "stages" / "topology",
    ):
        if candidate.exists():
            for f in candidate.glob("*.glb"):
                return f
    return None


def _choose_source(build_dir: Path, node) -> Path | None:
    sel = node.selector
    if sel is None or sel.kind in {"asset", "variant"}:
        return _primary_glb(build_dir)
    if sel.kind == "stage":
        stage_dir = build_dir / "stages" / sel.id
        for cand in (stage_dir / "bundle.json", *stage_dir.glob("*.glb")):
            if cand.exists():
                return cand
        return None
    if sel.kind == "part":
        part_glb = build_dir / "stages" / "package" / f"part_{sel.id}.glb"
        if part_glb.exists():
            return part_glb
        return _primary_glb(build_dir)
    if sel.kind in {"face", "edge", "vertex"}:
        return None
    return None


def run_ref_copy(args) -> None:
    token = args.token
    try:
        node = parse_ref(token)
    except RefParseError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(2)
    repo_root = Path(getattr(args, "repo_root", None) or Path.cwd())
    result = resolve_ref(node, repo_root=repo_root)
    if not result.get("ok"):
        print(json.dumps({"ok": False, "ref": asdict(node), "resolution": result}, indent=2), file=sys.stderr)
        raise SystemExit(3)

    target_path = Path(result.get("target_path") or (repo_root / node.target))
    src = _choose_source(target_path, node)
    if src is None or not src.exists():
        print(json.dumps({
            "ok": False,
            "error": "no_copyable_artifact",
            "ref": asdict(node),
            "message": f"no glb/bundle found for {node.raw} in {target_path}",
        }, indent=2), file=sys.stderr)
        raise SystemExit(4)

    dest = Path(args.target_path)
    if dest.is_dir() or str(dest).endswith(("/", "\\")):
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(json.dumps({
        "ok": True,
        "ref": asdict(node),
        "source": str(src),
        "dest": str(dest),
    }, indent=2))
