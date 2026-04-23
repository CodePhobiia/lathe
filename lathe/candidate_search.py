from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .assembly_kernel import AssemblyBlueprint, BlueprintComponent
from .asset_graph import AssetGraph
from .fidelity import FidelityProfile


@dataclass
class CandidateParams:
    width_scale: float
    height_scale: float
    depth_scale: float
    feature_density: float
    panel_depth: float
    edge_weight: float
    support_spread: float
    attachment_spread: float
    trim_scale: float
    silhouette_bias: float
    rotor_guard_scale: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * 977)


_SEARCH_DIMENSIONS = {
    "width_scale": ("width_scale",),
    "height_scale": ("height_scale",),
    "depth_scale": ("depth_scale",),
    "feature_density": ("feature_density",),
    "panel_depth": ("panel_depth",),
    "edge_weight": ("edge_weight",),
    "support_spread": ("support_spread",),
    "attachment_spread": ("attachment_spread",),
    "trim_scale": ("trim_scale",),
    "silhouette_bias": ("silhouette_bias",),
    "rotor_guard_scale": ("rotor_guard_scale",),
}

_FROZEN_DEFAULTS = {
    "width_scale": lambda fidelity: 1.0,
    "height_scale": lambda fidelity: 1.0,
    "depth_scale": lambda fidelity: 1.0,
    "feature_density": lambda fidelity: float(fidelity.detail_density),
    "panel_depth": lambda fidelity: float(fidelity.panel_depth),
    "edge_weight": lambda fidelity: float(fidelity.edge_weight),
    "support_spread": lambda fidelity: 1.0,
    "attachment_spread": lambda fidelity: 1.0,
    "trim_scale": lambda fidelity: 1.0,
    "silhouette_bias": lambda fidelity: 1.0,
    "rotor_guard_scale": lambda fidelity: 1.0,
}


def _domain_bounds(domain: object) -> tuple[float, float] | None:
    if isinstance(domain, dict) and domain.get("type") == "range":
        try:
            return float(domain["from"]), float(domain["to"])
        except Exception:  # noqa: BLE001
            return None
    return None


def generate_candidate_params(asset_graph: AssetGraph, *, seed: int, candidate_index: int, fidelity: FidelityProfile) -> CandidateParams:
    rng = _rng(seed, candidate_index)
    silhouette_window = 0.08 * fidelity.silhouette_refinement
    detail_window = 0.22 * fidelity.detail_density
    shape_mode = str(asset_graph.authoring.get("shape_mode", "generate"))
    if shape_mode == "adapt":
        silhouette_window *= 0.45
        detail_window *= 0.70
    elif shape_mode == "reconstruct":
        silhouette_window *= 0.55
        detail_window *= 0.75
    elif shape_mode == "assemble":
        silhouette_window *= 0.60
    params = CandidateParams(
        width_scale=float(1.0 + rng.uniform(-silhouette_window, silhouette_window)),
        height_scale=float(1.0 + rng.uniform(-silhouette_window * 0.75, silhouette_window * 0.75)),
        depth_scale=float(1.0 + rng.uniform(-silhouette_window, silhouette_window)),
        feature_density=float(max(0.65, fidelity.detail_density + rng.uniform(-detail_window, detail_window))),
        panel_depth=float(max(0.65, fidelity.panel_depth + rng.uniform(-0.18, 0.18))),
        edge_weight=float(max(0.65, fidelity.edge_weight + rng.uniform(-0.16, 0.16))),
        support_spread=float(1.0 + rng.uniform(-0.12, 0.16)),
        attachment_spread=float(1.0 + rng.uniform(-0.12, 0.14)),
        trim_scale=float(0.95 + rng.uniform(-0.10, 0.18)),
        silhouette_bias=float(1.0 + rng.uniform(-0.10, 0.16) * fidelity.silhouette_refinement),
        rotor_guard_scale=float(0.92 + rng.uniform(-0.10, 0.18) * fidelity.detail_density),
    )
    space = asset_graph.authoring.get("space", {})
    frozen = set(space.get("freeze", []))
    if shape_mode in {"adapt", "reconstruct"}:
        frozen.update({"width_scale", "height_scale", "depth_scale"})
    for item in space.get("vary", []):
        path = str(item.get("path", ""))
        bounds = _domain_bounds(item.get("domain"))
        if path not in _SEARCH_DIMENSIONS or bounds is None:
            continue
        if path in frozen:
            continue
        setattr(params, _SEARCH_DIMENSIONS[path][0], float(rng.uniform(bounds[0], bounds[1])))
    for path in frozen:
        if path in _SEARCH_DIMENSIONS:
            setattr(params, _SEARCH_DIMENSIONS[path][0], _FROZEN_DEFAULTS[path](fidelity))
    return params


