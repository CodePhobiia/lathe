from __future__ import annotations

import numpy as np

from ..asset_graph import AssetGraph
from ..shape_ir import ShapeIR, ShapePrimitive


def build_drone_shape_ir(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> ShapeIR:
    scale = asset_graph.scale_cm
    width = scale * 0.56 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.20 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.70 * float(1.0 + rng.uniform(-0.03, 0.03))
    arm_span = width * 2.2
    arm_depth = depth * 0.86
    rotor_radius = scale * 0.11

    rotor_positions = {
        "rotor_fl": (width * 1.00, height * 0.74, depth * 0.96),
        "rotor_fr": (-width * 1.00, height * 0.74, depth * 0.96),
        "rotor_rl": (width * 1.00, height * 0.74, -depth * 0.96),
        "rotor_rr": (-width * 1.00, height * 0.74, -depth * 0.96),
    }
    primitives: list[ShapePrimitive] = [
        ShapePrimitive("box", "body", (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "hull"]),
        ShapePrimitive("box", "body", (0.0, height * 0.32, 0.0), (width * 0.62, height * 0.40, depth * 0.44), tags=["canopy"]),
        ShapePrimitive("box", "body", (0.0, -height * 0.36, depth * 0.20), (width * 0.74, height * 0.26, depth * 0.30), tags=["cargo_bay"]),
        ShapePrimitive("box", "body", (0.0, height * 0.18, depth * 0.48), (arm_span, height * 0.12, width * 0.08), tags=["arm"]),
        ShapePrimitive("box", "body", (0.0, height * 0.18, -depth * 0.48), (arm_span, height * 0.12, width * 0.08), tags=["arm"]),
        ShapePrimitive("box", "body", (arm_span * 0.48, height * 0.18, 0.0), (width * 0.08, height * 0.12, arm_depth), tags=["arm"]),
        ShapePrimitive("box", "body", (-arm_span * 0.48, height * 0.18, 0.0), (width * 0.08, height * 0.12, arm_depth), tags=["arm"]),
        ShapePrimitive("box", "cargo_door", (0.0, -height * 0.42, depth * 0.36), (width * 0.70, height * 0.14, depth * 0.14), tags=["door", "cargo"]),
        ShapePrimitive("box", "landing_leg_l", (width * 0.52, -height * 0.90, depth * 0.22), (width * 0.08, height * 0.66, width * 0.08), tags=["leg", "left"]),
        ShapePrimitive("box", "landing_leg_r", (-width * 0.52, -height * 0.90, -depth * 0.22), (width * 0.08, height * 0.66, width * 0.08), tags=["leg", "right"]),
    ]
    for part_name, center in rotor_positions.items():
        primitives.append(ShapePrimitive("cylinder", part_name, center, radius=rotor_radius, height=scale * 0.025, axis="y", tags=["rotor"]))
        primitives.append(ShapePrimitive("cylinder", part_name, (center[0], center[1] - scale * 0.035, center[2]), radius=rotor_radius * 0.32, height=scale * 0.08, axis="y", tags=["rotor_hub"]))
    signature = {
        "expected_extents": [round(width * 2.2, 6), round(height * 2.2, 6), round(depth * 2.0, 6)],
        "projected_ratio": [round((width * 2.2) / max(width * 2.2, depth * 2.0, height * 2.2), 6), round((height * 2.2) / max(width * 2.2, depth * 2.0, height * 2.2), 6), round((depth * 2.0) / max(width * 2.2, depth * 2.0, height * 2.2), 6)],
        "minimum_triangle_density": 0.72,
        "expected_part_names": [part.name for part in asset_graph.parts],
        "part_targets": {name: {"center": list(center)} for name, center in rotor_positions.items()},
    }
    return ShapeIR(asset_graph.name, asset_graph.family, asset_graph.symmetry_axis, "cm", primitives, signature)
