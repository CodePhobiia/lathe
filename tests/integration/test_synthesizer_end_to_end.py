"""End-to-end test: synthesizer drives real geometry through the shape stage.

Constructs a programmatic asset (no recipe, no mesh_program block, just
an authored construction_graph), passes it through
``run_shape_backend``, and asserts that:

  - The synthesizer arm activated.
  - A real ``trimesh.Trimesh`` was produced.
  - The runtime candidate's metadata names the synthesizer as the
    shape source.
  - ``family_dispatch_used: False`` appears in the synthesizer trace.

This is the Cycle 1 production-grade proof per
``docs/asset-quality/procedural-synthesizer-architecture-correction.md``
§"Acceptance bar's 'real GLB' is now achievable in Cycle 1." The test
runs the shape stage but skips downstream topology/UV/surface stages
to keep wall-clock fast — the shape stage is what proves the
synthesizer drove real geometry.

Bypasses the parser intentionally: authored ``.lth`` syntax for the
``procedural{}`` block lands later in the implementation plan; this
test exercises the substrate that syntax will lower to.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh
from lathe.shape.backend import run_shape_backend


def _build_procedural_asset() -> dict:
    """Construct an asset dict that triggers the synthesizer arm.

    Carries:
      - No family recipe (no ``family`` field in brief).
      - No ``mesh_program{}`` block (the synthesizer arm activates).
      - A construction graph with primary_volume + 1 panel + attached_to
        edge. Enough authored intent to drive non-empty synthesis.
    """
    return {
        "name": "synthesizer_e2e_proof",
        "intent": {
            "parts": ["body", "front_panel"],
            "tags": [],
            "construction_graph": {
                "nodes": [
                    {
                        "node_id": "body",
                        "node_type": "primary_volume",
                        "attributes": {
                            "shape": "rounded_box",
                            "dimensions_cm": {"x": 30.0, "y": 20.0, "z": 12.0},
                            "rounding_cm": 0.8,
                        },
                    },
                    {
                        "node_id": "front_panel",
                        "node_type": "panel",
                        "attributes": {
                            "plane": "xy",
                            "width_cm": 20.0,
                            "height_cm": 12.0,
                            "thickness_cm": 0.6,
                        },
                    },
                ],
                "edges": [
                    {
                        "source_id": "front_panel",
                        "target_id": "body",
                        "edge_type": "attached_to",
                        "attributes": {},
                    },
                ],
            },
        },
        "assembly": {"resolved_components": []},
        "build": {
            "shape": {
                "mode": "generate",
                "candidates": 1,
                "seed": "auto",
            },
            "topology": {},
            "uv": {},
            "surface": {},
            "package": {},
        },
        "surface": {},
    }


def test_synthesizer_drives_real_shape_stage_output(tmp_path: Path) -> None:
    """The synthesizer arm must produce a real trimesh through the shape stage.

    This is the Cycle 1 acceptance proof: an unknown-family asset whose
    only "what to build" signal is the construction graph produces
    visible geometry via the procedural pipeline.
    """
    asset = _build_procedural_asset()
    work_dir = tmp_path / "shape_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    result = run_shape_backend(
        "lathe.shape.intent_mesh_handoff_v1",
        asset,
        source_root=tmp_path,
        seed=42,
        candidates_count=1,
        conditioning={},
        work_dir=work_dir,
        runtime_config=None,
        backend_version=None,
    )

    # Top-level structure — run_shape_backend returns a dict with
    # runtime_candidates, asset_graph, provider_report, etc. at top
    # level (not wrapped in a 'report' key).
    assert "runtime_candidates" in result
    candidates = result["runtime_candidates"]
    assert len(candidates) >= 1, "shape stage produced no runtime candidates"

    candidate = candidates[0]

    # Real mesh
    mesh = candidate["mesh"]
    assert isinstance(mesh, trimesh.Trimesh), (
        f"expected trimesh.Trimesh, got {type(mesh).__name__}"
    )
    assert len(mesh.vertices) > 0, "synthesizer-driven mesh has zero vertices"
    assert len(mesh.faces) > 0, "synthesizer-driven mesh has zero faces"

    # Synthesizer attribution via blueprint_id
    meta = candidate.get("meta", {})
    blueprint_id = meta.get("blueprint_id")
    assert blueprint_id == "procedural_synthesizer_v1", (
        f"expected blueprint_id='procedural_synthesizer_v1', got "
        f"{blueprint_id!r}. If 'mesh_program_v1' or a family blueprint, "
        f"the dispatch didn't route to the synthesizer."
    )
    shape_source = meta.get("conditioning", {}).get("shape_source")
    assert shape_source == "procedural_synthesizer", (
        f"expected shape_source='procedural_synthesizer', got {shape_source!r}"
    )

    # Synthesizer trace in candidate metadata
    synth_trace = meta.get("synthesizer_trace")
    assert isinstance(synth_trace, dict), (
        "synthesizer trace not attached to runtime candidate metadata"
    )
    assert synth_trace.get("family_dispatch_used") is False
    assert synth_trace.get("attempted_via") == "procedural_engine"


def test_synthesizer_glb_export_is_well_formed(tmp_path: Path) -> None:
    """The synthesizer's mesh round-trips through trimesh GLB export.

    Establishes that the shape-stage output is suitable for downstream
    package export — the "real GLB" half of the acceptance bar. Skips
    the full lathe-build pipeline (topology / UV / surface / package
    stages); their compatibility is established by the existing
    contract test ``test_shape_handoff_v1``.
    """
    asset = _build_procedural_asset()
    work_dir = tmp_path / "shape_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    result = run_shape_backend(
        "lathe.shape.intent_mesh_handoff_v1",
        asset,
        source_root=tmp_path,
        seed=42,
        candidates_count=1,
        conditioning={},
        work_dir=work_dir,
        runtime_config=None,
        backend_version=None,
    )
    mesh = result["runtime_candidates"][0]["mesh"]

    glb_path = tmp_path / "synthesizer_proof.glb"
    glb_bytes = mesh.export(file_type="glb")
    glb_path.write_bytes(glb_bytes)
    assert glb_path.exists()
    assert glb_path.stat().st_size > 100, (
        "GLB export is suspiciously small — synthesizer mesh may be degenerate"
    )

    # Re-load the GLB to confirm it parses
    scene = trimesh.load(glb_path, force="scene")
    geometries = list(scene.geometry.values()) if hasattr(scene, "geometry") else [scene]
    assert geometries, "exported GLB contains no geometry"
    reloaded = geometries[0]
    assert len(reloaded.vertices) == len(mesh.vertices)
    assert len(reloaded.faces) == len(mesh.faces)


def test_synthesizer_eligibility_predicate_routes_correctly() -> None:
    """The synthesizer_eligible predicate gates dispatch correctly.

    Verifies the precedence rules at the predicate level: mesh_program
    always wins, then synthesizer eligibility, then the legacy
    scaffold path. The dispatch in run_shape_backend honors these
    rules directly.
    """
    from lathe.shape.procedural_program_path import synthesizer_eligible

    asset = _build_procedural_asset()
    assert synthesizer_eligible(asset, None) is True

    # Adding mesh_program with non-empty statements disables synthesizer
    asset_with_mp = dict(asset)
    asset_with_mp["build"] = {
        **asset["build"],
        "shape": {
            **asset["build"]["shape"],
            "mesh_program": {
                "node_type": "mesh_program",
                "statements": [{"any": "non-empty"}],
            },
        },
    }
    assert synthesizer_eligible(asset_with_mp, None) is False

    # An asset with neither mesh_program nor construction_graph falls
    # through to the legacy scaffold path
    asset_empty = {"name": "empty", "intent": {}, "build": {"shape": {}}}
    assert synthesizer_eligible(asset_empty, None) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
