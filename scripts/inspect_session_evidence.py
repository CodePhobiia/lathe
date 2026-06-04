"""Session-evidence inspector for the visible-artifact goal.

Reads build outputs in ``dist_session_evidence/<asset>/`` and reports
exactly the criteria the session goal requires:

  - build_report.json exists + score
  - shape stage: shape_source == "procedural_synthesizer"
                 synthesizer_trace.family_dispatch_used is False
                 synthesizer_trace.attempted_via == "procedural_engine"
  - package stage: kernel_edge_treatment_count > 0
  - validate stage: edge_treatment_coverage diagnostic absent or non-critical
  - topology / package: face_count >= 200
  - previews/turntable.png exists and has non-trivial size

Run with::

  python scripts/inspect_session_evidence.py dist_session_evidence/industrial_crate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _ok(label: str, value: object, threshold: object = None) -> str:
    return f"  PASS  {label}: {value!r}" + (f" (threshold {threshold!r})" if threshold else "")


def _fail(label: str, value: object, expected: object) -> str:
    return f"  FAIL  {label}: got {value!r}, expected {expected!r}"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - inspector-only
        print(f"  ERROR reading {path}: {exc}")
        return None


def inspect(asset_dir: Path) -> bool:
    print(f"=== Evidence inspection: {asset_dir} ===")
    overall_ok = True

    build_report = _load(asset_dir / "build_report.json")
    if build_report is None:
        print(f"  FAIL  build_report.json missing at {asset_dir / 'build_report.json'}")
        return False
    print(_ok("build_report.json present", True))
    print(_ok("score", build_report.get("score")))
    print(_ok("threshold", build_report.get("threshold")))

    shape_bundle = _load(asset_dir / "stages" / "shape" / "bundle.json")
    if shape_bundle is None:
        print("  FAIL  stages/shape/bundle.json missing")
        return False
    report = shape_bundle.get("report", {}) or {}
    shape_source = report.get("shape_source")
    if shape_source == "procedural_synthesizer":
        print(_ok("shape_source", shape_source))
    else:
        print(_fail("shape_source", shape_source, "procedural_synthesizer"))
        overall_ok = False
    trace = report.get("synthesizer_trace") or {}
    fdu = trace.get("family_dispatch_used")
    if fdu is False:
        print(_ok("synthesizer_trace.family_dispatch_used", fdu))
    else:
        print(_fail("synthesizer_trace.family_dispatch_used", fdu, False))
        overall_ok = False
    av = trace.get("attempted_via")
    if av == "procedural_engine":
        print(_ok("synthesizer_trace.attempted_via", av))
    else:
        print(_fail("synthesizer_trace.attempted_via", av, "procedural_engine"))
        overall_ok = False
    nodes = report.get("synthesized_graph_nodes") or []
    print(_ok("synthesized_graph_nodes count", len(nodes)))
    primitives = report.get("primitives_used") or []
    print(_ok("primitives_used", primitives))

    package_bundle = _load(asset_dir / "stages" / "package" / "bundle.json")
    if package_bundle is not None:
        kec = package_bundle.get("kernel_edge_treatment_count", 0)
        if isinstance(kec, int) and kec > 0:
            print(_ok("kernel_edge_treatment_count", kec, threshold=">0"))
        else:
            print(_fail("kernel_edge_treatment_count", kec, ">0"))
            overall_ok = False
        # Face count surfaces in the package bundle's mesh stats too.
        for key in ("face_count", "mesh_face_count"):
            if key in package_bundle:
                print(_ok(f"package.{key}", package_bundle[key]))
                break
    else:
        print("  WARN  stages/package/bundle.json missing")
        overall_ok = False

    topology_bundle = _load(asset_dir / "stages" / "topology" / "bundle.json")
    if topology_bundle is not None:
        # Look for face_count anywhere in the topology bundle (different
        # shape backends record it under different keys).
        face_count = (
            topology_bundle.get("face_count")
            or topology_bundle.get("mesh_face_count")
            or (topology_bundle.get("mesh") or {}).get("face_count")
            or (topology_bundle.get("runtime_mesh") or {}).get("face_count")
        )
        if isinstance(face_count, int) and face_count >= 200:
            print(_ok("topology face_count", face_count, threshold=">=200"))
        else:
            print(_fail("topology face_count", face_count, ">=200"))
            overall_ok = False

    validate_report = _load(asset_dir / "stages" / "validate" / "report.json")
    if validate_report is not None:
        diags = validate_report.get("diagnostics") or []
        edge_diags = [d for d in diags if "edge_treatment" in str(d.get("code", ""))]
        if not edge_diags:
            print(_ok("validate edge_treatment diagnostics", "none"))
        else:
            print(_fail("validate edge_treatment diagnostics", edge_diags, "none"))
            overall_ok = False
        print(_ok("validate score", validate_report.get("score")))

    turntable_png = asset_dir / "stages" / "package" / "previews" / "turntable.png"
    if turntable_png.is_file():
        size = turntable_png.stat().st_size
        if size > 1024:
            print(_ok("turntable.png", f"{size} bytes", threshold=">1KB"))
        else:
            print(_fail("turntable.png", f"{size} bytes", ">1KB"))
            overall_ok = False
    else:
        print(_fail("turntable.png", "MISSING", "exists"))
        overall_ok = False

    glb_path = build_report.get("outputs", {}).get("glb")
    if glb_path:
        glb_full = asset_dir / glb_path if not Path(glb_path).is_absolute() else Path(glb_path)
        if glb_full.is_file():
            size = glb_full.stat().st_size
            print(_ok("glb output", f"{size} bytes at {glb_full}"))
        else:
            print(_fail("glb output", "missing on disk", "exists"))
            overall_ok = False

    print()
    print("=" * 60)
    print(f"  VERDICT: {'PASS' if overall_ok else 'FAIL'}")
    print("=" * 60)
    return overall_ok


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: inspect_session_evidence.py <asset_dir>")
        return 2
    asset_dir = Path(argv[1])
    if not asset_dir.is_dir():
        print(f"not a directory: {asset_dir}")
        return 2
    return 0 if inspect(asset_dir) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
