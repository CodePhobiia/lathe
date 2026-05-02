from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np

from .assembly_kernel import AssemblyBlueprint, BlueprintComponent
from .asset_graph import AssetGraph
from .fidelity import FidelityProfile
from .geometry_detail import geometry_detail_controls_from_authoring


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
        except (KeyError, TypeError, ValueError):
            return None
    return None


def generate_candidate_params(
    asset_graph: AssetGraph, *, seed: int, candidate_index: int, fidelity: FidelityProfile
) -> CandidateParams:
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
        feature_density=float(
            max(0.65, fidelity.detail_density + rng.uniform(-detail_window, detail_window))
        ),
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


def apply_quality_adapters_to_candidate_params(
    params: CandidateParams, adapters: dict[str, object] | None
) -> CandidateParams:
    """Return candidate params steered by pre-shape quality-plan adapters.

    The adapter uses generic art-direction dimensions only. It does not know
    about crates, swords, or any specific family; it simply turns desired
    silhouette/detail/material hierarchy into existing search-space knobs.
    """
    safe = adapters if isinstance(adapters, dict) else {}

    def factor(key: str, default: float = 1.0) -> float:
        try:
            return float(safe.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    runtime_budget = factor("runtime_budget_multiplier", 1.0)
    return replace(
        params,
        feature_density=_bounded(
            params.feature_density * factor("feature_density_multiplier") * runtime_budget,
            0.45,
            2.5,
        ),
        panel_depth=_bounded(params.panel_depth * factor("panel_depth_multiplier"), 0.45, 2.0),
        edge_weight=_bounded(params.edge_weight * factor("edge_weight_multiplier"), 0.45, 2.0),
        silhouette_bias=_bounded(
            params.silhouette_bias * factor("silhouette_bias_multiplier"),
            0.65,
            1.8,
        ),
        trim_scale=_bounded(params.trim_scale * factor("trim_scale_multiplier"), 0.55, 1.8),
    )


def apply_style_modifiers_to_candidate_params(
    params: CandidateParams, asset_graph: AssetGraph
) -> CandidateParams:
    """Return candidate params steered by authored style language."""
    controls = geometry_detail_controls_from_authoring(asset_graph.authoring)
    styles = set(controls.style_modifiers)
    silhouette_profile = str(controls.silhouette_profile or "")
    silhouette_motifs = set(controls.silhouette_motifs)
    if not styles and not silhouette_profile and not silhouette_motifs:
        return params
    silhouette_intensity = max(0.25, float(controls.silhouette_intensity or 1.0))

    width = params.width_scale
    height = params.height_scale
    depth = params.depth_scale
    feature_density = params.feature_density
    panel_depth = params.panel_depth
    edge_weight = params.edge_weight
    support_spread = params.support_spread
    attachment_spread = params.attachment_spread
    trim_scale = params.trim_scale
    silhouette_bias = params.silhouette_bias
    rotor_guard_scale = params.rotor_guard_scale

    if styles & {"brutalist", "industrial"}:
        width *= 1.08
        depth *= 1.10
        height *= 0.96
        feature_density *= 1.14
        panel_depth *= 1.12
        edge_weight *= 1.16
        trim_scale *= 1.08
        silhouette_bias *= 1.08
    if styles & {"elegant", "luxury"}:
        width *= 0.94
        height *= 1.12
        depth *= 0.96
        feature_density *= 1.06
        panel_depth *= 0.88
        edge_weight *= 0.92
        trim_scale *= 0.88
        silhouette_bias *= 0.96
    if "modular" in styles:
        support_spread *= 1.08
        attachment_spread *= 1.14
        feature_density *= 1.08
        panel_depth *= 1.06
    if "organic" in styles:
        width *= 0.97
        height *= 1.06
        depth *= 1.04
        edge_weight *= 0.86
        trim_scale *= 0.90
        silhouette_bias *= 0.92
    if "prototype" in styles:
        depth *= 1.08
        feature_density *= 1.16
        attachment_spread *= 1.10
        rotor_guard_scale *= 1.10
    if styles & {"battle_worn", "salvaged", "field_used"}:
        width *= 1.03
        depth *= 1.04
        feature_density *= 1.10
        edge_weight *= 1.06
        trim_scale *= 1.04
    if silhouette_profile in {"wide_heavy", "reinforced_field", "tripod"}:
        width *= 1.0 + 0.10 * silhouette_intensity
        depth *= 1.0 + 0.05 * silhouette_intensity
        height *= max(0.82, 1.0 - 0.035 * silhouette_intensity)
        support_spread *= 1.0 + 0.10 * silhouette_intensity
        silhouette_bias *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_profile in {"sleek_winged", "winged"}:
        width *= 1.0 + 0.12 * silhouette_intensity
        depth *= 1.0 + 0.07 * silhouette_intensity
        height *= max(0.80, 1.0 - 0.04 * silhouette_intensity)
        attachment_spread *= 1.0 + 0.12 * silhouette_intensity
        silhouette_bias *= 1.0 + 0.06 * silhouette_intensity
    if silhouette_profile in {"ornate_spire", "tower", "tall", "spined"}:
        height *= 1.0 + 0.12 * silhouette_intensity
        width *= max(0.76, 1.0 - 0.035 * silhouette_intensity)
        depth *= max(0.78, 1.0 - 0.025 * silhouette_intensity)
        feature_density *= 1.0 + 0.05 * silhouette_intensity
    if silhouette_profile == "blade_like":
        depth *= 1.0 + 0.14 * silhouette_intensity
        width *= max(0.74, 1.0 - 0.04 * silhouette_intensity)
        edge_weight *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_profile == "compact":
        width *= max(0.78, 1.0 - 0.06 * silhouette_intensity)
        depth *= max(0.78, 1.0 - 0.06 * silhouette_intensity)
        height *= max(0.84, 1.0 - 0.04 * silhouette_intensity)
        feature_density *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_motifs & {"wing", "fin", "fins", "stabilizer"}:
        width *= 1.0 + 0.07 * silhouette_intensity
        attachment_spread *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_motifs & {"tower", "spire", "mast", "antenna", "sensor_mast"}:
        height *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_motifs & {"outrigger", "outriggers", "support"}:
        width *= 1.0 + 0.05 * silhouette_intensity
        support_spread *= 1.0 + 0.08 * silhouette_intensity
    if silhouette_motifs & {"blade", "blades", "tool_head"}:
        depth *= 1.0 + 0.08 * silhouette_intensity
        edge_weight *= 1.0 + 0.05 * silhouette_intensity

    return replace(
        params,
        width_scale=_bounded(width, 0.70, 1.55),
        height_scale=_bounded(height, 0.70, 1.55),
        depth_scale=_bounded(depth, 0.70, 1.55),
        feature_density=_bounded(feature_density, 0.45, 2.75),
        panel_depth=_bounded(panel_depth, 0.45, 2.20),
        edge_weight=_bounded(edge_weight, 0.45, 2.20),
        support_spread=_bounded(support_spread, 0.65, 1.55),
        attachment_spread=_bounded(attachment_spread, 0.65, 1.55),
        trim_scale=_bounded(trim_scale, 0.50, 1.90),
        silhouette_bias=_bounded(silhouette_bias, 0.65, 1.95),
        rotor_guard_scale=_bounded(rotor_guard_scale, 0.65, 1.75),
    )


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def objective_weights(asset_graph: AssetGraph) -> dict[str, float]:
    objectives = list(
        asset_graph.authoring.get("objectives", [])
        or asset_graph.authoring.get("space", {}).get("objectives", [])
    )
    total = sum(float(item.get("weight", 0.0) or 0.0) for item in objectives)
    if total <= 0:
        return {}
    return {str(item["metric"]): float(item.get("weight", 0.0) or 0.0) / total for item in objectives}


def apply_candidate_params(
    blueprint: AssemblyBlueprint, params: CandidateParams, asset_graph: AssetGraph
) -> AssemblyBlueprint:
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
        elif component.component_type in {
            "panel",
            "bezel",
            "frame",
            "lid",
            "door",
            "lock_plate",
            "latch",
            "socket_plate",
            "anchor_plate",
        }:
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
    notes = list(blueprint.notes) + [
        f"candidate_search: width={params.width_scale:.3f} depth={params.depth_scale:.3f} feature_density={params.feature_density:.3f}"
    ]
    return AssemblyBlueprint(blueprint.blueprint_id, blueprint.family, components, notes=notes)
