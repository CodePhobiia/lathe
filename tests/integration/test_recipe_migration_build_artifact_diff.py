"""Integration test: every FamilyAlias drives a valid synthesizer build.

Per ``docs/asset-quality/lathe-northstar-full-implementation-plan.md``
v2 §6.4 (Cycle 3 post-decommission):

> All families that existed in the registry at Cycle 3 start produce
> ShapeProgram outputs through the procedural synthesizer.
> For each family migrated: a build-artifact diff test exists.

After Cycle 3 Round 6 decommissioned ``_RECIPES``, the "diff" loses
its recipe baseline — there is no recipe path left to compare
against. What remains is the per-alias **build-artifact** check:
every FamilyAlias under ``std/procedural/knowledge/aliases/*.json``
must drive a full shape-backend build end-to-end and produce a
non-empty Trimesh result plus a synthesizer trace proving the
procedural pipeline ran.

This is the integration-level verification floor for the procedural
synthesizer. A new family's alias adds a new parametrize ID; no test
code changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import trimesh

from lathe.shape.backend import run_shape_backend


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALIAS_ROOT = _REPO_ROOT / "std" / "procedural" / "knowledge" / "aliases"


# Per-NODE_TYPE attribute templates. Keep in sync with the canonical
# 10-NODE_TYPE pattern emitted by procedural synthesizer generators.
_ATTRS = {
    "primary_volume": {
        "shape": "rounded_box",
        "dimensions_cm": {"x": 30.0, "y": 30.0, "z": 30.0},
        "rounding_cm": 1.5,
    },
    "panel": {
        "shape": "rectangular",
        "width_cm": 14.0,
        "height_cm": 10.0,
        "thickness_cm": 0.4,
        "host_face_axis": "z",
    },
    "frame": {
        "plane": "xy",
        "outer_width_cm": 14.0,
        "outer_height_cm": 14.0,
        "member_thickness_cm": 0.6,
        "protrusion_cm": 0.4,
    },
    "trim": {
        "profile": "flat_band",
        "length_cm": 14.0,
        "width_cm": 1.0,
        "thickness_cm": 0.4,
        "axis": "x",
    },
    "fastener": {
        "kind": "rivet",
        "head_radius_cm": 0.3,
        "head_height_cm": 0.4,
        "shaft_radius_cm": 0.15,
        "shaft_length_cm": 0.6,
    },
    "handle": {"style": "bar", "length_cm": 14.0, "grip_radius_cm": 0.8, "axis": "x"},
    "inset": {
        "depth_axis": "z",
        "depth_cm": 0.4,
        "width_cm": 6.0,
        "height_cm": 4.0,
        "profile": "flat",
    },
    "rail": {"axis": "x", "length_cm": 14.0, "radius_cm": 0.4, "cross_section": "round"},
    "socket": {"depth_axis": "x", "depth_cm": 1.0, "radius_cm": 0.6, "profile": "round"},
    "mount": {"style": "flat_pad", "width_cm": 4.0, "depth_cm": 4.0, "height_cm": 0.6},
    "guard": {
        "style": "perimeter_rail",
        "width_cm": 16.0,
        "height_cm": 6.0,
        "depth_cm": 16.0,
        "bar_radius_cm": 0.3,
        "bar_count": 4,
        "axis": "y",
    },
    "hinge": {
        "style": "butt",
        "leaf_width_cm": 3.0,
        "leaf_height_cm": 6.0,
        "leaf_thickness_cm": 0.3,
        "barrel_radius_cm": 0.4,
        "pin_axis": "y",
    },
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


def _canonical_construction_graph(family: str) -> dict[str, Any]:
    """Build a canonical 10-node hard-surface construction graph.

    Every alias under ``std/procedural/knowledge/aliases/`` resolves to
    the panelized_hard_surface_object policy + industrial_pbr_v1 style,
    which the synthesizer's hard_surface generators consume. The graph
    below exercises 9 NODE_TYPE generators so the build path is broad
    enough to detect routing regressions per family.
    """
    return {
        "nodes": [
            {"node_id": f"{family}.body", "node_type": "primary_volume",
             "domain": "hard_surface", "attributes": _ATTRS["primary_volume"]},
            {"node_id": f"{family}.material_zone", "node_type": "material_zone",
             "domain": "hard_surface",
             "attributes": {"zone_id": "primary_material", "material_hint": "painted_emblem"}},
            {"node_id": f"{family}.decal_zone", "node_type": "decal_zone",
             "domain": "hard_surface",
             "attributes": {"zone_id": "primary_decal", "decal_intent": "label",
                            "size_cm": [8.0, 4.0], "host_face_axis": "z"}},
            {"node_id": f"{family}.wear_zone", "node_type": "wear_zone",
             "domain": "hard_surface",
             "attributes": {"zone_id": "primary_wear", "wear_kind": "handled",
                            "intensity": "moderate", "coverage_fraction": 0.4}},
            {"node_id": f"{family}.fastener", "node_type": "fastener",
             "domain": "hard_surface", "attributes": _ATTRS["fastener"]},
            {"node_id": f"{family}.handle", "node_type": "handle",
             "domain": "hard_surface", "attributes": _ATTRS["handle"]},
            {"node_id": f"{family}.inset", "node_type": "inset",
             "domain": "hard_surface", "attributes": _ATTRS["inset"]},
            {"node_id": f"{family}.rail", "node_type": "rail",
             "domain": "hard_surface", "attributes": _ATTRS["rail"]},
            {"node_id": f"{family}.socket", "node_type": "socket",
             "domain": "hard_surface", "attributes": _ATTRS["socket"]},
            {"node_id": f"{family}.mount", "node_type": "mount",
             "domain": "hard_surface", "attributes": _ATTRS["mount"]},
        ],
        "edges": [],
    }


def _build_synth_path(family: str, tmp_path: Path) -> dict[str, Any]:
    """Run the full shape backend with a canonical construction graph for ``family``."""
    cg = _canonical_construction_graph(family)
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
        f"family {family!r} produced no runtime candidates; shape stage "
        f"failed to build through the synthesizer path."
    )
    return candidates[0]


_FAMILY_IDS = _alias_family_ids()


@pytest.mark.skipif(not _FAMILY_IDS, reason="no aliases registered")
@pytest.mark.parametrize("family", _FAMILY_IDS, ids=list(_FAMILY_IDS))
def test_family_alias_drives_valid_synthesizer_build(
    family: str,
    tmp_path: Path,
) -> None:
    """Each registered FamilyAlias produces a valid build artifact.

    Per plan v2 §6.4 the build-artifact verifier checks:
      - The shape backend produces at least one runtime candidate.
      - The candidate carries a non-empty Trimesh mesh.
      - The candidate carries a synthesizer_trace proving the
        procedural pipeline ran (not silently falling back to a
        scaffold path).

    Face-count and material-zone parity against a recipe baseline is
    no longer applicable — Cycle 3 Round 6 decommissioned ``_RECIPES``.
    """
    candidate = _build_synth_path(family, tmp_path)

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


def test_alias_directory_has_at_least_one_alias() -> None:
    """Sanity invariant: the alias directory is non-empty.

    Catches accidental directory deletion. The plan v2 §6.4 acceptance
    says "all families that existed in the registry at Cycle 3 start
    produce ShapeProgram outputs"; zero aliases would mean the
    decommission removed the migration substrate too.
    """
    assert _FAMILY_IDS, (
        f"no FamilyAlias JSON files found under {_ALIAS_ROOT}. "
        f"The procedural synthesizer's family routing is broken."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
