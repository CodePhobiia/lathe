from __future__ import annotations

import numpy as np

from ..asset_graph import AssetGraph
from ..shape_ir import ShapeIR, ShapePrimitive


def build_chest_shape_ir(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> ShapeIR:
    scale = asset_graph.scale_cm
    width = scale * 0.78 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.50 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.52 * float(1.0 + rng.uniform(-0.03, 0.03))
    base_height = height * 0.56
    lid_height = height * 0.34
    foot_height = height * 0.10

    primitives: list[ShapePrimitive] = [
        ShapePrimitive(
            "box", "body", (0.0, -height * 0.12, 0.0), (width, base_height, depth), tags=["body", "container"]
        ),
        ShapePrimitive(
            "box",
            "lid_panel",
            (0.0, base_height * 0.32, 0.0),
            (width * 0.94, lid_height, depth * 0.92),
            tags=["lid", "container"],
        ),
        ShapePrimitive(
            "box",
            "lid_panel",
            (0.0, base_height * 0.47, 0.0),
            (width * 0.72, lid_height * 0.58, depth * 0.82),
            tags=["lid", "crest"],
        ),
        ShapePrimitive(
            "box",
            "front_hatch",
            (0.0, -height * 0.04, depth * 0.49),
            (width * 0.78, base_height * 0.30, depth * 0.08),
            tags=["door", "front"],
        ),
        ShapePrimitive(
            "box",
            "lock_plate",
            (0.0, height * 0.04, depth * 0.53),
            (width * 0.16, height * 0.18, depth * 0.08),
            tags=["lock", "front"],
        ),
        ShapePrimitive(
            "cylinder",
            "handle_l",
            (-width * 0.51, -height * 0.02, 0.0),
            radius=height * 0.10,
            height=width * 0.08,
            axis="x",
            tags=["handle", "left"],
        ),
        ShapePrimitive(
            "cylinder",
            "handle_r",
            (width * 0.51, -height * 0.02, 0.0),
            radius=height * 0.10,
            height=width * 0.08,
            axis="x",
            tags=["handle", "right"],
        ),
        ShapePrimitive(
            "box",
            "foot_l",
            (-width * 0.30, -height * 0.47, depth * 0.20),
            (width * 0.12, foot_height, depth * 0.16),
            tags=["foot", "left"],
        ),
        ShapePrimitive(
            "box",
            "foot_r",
            (width * 0.30, -height * 0.47, -depth * 0.20),
            (width * 0.12, foot_height, depth * 0.16),
            tags=["foot", "right"],
        ),
        ShapePrimitive(
            "box",
            "body",
            (0.0, -height * 0.20, 0.0),
            (width * 0.88, base_height * 0.86, depth * 0.88),
            tags=["liner"],
        ),
        ShapePrimitive(
            "box",
            "body",
            (0.0, -height * 0.10, depth * 0.42),
            (width * 0.90, base_height * 0.18, depth * 0.05),
            tags=["band", "front"],
        ),
        ShapePrimitive(
            "box",
            "body",
            (0.0, -height * 0.10, -depth * 0.42),
            (width * 0.90, base_height * 0.18, depth * 0.05),
            tags=["band", "rear"],
        ),
    ]
    signature = {
        "expected_extents": [round(width, 6), round(height, 6), round(depth, 6)],
        "projected_ratio": [
            round(width / max(width, depth, height), 6),
            round(height / max(width, depth, height), 6),
            round(depth / max(width, depth, height), 6),
        ],
        "minimum_triangle_density": 0.60,
        "expected_part_names": [part.name for part in asset_graph.parts],
        "part_targets": {
            "front_hatch": {"center": [0.0, -height * 0.04, depth * 0.49]},
            "lock_plate": {"center": [0.0, height * 0.04, depth * 0.53]},
            "handle_l": {"center": [-width * 0.51, -height * 0.02, 0.0]},
            "handle_r": {"center": [width * 0.51, -height * 0.02, 0.0]},
        },
    }
    return ShapeIR(
        asset_graph.name, asset_graph.family, asset_graph.symmetry_axis, "cm", primitives, signature
    )
