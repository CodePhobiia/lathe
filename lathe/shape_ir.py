"""ShapeIR: intermediate representation for the shape stage.

Captures the authoritative geometry definition (scaffolds, features,
boolean ops, boundary constraints) in a form downstream stages can
read deterministically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ShapePrimitive:
    """ShapePrimitive.

    Currently supported ``primitive_type`` values:

    - ``"box"``: axis-aligned cuboid; uses ``extents`` (full, not half).
    - ``"cylinder"``: round cylinder along ``axis``; uses ``radius`` + ``height``.
    - ``"revolved_profile"``: solid of revolution around ``axis`` through
      ``center``, defined by ``profile_points`` as a list of
      ``(axial, radial)`` 2D points (cm). The profile is revolved 360° to
      produce a watertight, radially-symmetric mesh — the deterministic
      vocabulary needed for hard-surface assets like rifle barrels,
      scope tubes, magazine bodies, and stocks-of-revolution that the
      box+cylinder vocabulary cannot express.
    - ``"extruded_profile"``: linear extrusion of a 2D polygon along
      ``axis`` through ``center``, defined by ``profile_polygon`` as a
      CCW list of ``(u, v)`` 2D points in the cross-section plane
      perpendicular to ``axis``, swept ``extrude_height`` along ``axis``.
      Produces watertight prismatic geometry — the deterministic
      vocabulary for hard-surface features with a constant cross-section
      that the box+cylinder vocabulary cannot express: picatinny rails,
      magazine bodies, trigger groups, charging-handle slots, plate
      stocks, etc.
    - ``"torus"``: ring solid centered on ``center`` with ring axis
      ``axis``, defined by ``major_radius`` (distance from the ring
      center to the center of the tube) and ``minor_radius`` (tube
      radius). Closes the gap between cylinders and full revolved
      profiles for ring-shaped features such as trigger guards, sling
      loops, scope rings, and cap collars where authoring an entire
      profile polyline would be overkill.
    - ``"subdivision_box"``: axis-aligned cuboid with **per-corner**
      controllable rounding radii. Generalizes the uniform ``rounding``
      knob on ``"box"`` so each of the 8 corners gets its own radius
      (zero ⇒ sharp). Uses ``extents`` and ``center`` like a box, plus
      ``corner_radii`` (8-tuple) and ``corner_segments`` for mesh
      density. Order of corners follows
      ``(-x-y-z, +x-y-z, -x+y-z, +x+y-z, -x-y+z, +x-y+z, -x+y+z, +x+y+z)``
      so authors can round one face/edge/corner without touching the
      others — receivers with rounded backs / sharp fronts, stocks with
      chamfered buttplates, magazine wells with eased entry corners.
    """

    primitive_type: str
    part: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float] | None = None
    radius: float | None = None
    height: float | None = None
    axis: str = "y"
    tags: list[str] = field(default_factory=list)
    component: str | None = None
    region: str | None = None
    blend_mode: str = "union"
    rounding: float = 0.0
    # ``profile_points`` is a list of (axial, radial) 2D points used by
    # ``primitive_type="revolved_profile"``. None for box/cylinder.
    profile_points: list[tuple[float, float]] | None = None
    # ``profile_polygon`` is a CCW list of (u, v) 2D points in the
    # cross-section plane perpendicular to ``axis``, used by
    # ``primitive_type="extruded_profile"``. None for other types.
    profile_polygon: list[tuple[float, float]] | None = None
    # ``extrude_height`` is the linear sweep distance along ``axis`` for
    # ``primitive_type="extruded_profile"``. None for other types.
    extrude_height: float | None = None
    # ``major_radius`` / ``minor_radius`` are used by
    # ``primitive_type="torus"``: ``major_radius`` is the distance from
    # the ring center to the center of the tube, ``minor_radius`` is the
    # tube radius. None for non-torus primitives.
    major_radius: float | None = None
    minor_radius: float | None = None
    # ``corner_radii`` is an 8-tuple of per-corner rounding radii used by
    # ``primitive_type="subdivision_box"``. Order matches the cube's
    # vertex enumeration:
    # (-x-y-z, +x-y-z, -x+y-z, +x+y-z, -x-y+z, +x-y+z, -x+y+z, +x+y+z).
    # ``None`` for non-subdivision primitives.
    corner_radii: tuple[float, float, float, float, float, float, float, float] | None = None
    # ``corner_segments`` controls the per-corner sphere tessellation for
    # ``primitive_type="subdivision_box"``. Higher = smoother corners.
    corner_segments: int = 4

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class ShapeRegion:
    """ShapeRegion."""

    name: str
    part: str
    component: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    tags: list[str] = field(default_factory=list)
    adjacency: list[str] = field(default_factory=list)
    symmetry_mate: str | None = None
    interface_role: str | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class ShapeIR:
    """ShapeIR."""

    asset_name: str
    family: str
    blueprint_id: str
    symmetry_axis: str | None
    units: str
    primitives: list[ShapePrimitive]
    regions: list[ShapeRegion]
    primitives_used: list[str]
    part_graph: list[dict[str, str]]
    signature: dict[str, Any]
    assessment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        payload = asdict(self)
        payload["primitives"] = [primitive.to_dict() for primitive in self.primitives]
        payload["regions"] = [region.to_dict() for region in self.regions]
        return payload
