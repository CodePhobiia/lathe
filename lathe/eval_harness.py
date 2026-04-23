from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import trimesh

from .asset_graph import build_asset_graph
from .benchmarks import BENCHMARK_ROOT
from .executor import RuntimeMesh
from .executor import BuildError, build_asset
from .parser import parse_file
from .resolver import materialize_asset
from .scaffold_compiler import compile_scaffold_candidates
from .validators.semantic_quality import evaluate_semantic_quality
from .validators.visual_quality import evaluate_visual_quality


def load_benchmark_catalog() -> dict[str, Any]:
    return json.loads((BENCHMARK_ROOT / "catalog.json").read_text(encoding="utf-8"))


def _resolve_seed(seed: Any, asset_name: str) -> int:
    if isinstance(seed, int):
        return seed
    return sum(ord(ch) for ch in asset_name) % 100000


def _positive_scorecard(workspace: Path, benchmark: dict[str, Any]) -> dict[str, Any]:
    program = parse_file(workspace / benchmark["file"])
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / benchmark["asset"]
        report = build_asset(program, benchmark["asset"], out_dir)
        shape_bundle = json.loads((out_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
        validate_report = json.loads((out_dir / "stages" / "validate" / "report.json").read_text(encoding="utf-8"))
    return {
        "name": benchmark["name"],
        "asset": benchmark["asset"],
        "family": benchmark["family"],
        "ok": bool(report["certified"]),
        "score": report["score"],
        "threshold": report["threshold"],
        "blueprint_id": shape_bundle.get("blueprint_id"),
        "primitives_used": shape_bundle.get("primitives_used", []),
        "shared_primitives": bool(shape_bundle.get("primitives_used")),
        "shape_assessment": shape_bundle.get("shape_assessment", {}),
        "semantic_quality": validate_report.get("semantic_quality", {}),
        "visual_quality": validate_report.get("visual_quality", {}),
        "authoritative_candidate_reason": shape_bundle.get("authoritative_candidate_reason"),
    }


def _load_legacy_snapshot(workspace: Path, benchmark: dict[str, Any]) -> dict[str, Any]:
    if benchmark.get("snapshot"):
        return json.loads((BENCHMARK_ROOT / benchmark["snapshot"]).read_text(encoding="utf-8"))
    build_dir = workspace / benchmark["build_dir"]
    shape_bundle = json.loads((build_dir / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
    topology_bundle = json.loads((build_dir / "stages" / "topology" / "bundle.json").read_text(encoding="utf-8"))
    interfaces_bundle = json.loads((build_dir / "stages" / "interfaces" / "bundle.json").read_text(encoding="utf-8"))
    surface_bundle = json.loads((build_dir / "stages" / "surface" / "bundle.json").read_text(encoding="utf-8"))
    selected_id = shape_bundle["selected_candidate_id"]
    selected = next(item for item in shape_bundle["candidates"] if item["candidate_id"] == selected_id)
    topology_mesh_path = build_dir / topology_bundle.get("mesh_uri", "stages/topology/topology.glb")
    topology_runtime = None
    if topology_mesh_path.exists():
        try:
            mesh = trimesh.load(topology_mesh_path, force="mesh")
            default_part = topology_bundle.get("part_groups", [{}])[0].get("name", "mesh")
            topology_runtime = RuntimeMesh(
                mesh=mesh,
                face_parts=[default_part] * int(len(mesh.faces)),
                part_colors={default_part: (128, 128, 128)},
                units="cm",
            )
        except Exception:  # noqa: BLE001
            topology_runtime = None
    return {
        "asset": benchmark["asset"],
        "source_build": benchmark["build_dir"],
        "selection_notes": selected.get("selection_notes", []),
        "topology": topology_bundle,
        "interfaces": interfaces_bundle,
        "surface": surface_bundle,
        "topology_runtime": topology_runtime,
        "surface_stage_dir": build_dir / "stages" / "surface",
    }


def _negative_scorecard(workspace: Path, benchmark: dict[str, Any], *, expected_to_fail: bool = True) -> dict[str, Any]:
    program = parse_file(workspace / benchmark["file"])
    asset = materialize_asset(program, benchmark["asset"])
    asset_graph = build_asset_graph(asset)
    conditioning = {"reference_strength": 0.0, "image_refs": [], "material_refs": [], "mesh_refs": []}
    scaffold = compile_scaffold_candidates(
        asset_graph,
        seed=_resolve_seed(asset["build"]["shape"].get("seed", "auto"), benchmark["asset"]),
        candidates_count=1,
        conditioning=conditioning,
        mode=asset["build"]["shape"].get("mode", "generate"),
    )
    snapshot = _load_legacy_snapshot(workspace, benchmark)
    shape_bundle = {
        "shape_assessment": scaffold["shape_irs"][0].assessment,
        "scaffold_report": {
            "asset_graph": asset_graph.to_dict(),
            "signature": scaffold["shape_irs"][0].signature,
            "shape_assessment": scaffold["shape_irs"][0].assessment,
            "blueprint_id": scaffold["shape_irs"][0].blueprint_id,
        },
        "selected_candidate_id": "legacy_candidate_00",
        "candidates": [{"candidate_id": "legacy_candidate_00", "integration_report": {"mode": "constructive_fallback"}}],
    }
    if benchmark.get("build_dir"):
        build_shape = json.loads((workspace / benchmark["build_dir"] / "stages" / "shape" / "bundle.json").read_text(encoding="utf-8"))
        selected_id = build_shape["selected_candidate_id"]
        selected = next(item for item in build_shape["candidates"] if item["candidate_id"] == selected_id)
        shape_bundle["selected_candidate_id"] = selected_id
        shape_bundle["candidates"] = [selected]
    runtime = {
        "shape": {
            "bundle": shape_bundle
        },
        "topology": {"bundle": snapshot["topology"]},
        "interfaces": {"bundle": snapshot.get("interfaces", {"sockets": [], "anchors": []})},
    }
    if snapshot.get("topology_runtime") is not None:
        runtime["topology"]["runtime_mesh"] = snapshot["topology_runtime"]
    if snapshot.get("surface"):
        runtime["surface"] = {"bundle": snapshot["surface"], "stage_dir": snapshot.get("surface_stage_dir")}
    semantic = evaluate_semantic_quality(asset, runtime)
    runtime["semantic_quality"] = semantic
    visual = evaluate_visual_quality(asset, runtime)
    return {
        "name": benchmark["name"],
        "asset": benchmark["asset"],
        "ok": not (semantic["diagnostics"] or visual["diagnostics"]),
        "semantic_quality": semantic,
        "visual_quality": visual,
        "expected_to_fail": expected_to_fail,
        "selection_notes": snapshot.get("selection_notes", []),
        "source_build": snapshot.get("source_build"),
    }


def run_benchmark_suite(root: str | Path) -> dict[str, Any]:
    workspace = Path(root)
    catalog = load_benchmark_catalog()
    positive_results: list[dict[str, Any]] = []
    for benchmark in catalog.get("positive", []):
        try:
            positive_results.append(_positive_scorecard(workspace, benchmark))
        except BuildError as exc:
            positive_results.append(
                {
                    "name": benchmark["name"],
                    "asset": benchmark["asset"],
                    "family": benchmark["family"],
                    "ok": False,
                    "message": str(exc),
                    "diagnostics": exc.diagnostics,
                }
            )

    negative_results = [_negative_scorecard(workspace, benchmark, expected_to_fail=True) for benchmark in catalog.get("negative", [])]
    near_miss_results = [_negative_scorecard(workspace, benchmark, expected_to_fail=True) for benchmark in catalog.get("near_miss", [])]

    comparisons: list[dict[str, Any]] = []
    negative_by_asset = {item["asset"]: item for item in negative_results + near_miss_results}
    for positive in positive_results:
        legacy = negative_by_asset.get(positive["asset"])
        if legacy is None or not positive.get("semantic_quality"):
            continue
        before = legacy["semantic_quality"]["metrics"]
        after = positive["semantic_quality"]["metrics"]
        before_visual = legacy.get("visual_quality", {}).get("metrics", {})
        after_visual = positive.get("visual_quality", {}).get("metrics", {})
        comparisons.append(
            {
                "asset": positive["asset"],
                "before": before,
                "after": after,
                "improvements": {
                    "silhouette_fidelity": round(after["silhouette_fidelity"] - before["silhouette_fidelity"], 6),
                    "structural_richness": round(after["structural_richness"] - before["structural_richness"], 6),
                    "adjacency_score": round(after["adjacency_score"] - before["adjacency_score"], 6),
                    "fragmentation_penalty": round(before["fragmentation_penalty"] - after["fragmentation_penalty"], 6),
                    "detail_density": round(after_visual.get("detail_density", 0.0) - before_visual.get("detail_density", 0.0), 6),
                    "edge_readability": round(after_visual.get("edge_readability", 0.0) - before_visual.get("edge_readability", 0.0), 6),
                    "primitive_likeness_penalty": round(before_visual.get("primitive_likeness_penalty", 0.0) - after_visual.get("primitive_likeness_penalty", 0.0), 6),
                },
            }
        )

    positive_pass_rate = sum(1 for item in positive_results if item.get("ok")) / max(1, len(positive_results))
    failing_legacy = negative_results + near_miss_results
    negative_fail_rate = sum(1 for item in failing_legacy if not item.get("ok")) / max(1, len(failing_legacy))
    return {
        "positive": positive_results,
        "negative": negative_results,
        "near_miss": near_miss_results,
        "comparisons": comparisons,
        "positive_pass_rate": round(positive_pass_rate, 6),
        "negative_fail_rate": round(negative_fail_rate, 6),
        "shared_primitive_assets": [item["asset"] for item in positive_results if item.get("shared_primitives")],
    }
