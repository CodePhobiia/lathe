"""B8 — topology preserves craft: named part attribution must survive.

When the synthesizer emits N typed nodes (body + handles + brackets
+ fasteners + trim + zones) but the topology stage's
``part_groups`` collapses to a single label, the visible-quality
investment in part decomposition is lost: downstream surface zones,
per-part materials, and seam-class preservation all reference part
names that no longer exist in the mesh.

The diagnostic fires when:

  - the synthesizer reported a ``synthesized_node_count`` >= 3
    (body + at least two secondary parts), AND
  - the topology bundle's ``part_groups`` collapses everything into
    < ``_PART_GROUP_FLOOR`` distinct labels.

This is the structural "named part collapse" signal — independent
from the silhouette / bevel diagnostics. A model can pass
featureless_silhouette (it has visible protrusions) yet still fail
this (only one part label survived the boolean fusion, so its
material zones and decals lose their attribution target).

Repair routing is via the same ``add_secondary_features`` action
shape that re-emits the construction graph with explicit part
preservation hints.
"""

from __future__ import annotations

from typing import Any

VERSION = "lathe.validate.named_part_preservation_v1"

# Below this synthesized count, the asset is intentionally simple
# (a single primary volume with maybe one zone op) and a 1-part
# topology is correct.
_NODE_FLOOR = 3

# Below this part_group count, the topology bundle has effectively
# collapsed all the named parts into a single label.
_PART_GROUP_FLOOR = 2

_HARD_SURFACE_KINDS: frozenset[str] = frozenset(
    {
        "hard_surface_prop",
        "mechanical_prop",
        "industrial_prop",
        "container",
        "weapon_prop",
        "env_module",
        "shipping_prop",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _asset_kind(asset: dict[str, Any]) -> str:
    intent = _as_dict(asset.get("intent"))
    raw = intent.get("kind") or asset.get("kind")
    if isinstance(raw, str):
        return raw.strip().lower()
    return ""


def _synthesized_node_count(runtime: dict[str, Any]) -> int:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    candidates = bundle.get("runtime_candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            meta = _as_dict(first.get("meta"))
            assessment = _as_dict(meta.get("shape_assessment"))
            raw = assessment.get("synthesized_node_count")
            if isinstance(raw, int):
                return raw
            ir = _as_dict(meta.get("shape_ir"))
            sig = _as_dict(ir.get("signature"))
            raw = sig.get("synthesized_node_count")
            if isinstance(raw, int):
                return raw
    return 0


def _part_group_count(runtime: dict[str, Any]) -> int:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    groups = bundle.get("part_groups")
    if isinstance(groups, list):
        return len({g.get("name") for g in groups if isinstance(g, dict) and g.get("name")})
    return 0


def _part_group_names(runtime: dict[str, Any]) -> list[str]:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    groups = bundle.get("part_groups")
    if isinstance(groups, list):
        return sorted({
            str(g.get("name"))
            for g in groups
            if isinstance(g, dict) and g.get("name")
        })
    return []


def evaluate_named_part_preservation(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate whether synthesizer-named parts survive topology fusion."""
    asset_kind = _asset_kind(asset)
    node_count = _synthesized_node_count(runtime)
    part_group_count = _part_group_count(runtime)

    metrics: dict[str, Any] = {
        "asset_kind": asset_kind,
        "synthesized_node_count": node_count,
        "topology_part_group_count": part_group_count,
        "topology_part_group_names": _part_group_names(runtime),
    }

    activates = (
        asset_kind in _HARD_SURFACE_KINDS
        and node_count >= _NODE_FLOOR
        and part_group_count < _PART_GROUP_FLOOR
    )
    metrics["fires"] = activates

    diagnostics: list[dict[str, Any]] = []
    if activates:
        diagnostics.append(
            {
                "code": "L6404",
                "name": "named_part_collapse",
                "severity": "warning",
                "phase": "validate",
                "stage": "validate",
                "asset": asset.get("name"),
                "path": "validate.named_part_preservation",
                "message": (
                    f"Synthesizer emitted {node_count} typed graph nodes "
                    f"but the topology stage's part_groups collapses to "
                    f"{part_group_count} label(s). Named-part attribution "
                    f"is lost; downstream material zones, decals, and "
                    f"seam classes lose their attribution target. The "
                    f"northstar §B8 'topology preserves craft' signal."
                ),
                "details": dict(metrics),
                "suggested_repairs": [
                    "preserve_part_attribution_through_booleans",
                    "emit_per_part_submeshes",
                ],
                # No repair_actions wiring yet — this is a topology /
                # kernel-attribution fix that doesn't have a clean
                # patch operation. Diagnostic emits as visible
                # evidence to drive future implementation work.
            }
        )

    return {
        "version": VERSION,
        "metrics": metrics,
        "diagnostics": diagnostics,
    }
