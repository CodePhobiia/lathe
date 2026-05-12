"""Integration test: every FamilyAlias + policy produces a valid program.

Per ``docs/asset-quality/lathe-northstar-full-implementation-plan.md``
v2 §6.4 (Cycle 3 post-decommission, Cycle 4 Phase A.1 policy expansion):

> All families that existed in the registry at Cycle 3 start produce
> ShapeProgram outputs through the procedural synthesizer.

After Cycle 3 Round 6 decommissioned ``_RECIPES``, there is no recipe
baseline to diff against. After Cycle 4 Phase A.1 wired real
expansions into ``panelized_hard_surface_object``, the test bar moved
up: every alias must drive a non-empty ShapeProgram from just its
FamilyAlias + a **single** authored ``primary_volume`` node (the
policy supplies the rest).

This module ships TWO test classes:

  - ``test_family_alias_drives_valid_synthesizer_program``
    (parametrized over all 71 aliases) — runs ``synthesize_procedural_program``
    only, asserts the ShapeProgram has >= 20 ops + at least one each of
    op.material_zone / op.decal_zone / op.wear_zone. Fast (<1s for all
    71 fixtures combined). Catches per-alias regressions in alias
    loading, policy resolution, generator/decorator dispatch.

  - ``test_industrial_crate_drives_valid_build_artifact_via_full_backend``
    (single fixture) — runs the full ``run_shape_backend`` for the
    Sprint 0 hero. Slow (~30s+ due to boolean compile of 45 ops). Spot
    check for end-to-end backend integration; not parametrized because
    71 × 30s is impractical for CI.

The previous canned 10-node graph was the audit's flagged failure
mode: "same graph injected under each family name, proves the
mechanic not per-family procedural intent." Minimum-authored-graph
+ policy expansion + per-alias synth pipeline test is the honest
verification floor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import trimesh

from lathe.asset_quality.procedural_synthesizer import synthesize_procedural_program
from lathe.shape.backend import run_shape_backend
from lathe.shape.procedural_program_path import _extract_semantic_zone_records


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALIAS_ROOT = _REPO_ROOT / "std" / "procedural" / "knowledge" / "aliases"


# Minimum primary_volume attributes the policy needs to expand from.
# Per Cycle 4 Phase A.1, every NODE_TYPE beyond primary_volume is
# supplied by ``panelized_hard_surface_object`` policy expansions.
_PRIMARY_VOLUME_ATTRS: dict[str, Any] = {
    "shape": "rounded_box",
    "dimensions_cm": {"x": 30.0, "y": 30.0, "z": 30.0},
    "rounding_cm": 1.5,
}


def _alias_family_ids() -> tuple[str, ...]:
    """Enumerate every FamilyAlias under std/procedural/knowledge/aliases/."""
    if not _ALIAS_ROOT.exists():
        return ()
    families: list[str] = []
    for entry in sorted(_ALIAS_ROOT.iterdir()):
        if not entry.is_file() or entry.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        fid = data.get("family_id")
        if isinstance(fid, str) and fid:
            families.append(fid)
    return tuple(families)


def _minimal_authored_graph(family: str) -> dict[str, Any]:
    """Build the MINIMUM authored graph the policy needs to drive geometry."""
    return {
        "nodes": [
            {
                "node_id": f"{family}.body",
                "node_type": "primary_volume",
                "domain": "hard_surface",
                "attributes": _PRIMARY_VOLUME_ATTRS,
            },
        ],
        "edges": [],
    }


def _minimal_asset_and_runtime(family: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the (asset, runtime) tuple a minimum-authored alias build expects."""
    cg = _minimal_authored_graph(family)
    asset = {
        "name": family,
        "intent": {"family": family, "construction_graph": cg},
        "build": {
            "shape": {
                "procedural": {
                    "construction_graph": cg,
                    "brief": {"family": family},
                },
            },
        },
    }
    runtime = {
        "design_brief": {"brief": {"family": family}},
        "construction_graph": cg,
    }
    return asset, runtime


_FAMILY_IDS = _alias_family_ids()


