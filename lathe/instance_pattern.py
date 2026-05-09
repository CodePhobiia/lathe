"""Surface-projected instance patterns and parametric greeble kits.

This module implements roadmap V0.1 Phase 1 §5.8 (real surface-projected
greebles) and Phase 3 §7.7 (richer Houdini-Copy-to-Points semantics).

Phase 1 baseline:

1. A Poisson-disk sampler over a rectangular face region. Returns N
   points obeying a minimum-distance constraint (no kdtree dependency,
   uses a uniform spatial hash bucketing scheme so behaviour stays
   deterministic and dependency-free).
2. A per-point local frame builder. Faces are inherited from
   ``BlueprintComponent`` extents (axis-aligned), so the face normal
   is one of ``+/-x|y|z`` and tangent/bitangent come from the other two
   axes; the resulting local-to-world rotation is encoded by mapping
   greeble-local axes to world axes (no full 4x4 needed for the v1
   ShapePrimitive vocabulary).
3. Parametric greeble kits. Each kit is a small bundle of 1-3
   ``ShapePrimitive`` items (cap + recess + washer style) emitted with
   the per-point world transform applied to their local offsets.

Phase 3 §7.7 extends the layout step toward Houdini Copy-to-Points:

* **Per-instance attribute variation** (``scale_jitter``,
  ``rotation_jitter``, ``material_variant_count``, ``age_gradient``).
  All deterministic given ``seed_token``.
* **Instance LODs** (``lod0``/``lod1``/``lod2``). Each kit chooses a
  detail level based on distance to a focal point in face space; far
  instances collapse to a single primitive, near instances keep full
  detail.
* **Face-mask gating** via the ``§6.4`` attribute mini-language. Caller
  passes ``mask_expression``; per Poisson sample we evaluate it and
  drop the sample when the mask reads ``< 0.5``.
* **Attribute-driven density** via ``density_modulator`` (also an
  attr-lang expression). Acceptance probability is proportional to the
  modulator value, so density tracks curvature, AO, etc.

Worked example (rivets-on-armor with curvature-driven density)::

    distribute_greeble_kits(
        component=armor_plate,
        face=plate_front_face,
        count=200,
        kit_factory=GREEBLE_KITS["bolt_cap"],
        seed_token="armor_v1",
        min_spacing=0.02,
        mask_expression="mask.curvature_peaks(threshold=0.2)",
        density_modulator="0.3 + 0.7 * mask.curvature_peaks(threshold=0.1)",
        scale_jitter=(0.85, 1.15),
        rotation_jitter=0.3,                # ±0.3 rad about face normal
        material_variant_count=4,
        age_gradient=True,
        lod_focal_point=(0.0, 0.0, 0.0),
    )

This produces ~120-180 effective bolts (the rest are dropped by
``mask_expression`` or by the density modulator), each with slight
scale/rotation variance, a per-instance material variant index, and an
LOD assignment based on distance to the focal point.

The greeble distribution is wired into the existing surface-detail
feature emitters (see ``feature_ops.bolt_grid_features`` and
``feature_ops.socket_point_features``) so authoring code does not
change. Phase 3 additions are pure-kwarg extensions with safe defaults,
so existing callers continue to work without modification.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from .assembly_kernel import BlueprintComponent
from .shape_ir import ShapePrimitive


# A "face" descriptor is the axis-aligned rectangular surface region on
# which greebles are scattered. ``normal_axis`` selects the world axis
# that is normal to the face; ``normal_sign`` selects which side
# (+1 = positive face, -1 = negative face). Tangent/bitangent are
# derived deterministically from the remaining axes.
@dataclass(frozen=True)
class FaceFrame:
    """Rectangular axis-aligned face on a component.

    ``origin`` is the world-space point at the face center.
    ``half_u`` and ``half_v`` are the half-extents of the face along
    its tangent/bitangent in world units (cm). ``tangent_axis`` and
    ``bitangent_axis`` are world axes ("x"|"y"|"z"). ``normal_axis``
    is the third axis; ``normal_sign`` is +1 for the positive face,
    -1 for the negative face.
    """

    origin: tuple[float, float, float]
    half_u: float
    half_v: float
    tangent_axis: str
    bitangent_axis: str
    normal_axis: str
    normal_sign: int


_AXIS_VECTORS: dict[str, tuple[float, float, float]] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def primary_face_frame(
    component: BlueprintComponent,
    *,
    normal_axis: str = "z",
    normal_sign: int = 1,
    inset_ratio: float = 0.92,
    offset_ratio: float = 0.46,
) -> FaceFrame:
    """Build a FaceFrame on the named axis-aligned face of ``component``.

    Greeble layout uses an inset rectangle (``inset_ratio`` of the full
    face) so kits don't ride the silhouette edge, and an offset
    (``offset_ratio`` of the half-extent on the normal axis) so the
    kit origin sits slightly proud of the face. Both ratios mirror
    the constants the legacy ``bolt_grid_features`` used to position
    its grid -- this keeps existing assets visually similar.
    """
    width, height, depth = component.extents
    cx, cy, cz = component.center
    if normal_axis == "z":
        tangent_axis, bitangent_axis = "x", "y"
        half_u, half_v = width * 0.5, height * 0.5
        origin = (cx, cy, cz + depth * 0.5 * normal_sign * (offset_ratio / 0.5))
    elif normal_axis == "x":
        tangent_axis, bitangent_axis = "y", "z"
        half_u, half_v = height * 0.5, depth * 0.5
        origin = (cx + width * 0.5 * normal_sign * (offset_ratio / 0.5), cy, cz)
    else:
        tangent_axis, bitangent_axis = "x", "z"
        half_u, half_v = width * 0.5, depth * 0.5
        origin = (cx, cy + height * 0.5 * normal_sign * (offset_ratio / 0.5), cz)

    return FaceFrame(
        origin=origin,
        half_u=max(half_u * inset_ratio, 1e-3),
        half_v=max(half_v * inset_ratio, 1e-3),
        tangent_axis=tangent_axis,
        bitangent_axis=bitangent_axis,
        normal_axis=normal_axis,
        normal_sign=int(1 if normal_sign >= 0 else -1),
    )


def project_uv_to_world(
    face: FaceFrame, u: float, v: float, normal_offset: float = 0.0
) -> tuple[float, float, float]:
    """Project a face-local (u, v, normal_offset) point to world space.

    ``u`` and ``v`` are coordinates in the face's tangent/bitangent
    plane (cm, signed about the face origin). ``normal_offset`` is a
    distance along the outward face normal.
    """
    ox, oy, oz = face.origin
    t = _AXIS_VECTORS[face.tangent_axis]
    b = _AXIS_VECTORS[face.bitangent_axis]
    n = _AXIS_VECTORS[face.normal_axis]
    sign = float(face.normal_sign)
    return (
        ox + t[0] * u + b[0] * v + n[0] * normal_offset * sign,
        oy + t[1] * u + b[1] * v + n[1] * normal_offset * sign,
        oz + t[2] * u + b[2] * v + n[2] * normal_offset * sign,
    )


# ---------------------------------------------------------------------------
# Poisson-disk sampling on a 2D rectangle.
# ---------------------------------------------------------------------------


def _hash_seed(*tokens: object) -> int:
    """Deterministic seed from arbitrary tokens (no hashing of objects)."""
    state = 0x811C9DC5  # FNV-1a 32-bit offset
    for token in tokens:
        text = repr(token)
        for ch in text:
            state ^= ord(ch) & 0xFF
            state = (state * 0x01000193) & 0xFFFFFFFF
    return state or 1


def _xorshift(state: list[int]) -> float:
    """Tiny deterministic xorshift32 -> float in [0, 1)."""
    s = state[0]
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= (s >> 17) & 0xFFFFFFFF
    s ^= (s << 5) & 0xFFFFFFFF
    s &= 0xFFFFFFFF
    if s == 0:
        s = 0x9E3779B9
    state[0] = s
    return s / float(0x100000000)


def poisson_disk_sample_rect(
    half_u: float,
    half_v: float,
    *,
    target_count: int,
    min_distance: float | None = None,
    seed: int = 1,
    max_attempts_per_point: int = 24,
) -> list[tuple[float, float]]:
    """Sample up to ``target_count`` points in [-hu,+hu] x [-hv,+hv].

    Uses a simple grid-bucket Poisson dart-throwing scheme. Pure
    Python; deterministic given ``seed``. If ``min_distance`` is None,
    it is computed from the rectangle area and the requested count so
    the result is well-spread but predictable.

    Returns at most ``target_count`` points. Falls back to as many
    valid points as fit; never raises if the disk constraint is too
    tight.
    """
    target_count = max(int(target_count), 0)
    if target_count == 0:
        return []
    half_u = max(float(half_u), 1e-4)
    half_v = max(float(half_v), 1e-4)
    area = (2.0 * half_u) * (2.0 * half_v)
    if min_distance is None:
        # Pack ``target_count`` disks into ``area``; min_distance is
        # the diameter that would leave each disk a full neighbourhood.
        min_distance = math.sqrt(area / max(target_count, 1)) * 0.72
    min_distance = max(float(min_distance), 1e-3)

    cell = min_distance / math.sqrt(2.0)
    cols = max(1, int(math.ceil((2.0 * half_u) / cell)))
    rows = max(1, int(math.ceil((2.0 * half_v) / cell)))
    grid: dict[tuple[int, int], tuple[float, float]] = {}

    def _cell_index(u: float, v: float) -> tuple[int, int]:
        return (
            min(cols - 1, max(0, int((u + half_u) / cell))),
            min(rows - 1, max(0, int((v + half_v) / cell))),
        )

    def _has_neighbour(u: float, v: float) -> bool:
        cx, cy = _cell_index(u, v)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                p = grid.get((cx + dx, cy + dy))
                if p is None:
                    continue
                du = p[0] - u
                dv = p[1] - v
                if du * du + dv * dv < min_distance * min_distance:
                    return True
        return False

    rng = [seed & 0xFFFFFFFF or 1]
    points: list[tuple[float, float]] = []

    # Seed with one anchor near center for stability.
    points.append((0.0, 0.0))
    grid[_cell_index(0.0, 0.0)] = (0.0, 0.0)

    # Bridson-style active list, but bounded by target_count.
    active = [0]
    while active and len(points) < target_count:
        idx = active[-1]
        anchor = points[idx]
        accepted = False
        for _ in range(max_attempts_per_point):
            angle = _xorshift(rng) * 2.0 * math.pi
            radius = min_distance * (1.0 + _xorshift(rng))  # in [r, 2r)
            u = anchor[0] + math.cos(angle) * radius
            v = anchor[1] + math.sin(angle) * radius
            if u < -half_u or u > half_u or v < -half_v or v > half_v:
                continue
            if _has_neighbour(u, v):
                continue
            points.append((u, v))
            grid[_cell_index(u, v)] = (u, v)
            active.append(len(points) - 1)
            accepted = True
            break
        if not accepted:
            active.pop()

    if len(points) < target_count:
        # Fall back: scatter remaining via stratified jitter to hit the
        # exact requested count (relaxes the disk constraint at the
        # tail rather than under-delivering greebles).
        deficit = target_count - len(points)
        side = max(1, int(math.ceil(math.sqrt(deficit))))
        step_u = (2.0 * half_u) / side
        step_v = (2.0 * half_v) / side
        emitted = 0
        for j in range(side):
            for i in range(side):
                if emitted >= deficit:
                    break
                u = -half_u + (i + 0.5) * step_u + (_xorshift(rng) - 0.5) * step_u * 0.4
                v = -half_v + (j + 0.5) * step_v + (_xorshift(rng) - 0.5) * step_v * 0.4
                u = max(-half_u, min(half_u, u))
                v = max(-half_v, min(half_v, v))
                points.append((u, v))
                emitted += 1

    return points[:target_count]


# ---------------------------------------------------------------------------
# Per-instance attribute variation (Phase 3 §7.7).
#
# Houdini Copy-to-Points exposes per-instance attributes (``pscale``,
# ``orient``, ``shop_materialpath``, ``age``). We mirror the subset most
# useful for game greebles: a uniform/3D scale multiplier, a rotation
# offset around the face normal (radians), an integer material-variant
# index that maps into a palette, and a 0..1 wear/age gradient. All four
# are deterministic given ``seed_token`` so re-runs reproduce the layout.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstanceAttributes:
    """Per-instance attribute variation for a single Copy-to-Points sample.

    ``scale_uniform`` is a uniform multiplier applied to all primitive
    radii / heights / extrude depths in the kit. ``scale_xyz`` is an
    optional anisotropic multiplier (tangent, bitangent, normal) applied
    on top of ``scale_uniform`` when not ``None`` -- the default 3-tuple
    of 1.0s leaves the kit isotropic.

    ``rotation`` is a rotation in radians about the face normal axis.
    Applied to extruded slot polygons (subtractive Phillips slot etc.)
    by rotating the polygon vertices in face-local space; revolved
    profiles are radially symmetric so the rotation is recorded as a tag
    only.

    ``material_variant_index`` is an integer in ``[0, palette_size)``
    that downstream surface programs read to pick a material variant
    (e.g. four shades of brass on a riveted armor plate). ``age`` is a
    float in ``[0, 1]`` driving wear material variation (0 = pristine,
    1 = fully aged).
    """

    scale_uniform: float = 1.0
    scale_xyz: tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotation: float = 0.0
    material_variant_index: int = 0
    age: float = 0.0

    def tags(self) -> list[str]:
        """Encode the attribute values as ShapePrimitive tags."""
        out: list[str] = [
            f"scale_{self.scale_uniform:.3f}",
            f"rot_{self.rotation:.3f}",
            f"mvar_{self.material_variant_index}",
            f"age_{self.age:.3f}",
        ]
        if self.scale_xyz != (1.0, 1.0, 1.0):
            out.append(
                "scale3_"
                f"{self.scale_xyz[0]:.3f}_"
                f"{self.scale_xyz[1]:.3f}_"
                f"{self.scale_xyz[2]:.3f}"
            )
        return out

    def radial_scale(self) -> float:
        """Effective radial multiplier (tangent+bitangent average)."""
        return self.scale_uniform * 0.5 * (self.scale_xyz[0] + self.scale_xyz[1])

    def axial_scale(self) -> float:
        """Effective axial (face-normal) multiplier."""
        return self.scale_uniform * self.scale_xyz[2]


_DEFAULT_ATTRIBUTES = InstanceAttributes()


def _scale_profile(
    profile: list[tuple[float, float]], radial: float, axial: float
) -> list[tuple[float, float]]:
    """Scale a (axial, radial) revolved profile by per-instance factors."""
    return [(p[0] * axial, p[1] * radial) for p in profile]


def _rotate_polygon_2d(
    polygon: list[tuple[float, float]], angle: float
) -> list[tuple[float, float]]:
    """Rotate a face-local 2D polygon by ``angle`` radians (CCW)."""
    if abs(angle) < 1e-6:
        return list(polygon)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return [(p[0] * cos_a - p[1] * sin_a, p[0] * sin_a + p[1] * cos_a) for p in polygon]


def _scale_polygon_2d(
    polygon: list[tuple[float, float]], sx: float, sy: float
) -> list[tuple[float, float]]:
    """Scale a face-local 2D polygon by tangent/bitangent factors."""
    return [(p[0] * sx, p[1] * sy) for p in polygon]


# ---------------------------------------------------------------------------
# Instance LOD selection (Phase 3 §7.7).
#
# Each kit ships in three detail levels:
#   lod0 — full kit (existing Phase 1 behavior)
#   lod1 — mid-range simplification (drop secondary primitives)
#   lod2 — far-range single primitive (cylinder/torus replacement)
#
# The caller supplies a ``lod_focal_point`` (face-local UV or world XYZ);
# if a focal point is set, distance to that point in face space drives
# LOD selection. Without a focal point every instance stays at lod0,
# preserving Phase 1 behavior.
# ---------------------------------------------------------------------------


def select_lod_level(
    sample_uv: tuple[float, float],
    *,
    focal_uv: tuple[float, float] | None,
    close_radius: float,
    mid_radius: float,
) -> int:
    """Return 0/1/2 LOD index based on distance from focal point.

    ``close_radius`` and ``mid_radius`` are face-local distances in cm.
    Samples within ``close_radius`` use ``lod0``; samples within
    ``mid_radius`` use ``lod1``; further samples use ``lod2``. When
    ``focal_uv`` is None every sample collapses to lod0.
    """
    if focal_uv is None:
        return 0
    du = sample_uv[0] - focal_uv[0]
    dv = sample_uv[1] - focal_uv[1]
    distance = math.hypot(du, dv)
    if distance <= max(close_radius, 1e-6):
        return 0
    if distance <= max(mid_radius, close_radius + 1e-6):
        return 1
    return 2


# ---------------------------------------------------------------------------
# Parametric greeble kits. Each kit returns 1-3 ShapePrimitive items
# anchored at a face-local sample point.
# ---------------------------------------------------------------------------


def _greeble_revolved(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    profile: list[tuple[float, float]],
    feature_kind: str,
    tags: list[str],
    blend_mode: str,
    normal_offset: float = 0.0,
) -> ShapePrimitive:
    """Emit a revolved_profile primitive about the face normal axis."""
    cx, cy, cz = project_uv_to_world(face, sample_uv[0], sample_uv[1], normal_offset)
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=component.part,
        center=(cx, cy, cz),
        axis=face.normal_axis,
        profile_points=profile,
        tags=["feature", feature_kind, *tags, "mesh_op_revolved_profile"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
    )


def _greeble_extruded(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    profile_polygon: list[tuple[float, float]],
    extrude_height: float,
    feature_kind: str,
    tags: list[str],
    blend_mode: str,
    normal_offset: float = 0.0,
    rounding: float = 0.0,
) -> ShapePrimitive:
    """Emit an extruded_profile primitive aligned with the face normal."""
    cx, cy, cz = project_uv_to_world(face, sample_uv[0], sample_uv[1], normal_offset)
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=component.part,
        center=(cx, cy, cz),
        axis=face.normal_axis,
        profile_polygon=profile_polygon,
        extrude_height=extrude_height,
        tags=["feature", feature_kind, *tags, "mesh_op_polyextrude"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _bolt_cap_profile(radius: float, height: float) -> list[tuple[float, float]]:
    """Domed hex-ish bolt cap profile (axial, radial)."""
    half = max(height * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half, radius * 0.94),
        (-half * 0.45, radius),
        (half * 0.10, radius * 0.96),
        (half * 0.55, radius * 0.74),
        (half, radius * 0.32),
    ]


def _washer_profile(radius: float, thickness: float) -> list[tuple[float, float]]:
    """Thin washer ring profile that sits flush under the bolt cap."""
    half = max(thickness * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half, radius * 0.62),
        (-half * 0.30, radius),
        (half * 0.30, radius),
        (half, radius * 0.62),
    ]


def _phillips_head_profile(radius: float, height: float) -> list[tuple[float, float]]:
    """Pan-head screw profile (axial, radial)."""
    half = max(height * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half, radius * 0.78),
        (-half * 0.55, radius * 0.98),
        (-half * 0.05, radius),
        (half * 0.45, radius * 0.86),
        (half, radius * 0.30),
    ]


def _phillips_slot_polygon(width: float) -> list[tuple[float, float]]:
    """Cross/Phillips slot cross-section (used as a subtractive extrude)."""
    half = max(width * 0.5, 0.0005)
    arm = max(width * 0.18, 0.0005)
    return [
        (-half, -arm),
        (-arm, -arm),
        (-arm, -half),
        (arm, -half),
        (arm, -arm),
        (half, -arm),
        (half, arm),
        (arm, arm),
        (arm, half),
        (-arm, half),
        (-arm, arm),
        (-half, arm),
    ]


def _button_cap_profile(radius: float, height: float) -> list[tuple[float, float]]:
    """Soft mushroom button cap (axial, radial)."""
    half = max(height * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half, radius * 0.86),
        (-half * 0.20, radius),
        (half * 0.30, radius * 0.92),
        (half * 0.70, radius * 0.62),
        (half, radius * 0.18),
    ]


def _rivet_dome_profile(radius: float) -> list[tuple[float, float]]:
    """Half-dome rivet profile (axial, radial)."""
    radius = max(radius, 0.001)
    return [
        (-radius * 0.92, radius * 0.10),
        (-radius * 0.60, radius * 0.62),
        (-radius * 0.20, radius * 0.92),
        (radius * 0.18, radius),
        (radius * 0.62, radius * 0.78),
        (radius, radius * 0.10),
    ]


def _socket_recess_profile(radius: float, depth: float) -> list[tuple[float, float]]:
    """Tapered cup profile used as a subtractive socket recess."""
    half = max(depth * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half, radius * 0.62),
        (-half * 0.20, radius),
        (half * 0.42, radius * 0.86),
        (half, radius * 0.42),
    ]


def bolt_cap_kit(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    radius: float,
    height: float,
    index: int,
    head_style: str = "hex",
    lod_level: int = 0,
    attributes: InstanceAttributes = _DEFAULT_ATTRIBUTES,
) -> list[ShapePrimitive]:
    """Bolt cap + washer kit.

    ``head_style`` is recorded as a tag for trace/QA but does not
    branch the geometry today (revolve handles all radial heads
    uniformly; the polygon-cap variant lives behind future work).

    LOD variants:
      lod0 — washer + bolt cap (2 primitives, default)
      lod1 — bolt cap only (washer dropped at mid range)
      lod2 — single cylinder primitive standing in for the cap.
    """
    radial = attributes.radial_scale()
    axial = attributes.axial_scale()
    cap_radius = max(radius * radial, 0.05)
    cap_height = max(height * axial, cap_radius * 0.55)
    washer_radius = cap_radius * 1.32
    washer_thickness = max(cap_height * 0.30, 0.05)

    base_tags = [
        "surface_detail",
        "greeble",
        "bolt",
        f"bolt_{index}",
        f"head_{head_style}",
        "instance_pattern_kit",
        f"lod{lod_level}",
        *attributes.tags(),
    ]

    if lod_level >= 2:
        return [
            ShapePrimitive(
                primitive_type="cylinder",
                part=component.part,
                center=project_uv_to_world(
                    face, sample_uv[0], sample_uv[1], cap_height * 0.5
                ),
                radius=cap_radius,
                height=cap_height,
                axis=face.normal_axis,
                tags=[*base_tags, "kit_cap_lod2", "lod_cylinder"],
                component="bolt_cap",
                region=component.name,
                blend_mode="union",
            ),
        ]

    primitives: list[ShapePrimitive] = []
    if lod_level == 0:
        primitives.append(
            _greeble_revolved(
                component,
                face,
                sample_uv,
                profile=_washer_profile(washer_radius, washer_thickness),
                feature_kind="bolt_washer",
                tags=[*base_tags, "kit_washer"],
                blend_mode="union",
                normal_offset=washer_thickness * 0.5,
            )
        )
        cap_offset = washer_thickness + cap_height * 0.5
    else:
        cap_offset = cap_height * 0.5
    primitives.append(
        _greeble_revolved(
            component,
            face,
            sample_uv,
            profile=_bolt_cap_profile(cap_radius, cap_height),
            feature_kind="bolt_cap",
            tags=[*base_tags, "kit_cap", "domed_bolt"],
            blend_mode="union",
            normal_offset=cap_offset,
        )
    )
    return primitives


def phillips_screw_kit(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    radius: float,
    depth: float,
    index: int,
    slot_count: int = 4,
    lod_level: int = 0,
    attributes: InstanceAttributes = _DEFAULT_ATTRIBUTES,
) -> list[ShapePrimitive]:
    """Pan-head screw with carved Phillips slot.

    ``slot_count`` is informational; the cross polygon implements the
    canonical 4-arm Phillips. A non-default slot_count (3 or 6) is
    recorded as a tag for variant tracking but the slot geometry stays
    a 4-arm cross until future variants are added.

    LOD variants:
      lod0 — pan head + Phillips slot (2 primitives, default)
      lod1 — pan head only (slot dropped at mid range)
      lod2 — single cylinder primitive standing in for the head.
    """
    radial = attributes.radial_scale()
    axial = attributes.axial_scale()
    head_radius = max(radius * radial, 0.05)
    head_height = max(depth * 0.55 * axial, head_radius * 0.40)
    slot_width = head_radius * 1.10
    slot_depth = max(depth * 0.40 * axial, 0.04)

    base_tags = [
        "surface_detail",
        "greeble",
        "phillips_screw",
        f"screw_{index}",
        f"slot_{slot_count}",
        "instance_pattern_kit",
        f"lod{lod_level}",
        *attributes.tags(),
    ]

    if lod_level >= 2:
        return [
            ShapePrimitive(
                primitive_type="cylinder",
                part=component.part,
                center=project_uv_to_world(
                    face, sample_uv[0], sample_uv[1], head_height * 0.5
                ),
                radius=head_radius,
                height=head_height,
                axis=face.normal_axis,
                tags=[*base_tags, "kit_head_lod2", "lod_cylinder"],
                component="phillips_head",
                region=component.name,
                blend_mode="union",
            ),
        ]

    primitives: list[ShapePrimitive] = [
        _greeble_revolved(
            component,
            face,
            sample_uv,
            profile=_phillips_head_profile(head_radius, head_height),
            feature_kind="phillips_head",
            tags=[*base_tags, "kit_head"],
            blend_mode="union",
            normal_offset=head_height * 0.5,
        )
    ]
    if lod_level == 0:
        slot_polygon = _phillips_slot_polygon(slot_width)
        slot_polygon = _rotate_polygon_2d(slot_polygon, attributes.rotation)
        primitives.append(
            _greeble_extruded(
                component,
                face,
                sample_uv,
                profile_polygon=slot_polygon,
                extrude_height=slot_depth,
                feature_kind="phillips_slot",
                tags=[*base_tags, "kit_slot"],
                blend_mode="subtract",
                normal_offset=head_height - slot_depth * 0.45,
            )
        )
    return primitives


def panel_button_kit(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    radius: float,
    height: float,
    index: int,
    lod_level: int = 0,
    attributes: InstanceAttributes = _DEFAULT_ATTRIBUTES,
) -> list[ShapePrimitive]:
    """Mushroom panel button.

    LOD variants:
      lod0 — full mushroom revolve (default).
      lod1 — same as lod0 (already minimal).
      lod2 — single cylinder primitive standing in for the cap.
    """
    radial = attributes.radial_scale()
    axial = attributes.axial_scale()
    cap_radius = max(radius * radial, 0.05)
    cap_height = max(height * axial, cap_radius * 0.45)
    base_tags = [
        "surface_detail",
        "greeble",
        "panel_button",
        f"button_{index}",
        "instance_pattern_kit",
        f"lod{lod_level}",
        *attributes.tags(),
    ]
    if lod_level >= 2:
        return [
            ShapePrimitive(
                primitive_type="cylinder",
                part=component.part,
                center=project_uv_to_world(
                    face, sample_uv[0], sample_uv[1], cap_height * 0.5
                ),
                radius=cap_radius,
                height=cap_height,
                axis=face.normal_axis,
                tags=[*base_tags, "kit_button_lod2", "lod_cylinder"],
                component="panel_button",
                region=component.name,
                blend_mode="union",
            ),
        ]
    return [
        _greeble_revolved(
            component,
            face,
            sample_uv,
            profile=_button_cap_profile(cap_radius, cap_height),
            feature_kind="panel_button",
            tags=[*base_tags, "kit_button"],
            blend_mode="union",
            normal_offset=cap_height * 0.5,
        )
    ]


def rivet_kit(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    radius: float,
    index: int,
    lod_level: int = 0,
    attributes: InstanceAttributes = _DEFAULT_ATTRIBUTES,
) -> list[ShapePrimitive]:
    """Half-sphere rivet dome.

    LOD variants:
      lod0 — full half-dome revolve (default).
      lod1 — same as lod0 (already minimal).
      lod2 — single sphere primitive standing in for the dome.
    """
    radial = attributes.radial_scale()
    dome_radius = max(radius * radial, 0.04)
    base_tags = [
        "surface_detail",
        "greeble",
        "rivet",
        f"rivet_{index}",
        "instance_pattern_kit",
        f"lod{lod_level}",
        *attributes.tags(),
    ]
    if lod_level >= 2:
        return [
            ShapePrimitive(
                primitive_type="sphere",
                part=component.part,
                center=project_uv_to_world(
                    face, sample_uv[0], sample_uv[1], dome_radius * 0.40
                ),
                radius=dome_radius,
                axis=face.normal_axis,
                tags=[*base_tags, "kit_dome_lod2", "lod_sphere"],
                component="rivet",
                region=component.name,
                blend_mode="union",
            ),
        ]
    return [
        _greeble_revolved(
            component,
            face,
            sample_uv,
            profile=_rivet_dome_profile(dome_radius),
            feature_kind="rivet",
            tags=[*base_tags, "kit_dome"],
            blend_mode="union",
            normal_offset=dome_radius * 0.40,
        )
    ]


def socket_point_kit(
    component: BlueprintComponent,
    face: FaceFrame,
    sample_uv: tuple[float, float],
    *,
    radius: float,
    depth: float,
    index: int,
    lod_level: int = 0,
    attributes: InstanceAttributes = _DEFAULT_ATTRIBUTES,
) -> list[ShapePrimitive]:
    """Recessed socket cup + raised collar ring.

    Replaces the legacy single-revolved-cup that ``socket_point_features``
    used to emit with a cup + collar pair, so connectors read as
    socketed connectors rather than as plain holes.

    LOD variants:
      lod0 — collar + recessed cup (2 primitives, default).
      lod1 — recessed cup only (collar dropped at mid range).
      lod2 — single torus primitive standing in for the cup rim.
    """
    radial = attributes.radial_scale()
    axial = attributes.axial_scale()
    cup_radius = max(radius * radial, 0.06)
    cup_depth = max(depth * axial, cup_radius * 0.85)
    collar_radius = cup_radius * 1.28
    collar_thickness = max(cup_depth * 0.22, 0.05)

    base_tags = [
        "surface_detail",
        "socket",
        "connector",
        f"socket_{index}",
        "instance_pattern_kit",
        f"lod{lod_level}",
        *attributes.tags(),
    ]

    if lod_level >= 2:
        return [
            ShapePrimitive(
                primitive_type="torus",
                part=component.part,
                center=project_uv_to_world(
                    face, sample_uv[0], sample_uv[1], collar_thickness * 0.5
                ),
                axis=face.normal_axis,
                major_radius=collar_radius,
                minor_radius=max(collar_thickness * 0.5, 0.02),
                tags=[*base_tags, "kit_socket_lod2", "lod_torus"],
                component="socket_recess",
                region=component.name,
                blend_mode="union",
            ),
        ]

    primitives: list[ShapePrimitive] = []
    if lod_level == 0:
        primitives.append(
            _greeble_revolved(
                component,
                face,
                sample_uv,
                profile=_washer_profile(collar_radius, collar_thickness),
                feature_kind="socket_collar",
                tags=[*base_tags, "kit_collar"],
                blend_mode="union",
                normal_offset=collar_thickness * 0.5,
            )
        )
    primitives.append(
        _greeble_revolved(
            component,
            face,
            sample_uv,
            profile=_socket_recess_profile(cup_radius, cup_depth),
            feature_kind="socket_recess",
            tags=[*base_tags, "kit_recess", "lathed_socket_cup"],
            blend_mode="subtract",
            normal_offset=-cup_depth * 0.10,
        )
    )
    return primitives


# Public registry of kits keyed by name. ``feature_ops`` selects from
# this registry when promoting a 2D-grid greeble emitter to a real
# instance pattern.
GreebleKit = Callable[..., list[ShapePrimitive]]
GREEBLE_KITS: dict[str, GreebleKit] = {
    "bolt_cap": bolt_cap_kit,
    "phillips_screw": phillips_screw_kit,
    "panel_button": panel_button_kit,
    "rivet": rivet_kit,
    "socket_point": socket_point_kit,
}


# ---------------------------------------------------------------------------
# Surface-projected instance pattern entry point.
# ---------------------------------------------------------------------------


def _build_attr_lang_context(
    sample: tuple[float, float],
    *,
    face: FaceFrame,
    index: int,
    palettes: dict[str, list] | None,
):
    """Build an attr-lang ``EvalContext`` seeded with surface signals.

    Auto-derived signals seeded for each Poisson sample:

    - ``@uv``         normalized face-local coordinates in ``[-1, +1]``.
    - ``@P`` / ``@world_pos`` world-space sample point.
    - ``@P_local``    face-local ``(u, v, 0)``.
    - ``@N``          outward face normal (signed by ``normal_sign``).
    - ``@up_dot``     dot of ``@N`` with world-up (Z).
    - ``@id`` / ``@face_index`` integer sample index.
    - ``@curvature``, ``@ao``, ``@height``  defaults (0.0) so mask
      built-ins like ``mask.curvature_peaks`` evaluate without raising
      on rectangular face frames that lack richer signals; callers with
      real curvature data can pre-populate ``palettes`` and override.
    - ``@material_zone`` 0 by default.
    """
    from .attr_lang import EvalContext  # local import: avoid cycles at import time

    world = project_uv_to_world(face, sample[0], sample[1])
    normal = _AXIS_VECTORS[face.normal_axis]
    normal = tuple(c * face.normal_sign for c in normal)
    return EvalContext(
        attrs={
            "uv": (
                sample[0] / max(face.half_u, 1e-9),
                sample[1] / max(face.half_v, 1e-9),
            ),
            "P": world,
            "world_pos": world,
            "P_local": (sample[0], sample[1], 0.0),
            "N": normal,
            "up_dot": float(normal[2]),
            "id": index,
            "face_index": index,
            "vertex_index": index,
            "curvature": 0.0,
            "ao": 0.5,
            "height": 0.0,
            "material_zone": 0,
        },
        palettes=palettes or {},
    )


def _coerce_to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.0 if bool(value) else 0.0


def _kit_factory_supports(factory: Callable[..., list[ShapePrimitive]], *names: str) -> dict[str, bool]:
    """Return ``{name: supported}`` for kwargs the factory accepts.

    Falls back to "not supported" when the signature cannot be
    introspected (e.g. C-implemented callables); existing 4-arg
    factories declared in ``feature_ops`` therefore continue to work.
    """
    import inspect

    try:
        sig = inspect.signature(factory)
    except (TypeError, ValueError):
        return {name: False for name in names}
    params = sig.parameters
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    return {name: has_var_kw or name in params for name in names}


def distribute_greeble_kits(
    component: BlueprintComponent,
    face: FaceFrame,
    *,
    count: int,
    kit_factory: Callable[..., list[ShapePrimitive]],
    seed_token: object = "greeble",
    min_spacing: float | None = None,
    density_modulator: str | None = None,
    density_expression: str | None = None,
    mask_expression: str | None = None,
    scale_jitter: float | tuple[float, float] | tuple[float, float, float] | tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None = None,
    rotation_jitter: float | tuple[float, float] = 0.0,
    material_variant_count: int = 0,
    age_gradient: bool | tuple[float, float] = False,
    lod_focal_point: tuple[float, float] | tuple[float, float, float] | None = None,
    lod_close_radius: float | None = None,
    lod_mid_radius: float | None = None,
    palettes: dict[str, list] | None = None,
) -> list[ShapePrimitive]:
    """Distribute ``count`` greeble kits via Poisson-disk on ``face``.

    ``kit_factory`` receives ``(component, face, sample_uv, index)`` and
    returns the per-kit list of ShapePrimitive items. Factories that
    accept ``lod_level=`` and/or ``attributes=`` kwargs (the kits in
    ``GREEBLE_KITS`` do) automatically get per-instance LOD selection
    and attribute variation; legacy factories without those kwargs
    continue to work unchanged. The seed for the Poisson sampler is
    derived from ``component.name`` and ``seed_token`` so the same
    asset always lays the kits out the same way (a hard requirement
    for deterministic certification).

    Phase 3 §7.7 kwargs (all optional, default to Phase 1 behavior):

    ``mask_expression``
        Attr-lang expression evaluated per sample. Result ``>= 0.5``
        keeps the kit, ``< 0.5`` drops it. Use to gate samples by
        curvature, AO, slope, etc.
    ``density_modulator``
        Attr-lang expression evaluated per Poisson candidate. Sample
        acceptance probability is proportional to its value (clamped
        ``[0, 1]``). ``density_expression`` is a deprecated alias.
    ``scale_jitter``
        Per-sample scale multiplier. ``float`` ⇒ uniform jitter in
        ``[1-x, 1+x]``; ``(lo, hi)`` ⇒ uniform draw; ``(sx, sy, sz)``
        ⇒ anisotropic jitter range (each entry can itself be a tuple
        ``(lo, hi)`` for explicit ranges). Defaults to no jitter.
    ``rotation_jitter``
        Per-sample rotation about the face normal (radians). ``float``
        ⇒ symmetric range ``[-r, +r]``; ``(lo, hi)`` ⇒ asymmetric.
    ``material_variant_count``
        Integer palette size; per-sample ``material_variant_index`` is
        drawn uniformly in ``[0, count)``. ``0`` (default) emits 0 for
        every sample.
    ``age_gradient``
        ``True`` enables a per-sample wear/age float in ``[0, 1]``;
        ``(lo, hi)`` clamps to a custom range.
    ``lod_focal_point``
        Face-local ``(u, v)`` (cm) or world ``(x, y, z)`` (cm)
        proximity center. Without one every sample stays at lod0.
    ``lod_close_radius`` / ``lod_mid_radius``
        Override the lod0/lod1 cutoff distances (face-local cm). When
        ``None`` they default to ``1.0 * face_diagonal`` and
        ``2.0 * face_diagonal`` respectively.
    ``palettes``
        Forwarded to the attr-lang context for ``palette.lookup`` and
        ``ramp`` built-ins used inside the expressions.
    """
    if count <= 0:
        return []
    seed = _hash_seed(component.name, component.part, seed_token, count)
    samples = poisson_disk_sample_rect(
        face.half_u,
        face.half_v,
        target_count=count,
        min_distance=min_spacing,
        seed=seed,
    )

    # Resolve `density_expression` deprecated alias.
    if density_modulator is None and density_expression is not None:
        density_modulator = density_expression

    # Compile attr-lang programs once.
    compiled_mask = None
    compiled_density = None
    if mask_expression is not None or density_modulator is not None:
        from .attr_lang import compile_expression  # local import to avoid cycles

        if mask_expression is not None:
            compiled_mask = compile_expression(mask_expression)
        if density_modulator is not None:
            compiled_density = compile_expression(density_modulator)

    # Convert world-space focal point to face-local UV if needed.
    focal_uv: tuple[float, float] | None = None
    if lod_focal_point is not None:
        if len(lod_focal_point) == 2:
            focal_uv = (float(lod_focal_point[0]), float(lod_focal_point[1]))
        else:
            t = _AXIS_VECTORS[face.tangent_axis]
            b = _AXIS_VECTORS[face.bitangent_axis]
            ox, oy, oz = face.origin
            fx, fy, fz = lod_focal_point
            dx, dy, dz = fx - ox, fy - oy, fz - oz
            focal_uv = (
                t[0] * dx + t[1] * dy + t[2] * dz,
                b[0] * dx + b[1] * dy + b[2] * dz,
            )

    # LOD radii default from face diagonal.
    diag = math.hypot(face.half_u, face.half_v) * 2.0
    close_r = float(lod_close_radius) if lod_close_radius is not None else max(diag, 1e-3)
    mid_r = float(lod_mid_radius) if lod_mid_radius is not None else max(diag * 2.0, close_r + 1e-3)

    # Normalize jitter parameters into per-axis (lo, hi) ranges.
    scale_ranges = _resolve_scale_jitter(scale_jitter)
    rot_lo, rot_hi = _resolve_rotation_jitter(rotation_jitter)
    age_lo, age_hi = _resolve_age_range(age_gradient)

    factory_caps = _kit_factory_supports(kit_factory, "lod_level", "attributes")

    # Per-sample deterministic RNG seeded off the layout seed.
    jitter_state = [(seed * 0x9E3779B1) & 0xFFFFFFFF or 1]

    primitives: list[ShapePrimitive] = []
    for index, sample in enumerate(samples):
        # Mask gating.
        if compiled_mask is not None:
            ctx = _build_attr_lang_context(sample, face=face, index=index, palettes=palettes)
            mask_value = _coerce_to_float(compiled_mask(ctx))
            if mask_value < 0.5:
                continue

        # Density modulation (probabilistic acceptance).
        if compiled_density is not None:
            ctx = _build_attr_lang_context(sample, face=face, index=index, palettes=palettes)
            density_value = _coerce_to_float(compiled_density(ctx))
            density_value = max(0.0, min(1.0, density_value))
            if _xorshift(jitter_state) > density_value:
                continue

        # Per-instance attributes.
        attrs_kwargs = _draw_instance_attributes(
            jitter_state,
            scale_ranges=scale_ranges,
            rot_range=(rot_lo, rot_hi),
            material_variant_count=material_variant_count,
            age_range=(age_lo, age_hi),
        )

        # LOD selection.
        lod_level = select_lod_level(
            sample,
            focal_uv=focal_uv,
            close_radius=close_r,
            mid_radius=mid_r,
        )

        kwargs: dict[str, object] = {}
        if factory_caps.get("lod_level"):
            kwargs["lod_level"] = lod_level
        if factory_caps.get("attributes"):
            kwargs["attributes"] = attrs_kwargs
        primitives.extend(kit_factory(component, face, sample, index, **kwargs))
    return primitives


def _resolve_scale_jitter(
    scale_jitter: object,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Normalize scale_jitter into ``((lo,hi),(lo,hi),(lo,hi))`` per-axis."""
    if scale_jitter is None:
        return ((1.0, 1.0), (1.0, 1.0), (1.0, 1.0))
    if isinstance(scale_jitter, (int, float)):
        delta = float(scale_jitter)
        rng = (1.0 - delta, 1.0 + delta)
        return (rng, rng, rng)
    if isinstance(scale_jitter, tuple) and len(scale_jitter) == 2 and all(
        isinstance(x, (int, float)) for x in scale_jitter
    ):
        # (lo, hi) uniform jitter applied to all three axes.
        rng = (float(scale_jitter[0]), float(scale_jitter[1]))
        return (rng, rng, rng)
    if isinstance(scale_jitter, tuple) and len(scale_jitter) == 3:
        out: list[tuple[float, float]] = []
        for axis_jitter in scale_jitter:
            if isinstance(axis_jitter, (int, float)):
                d = float(axis_jitter)
                out.append((1.0 - d, 1.0 + d))
            elif isinstance(axis_jitter, tuple) and len(axis_jitter) == 2:
                out.append((float(axis_jitter[0]), float(axis_jitter[1])))
            else:
                out.append((1.0, 1.0))
        return (out[0], out[1], out[2])
    return ((1.0, 1.0), (1.0, 1.0), (1.0, 1.0))


