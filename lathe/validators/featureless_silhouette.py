"""B10 — visible-blockout detector that catches the "featureless cube" case.

Sibling to ``edge_treatment_coverage.py``. Where that validator catches
*zero edge treatment* (a body without bevels), this one catches the
adjacent failure mode the user just rejected: a body **with** bevels
but **without** secondary features — the silhouette reads as a single
primary primitive with no panels / brackets / handles / fasteners /
trim breaks past its bounding faces.

Two structural signals together fire the diagnostic:

  1. ``synthesized_node_count`` is below ``_NODE_FLOOR`` — the synth
     pipeline emitted only the primary_volume (and maybe one or two
     trivial zones). A real hard-surface asset routes through 5+
     typed nodes (body + at least 2 secondary parts + 2 zones).
  2. The mesh bounding extents do not exceed the intent
     ``dimensions_cm`` by more than ``_PROTRUSION_FLOOR_CM`` on any
     axis — i.e. nothing sticks out past the body's bounding box.
     A handle or bracket protruding from a face widens the bound;
     a featureless body keeps the bound flush.

Activates on hard-surface kinds with non-trivial face counts. Like its
sibling, it is reusable across hero fixtures (industrial_crate,
mechanical_door, fantasy_weapon, etc.) — no per-family logic.

Repair suggestions point at the synthesizer / repair-executor's
``add_secondary_features`` mapping (B11).
"""

from __future__ import annotations

from typing import Any

VERSION = "lathe.validate.featureless_silhouette_v1"

# A hard-surface asset should have at least this many typed nodes in
# its construction graph to count as "composed" rather than "blockout".
# Body + 2 secondary parts + 2 zones = 5 is the canonical minimum.
_NODE_FLOOR = 5

# Below this face count, the asset is small / detail-only and a
# minimal-feature state is not a visible-blockout failure mode.
_FACE_COUNT_FLOOR = 200

# Mesh extents must exceed intent.dimensions_cm by at least this many
# centimeters on at least one axis for the silhouette to count as
# "has visible protrusions". A handle, bracket, or fastener will push
# the bound past the primary volume by several centimeters.
_PROTRUSION_FLOOR_CM = 1.0

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


