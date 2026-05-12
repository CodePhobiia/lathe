"""ShapeIR: intermediate representation for the shape stage.

Captures the authoritative geometry definition (scaffolds, features,
boolean ops, boundary constraints) in a form downstream stages can
read deterministically.
"""

from __future__ import annotations

import weakref
from dataclasses import asdict, dataclass, field
from typing import Any


# Step 2 of the kernel-perf audit (after Step 1 found no net win from
# bulk deepcopy→_metadata_safe_value swap): cache ShapePrimitive.to_dict()
# results. The profile shows 29 calls × 0.46s = 13.3s in a 7-primitive
# build — the same primitive instance gets to_dict'd many times during
# v1 lowering. ShapePrimitive isn't hashable (mutable dataclass), so
# this is a WeakValueDictionary keyed by id(instance) — when the
# primitive is garbage-collected, its cached dict is collected too.
# Mutating a primitive after a to_dict() call won't invalidate the
# cache, but no code path in the lowering chain does so today.
_TO_DICT_CACHE: weakref.WeakValueDictionary[int, dict[str, Any]] = (
    weakref.WeakValueDictionary()
)


class _CachedDict(dict):
    """Plain dict subclass so WeakValueDictionary can hold weak refs.

    WeakValueDictionary requires values to be weak-referenceable;
    builtin dict isn't, but a subclass is.
    """
    __slots__ = ("__weakref__",)