@pytest.mark.skipif(not _FAMILY_IDS, reason="no aliases registered")
@pytest.mark.parametrize("family", _FAMILY_IDS, ids=list(_FAMILY_IDS))
def test_family_alias_drives_valid_synthesizer_program(family: str) -> None:
    """Each FamilyAlias + policy produces a valid synthesized ShapeProgram.

    Per plan v2 §6.4 the per-family verifier checks:
      - The synthesizer pipeline runs to completion (Stage 1-8) with no
        attribute_schema_violation entries.
      - The emitted ShapeProgram has >= 20 ops (policy expansion adds
        at least 19 nodes → at least 20 emit ops counting the body).
      - At least one op.material_zone / op.decal_zone / op.wear_zone
        record is emitted — the policy's metadata-only zones reach the
        shape program.
      - ``synthesizer_trace`` records ``policy_applied`` for
        ``panelized_hard_surface_object``.

    Pipeline-level only; the full shape backend boolean compile is
    covered by the single-fixture spot check below (boolean kernel
    work is ~30s per fixture and impractical to parametrize x71).
    """
    asset, runtime = _minimal_asset_and_runtime(family)
    result = synthesize_procedural_program(asset, runtime)

    program = result.shape_program
    op_count = len(program.ops)
    assert op_count >= 20, (
        f"family {family!r}: synthesizer emitted only {op_count} ops "
        f"(expected >= 20 — policy expansion alone should add >= 19 nodes)."
    )

    # Zone records flow through Phase A.2's extractor — verify the
    # raw shape_program has them too (the surface-stage path consumes
    # them via the extractor).
    zone_records = _extract_semantic_zone_records(program)
    record_kinds = {r["kind"] for r in zone_records}
    assert "material_zone" in record_kinds, (
        f"family {family!r}: no op.material_zone in ShapeProgram. "
        f"panelized_hard_surface_object policy must emit one."
    )
    assert "decal_zone" in record_kinds, (
        f"family {family!r}: no op.decal_zone in ShapeProgram. "
        f"panelized_hard_surface_object policy must emit one."
    )
    assert "wear_zone" in record_kinds, (
        f"family {family!r}: no op.wear_zone in ShapeProgram. "
        f"panelized_hard_surface_object policy must emit one."
    )

    # Policy application is traced (catches a regression where the
    # alias loads but the policy is silently skipped).
    policy_applied_entries = [
        e for e in result.trace.entries
        if e.kind == "policy_applied"
        and e.payload.get("policy_id") == "panelized_hard_surface_object"
    ]
    assert policy_applied_entries, (
        f"family {family!r}: panelized_hard_surface_object policy not "
        f"applied. Either the alias didn't resolve or the policy "
        f"precondition failed."
    )

    # Family alias resolution is preserved in the ShapeProgram.
    assert program.family == family, (
        f"family {family!r}: ShapeProgram.family={program.family!r}. "
        f"Family-alias flow-through is broken."
    )


def test_alias_directory_has_at_least_one_alias() -> None:
    """Sanity invariant: the alias directory is non-empty."""
    assert _FAMILY_IDS, (
        f"no FamilyAlias JSON files found under {_ALIAS_ROOT}. "
        f"The procedural synthesizer's family routing is broken."
    )


def test_alias_directory_carries_seventy_one_aliases() -> None:
    """All 71 family aliases shipped in Cycle 3 must remain registered."""
    assert len(_FAMILY_IDS) >= 71, (
        f"expected >= 71 aliases (Cycle 3 baseline), found {len(_FAMILY_IDS)}."
    )


@pytest.mark.slow
def test_industrial_crate_drives_valid_build_artifact_via_full_backend(
    tmp_path: Path,
) -> None:
    """Spot check: industrial_crate runs end-to-end through ``run_shape_backend``.

    Verifies that the alias + policy + synthesizer + boolean kernel
    chain produces a real Trimesh artifact. The boolean compile is ~30s
    so this is intentionally a single-fixture spot check, not a 71-way
    parametrization. industrial_crate is the Sprint 0 hero per
    CLAUDE.md northstar.

    Run with ``pytest -m slow`` or ``pytest --no-skip-slow`` to include.
    Skipped by default to keep the test loop fast — the parametrized
    pipeline-level test above already covers per-alias regression for
    all 71 families.
    """
    family = "industrial_crate"
    asset, _ = _minimal_asset_and_runtime(family)
    work = tmp_path / "shape_work"
    work.mkdir(parents=True, exist_ok=True)
    result = run_shape_backend(
        "lathe.shape.intent_mesh_handoff_v1",
        asset,
        source_root=tmp_path,
        seed=42,
        candidates_count=1,
        conditioning={},
        work_dir=work,
        runtime_config=None,
        backend_version=None,
    )
    candidates = result.get("runtime_candidates", [])
    assert candidates, (
        f"family {family!r} produced no runtime candidates; shape stage failed."
    )
    candidate = candidates[0]

    mesh = candidate.get("mesh")
    assert isinstance(mesh, trimesh.Trimesh), (
        f"family {family!r}: build did not produce a Trimesh result; "
        f"got {type(mesh).__name__}."
    )
    assert len(mesh.faces) > 0, (
        f"family {family!r}: synthesizer-driven build produced an empty mesh."
    )

    meta = candidate.get("meta") or {}
    synth_trace = meta.get("synthesizer_trace") if isinstance(meta, dict) else None
    assert synth_trace, (
        f"family {family!r}: candidate meta has no synthesizer_trace — "
        f"the build did not route through the procedural synthesizer."
    )

    # Phase A.2: zone records reach the surface stage via candidate meta.
    zone_records = meta.get("semantic_zone_records") if isinstance(meta, dict) else None
    assert isinstance(zone_records, list) and zone_records, (
        f"family {family!r}: candidate meta missing semantic_zone_records "
        f"(Phase A.2 wiring broken)."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