def _resolve_rotation_jitter(rotation_jitter: object) -> tuple[float, float]:
    if isinstance(rotation_jitter, (int, float)):
        r = float(rotation_jitter)
        return (-r, r)
    if isinstance(rotation_jitter, tuple) and len(rotation_jitter) == 2:
        return (float(rotation_jitter[0]), float(rotation_jitter[1]))
    return (0.0, 0.0)


def _resolve_age_range(age_gradient: object) -> tuple[float, float]:
    if age_gradient is False or age_gradient is None:
        return (0.0, 0.0)
    if age_gradient is True:
        return (0.0, 1.0)
    if isinstance(age_gradient, tuple) and len(age_gradient) == 2:
        return (float(age_gradient[0]), float(age_gradient[1]))
    return (0.0, 0.0)


def _draw_instance_attributes(
    rng_state: list[int],
    *,
    scale_ranges: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    rot_range: tuple[float, float],
    material_variant_count: int,
    age_range: tuple[float, float],
) -> InstanceAttributes:
    """Draw a deterministic ``InstanceAttributes`` from the RNG."""

    def _u(lo: float, hi: float) -> float:
        if lo == hi:
            return lo
        return lo + (hi - lo) * _xorshift(rng_state)

    sx = _u(*scale_ranges[0])
    sy = _u(*scale_ranges[1])
    sz = _u(*scale_ranges[2])
    rotation = _u(*rot_range)
    if material_variant_count > 0:
        variant = int(_xorshift(rng_state) * material_variant_count)
        variant = max(0, min(material_variant_count - 1, variant))
    else:
        variant = 0
    age = _u(*age_range)
    return InstanceAttributes(
        scale_uniform=1.0,
        scale_xyz=(sx, sy, sz),
        rotation=rotation,
        material_variant_index=variant,
        age=age,
    )
