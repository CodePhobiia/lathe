"""Feature fusion: combine scaffold primitives into search geometry.

Runs the boolean/chamfer/bevel cascade that turns feature-grammar
output into the fused mesh used for conformance fitting.
"""

from __future__ import annotations

from typing import Any

from .fidelity import FidelityProfile
from .shape_ir import ShapePrimitive


def integration_config_for_family(family: str, fidelity: FidelityProfile) -> dict[str, Any]:
    """Integration config for family.

    Args:
        family: family argument.
        fidelity: fidelity argument.

    Returns:
        The result.
    """
    hero_family = family in {
        "brassbound_chest",
        "industrial_crate",
        "mechanical_door",
        "console_terminal",
        "service_cabinet",
        "control_pedestal",
        "supply_container",
        "hero_sword",
    }
    pitch = 2.1 if fidelity.tier == "hero" else 2.35 if fidelity.tier == "game" else 2.6
    blur_sigma = 0.42 if fidelity.tier == "hero" else 0.28 if fidelity.tier == "game" else 0.16
    if family == "courier_drone":
        pitch *= 1.05
    return {
        "enabled": hero_family,
        "pitch": round(pitch, 4),
        "blur_sigma": round(blur_sigma, 4),
        "hero_family": hero_family,
        "exact_finalize": hero_family,
        "exact_mode": "component_assembly"
        if family in {"console_terminal", "control_pedestal", "service_cabinet"}
        else ("explicit_mesh" if hero_family else "sdf_voxel_fusion"),
    }


def primitive_rounding(primitive: ShapePrimitive, fidelity: FidelityProfile) -> float:
    """Primitive rounding.

    Args:
        primitive: primitive argument.
        fidelity: fidelity argument.

    Returns:
        The result.
    """
    base = float(getattr(primitive, "rounding", 0.0) or 0.0)
    if base > 0:
        return base
    if primitive.component in {"shell", "body", "lid", "door", "bezel", "frame"}:
        return 0.7 if fidelity.tier == "hero" else 0.45
    if primitive.component in {"rotor_pod", "hinge", "handle", "clasp_set"}:
        return 0.4 if fidelity.tier == "hero" else 0.25
    return 0.0


def primitive_blend_mode(primitive: ShapePrimitive) -> str:
    """Primitive blend mode.

    Args:
        primitive: primitive argument.

    Returns:
        The result.
    """
    return getattr(primitive, "blend_mode", "union") or "union"
