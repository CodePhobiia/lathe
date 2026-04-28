from __future__ import annotations

import numpy as np

from ..asset_graph import AssetGraph
from ..shape_ir import ShapeIR, ShapePrimitive


def build_wall_panel_shape_ir(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> ShapeIR:
    scale = asset_graph.scale_cm
    width = scale * 1.10 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 1.48 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.18 * float(1.0 + rng.uniform(-0.02, 0.02))
    primitives: list[ShapePrimitive] = [
        ShapePrimitive("box", "body", (0.0, 0.0, 0.0), (width, height, depth), tags=["panel", "frame"]),
        ShapePrimitive(
            "box",
            "body",
            (0.0, 0.0, -depth * 0.12),
            (width * 0.90, height * 0.90, depth * 0.40),
            tags=["inset"],
        ),
        ShapePrimitive(
            "box",
            "screen_panel",
            (0.0, height * 0.10, depth * 0.14),
            (width * 0.52, height * 0.42, depth * 0.12),
            tags=["screen"],
        ),
        ShapePrimitive(
            "box",
            "screen_frame",
            (0.0, height * 0.10, depth * 0.17),
            (width * 0.62, height * 0.50, depth * 0.05),
            tags=["frame"],
        ),
        ShapePrimitive(
            "box",
            "vent_l",
            (-width * 0.26, -height * 0.18, depth * 0.14),
            (width * 0.16, height * 0.26, depth * 0.10),
            tags=["vent", "left"],
        ),
        ShapePrimitive(
            "box",
            "vent_r",
            (width * 0.26, -height * 0.18, depth * 0.14),
            (width * 0.16, height * 0.26, depth * 0.10),
            tags=["vent", "right"],
        ),
        ShapePrimitive(
            "box",
            "console_strip",
            (0.0, -height * 0.36, depth * 0.16),
            (width * 0.60, height * 0.12, depth * 0.09),
            tags=["console"],
        ),
        ShapePrimitive(
            "box",
            "mount_top",
            (0.0, height * 0.56, -depth * 0.08),
            (width * 0.28, height * 0.08, depth * 0.34),
            tags=["mount"],
        ),
        ShapePrimitive(
            "box",
            "mount_bottom",
            (0.0, -height * 0.56, -depth * 0.08),
            (width * 0.28, height * 0.08, depth * 0.34),
            tags=["mount"],
        ),
    ]
    signature = {
        "expected_extents": [round(width, 6), round(height, 6), round(depth, 6)],
        "projected_ratio": [
            round(width / max(width, height, depth), 6),
            round(height / max(width, height, depth), 6),
            round(depth / max(width, height, depth), 6),
        ],
        "minimum_triangle_density": 0.58,
        "expected_part_names": [part.name for part in asset_graph.parts],
        "part_targets": {
            "screen_panel": {"center": [0.0, height * 0.10, depth * 0.14]},
            "vent_l": {"center": [-width * 0.26, -height * 0.18, depth * 0.14]},
            "vent_r": {"center": [width * 0.26, -height * 0.18, depth * 0.14]},
        },
    }
    return ShapeIR(
        asset_graph.name, asset_graph.family, asset_graph.symmetry_axis, "cm", primitives, signature
    )
