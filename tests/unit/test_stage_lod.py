"""Unit tests for the LOD decimation module (STAGE-1, V0.2 E3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import trimesh

from lathe.stages import lod as lod_mod


@pytest.fixture()
def sphere() -> trimesh.Trimesh:
    """~1280 face sphere used as the standard LOD input."""
    return trimesh.creation.icosphere(subdivisions=3)


def _faces(mesh: trimesh.Trimesh) -> int:
    return int(len(mesh.faces))


def test_default_ratios_produce_four_lods_with_expected_tri_counts(sphere: trimesh.Trimesh) -> None:
    results = lod_mod.build_lods(sphere, [1.0, 0.5, 0.25, 0.1])
    assert [r.level for r in results] == [0, 1, 2, 3]
    # LOD0 is identity.
    assert results[0].tris == _faces(sphere)
    # Each subsequent LOD must be within ±10% of ratio * source.
    source = _faces(sphere)
    for result in results[1:]:
        expected = int(round(result.ratio * source))
        tolerance = max(4, int(0.10 * expected))
        assert abs(result.tris - expected) <= tolerance, (
            f"LOD{result.level}: got {result.tris}, expected {expected} ±{tolerance}"
        )


def test_ratio_1_returns_a_copy_not_the_same_object(sphere: trimesh.Trimesh) -> None:
    decimated = lod_mod.decimate(sphere, 1.0)
    assert decimated is not sphere
    assert _faces(decimated) == _faces(sphere)


def test_decimation_is_deterministic(sphere: trimesh.Trimesh) -> None:
    a = lod_mod.decimate(sphere, 0.5)
    b = lod_mod.decimate(sphere, 0.5)
    ha = hashlib.sha256(a.export(file_type="glb")).hexdigest()
    hb = hashlib.sha256(b.export(file_type="glb")).hexdigest()
    assert ha == hb
    # Arrays should also match exactly.
    assert a.vertices.tolist() == b.vertices.tolist()
    assert a.faces.tolist() == b.faces.tolist()


def test_empty_mesh_yields_single_lod0(tmp_path: Path) -> None:
    empty = trimesh.Trimesh(vertices=[], faces=[], process=False)
    results = lod_mod.build_lods(empty, [1.0, 0.5, 0.25, 0.1])
    assert len(results) == 1
    assert results[0].level == 0
    assert results[0].tris == 0


def test_manifest_structure_round_trips_through_json(sphere: trimesh.Trimesh) -> None:
    results = lod_mod.build_lods(sphere, [1.0, 0.5, 0.25, 0.1])
    manifest = {
        "schemaVersion": 1,
        "lods": [
            {
                "level": r.level,
                "ratio": r.ratio,
                "tris": r.tris,
                "verts": r.verts,
                "path": f"stages/optimize/lod_{r.level}.glb",
            }
            for r in results
        ],
    }
    # Round-trip through JSON — ensure all fields are JSON-serializable and preserved.
    round_trip = json.loads(json.dumps(manifest))
    assert round_trip["schemaVersion"] == 1
    assert {e["level"] for e in round_trip["lods"]} == {0, 1, 2, 3}
    for entry in round_trip["lods"]:
        assert entry["tris"] >= 0
        assert entry["verts"] >= 0
        assert isinstance(entry["ratio"], float)


def test_large_mesh_decimation_smoke_does_not_hang() -> None:
    """subdivisions=5 → ~20480 faces; must complete in a bounded budget."""
    big = trimesh.creation.icosphere(subdivisions=5)
    result = lod_mod.decimate(big, 0.1)
    # Much coarser output — tri count must fall roughly by the target ratio.
    assert _faces(result) < _faces(big) // 5


def test_ratios_below_one_reduce_vertex_count(sphere: trimesh.Trimesh) -> None:
    base_verts = int(len(sphere.vertices))
    r = lod_mod.decimate(sphere, 0.25)
    assert int(len(r.vertices)) < base_verts
    # Decimated LOD must remain a valid, non-empty trimesh.
    assert _faces(r) > 0
    assert int(len(r.vertices)) > 0


def test_runtime_config_override_changes_resolved_ratios() -> None:
    """The optimize-stage ratio resolver must honor runtime_config.optimize.lod_ratios."""
    from lathe.core.stages.optimize import _resolve_lod_ratios

    asset_cfg = {"lods": 4}
    overridden = _resolve_lod_ratios(asset_cfg, {"optimize": {"lod_ratios": [1.0, 0.75, 0.5]}})
    assert overridden == [1.0, 0.75, 0.5]
    defaults = _resolve_lod_ratios(asset_cfg, {})
    assert defaults == [1.0, 0.5, 0.25, 0.1]
    asset_override = _resolve_lod_ratios({"lod_ratios": [1.0, 0.3]}, {})
    assert asset_override == [1.0, 0.3]
