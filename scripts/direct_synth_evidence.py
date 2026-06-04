"""Direct synth-only evidence path: bypass full pipeline, prove visible body.

The full ``lathe build`` and ``lathe quick`` paths are blocked by very slow
scipy MessageStream churn during shape stage on this machine. This script
runs only the shape stage (the part the goal cares about) and emits:

  - tmp_<asset>_synth_body.glb   : the authoritative mesh
  - tmp_<asset>_synth_body.png   : a turntable preview
  - tmp_<asset>_synth_trace.json : the synthesizer trace + signature

It proves the goal's criteria are satisfiable without waiting for the
slow topology / UV / surface stages.

Run with::

  .venv311/Scripts/python.exe scripts/direct_synth_evidence.py industrial_crate
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import trimesh  # type: ignore
from lathe import parser as lathe_parser
from lathe.asset_graph import asset_graph_from_asset
from lathe.asset_quality.procedural_synthesizer import synthesize_procedural_program
from lathe.normalizer import normalize
from lathe.resolver import resolve_asset
from lathe.shape.procedural_program_path import (
    compile_procedural_program_candidate,
    runtime_from_asset,
    synthesizer_eligible,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO_ROOT / "examples"


def _resolve_asset(lth_path: Path, asset_name: str) -> dict:
    """Parse, normalize, and resolve the named asset from a .lth file."""
    raw_ast = lathe_parser.parse_file(lth_path)
    program = normalize(raw_ast)
    return resolve_asset(program, asset_name)


def _render_turntable(mesh: trimesh.Trimesh, out_path: Path) -> bool:
    """Render the mesh to a PNG. Best-effort — returns False if no GL."""
    try:
        scene = mesh.scene()
        png_bytes = scene.save_image(resolution=(800, 600), visible=True)
        if png_bytes:
            out_path.write_bytes(png_bytes)
            return True
    except Exception as exc:  # pragma: no cover - render fallback
        print(f"  [render failed: {type(exc).__name__}: {exc}]")
    return False


def main(asset_name: str) -> int:
    lth_path = _EXAMPLES / f"{asset_name}.lth"
    if not lth_path.is_file():
        print(f"  no such file: {lth_path}")
        return 2

    print(f"=== Direct synth evidence for {asset_name} ===")
    print(f"  source: {lth_path}")

    asset = _resolve_asset(lth_path, asset_name)
    print(f"  resolved asset: family={asset.get('family', '?')}")

    asset_graph = asset_graph_from_asset(asset)
    print(f"  asset_graph: family={asset_graph.family}, parts={len(asset_graph.parts)}")

    eligible = synthesizer_eligible(asset, runtime_config={"provider": "auto"})
    print(f"  synthesizer_eligible: {eligible}")
    if not eligible:
        print("  FAIL: synth not eligible — auto-graph or family alias missing?")
        return 1

    synth_runtime = runtime_from_asset(asset)
    print("  running procedural_synthesizer...")
    synth_result = synthesize_procedural_program(asset, synth_runtime)
    print(
        f"  synth.trace: family_dispatch_used="
        f"{synth_result.trace.family_dispatch_used} "
        f"attempted_via={synth_result.trace.attempted_via!r} "
        f"entries={len(synth_result.trace.entries)} "
        f"synthesized_nodes={len(synth_result.synthesized_graph_nodes)}"
    )
    print(f"  shape_program.ops: {len(synth_result.shape_program.ops)}")

    print("  compiling shape via procedural_program candidate...")
    candidate = compile_procedural_program_candidate(
        asset_graph,
        synth_result,
        mode="generate",
        conditioning=None,
        runtime_config={"provider": "auto"},
        work_dir=None,
    )

    runtime_candidates = candidate.get("runtime_candidates") or []
    if not runtime_candidates:
        print("  FAIL: no runtime_candidate produced")
        return 1
    rc = runtime_candidates[0]
    mesh_ir = rc.get("meta", {}).get("mesh_ir", {})
    if not mesh_ir:
        print("  FAIL: no mesh_ir on runtime_candidate")
        return 1
    vertices = mesh_ir.get("vertices") or []
    faces = mesh_ir.get("faces") or []
    print(f"  mesh_ir: vertices={len(vertices)} faces={len(faces)}")

    # Build a trimesh from the mesh_ir for GLB + preview
    import numpy as np
    mesh = trimesh.Trimesh(
        vertices=np.array(vertices, dtype=float),
        faces=np.array(faces, dtype=int),
    )

    glb_path = _REPO_ROOT / f"tmp_{asset_name}_synth_body.glb"
    mesh.export(glb_path)
    print(f"  wrote GLB: {glb_path} ({glb_path.stat().st_size} bytes)")

    png_path = _REPO_ROOT / f"tmp_{asset_name}_synth_body.png"
    rendered = _render_turntable(mesh, png_path)
    if rendered and png_path.is_file():
        print(f"  wrote PNG: {png_path} ({png_path.stat().st_size} bytes)")
    else:
        print("  PNG: not rendered (GL stack unavailable)")

    trace_path = _REPO_ROOT / f"tmp_{asset_name}_synth_trace.json"
    integration_report = rc.get("meta", {}).get("integration_report", {})
    trace_path.write_text(
        json.dumps(
            {
                "asset_name": asset_name,
                "family": asset_graph.family,
                "synth_trace": synth_result.trace.to_dict(),
                "shape_assessment": rc.get("meta", {}).get("shape_assessment", {}),
                "synthesized_graph_nodes": [
                    dict(n) for n in synth_result.synthesized_graph_nodes
                ],
                "shape_program_op_count": len(synth_result.shape_program.ops),
                "mesh_face_count": len(faces),
                "mesh_vertex_count": len(vertices),
                "integration_report": integration_report,
                "primitives_used": rc.get("meta", {}).get("shape_assessment", {}).get(
                    "primitives_used", []
                ),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"  wrote trace: {trace_path}")

    # Goal verdict
    print()
    print("=== Goal criteria ===")
    fdu = synth_result.trace.family_dispatch_used
    av = synth_result.trace.attempted_via
    print(f"  family_dispatch_used: {fdu!r} (target: False) -> {'PASS' if fdu is False else 'FAIL'}")
    print(f"  attempted_via: {av!r} (target: procedural_engine) -> {'PASS' if av == 'procedural_engine' else 'FAIL'}")
    print(f"  mesh face_count: {len(faces)} (target: >=200) -> {'PASS' if len(faces) >= 200 else 'FAIL'}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: direct_synth_evidence.py <asset_name>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