@dataclass
class ShapePrimitive:
    """ShapePrimitive.

    Currently supported ``primitive_type`` values:

    - ``"box"``: axis-aligned cuboid; uses ``extents`` (full, not half).
    - ``"cylinder"``: round cylinder along ``axis``; uses ``radius`` + ``height``.
    - ``"sphere"``: round solid centered on ``center``; uses ``radius``.
      This is the smallest organic/soft-form primitive in the stable
      ShapeIR vocabulary and is used for domes, foliage masses, bulbs,
      rounded caps, soft props, and any component that should not be
      coerced into a box or cylinder.
    - ``"capsule"``: a cylinder with hemispherical end caps along
      ``axis``; uses ``radius`` plus total ``length``. This is the
      stable rounded-strut vocabulary for handles, limbs, hoses, rails,
      pads, and ergonomic mechanical forms that should not collapse
      into three unrelated cylinder/sphere parts.
    - ``"revolved_profile"``: solid of revolution around ``axis`` through
      ``center``, defined by ``profile_points`` as a list of
      ``(axial, radial)`` 2D points (cm). By default the profile is revolved
      360 degrees to produce a watertight, radially-symmetric mesh; optional
      ``revolve_degrees`` and ``revolve_start_degrees`` can emit capped
      partial revolves for fan guards, knobs, cutaway collars, and
      crescent-shaped hard-surface details that a full lathe cannot express.
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
    - ``"tube"``: a straight hollow cylinder along ``axis`` with
      ``outer_radius``, ``inner_radius``, and ``height``. It preserves
      annular rims, bores, sockets, barrels, collars, and pipe sections
      as one semantic primitive instead of a subtractive cylinder pair.
    - ``"gear"``: an extruded involute-style spur/helical gear with
      ``teeth``, ``pitch_radius``, ``thickness``, optional bore, and
      tooth profile controls. It preserves mechanical tooth intent as
      a semantic primitive instead of an anonymous extruded polygon.
    - ``"flange"``: an annular mounting plate with optional straight
      bolt-circle holes. It uses ``outer_radius``, ``inner_radius``,
      ``thickness``, optional ``bolt_count``, ``bolt_radius``,
      ``bolt_circle_radius``, ``start_angle_degrees``, and ``rim_bevel``.
      It preserves mechanical mounting intent as one semantic primitive
      instead of an anonymous tube plus repeated subtractive cylinders.
    - ``"rounded_slot"``: a capsule-ended slot cutter/solid with
      ``length``, ``width``, ``depth``, ``axis``, and optional
      ``rotation_degrees``. It preserves slotted-hole intent instead of
      lowering immediately into an anonymous extruded profile.
    - ``"socket"``: a semantic seating/clearance cutter or solid for
      component integration. Uses ``socket_shape``/``style`` plus
      ``clearance``, ``width``, ``height``, ``depth``, optional ``radius``,
      ``length``, ``axis``, and ``rotation_degrees`` to preserve round,
      rectangular, and capsule socket intent instead of erasing it into
      anonymous cylinder/profile cutters.
    - ``"countersunk_hole"``: a straight, countersunk, or counterbored
      cylindrical bore cutter generated from ``radius``, ``depth``,
      ``style``, and optional sink/bore shoulder dimensions. It keeps
      hole style intent visible to the kernel instead of erasing it into
      a generic revolved profile.
    - ``"countersunk_hole_set"``: repeated straight, countersunk, or
      counterbored bore cutters sharing one style/dimension definition.
      Uses ``hole_centers``, ``radius``, ``depth``, ``axis``, ``style``,
      and optional sink/bore shoulder dimensions so screw-hole patterns
      survive as one semantic cutter field.
    - ``"panel"``: a rectangular or rounded rectangular plate generated
      from ``width``, ``height``, ``thickness``, ``axis``, optional
      ``rounding``, and ``corner_segments``. It preserves panel intent
      instead of erasing the source into a generic extruded polygon.
    - ``"panel_frame"``: a rectangular frame/ring generated from
      ``width``, ``height``, ``border_width``, ``thickness``, and frame
      axes. It preserves framed-panel intent as one semantic primitive
      instead of four unrelated box bars.
    - ``"panel_line_cut"``: a semantic rectangular groove/cutter generated
      from ``length``, ``width``, ``depth``, ``length_axis``,
      ``width_axis``, and ``normal_axis``. It preserves panel-line/groove
      intent for hard-surface seams instead of erasing it into an
      anonymous extruded profile.
    - ``"inset_cut"``: a semantic shallow face-recess cutter generated
      from a source envelope or explicit extents. It preserves inset/recess
      intent, side, normal axis, and margin instead of lowering directly
      to an anonymous box.
    - ``"ribbed_panel"``: a panel with repeated raised stiffener ribs.
      It uses ``width``, ``height``, ``thickness``, ``rib_count``, rib
      sizing/profile fields, optional cross ribs, and axis controls so
      reinforced hatches and sci-fi plates stay one semantic construct.
    - ``"perforated_panel"``: a rectangular or rounded plate with a
      grid/staggered grid of circular or rounded-slot through-holes. It
      keeps grate, vent, and armor-perforation intent visible as one
      semantic primitive.
    - ``"fastener_grid"``: a repeated washer/head hardware grid generated
      from row/column counts, spacing, radius, head style, washer controls,
      normal axis, and row/column axes. It keeps purposeful bolt/rivet
      detail as one semantic construct instead of loose cylinders or
      revolved-profile instances.
    - ``"weld_seam"``: a semantic weld bead generated either along an
      explicit path or along a straight axis. Uses ``weld_mode``,
      ``width``, ``radius``, ``cross_section``/``sweep_path`` for path
      welds, or ``length``/``axis`` for straight welds so attachment
      seams remain weld intent instead of anonymous swept/extruded profiles.
    - ``"edge_chip_set"``: a repeated set of spherical edge/corner chip
      cutters generated from a source envelope, selected corner signs, and
      chip radius. It preserves damage intent as one semantic operation
      instead of unrelated subtractive spheres.
    - ``"dent_mask_set"``: a repeated set of spherical dent cutters
      placed on a source face. Uses ``dent_centers``, ``radius``,
      ``depth``, ``normal_axis``, and ``side`` so impact/damage masks
      remain a coherent semantic field instead of unrelated spheres.
    - ``"surface_patch_set"``: a repeated set of rectangular surface
      patches or shallow groove cutters. Uses ``patch_centers``,
      ``patch_kind``, ``length``, ``width``, depth/thickness, and tangent
      axes so scratches, grime strips, and similar surface detail remain
      one semantic field instead of unrelated boxes.
    - ``"structural_beam"``: an extruded structural section such as an
      I-beam, C-channel, U-channel, L-angle, or T-beam. It uses
      ``length``, ``width``, ``height``, ``profile_shape``,
      ``web_thickness``, and ``flange_thickness`` so supports and frames
      remain semantic instead of becoming anonymous extruded polygons.
    - ``"rail"``: an extruded mechanical rail section such as square,
      rectangular, dovetail, trapezoid, or T-slot. It uses ``length``,
      ``profile``, ``profile_height``, ``profile_shape``, and optional
      shape-specific width controls so guide rails, machine tracks, and
      keyed mounts remain semantic kernel primitives.
    - ``"louver_panel"``: a framed panel with repeated angled slats. It
      uses ``width``, ``height``, ``thickness``, ``slat_count``, slat
      sizing/angle fields, and optional axis controls so vent grilles,
      shutters, heat exchangers, and sci-fi panels stay one semantic
      visible construct instead of loose boxes and anonymous extrusions.
    - ``"vent_slats"``: a repeated rectangular slat array generated from
      ``slat_count``, ``slat_spacing``, ``length``, ``height``,
      ``thickness``, normal axis, row axis, and length axis. It preserves
      vent/readable-secondary-detail intent without exploding the common
      case into anonymous box records.
    - ``"ladder_frame"``: two side rails plus repeated rungs, generated
      from ``length``, ``width``, ``rail_radius``, ``rung_count``,
      optional rung radius/spacing/span controls, and axis fields. It
      preserves rail-and-rung frame intent as one semantic construct
      instead of a loose set of cylinders.
    - ``"truss_frame"``: chords, posts, diagonal braces, and optional
      depth ties generated from ``length``, ``height``, ``depth``,
      ``member_radius``, ``bay_count``, bracing pattern, and axis fields.
      It keeps structural-frame intent as one semantic primitive.
    - ``"support_bracket"``: an L-style mounting bracket with vertical
      plate, foot plate, and optional triangular gussets. It uses
      ``width``, ``height``, ``depth``, ``thickness``, bracket axes, and
      gusset controls so attachment support intent survives kernel
      execution as one construct.
    - ``"trim_band"``: a visible raised or subtractive rectangular strip
      generated from ``length``, ``width``, ``thickness``, and axis
      controls. It preserves trim/detail hierarchy intent instead of
      reporting the strip as a generic box.
    - ``"corner_guard_set"``: repeated protective corner bars generated
      from a source envelope, selected axes, corner signs, guard size,
      thickness, and seat depth. It preserves hardware-corner intent as
      one semantic primitive instead of many anonymous box bars.
    - ``"hinge"``: a mechanical barrel hinge with two leaves, center pin,
      and alternating knuckles. It uses ``length``, ``leaf_width``,
      ``leaf_thickness``, ``barrel_radius``, ``pin_radius``,
      ``knuckle_count``, ``knuckle_gap``, and hinge/leaf axes so hardware
      intent survives as one kernel primitive instead of loose boxes and
      cylinders.
    - ``"handle"``: a U-pull or grab handle with swept grip and mount
      pads. It uses ``span``, ``standoff``, ``grip_radius``,
      ``pad_radius``, ``pad_thickness``, span/normal/cross axes, and
      segment controls so hardware attachment intent remains one
      primitive.
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
    - ``"swept_profile"``: a 2D ``cross_section`` polygon swept along a
      3D ``sweep_path`` polyline through ``center``. The cross-section's
      local Y aligns with the path tangent at each frame; the local X/Z
      span the perpendicular plane. This is the most general curved
      vocabulary in the kit — covers ergonomic stocks, curved barrel
      shrouds, hose-like trim, sling cables, and contoured rail covers
      that a single straight-axis revolve cannot express.
    - ``"helical_sweep"``: a compact helix generator for coils, springs,
      thread ridges, hoses, and cable wraps. It uses ``radius``,
      ``height``, ``turns``, ``axis``, optional ``tube_radius`` or an
      authored ``cross_section``, plus ``segments_per_turn``,
      ``cross_section_segments``, ``phase_degrees``, and ``handedness``.
      It preserves the helical construction parameters instead of
      expanding intent immediately into a large sampled ``sweep_path``.
    - ``"threaded_cylinder"``: a single analytic external-thread cylinder
      primitive generated from ``radius``, ``height``, ``thread_pitch``,
      ``thread_depth``, ``turns``, axis, handedness, phase, clearance, and
      profile-shape controls. It preserves fastener/thread intent as one
      kernel construct instead of lowering first to a cylinder plus loose
      helical ridge geometry.
    - ``"curved_tube"``: a compact circular-arc pipe/elbow generator for
      hoses, bent rails, conduits, exhausts, handles, and hard-surface
      routed tubes. It uses ``radius`` (arc centerline radius),
      ``tube_radius``, ``angle_degrees``, ``plane_axis``, optional
      ``start_angle_degrees``, optional ``inner_tube_radius`` for a
      hollow shell, plus path/cross-section segment controls. It
      preserves analytic bend intent instead of immediately expanding
      the part into a generic sampled ``swept_profile``.
    - ``"heightfield"``: regular 2D grid of elevation samples laid out in
      the XY plane and lifted along the world-up axis. Defined by
      ``resolution`` (``(nx, ny)`` cell counts), ``height_data`` (a
      nested list of ``ny`` rows × ``nx`` columns of floats), ``bounds_xy``
      (``(xmin, ymin, xmax, ymax)``) and ``vertical_scale`` (multiplier
      applied to ``height_data`` before emitting Z). Each cell becomes
      two triangles; UVs are the lattice coordinates and normals come
      from the height gradient. This is the first-class data type
      consumed by the §7.2 terrain pipeline (Tu-Pham hydraulic +
      thermal erosion + biome layering) and produces the slope, flow,
      and deposition masks downstream surface_graph layers depend on.
    - ``"terrain_patch"``: a semantic terrain primitive backed by the
      same regular heightfield payload, preserving biome/erosion/terrain
      intent while emitting explicit heightfield triangles for downstream
      stages.
    - ``"lofted_solid"``: a tapered/varying tube formed by stitching a
      sequence of 2D cross-section polygons placed along a 3D path.
      Defined by ``cross_sections`` (>= 2 CCW (u, v) polygons in the
      per-section local plane, all sharing the same vertex count) and
      ``section_centers`` (a list of 3D path origins, one per section).
      Adjacent rings are connected with quads (triangulated for the
      trimesh export) and the first/last sections cap the ends. This
      closes the gap between ``swept_profile`` (constant cross-section)
      and a free-form mesh — covers tapered handles, flared hoods,
      heat shrouds with varying inlet/outlet diameters, gun-stock
      necks that pinch and flare, and arch ribs whose cross-section
      evolves along the span. The cross-section's local Y aligns with
      the tangent of the path between adjacent section centers; local
      X/Z span the perpendicular plane.
    - ``"sdf_mesh"``: a raw triangle mesh produced by extracting the
      iso-surface of an F-Rep / SDF expression (typically via marching
      cubes from ``lathe.f_rep``). Defined by ``mesh_vertices`` (an
      ``(N, 3)`` list of world-space coordinates, cm) and
      ``mesh_faces`` (an ``(M, 3)`` list of vertex indices). This is
      the bridge from the implicit-surface SDF authoring layer
      (``mesh_program`` ``sdf_*`` ops) into the stable explicit-mesh
      vocabulary downstream stages already consume. Organic / creature
      / blob primitives — the kind of thing capsule/box/sphere
      booleans cannot express — round-trip through this type.
    - ``"component_assembly"``: a semantic compound primitive that stores
      a list of existing ShapePrimitive-compatible component records.
      It keeps high-level procedural solids such as vegetation, CGA
      facades, and modular assemblies as one object while still emitting
      visible exact geometry for each component.
    - ``"sdf_metaball_cluster"``: an extracted smooth-union organic SDF
      cluster that preserves metaball/F-Rep intent while carrying the
      concrete mesh vertices/faces needed by downstream explicit stages.
    - ``"terrain_mesh"``: a mesh-backed result of importing a
      ``terrain_patch`` through a geometry kernel while preserving
      biome, erosion, terrace, and heightfield intent alongside explicit
      vertices/faces.
    - ``"kernel_primitive_mesh"``: a mesh-backed result of importing a
      stable ShapeIR primitive through a geometry kernel while preserving
      the original primitive type in semantic metadata.
    - ``"instance_mesh"``: a mesh-backed result of repeat, distribute,
      copy-to-points, mirror, or scatter-on-surface placement programs
      that keeps instance/placement intent alongside explicit
      vertices/faces.
    - ``"component_assembly_mesh"``: a mesh-backed result of importing a
      semantic component assembly through a geometry kernel while
      preserving assembly kind, component count, and domain modifiers.
    - ``"profile_mesh"``: a mesh-backed result of importing profile,
      sweep, loft, polywire, helical, spring, curved-tube, threaded, or
      carve construction through a geometry kernel while preserving the
      profile-operation modifier payload.
    - ``"construction_feature_mesh"``: a mesh-backed result of importing
      visible hard-surface construction features such as trim bands,
      panel frames, brackets, mount plates, weld seams, and related
      detail primitives while preserving their v2 modifier payloads.
    - ``"edge_control_mesh"``: a mesh-backed result of importing hard-edge
      or weighted-normal edge-control operations while preserving the
      edge-operation modifier payload.
    - ``"polybevel_mesh"``: a mesh-backed result of ``sop.polybevel``,
      ``op.bevel``, or ``op.chamfer`` that keeps visible edge-treatment
      intent alongside explicit vertices/faces.
    - ``"hull_mesh"``: a mesh-backed result of ``op.hull`` that keeps
      convex-hull construction intent alongside explicit vertices/faces.
    - ``"minkowski_mesh"``: a mesh-backed result of ``op.minkowski`` that
      keeps Minkowski/shell-expansion intent alongside explicit
      vertices/faces.
    - ``"subdivision_mesh"``: a mesh-backed result of ``sop.subdivide``
      that keeps subdivision/finishing intent alongside explicit
      vertices/faces.
    - ``"remesh_mesh"``: a mesh-backed result of ``sop.remesh`` that
      keeps remeshing/target-edge intent alongside explicit
      vertices/faces.
    - ``"deform_mesh"``: a mesh-backed result of twist/taper/bend
      deformers that keeps deformation intent alongside explicit
      vertices/faces.
    - ``"boolean_mesh"``: a mesh-backed result of kernel boolean
      composition that keeps union/subtract/intersect intent,
      attempted-vs-actual kernel metadata, seam groups, and explicit
      vertices/faces together.
    - ``"spring"``: a semantic helical wire coil with ``radius``,
      ``tube_radius`` (wire radius), ``height``, ``turns``, optional
      ``axis``, ``segments_per_turn``, ``cross_section_segments``,
      ``phase_degrees``, and ``handedness``. It preserves mechanical
      spring intent while emitting the same visible swept wire geometry
      expected by downstream stages.
    """

    primitive_type: str
    part: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float] | None = None
    radius: float | None = None
    height: float | None = None
    length: float | None = None
    width: float | None = None
    depth: float | None = None
    axis: str = "y"
    sections: int | None = None
    rings: int | None = None
    tags: list[str] = field(default_factory=list)
    component: str | None = None
    region: str | None = None
    blend_mode: str = "union"
    rounding: float = 0.0
    # ``profile_points`` is a list of (axial, radial) 2D points used by
    # ``primitive_type="revolved_profile"``. None for box/cylinder.
    profile_points: list[tuple[float, float]] | None = None
    # ``revolve_degrees`` / ``revolve_start_degrees`` optionally limit a
    # revolved profile to a capped angular segment. None means the legacy
    # full 360-degree revolve.
    revolve_degrees: float | None = None
    revolve_start_degrees: float | None = None
    # ``profile_polygon`` is a CCW list of (u, v) 2D points in the
    # cross-section plane perpendicular to ``axis``, used by
    # ``primitive_type="extruded_profile"``. None for other types.
    profile_polygon: list[tuple[float, float]] | None = None
    # ``extrude_height`` is the linear sweep distance along ``axis`` for
    # ``primitive_type="extruded_profile"``. None for other types.
    extrude_height: float | None = None
    # Optional generalized extrusion controls. Defaults preserve the
    # legacy straight prism; non-default values make a ring-stitched,
    # capped exact mesh with scale/twist varying along the extrusion axis.
    extrude_start_scale: float | None = None
    extrude_end_scale: float | None = None
    extrude_twist_degrees: float | None = None
    extrude_segments: int | None = None
    # ``major_radius`` / ``minor_radius`` are used by
    # ``primitive_type="torus"``: ``major_radius`` is the distance from
    # the ring center to the center of the tube, ``minor_radius`` is the
    # tube radius. None for non-torus primitives.
    major_radius: float | None = None
    minor_radius: float | None = None
    # ``outer_radius`` / ``inner_radius`` are used by
    # ``primitive_type="tube"`` for straight annular solids. ``rim_bevel``
    # optionally eases the inner/outer rims while staying one watertight
    # primitive.
    outer_radius: float | None = None
    inner_radius: float | None = None
    rim_bevel: float | None = None
    # Gear primitives.
    teeth: int | None = None
    pitch_radius: float | None = None
    thickness: float | None = None
    pressure_angle_degrees: float | None = None
    addendum: float | None = None
    dedendum: float | None = None
    root_radius: float | None = None
    base_radius: float | None = None
    bore_radius: float | None = None
    tooth_samples: int | None = None
    backlash: float | None = None
    helix_angle_degrees: float | None = None
    helix_handedness: str | None = None
    # Flange primitives.
    bolt_count: int | None = None
    bolt_radius: float | None = None
    bolt_circle_radius: float | None = None
    # ``corner_radii`` is an 8-tuple of per-corner rounding radii used by
    # ``primitive_type="subdivision_box"``. Order matches the cube's
    # vertex enumeration:
    # (-x-y-z, +x-y-z, -x+y-z, +x+y-z, -x-y+z, +x-y+z, -x+y+z, +x+y+z).
    # ``None`` for non-subdivision primitives.
    corner_radii: tuple[float, float, float, float, float, float, float, float] | None = None
    # ``corner_segments`` controls the per-corner sphere tessellation for
    # ``primitive_type="subdivision_box"``. Higher = smoother corners.
    corner_segments: int = 4
    # ``cross_section`` is a closed CCW 2D polygon (local x, z) used by
    # ``primitive_type="swept_profile"``. None for other types.
    cross_section: list[tuple[float, float]] | None = None
    # ``sweep_path`` is a 3D polyline of frame origins used by
    # ``primitive_type="swept_profile"``. None for other types.
    sweep_path: list[tuple[float, float, float]] | None = None
    # Compact helical sweep controls. ``radius`` is the helix path radius,
    # ``height`` is the axial span, and ``tube_radius`` is used when no
    # authored cross_section polygon is provided.
    tube_radius: float | None = None
    turns: float | None = None
    segments_per_turn: int | None = None
    cross_section_segments: int | None = None
    phase_degrees: float | None = None
    handedness: str | None = None
    # External-thread controls for ``primitive_type="threaded_cylinder"``.
    # ``radius`` remains the minor/core cylinder radius and ``height`` the
    # full body height; these fields describe the raised thread surface.
    thread_pitch: float | None = None
    actual_pitch: float | None = None
    thread_depth: float | None = None
    thread_start_clearance: float | None = None
    thread_end_clearance: float | None = None
    thread_profile_shape: str | None = None
    thread_profile_radius: float | None = None
    thread_profile_width: float | None = None
    thread_profile_height: float | None = None
    thread_profile_top_width: float | None = None
    # Compact circular-arc pipe/elbow controls for
    # ``primitive_type="curved_tube"``. ``radius`` is the arc centerline
    # radius and ``tube_radius`` is the pipe radius. ``plane_axis`` names
    # the normal of the bend plane.
    angle_degrees: float | None = None
    start_angle_degrees: float | None = None
    plane_axis: str | None = None
    path_segments: int | None = None
    inner_tube_radius: float | None = None
    rotation_degrees: float | None = None
    style: str | None = None
    countersink_radius: float | None = None
    countersink_depth: float | None = None
    counterbore_radius: float | None = None
    counterbore_depth: float | None = None
    normal_sign: float | None = None
    socket_shape: str | None = None
    profile_shape: str | None = None
    profile: float | None = None
    profile_height: float | None = None
    base_width: float | None = None
    top_width: float | None = None
    stem_width: float | None = None
    flange_width: float | None = None
    flange_height: float | None = None
    web_thickness: float | None = None
    flange_thickness: float | None = None
    slat_count: int | None = None
    border_width: float | None = None
    slat_thickness: float | None = None
    slat_depth: float | None = None
    slat_spacing: float | None = None
    slat_angle_degrees: float | None = None
    slat_centers: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    slat_scales: tuple[float, ...] | list[float] | None = None
    slat_roll_degrees: tuple[float, ...] | list[float] | None = None
    rib_count: int | None = None
    cross_rib_count: int | None = None
    rib_width: float | None = None
    rib_height: float | None = None
    rib_top_width: float | None = None
    edge_margin: float | None = None
    rib_orientation: str | None = None
    rib_profile: str | None = None
    hole_radius: float | None = None
    hole_centers: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    hole_rows: int | None = None
    hole_columns: int | None = None
    row_axis: str | None = None
    column_axis: str | None = None
    row_span: float | None = None
    column_span: float | None = None
    stagger: bool | None = None
    stagger_offset: float | None = None
    hole_shape: str | None = None
    slot_length: float | None = None
    fastener_rows: int | None = None
    fastener_columns: int | None = None
    fastener_spacing: float | None = None
    fastener_centers: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    fastener_scales: tuple[float, ...] | list[float] | None = None
    fastener_roll_degrees: tuple[float, ...] | list[float] | None = None
    washer_radius: float | None = None
    washer_height: float | None = None
    head_height: float | None = None
    head_style: str | None = None
    include_washer: bool | None = None
    weld_mode: str | None = None
    dent_centers: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    patch_centers: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    patch_kind: str | None = None
    side: str | None = None
    leaf_width: float | None = None
    leaf_thickness: float | None = None
    barrel_radius: float | None = None
    pin_radius: float | None = None
    knuckle_count: int | None = None
    knuckle_gap: float | None = None
    hinge_axis: str | None = None
    leaf_axis: str | None = None
    span: float | None = None
    standoff: float | None = None
    grip_radius: float | None = None
    pad_radius: float | None = None
    pad_thickness: float | None = None
    span_axis: str | None = None
    cross_axis: str | None = None
    pad_segments: int | None = None
    guard_size: float | None = None
    guard_axes: tuple[str, ...] | list[str] | None = None
    corner_signs: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None = None
    source_extents: tuple[float, float, float] | list[float] | None = None
    seat_depth: float | None = None
    rail_radius: float | None = None
    rung_radius: float | None = None
    rung_count: int | None = None
    rung_spacing: float | None = None
    rail_span: float | None = None
    rung_length: float | None = None
    rung_socket_depth: float | None = None
    member_radius: float | None = None
    bay_count: int | None = None
    bracing_pattern: str | None = None
    depth_axis: str | None = None
    include_depth_ties: bool | None = None
    clearance: float | None = None
    mount_type: str | None = None
    normal_axis: str | None = None
    include_gussets: bool | None = None
    gusset_count: int | None = None
    gusset_thickness: float | None = None
    gusset_height: float | None = None
    gusset_depth: float | None = None
    length_axis: str | None = None
    width_axis: str | None = None
    height_axis: str | None = None
    # ``cross_sections`` is the per-section CCW (u, v) polygon list used
    # by ``primitive_type="lofted_solid"``. Each entry is one closed
    # cross-section in its local plane; all entries must share the same
    # vertex count so adjacent rings can be quad-stitched. None for
    # other types.
    cross_sections: list[list[tuple[float, float]]] | None = None
    # ``section_centers`` is the 3D path origin per cross-section used
    # by ``primitive_type="lofted_solid"``. Length must equal
    # ``len(cross_sections)`` and the path direction between adjacent
    # entries defines each frame's local Y axis. None for other types.
    section_centers: list[tuple[float, float, float]] | None = None
    # ``resolution`` is the ``(nx, ny)`` cell count for
    # ``primitive_type="heightfield"``. ``nx`` columns and ``ny`` rows;
    # ``height_data`` must be ``ny`` rows of ``nx`` floats. None for
    # other types.
    resolution: tuple[int, int] | None = None
    # ``height_data`` is the per-cell elevation grid for
    # ``primitive_type="heightfield"`` as a nested list of floats
    # (rows-major: ``height_data[row][col]``). None for other types.
    height_data: list[list[float]] | None = None
    # ``bounds_xy`` is the ``(xmin, ymin, xmax, ymax)`` rectangle the
    # heightfield grid spans in world space (XY plane) for
    # ``primitive_type="heightfield"``. None for other types.
    bounds_xy: tuple[float, float, float, float] | None = None
    # ``vertical_scale`` multiplies ``height_data`` to produce world-up
    # elevation for ``primitive_type="heightfield"``. None for other
    # types; defaults to 1.0 inside the mesh emitter when omitted.
    vertical_scale: float | None = None
    # Raw triangle mesh data for ``primitive_type="sdf_mesh"``. The
    # vertices live in world-space cm (already offset by ``center``) and
    # faces are zero-indexed CCW triangles. Both lists are stored in
    # JSON-friendly nested form so the ShapePrimitive remains
    # round-trippable through ``to_dict``. None for other types.
    mesh_vertices: list[list[float]] | None = None
    mesh_faces: list[list[int]] | None = None
    # Semantic compound exact primitive data for
    # ``primitive_type="component_assembly"``.
    assembly_kind: str | None = None
    assembly_primitives: list[dict[str, Any]] | None = None
    # Optional topology finishing intent. These fields are source-preserving
    # modifiers emitted by ShapeIR v2 named SOPs and consumed by the exact
    # mesh path after the base primitive has been generated.
    subdivision_levels: int = 0
    subdivision_scheme: str = "catmull_clark"
    remesh_target_edge_length_cm: float | None = None
    remesh_mode: str = "adaptive"
    v2_subdivision_modifier: dict[str, Any] | None = None
    v2_remesh_modifier: dict[str, Any] | None = None
    # Boolean -> bevel handoff intent. Boolean-producing ShapeIR v2 ops can
    # name seam groups, and PolyBevel can target those groups without losing
    # the source primitive or pretending a full edge-loop topology model exists.
    boolean_seam_groups: list[dict[str, Any]] = field(default_factory=list)
    bevel_seam_groups: list[dict[str, Any]] = field(default_factory=list)
    v2_polybevel_modifier: dict[str, Any] | None = None
    hard_edge_groups: list[dict[str, Any]] = field(default_factory=list)
    v2_mark_hard_edge_modifier: dict[str, Any] | None = None
    v2_weighted_normals_modifier: dict[str, Any] | None = None
    v2_hull_modifier: dict[str, Any] | None = None
    v2_minkowski_modifier: dict[str, Any] | None = None
    # Extra source-semantic metadata that does not yet have a dedicated
    # ShapePrimitive field. This keeps v2 construction details such as
    # distribution/repetition provenance alive through kernel execution
    # without expanding the public language surface for every new op.
    semantic_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this primitive as a dict.

        Cached per-instance via ``_TO_DICT_CACHE`` (see module top) —
        ``asdict(self)`` deep-walks every dataclass field and is the
        single largest cost in v1 lowering (~13s of 174s in profiling).
        Within a build, the same primitive is to_dict'd many times by
        different downstream code paths; this caches the first result.
        """
        key = id(self)
        cached = _TO_DICT_CACHE.get(key)
        if cached is not None:
            return dict(cached)  # defensive copy so callers can mutate
        result = _CachedDict(asdict(self))
        _TO_DICT_CACHE[key] = result
        return dict(result)


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
