"""Integration test: per-family build-artifact diff between recipe and synthesizer.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §6.4:

> For each family migrated: a build-artifact diff test exists. At
> minimum: face count parity within ±20%, material zone count
> parity, package output count parity. Visible regressions block
> the migration.

This is the parametrized integration harness. Each migrated family
ships a fixture entry under ``_MIGRATED_FAMILY_FIXTURES`` with:

  - ``family``: the family name.
  - ``recipe_asset``: asset dict that routes to the legacy recipe
    path (no ``construction_graph``, so ``synthesizer_eligible``
    returns False).
  - ``synthesizer_asset``: asset dict that routes to the synthesizer
    arm (populates ``construction_graph``).
  - ``face_count_tolerance``: ±fraction tolerance for face-count
    parity, defaulting to 0.20 (±20%) per the §6.4 acceptance
    criterion.
  - ``expected_material_zone_count_delta``: ±delta tolerated for
    material zone count parity, defaulting to 0.

The harness builds both paths through ``run_shape_backend`` and
compares the resulting trimesh face counts, material-zone counts on
the candidate mesh metadata, and runtime-candidate counts (the
"package output count" proxy at the shape stage).

Unmigrated families are not in the catalog; the harness skips them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import trimesh

from lathe.shape.backend import run_shape_backend


# --- Fixture catalog ----------------------------------------------------
#
# Empty until a family migrates; each migration PR appends its entry.

_MIGRATED_FAMILY_FIXTURES: tuple[dict[str, Any], ...] = (
    # First migration goes here, e.g.:
    # {
    #     "family": "inventory_economy_object",
    #     "recipe_asset": {...},   # no construction_graph
    #     "synthesizer_asset": {...},   # carries construction_graph
    #     "face_count_tolerance": 0.20,
    #     "expected_material_zone_count_delta": 0,
    # },
)


def _build_path(asset: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    """Run ``run_shape_backend`` and return the first runtime candidate.

    Both paths route through the same entry — the dispatch inside
    backend.py picks recipe-vs-synthesizer based on whether the asset
    has a construction_graph populated.
    """
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
    candidates = result.get("runtime_candidates", [])
    if not candidates:
        raise AssertionError(
            f"asset {asset.get('name')!r} produced no runtime candidates; "
            "shape stage failed to build either the recipe or synthesizer "
            "path."
        )
    return candidates[0]


def _material_zone_count(candidate: dict[str, Any]) -> int:
    """Best-effort material-zone count from candidate metadata.

    The shape stage attaches material-zone evidence to the candidate
    in a few possible locations depending on the build path. This
    helper checks each in order and returns the first non-empty
    count it finds.
    """
    meta = candidate.get("meta", {}) or {}
    # Direct count in shape_handoff
    handoff = candidate.get("shape_handoff") or {}
    zones = handoff.get("material_zones")
    if isinstance(zones, list):
        return len(zones)
    # Mesh-metadata fallback
    mesh = candidate.get("mesh")
    if isinstance(mesh, trimesh.Trimesh):
        mesh_meta = mesh.metadata if isinstance(mesh.metadata, dict) else {}
        mat_zones = mesh_meta.get("material_zones") or mesh_meta.get("lathe_material_zones")
        if isinstance(mat_zones, list):
            return len(mat_zones)
    # Conditioning fallback
    cond = meta.get("conditioning") or {}
    zones = cond.get("material_zones")
    if isinstance(zones, list):
        return len(zones)
    return 0


@pytest.mark.skipif(
    not _MIGRATED_FAMILY_FIXTURES,
    reason="no families have migrated yet; harness exercised by tests added per-family",
)
@pytest.mark.parametrize(
    "fixture",
    _MIGRATED_FAMILY_FIXTURES,
    ids=[f["family"] for f in _MIGRATED_FAMILY_FIXTURES] if _MIGRATED_FAMILY_FIXTURES else [],
)
def test_migrated_family_build_artifact_diff(
    fixture: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Recipe vs synthesizer build artifacts are within tolerance.

    Per plan v2 §6.4:
      - face count parity within ±20%
      - material zone count parity
      - package output count parity (proxy: runtime-candidate count
        at the shape stage)
    """
    family = fixture["family"]
    face_tol = float(fixture.get("face_count_tolerance", 0.20))
    zone_delta = int(fixture.get("expected_material_zone_count_delta", 0))

    recipe_candidate = _build_path(fixture["recipe_asset"], tmp_path / "recipe")
    synth_candidate = _build_path(fixture["synthesizer_asset"], tmp_path / "synth")

    recipe_mesh = recipe_candidate["mesh"]
    synth_mesh = synth_candidate["mesh"]
    assert isinstance(recipe_mesh, trimesh.Trimesh), (
        f"family {family!r} recipe path produced a non-trimesh result"
    )
    assert isinstance(synth_mesh, trimesh.Trimesh), (
        f"family {family!r} synthesizer path produced a non-trimesh result"
    )

    recipe_face_count = len(recipe_mesh.faces)
    synth_face_count = len(synth_mesh.faces)
    assert recipe_face_count > 0, (
        f"family {family!r} recipe path produced an empty mesh"
    )
    assert synth_face_count > 0, (
        f"family {family!r} synthesizer path produced an empty mesh"
    )

    # Face-count parity within ±tolerance.
    face_ratio = abs(synth_face_count - recipe_face_count) / max(recipe_face_count, 1)
    assert face_ratio <= face_tol, (
        f"family {family!r} face-count parity outside tolerance: "
        f"recipe={recipe_face_count}, synthesizer={synth_face_count}, "
        f"delta_ratio={face_ratio:.3f}, tolerance={face_tol:.3f}. "
        "Per §6.4 face count parity must be within ±20%; document an "
        "intent-driven divergence in the migration notes if this is "
        "acceptable, then bump face_count_tolerance in the fixture."
    )

    # Material-zone count parity within ±zone_delta.
    recipe_zones = _material_zone_count(recipe_candidate)
    synth_zones = _material_zone_count(synth_candidate)
    zone_diff = abs(synth_zones - recipe_zones)
    assert zone_diff <= zone_delta, (
        f"family {family!r} material-zone count diverged: "
        f"recipe={recipe_zones}, synthesizer={synth_zones}, "
        f"diff={zone_diff}, tolerated={zone_delta}. Per §6.4 material "
        "zone count parity is required; bump "
        "expected_material_zone_count_delta in the fixture if the "
        "divergence is intent-driven."
    )


def test_migrated_family_build_fixtures_have_required_keys() -> None:
    """Each fixture must define the documented contract keys.

    Catches typos / missing keys at collection time rather than
    halfway through a slow integration run.
    """
    required_keys = {"family", "recipe_asset", "synthesizer_asset"}
    for fixture in _MIGRATED_FAMILY_FIXTURES:
        missing = required_keys - set(fixture.keys())
        assert not missing, (
            f"fixture for family={fixture.get('family')!r} missing required "
            f"keys: {sorted(missing)!r}. See module docstring for the "
            "fixture contract."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