def objective_weights(asset_graph: AssetGraph) -> dict[str, float]:
    objectives = list(asset_graph.authoring.get("objectives", []) or asset_graph.authoring.get("space", {}).get("objectives", []))
    total = sum(float(item.get("weight", 0.0) or 0.0) for item in objectives)
    if total <= 0:
        return {}
    return {str(item["metric"]): float(item.get("weight", 0.0) or 0.0) / total for item in objectives}


def apply_candidate_params(blueprint: AssemblyBlueprint, params: CandidateParams, asset_graph: AssetGraph) -> AssemblyBlueprint:
    components: list[BlueprintComponent] = []
    for component in blueprint.components:
        cx, cy, cz = component.center
        ex, ey, ez = component.extents
        width_scale = params.width_scale
        height_scale = params.height_scale
        depth_scale = params.depth_scale
        if component.component_type in {"shell", "body"}:
            extents = (
                ex * width_scale * params.silhouette_bias,
                ey * height_scale,
                ez * depth_scale * params.silhouette_bias,
            )
        elif component.component_type in {"panel", "bezel", "frame", "lid", "door", "lock_plate", "latch", "socket_plate", "anchor_plate"}:
            extents = (
                ex * width_scale,
                ey * height_scale,
                ez * params.panel_depth,
            )
        elif component.component_type in {"handle", "hinge"}:
            extents = (ex, ey * params.trim_scale, ez * params.trim_scale)
            cx *= params.attachment_spread
            cz *= params.attachment_spread
        elif component.component_type in {"foot", "stand", "bracket"}:
            extents = (ex * params.trim_scale, ey * params.support_spread, ez * params.trim_scale)
            cx *= params.support_spread
            cz *= params.support_spread
        elif component.component_type in {"rotor_arm"}:
            extents = (
                ex * params.support_spread,
                ey * params.edge_weight,
                ez * params.support_spread,
            )
        elif component.component_type in {"rotor_pod"}:
            extents = (
                ex * params.rotor_guard_scale,
                ey * params.rotor_guard_scale,
                ez * params.rotor_guard_scale,
            )
            cx *= params.support_spread
            cz *= params.support_spread
        elif component.component_type in {"vent", "grille"}:
            extents = (ex * params.trim_scale, ey * params.trim_scale, ez * params.panel_depth)
        else:
            extents = (
                ex * width_scale,
                ey * height_scale,
                ez * depth_scale,
            )
        components.append(
            BlueprintComponent(
                name=component.name,
                component_type=component.component_type,
                part=component.part,
                center=(cx, cy, cz),
                extents=extents,
                tags=list(component.tags),
                adjacency=list(component.adjacency),
                axis=component.axis,
                radius=component.radius * params.rotor_guard_scale if component.radius is not None else None,
                height=component.height * params.trim_scale if component.height is not None else None,
                symmetry_mate=component.symmetry_mate,
                interface_role=component.interface_role,
            )
        )
    notes = list(blueprint.notes) + [f"candidate_search: width={params.width_scale:.3f} depth={params.depth_scale:.3f} feature_density={params.feature_density:.3f}"]
    return AssemblyBlueprint(blueprint.blueprint_id, blueprint.family, components, notes=notes)