def _runtime_candidate_first(runtime: dict[str, Any]) -> dict[str, Any]:
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    candidates = bundle.get("runtime_candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            return first
    return {}


def _synthesized_node_count(runtime: dict[str, Any]) -> int:
    candidate = _runtime_candidate_first(runtime)
    meta = _as_dict(candidate.get("meta"))
    assessment = _as_dict(meta.get("shape_assessment"))
    raw = assessment.get("synthesized_node_count")
    if isinstance(raw, int):
        return raw
    # Fallback path: shape_ir.signature
    ir = _as_dict(meta.get("shape_ir"))
    sig = _as_dict(ir.get("signature"))
    raw = sig.get("synthesized_node_count")
    if isinstance(raw, int):
        return raw
    # Fallback path: bundle.shape_assessment
    shape = _as_dict(runtime.get("shape"))
    bundle = _as_dict(shape.get("bundle"))
    bundle_assessment = _as_dict(bundle.get("shape_assessment"))
    raw = bundle_assessment.get("synthesized_node_count")
    if isinstance(raw, int):
        return raw
    return 0


def _intent_dimensions_cm(asset: dict[str, Any]) -> dict[str, float] | None:
    """Best-effort body dimensions extraction from intent.scale.

    Returns None when the asset has no parseable intent dimensions.
    """
    intent = _as_dict(asset.get("intent"))
    scale = intent.get("scale")
    if isinstance(scale, dict):
        if "x" in scale and "y" in scale and "z" in scale:
            try:
                return {
                    "x": float(scale["x"]),
                    "y": float(scale["y"]),
                    "z": float(scale["z"]),
                }
            except (TypeError, ValueError):
                return None
        if scale.get("type") == "unit":
            try:
                value = float(scale.get("value", 0.0))
                unit = str(scale.get("unit", "cm")).lower()
                if unit == "m":
                    d = value * 100.0
                elif unit == "cm":
                    d = value
                elif unit == "mm":
                    d = value / 10.0
                else:
                    d = value
                if d > 0:
                    return {"x": d, "y": d * 0.7, "z": d * 0.7}
            except (TypeError, ValueError):
                return None
    return None


def _mesh_extents(runtime: dict[str, Any]) -> dict[str, float] | None:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    mesh_stats = _as_dict(bundle.get("mesh_stats"))
    bounds = mesh_stats.get("bounds_cm") or mesh_stats.get("aabb_cm")
    if isinstance(bounds, dict):
        try:
            mn = bounds.get("min") or bounds.get("min_cm")
            mx = bounds.get("max") or bounds.get("max_cm")
            if isinstance(mn, (list, tuple)) and isinstance(mx, (list, tuple)) and len(mn) >= 3 and len(mx) >= 3:
                return {
                    "x": float(mx[0]) - float(mn[0]),
                    "y": float(mx[1]) - float(mn[1]),
                    "z": float(mx[2]) - float(mn[2]),
                }
        except (TypeError, ValueError):
            return None
    return None


def _final_face_count(runtime: dict[str, Any]) -> int:
    topology = _as_dict(runtime.get("topology"))
    bundle = _as_dict(topology.get("bundle"))
    mesh_stats = _as_dict(bundle.get("mesh_stats"))
    raw = mesh_stats.get("triangle_count") or mesh_stats.get("face_count")
    if isinstance(raw, int) and raw > 0:
        return raw
    groups = bundle.get("part_groups")
    if isinstance(groups, list):
        return sum(
            int(g.get("face_count") or 0)
            for g in groups
            if isinstance(g, dict)
        )
    return 0


def evaluate_featureless_silhouette(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate the silhouette/feature signal for hard-surface bodies.

    Returns an additive payload with ``version``, ``metrics``, and a
    ``diagnostics`` list. Fires when both:

      - synthesized_node_count is below _NODE_FLOOR, OR
      - mesh extents fail to exceed intent.dimensions on every axis
        by more than _PROTRUSION_FLOOR_CM (no visible protrusions).

    Each condition alone is meaningful; both together are the
    canonical "featureless cube" signature the user rejected.
    """
    asset_kind = _asset_kind(asset)
    face_count = _final_face_count(runtime)
    node_count = _synthesized_node_count(runtime)
    intent_dims = _intent_dimensions_cm(asset)
    mesh_dims = _mesh_extents(runtime)

    protrusion_delta_cm: dict[str, float] = {}
    has_visible_protrusion = False
    if intent_dims is not None and mesh_dims is not None:
        for axis in ("x", "y", "z"):
            delta = float(mesh_dims.get(axis, 0.0)) - float(intent_dims.get(axis, 0.0))
            protrusion_delta_cm[axis] = round(delta, 3)
            if delta > _PROTRUSION_FLOOR_CM:
                has_visible_protrusion = True
    elif mesh_dims is None:
        # No mesh-bounds evidence — be conservative; don't fire on the
        # protrusion signal alone.
        has_visible_protrusion = True

    low_node_count = node_count < _NODE_FLOOR
    no_protrusion = not has_visible_protrusion

    metrics: dict[str, Any] = {
        "asset_kind": asset_kind,
        "face_count": face_count,
        "synthesized_node_count": node_count,
        "intent_dimensions_cm": intent_dims or {},
        "mesh_extents_cm": mesh_dims or {},
        "protrusion_delta_cm": protrusion_delta_cm,
        "has_visible_protrusion": has_visible_protrusion,
        "low_node_count": low_node_count,
    }

    activates = (
        asset_kind in _HARD_SURFACE_KINDS
        and face_count >= _FACE_COUNT_FLOOR
        and (low_node_count or no_protrusion)
    )
    metrics["fires"] = activates

    diagnostics: list[dict[str, Any]] = []
    if activates:
        reasons: list[str] = []
        if low_node_count:
            reasons.append(
                f"only {node_count} synthesized graph nodes (floor {_NODE_FLOOR})"
            )
        if no_protrusion:
            reasons.append(
                f"mesh extents do not exceed intent.dimensions_cm by "
                f"{_PROTRUSION_FLOOR_CM}cm on any axis "
                f"(protrusion_delta_cm={protrusion_delta_cm})"
            )
        diagnostics.append(
            {
                "code": "L6403",
                "name": "featureless_silhouette",
                "severity": "warning",
                "phase": "validate",
                "stage": "validate",
                "asset": asset.get("name"),
                "path": "validate.featureless_silhouette",
                "message": (
                    f"Hard-surface asset ({asset_kind!r}) renders as a "
                    f"single primary primitive with no visible secondary "
                    f"features: {' AND '.join(reasons)}. This is the "
                    f"'featureless cube' failure mode — the body has "
                    f"bevels and a watertight mesh, but the silhouette "
                    f"reads as one primitive box and the asset does not "
                    f"look like the class it claims to be."
                ),
                "details": dict(metrics),
                "suggested_repairs": [
                    "add_secondary_features",
                    "expand_policy_density",
                    "widen_auto_graph_part_materialization",
                ],
            }
        )

    return {
        "version": VERSION,
        "metrics": metrics,
        "diagnostics": diagnostics,
    }
