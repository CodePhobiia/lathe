"""GEO-1 benchmark harness: Lathe native kernel vs Manifold kernel.

Runs identical CSG scenes through both kernels and reports:
  - watertight rate
  - body-count stability across 3 rebuilds
  - triangle count
  - wall-clock
  - determinism hash (sha256 of triangle coords in canonical order)

Usage:
    python scripts/bench_geometry_kernel.py
    python scripts/bench_geometry_kernel.py --only courier_drone
    python scripts/bench_geometry_kernel.py --seed 7 --output docs/benchmarks/geometry_kernel_eval_CUSTOM.json

If manifold3d is not installed, the harness still profiles the Lathe
native kernel and records the absence in the output report.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lathe.asset_graph import build_asset_graph
from lathe.fidelity import infer_fidelity_profile
from lathe.geometry_kernel import fuse_shape_ir
from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.scaffold_compiler import compile_scaffold_candidates
from lathe.shape_ir import ShapeIR, ShapePrimitive

try:
    from lathe.adapters.manifold_kernel import ManifoldKernel, manifold_available
except ImportError:
    ManifoldKernel = None  # type: ignore[assignment]

    def manifold_available() -> bool:  # type: ignore[misc]
        return False


HEROES = ("courier_drone", "brassbound_chest", "mechanical_door")


def _canonical_triangle_hash(vertices: np.ndarray, faces: np.ndarray) -> str:
    """Deterministic hash over triangle coordinates.

    Each triangle is represented as a 9-float tuple of its vertex
    coordinates after rounding, then the full set is sorted to remove
    face-order nondeterminism.
    """
    if len(faces) == 0 or len(vertices) == 0:
        return "empty"
    tris = vertices[faces].reshape(-1, 9)
    tris = np.round(tris, decimals=6)
    ordered = np.asarray(sorted(tuple(row) for row in tris))
    digest = hashlib.sha256(ordered.tobytes()).hexdigest()
    return digest


def _load_shape_ir(hero: str, seed: int) -> tuple[ShapeIR, Any]:
    path = REPO_ROOT / "examples" / f"{hero}.lth"
    if not path.exists():
        raise FileNotFoundError(f"Hero source not found: {path}")
    program = parse_file(str(path))
    asset = materialize_asset(program, hero)
    graph = build_asset_graph(asset)
    result = compile_scaffold_candidates(
        graph,
        seed=seed,
        candidates_count=1,
        conditioning={},
        mode="generate",
    )
    shape_irs = result["shape_irs"]
    if not shape_irs:
        raise RuntimeError(f"No shape_ir compiled for hero {hero!r}")
    return shape_irs[0], graph


def _bench_lathe_native(shape_ir: ShapeIR, fidelity: Any) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for run in range(3):
        t0 = time.perf_counter()
        mesh_ir, report = fuse_shape_ir(shape_ir, fidelity)
        elapsed = time.perf_counter() - t0
        if mesh_ir is None:
            runs.append({
                "run": run,
                "status": "fallback",
                "report_mode": report.get("mode"),
                "elapsed_s": elapsed,
            })
            continue
        vertices = np.asarray(mesh_ir.vertices, dtype=np.float64)
        faces = np.asarray(mesh_ir.faces, dtype=np.int64)
        # Re-compute watertight via trimesh view without mutating mesh_ir.
        import trimesh
        tm = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        runs.append({
            "run": run,
            "status": "ok",
            "elapsed_s": elapsed,
            "num_tri": int(len(faces)),
            "num_vert": int(len(vertices)),
            "body_count": int(tm.body_count) if hasattr(tm, "body_count") else _body_count_trimesh(tm),
            "is_watertight": bool(tm.is_watertight),
            "hash": _canonical_triangle_hash(vertices, faces),
            "search_mode": report.get("search_mode"),
        })
    return _summarize("lathe_native_v1", runs)


def _body_count_trimesh(tm: Any) -> int:
    try:
        return len(tm.split(only_watertight=False))
    except Exception:
        return 0


def _bench_manifold(shape_ir: ShapeIR) -> dict[str, Any]:
    if ManifoldKernel is None or not manifold_available():
        return {
            "name": "lathe.geometry.manifold_v1",
            "available": False,
            "skipped_reason": "manifold3d not installed",
            "runs": [],
            "summary": {},
        }
    kernel = ManifoldKernel()
    runs: list[dict[str, Any]] = []
    for run in range(3):
        t0 = time.perf_counter()
        try:
            result = _fuse_via_manifold(kernel, shape_ir.primitives)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            runs.append({
                "run": run,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": elapsed,
            })
            continue
        elapsed = time.perf_counter() - t0
        if result.is_empty():
            runs.append({
                "run": run,
                "status": "empty",
                "elapsed_s": elapsed,
            })
            continue
        tm = kernel.to_trimesh(result)
        runs.append({
            "run": run,
            "status": "ok",
            "elapsed_s": elapsed,
            "num_tri": result.num_tri(),
            "num_vert": result.num_vert(),
            "body_count": kernel.body_count(result),
            "is_watertight": kernel.is_watertight(result),
            "hash": _canonical_triangle_hash(
                np.asarray(tm.vertices, dtype=np.float64),
                np.asarray(tm.faces, dtype=np.int64),
            ),
            "volume": float(result.volume()),
            "genus": result.genus(),
        })
    return _summarize("lathe.geometry.manifold_v1", runs)


def _fuse_via_manifold(kernel: "ManifoldKernel", primitives: list[ShapePrimitive]) -> Any:
    """Reduce a list of ShapePrimitive into a single Manifold via CSG.

    Primitives with blend_mode == "subtract" are applied as differences
    from the accumulated positive volume, matching the semantics used
    by `lathe/geometry_kernel.py::fuse_shape_ir`'s SDF branch.
    """
    acc = None
    for prim in primitives:
        mesh = _primitive_to_manifold(kernel, prim)
        if mesh is None:
            continue
        if acc is None:
            # A first subtract with no accumulator is effectively a no-op,
            # same as the SDF kernel ignoring negative-only input.
            if prim.blend_mode == "subtract":
                continue
            acc = mesh
            continue
        if prim.blend_mode == "subtract":
            acc = kernel.difference(acc, mesh)
        else:
            acc = kernel.union(acc, mesh)
    if acc is None:
        raise ValueError("no positive primitives to fuse")
    return acc


def _primitive_to_manifold(kernel: "ManifoldKernel", prim: ShapePrimitive) -> Any:
    if prim.primitive_type == "box":
        if prim.extents is None:
            return None
        return kernel.build_primitive("box", extents=prim.extents, center=prim.center)
    if prim.primitive_type == "cylinder":
        if prim.radius is None or prim.height is None:
            return None
        return kernel.build_primitive(
            "cylinder", radius=prim.radius, height=prim.height,
            axis=prim.axis, center=prim.center,
        )
    return None


def _summarize(name: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    ok_runs = [r for r in runs if r.get("status") == "ok"]
    watertight_rate = (
        sum(1 for r in ok_runs if r.get("is_watertight")) / len(ok_runs)
        if ok_runs else 0.0
    )
    body_counts = [r.get("body_count") for r in ok_runs]
    body_stable = len(set(body_counts)) <= 1 if body_counts else False
    hashes = [r.get("hash") for r in ok_runs]
    deterministic = len(set(hashes)) <= 1 if hashes else False
    mean_tri = (
        int(sum(r.get("num_tri", 0) for r in ok_runs) / len(ok_runs))
        if ok_runs else 0
    )
    mean_elapsed = (
        sum(r.get("elapsed_s", 0.0) for r in ok_runs) / len(ok_runs)
        if ok_runs else 0.0
    )
    summary = {
        "ok_run_count": len(ok_runs),
        "total_run_count": len(runs),
        "watertight_rate": watertight_rate,
        "body_count_stable": body_stable,
        "body_counts": body_counts,
        "deterministic": deterministic,
        "unique_hashes": sorted(set(hashes)) if hashes else [],
        "mean_triangles": mean_tri,
        "mean_wall_clock_s": mean_elapsed,
    }
    return {"name": name, "runs": runs, "summary": summary}


def run_bench(heroes: list[str], seed: int) -> dict[str, Any]:
    results: dict[str, Any] = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "seed": seed,
        "manifold3d_available": manifold_available(),
        "heroes": {},
    }
    for hero in heroes:
        print(f"[bench] hero={hero}", flush=True)
        try:
            shape_ir, graph = _load_shape_ir(hero, seed)
        except Exception as exc:
            print(f"  skip: {type(exc).__name__}: {exc}")
            results["heroes"][hero] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        primitive_count = len(shape_ir.primitives)
        print(f"  primitives: {primitive_count}")
        fidelity = infer_fidelity_profile(graph)
        native = _bench_lathe_native(shape_ir, fidelity)
        print(
            f"  native: watertight={native['summary']['watertight_rate']:.2f} "
            f"bodies={native['summary']['body_counts']} "
            f"deterministic={native['summary']['deterministic']}"
        )
        manifold = _bench_manifold(shape_ir)
        if manifold.get("available", True) and manifold.get("summary"):
            print(
                f"  manifold: watertight={manifold['summary']['watertight_rate']:.2f} "
                f"bodies={manifold['summary']['body_counts']} "
                f"deterministic={manifold['summary']['deterministic']}"
            )
        else:
            print(f"  manifold: skipped ({manifold.get('skipped_reason', 'n/a')})")
        results["heroes"][hero] = {
            "primitive_count": primitive_count,
            "family": shape_ir.family,
            "lathe_native_v1": native,
            "manifold_v1": manifold,
        }
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        help="Limit to a specific hero (repeatable). Default: all.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path. Defaults to docs/benchmarks/geometry_kernel_eval_<date>.json.",
    )
    args = parser.parse_args(argv)

    heroes = args.only if args.only else list(HEROES)
    report = run_bench(heroes, args.seed)

    if args.output:
        out_path = Path(args.output)
    else:
        date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
        out_path = REPO_ROOT / "docs" / "benchmarks" / f"geometry_kernel_eval_{date}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[bench] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
