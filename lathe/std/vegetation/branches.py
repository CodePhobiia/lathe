"""Recursive branch skeleton generator.

Builds a deterministic L-system-style tree of ``BranchSegment`` records.
Each segment carries:

- ``path``: a 3D polyline (one entry per node along the segment), used
  later to lower into a stable ShapeIR ``swept_profile`` primitive.
- ``base_radius`` / ``tip_radius``: cylindrical radii at the start/end
  of the segment, used to drive a tapered round cross-section.
- ``depth``: recursion depth (0 = trunk).
- ``parent_index``: index of the parent segment (-1 for trunk).
- ``children``: indices of child segments.
- ``tip``: world-space tip position (used as a leaf-placement seed).

The kernel is intentionally pure-Python and seeded — same parameters
plus same seed produces the same skeleton, every time.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class BranchSegment:
    """A single branch segment in a tree skeleton."""

    path: list[tuple[float, float, float]]
    base_radius: float
    tip_radius: float
    depth: int
    parent_index: int
    children: list[int] = field(default_factory=list)
    tip: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def to_dict(self) -> dict:
        """Return a JSON-serializable view of the segment."""
        return {
            "path": [list(p) for p in self.path],
            "base_radius": self.base_radius,
            "tip_radius": self.tip_radius,
            "depth": self.depth,
            "parent_index": self.parent_index,
            "children": list(self.children),
            "tip": list(self.tip),
        }


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-12:
        return (0.0, 1.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def _perpendicular(v: tuple[float, float, float]) -> tuple[float, float, float]:
    if abs(v[1]) < 0.95:
        ax = (0.0, 1.0, 0.0)
    else:
        ax = (1.0, 0.0, 0.0)
    cx = v[1] * ax[2] - v[2] * ax[1]
    cy = v[2] * ax[0] - v[0] * ax[2]
    cz = v[0] * ax[1] - v[1] * ax[0]
    return _normalize((cx, cy, cz))


def _rotate_around(
    axis: tuple[float, float, float], v: tuple[float, float, float], angle_rad: float
) -> tuple[float, float, float]:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    ax, ay, az = _normalize(axis)
    dot = ax * v[0] + ay * v[1] + az * v[2]
    cx = ay * v[2] - az * v[1]
    cy = az * v[0] - ax * v[2]
    cz = ax * v[1] - ay * v[0]
    return (
        v[0] * c + cx * s + ax * dot * (1.0 - c),
        v[1] * c + cy * s + ay * dot * (1.0 - c),
        v[2] * c + cz * s + az * dot * (1.0 - c),
    )


def _bend_direction(
    direction: tuple[float, float, float],
    bend_axis: tuple[float, float, float],
    bend_angle_rad: float,
) -> tuple[float, float, float]:
    return _normalize(_rotate_around(bend_axis, direction, bend_angle_rad))


def _segment_path(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    length: float,
    *,
    nodes: int = 5,
    bend_amount_rad: float = 0.0,
    bend_axis: tuple[float, float, float] | None = None,
) -> tuple[list[tuple[float, float, float]], tuple[float, float, float]]:
    """Build a curved poly-line path from origin along direction.

    Returns the path (list of points) and the final outgoing direction.
    """
    nodes = max(2, int(nodes))
    if bend_axis is None:
        bend_axis = _perpendicular(direction)
    step_len = length / (nodes - 1)
    pts: list[tuple[float, float, float]] = [origin]
    cur_dir = direction
    cur_pos = origin
    for _i in range(nodes - 1):
        # Apply incremental bend along the segment so the curve is gentle.
        if bend_amount_rad != 0.0:
            cur_dir = _bend_direction(cur_dir, bend_axis, bend_amount_rad / (nodes - 1))
        cur_pos = _add(cur_pos, _scale(cur_dir, step_len))
        pts.append(cur_pos)
    return pts, cur_dir


def generate_branch_skeleton(
    *,
    trunk_height_cm: float = 600.0,
    trunk_radius_cm: float = 18.0,
    max_depth: int = 4,
    branching_factor: int = 4,
    length_decay: float = 0.62,
    radius_decay: float = 0.55,
    angle_jitter_rad: float = 0.45,
    branch_pitch_rad: float = 0.95,
    bend_amount_rad: float = 0.18,
    nodes_per_segment: int = 5,
    seed: int = 1234,
) -> list[BranchSegment]:
    """Build a deterministic recursive branch skeleton.

    Parameters mirror the SpeedTree-style branch grammar:
    trunk_height/radius set the scale; max_depth caps recursion;
    branching_factor controls how many children spawn at each node;
    length/radius_decay attenuate scale per depth; angle_jitter and
    branch_pitch govern branch direction; bend_amount curls each
    segment.
    """
    rng = random.Random(seed)
    segments: list[BranchSegment] = []

    # Trunk: vertical, slight bend, with intermediate nodes so child
    # branches can fork from interior whorls.
    trunk_path, _trunk_dir = _segment_path(
        (0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        trunk_height_cm,
        nodes=max(nodes_per_segment, 6),
        bend_amount_rad=bend_amount_rad * 0.4,
        bend_axis=(1.0, 0.0, 0.0),
    )
    trunk = BranchSegment(
        path=trunk_path,
        base_radius=trunk_radius_cm,
        tip_radius=trunk_radius_cm * radius_decay,
        depth=0,
        parent_index=-1,
        tip=trunk_path[-1],
    )
    segments.append(trunk)

    def _spawn(parent_idx: int, depth: int) -> None:
        if depth >= max_depth:
            return
        parent = segments[parent_idx]
        # Spawn branches from the upper half of the parent path.
        n_children = max(1, int(branching_factor))
        # Each child fork point is a node along the second half of the path.
        usable = parent.path[len(parent.path) // 2 :]
        if not usable:
            return
        # Decay length and radius with depth.
        parent_segment_len = math.dist(parent.path[0], parent.path[-1])
        child_length = parent_segment_len * length_decay
        child_base = parent.tip_radius
        child_tip = max(child_base * radius_decay, 0.05)
        for k in range(n_children):
            fork_idx = (k * len(usable)) // max(1, n_children)
            fork_idx = min(fork_idx, len(usable) - 1)
            fork = usable[fork_idx]
            # Branch direction: rotate from parent's tip-direction by
            # branch_pitch, then jitter around it for organic spread.
            parent_dir = _normalize(
                (
                    parent.path[-1][0] - parent.path[0][0],
                    parent.path[-1][1] - parent.path[0][1],
                    parent.path[-1][2] - parent.path[0][2],
                )
            )
            azimuth = (k / max(1, n_children)) * 2.0 * math.pi + rng.uniform(
                -angle_jitter_rad, angle_jitter_rad
            )
            # Rotate parent_dir off-axis by branch_pitch around an
            # azimuthally chosen perpendicular.
            perp = _perpendicular(parent_dir)
            rotated_perp = _rotate_around(parent_dir, perp, azimuth)
            child_dir = _bend_direction(parent_dir, rotated_perp, branch_pitch_rad)
            child_path, _ = _segment_path(
                fork,
                child_dir,
                child_length,
                nodes=nodes_per_segment,
                bend_amount_rad=bend_amount_rad,
                bend_axis=rotated_perp,
            )
            seg = BranchSegment(
                path=child_path,
                base_radius=child_base,
                tip_radius=child_tip,
                depth=depth,
                parent_index=parent_idx,
                tip=child_path[-1],
            )
            new_idx = len(segments)
            segments.append(seg)
            parent.children.append(new_idx)
            _spawn(new_idx, depth + 1)

    _spawn(0, 1)
    return segments


def lower_to_swept_profiles(
    segments: list[BranchSegment],
    *,
    cross_section_sides: int = 6,
) -> list[dict]:
    """Lower branch segments into stable ShapeIR ``swept_profile`` records.

    Returns a list of dicts shaped like ``ShapePrimitive.to_dict()`` so
    the caller can hand them off to assembly code without depending on
    the dataclass at this layer.
    """
    primitives: list[dict] = []
    for idx, seg in enumerate(segments):
        radius = max(seg.base_radius, 0.04)
        cross_section = []
        for i in range(cross_section_sides):
            theta = 2.0 * math.pi * i / cross_section_sides
            cross_section.append((radius * math.cos(theta), radius * math.sin(theta)))
        primitives.append(
            {
                "primitive_type": "swept_profile",
                "part": f"branch_{idx}_d{seg.depth}",
                "center": (
                    sum(p[0] for p in seg.path) / len(seg.path),
                    sum(p[1] for p in seg.path) / len(seg.path),
                    sum(p[2] for p in seg.path) / len(seg.path),
                ),
                "axis": "y",
                "tags": ["vegetation", "branch", f"depth_{seg.depth}"],
                "blend_mode": "union",
                "cross_section": cross_section,
                "sweep_path": [tuple(p) for p in seg.path],
                "rounding": 0.0,
                # Carry a hint — taper from base to tip — for downstream
                # consumers that can honor varying radius.
                "vegetation_branch_taper": {
                    "base_radius_cm": seg.base_radius,
                    "tip_radius_cm": seg.tip_radius,
                },
                "wind_band": _wind_band_for_depth(seg.depth),
            }
        )
    return primitives


def _wind_band_for_depth(depth: int) -> int:
    """Map a recursion depth to the canonical wind-sway band index."""
    if depth == 0:
        return 0  # rigid trunk
    if depth == 1:
        return 1  # medium-sway main branches
    return 2  # max-sway secondary branches


def collect_leaf_anchor_points(
    segments: list[BranchSegment],
    *,
    min_depth: int = 2,
) -> list[tuple[tuple[float, float, float], int]]:
    """Pull anchor points from segments at or beyond ``min_depth``.

    Each point is paired with the segment's depth so the leaf scatterer
    can size and tint per-depth.
    """
    anchors: list[tuple[tuple[float, float, float], int]] = []
    for seg in segments:
        if seg.depth < min_depth:
            continue
        # Anchor at the tip plus midpoint, so foliage isn't only at tips.
        anchors.append((seg.tip, seg.depth))
        if len(seg.path) >= 3:
            anchors.append((seg.path[len(seg.path) // 2], seg.depth))
    return anchors
