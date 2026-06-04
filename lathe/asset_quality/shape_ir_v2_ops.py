"""ShapeIR v2 op-family registry.

Extracted from :mod:`lathe.asset_quality.shape_ir_v2` per the P1 module
decomposition. Holds the eight op family frozensets plus the
:data:`ALL_OPS` union and :data:`SHAPE_IR_V2_VERSION` constant.

This module is import-stable: the public names below are re-exported from
``lathe.asset_quality.shape_ir_v2`` so existing callers do not need to
move. Future extractions (types, validators, IO helpers) should follow the
same compatibility-facade pattern.

Op families:

- ``SOLID_OPS`` — primitive solids that introduce new geometry.
- ``BOOLEAN_OPS`` (7) — boolean and construction modifiers.
- ``EDGE_OPS`` (4) — edge-control modifiers (bevels, weighted normals).
- ``SOP_OPS`` — named geometry-kernel operations with Houdini-style names.
- ``REPETITION_OPS`` — semantic repetition / detail strips.
- ``INTEGRATION_OPS`` (4) — attachment / seating ops (sockets, brackets).
- ``WEAR_OPS`` (4) — wear / damage authoring ops.
- ``ZONE_OPS`` (3) — material / decal / wear zone annotation ops.

``ALL_OPS`` is the disjoint union of the eight families.
"""

from __future__ import annotations

SHAPE_IR_V2_VERSION = "shape_ir_v2"


SOLID_OPS: frozenset[str] = frozenset(
    {
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.sphere",
        "solid.torus",
        "solid.revolved_profile",
        "solid.extruded_profile",
        "solid.curve_extruded_profile",
        "solid.curve_revolved_profile",
        "solid.curve_swept_profile",
        "solid.curve_lofted_solid",
        "solid.swept_profile",
        "solid.subdivision_box",
        "solid.prism",
        "solid.rail",
        "solid.panel",
        "solid.gear",
        "solid.capsule",
        "solid.flange",
        "solid.hinge",
        "solid.handle",
        "solid.perforated_panel",
        "solid.structural_beam",
        "solid.ladder_frame",
        "solid.truss_frame",
        "solid.ribbed_panel",
        "solid.louver_panel",
        "solid.terrain_patch",
        "solid.branching_tree",
        "solid.sdf_metaball_cluster",
        "solid.wfc_modular_assembly",
        "solid.cga_facade",
        "solid.spring",
        "solid.threaded_cylinder",
        "solid.tube",
        "solid.curved_tube",
    }
)


BOOLEAN_OPS: frozenset[str] = frozenset(
    {
        "op.union",
        "op.subtract",
        "op.intersect",
        "op.inset",
        "op.extrude",
        "op.shell",
        "op.hull",
        "op.minkowski",
        "op.cut_panel_line",
        "op.countersunk_hole",
        "op.rounded_slot",
    }
)


EDGE_OPS: frozenset[str] = frozenset(
    {
        "op.bevel",
        "op.chamfer",
        "op.weighted_normals",
        "op.mark_hard_edge",
    }
)


SOP_OPS: frozenset[str] = frozenset(
    {
        "sop.boolean",
        "sop.polybevel",
        "sop.sweep",
        "sop.polyextrude",
        "sop.loft",
        "sop.copy_to_points",
        "sop.scatter_on_surface",
        "sop.subdivide",
        "sop.remesh",
        "sop.carve",
        "sop.polywire",
        "sop.helical_sweep",
        "sop.transform",
        "sop.twist",
        "sop.taper",
        "sop.bend",
    }
)


REPETITION_OPS: frozenset[str] = frozenset(
    {
        "op.repeat",
        "op.distribute",
        "op.fastener_grid",
        "op.vent_slats",
        "op.trim_band",
        "op.panel_frame",
        "op.corner_guard_set",
        "op.mirror",
    }
)


INTEGRATION_OPS: frozenset[str] = frozenset(
    {
        "op.socket",
        "op.bracket",
        "op.mount_plate",
        "op.weld_seam",
    }
)


WEAR_OPS: frozenset[str] = frozenset(
    {
        "op.chip_edges",
        "op.scratch_mask",
        "op.dent_mask",
        "op.grime_mask",
    }
)


ZONE_OPS: frozenset[str] = frozenset(
    {
        "op.material_zone",
        "op.decal_zone",
        "op.wear_zone",
    }
)


ALL_OPS: frozenset[str] = (
    SOLID_OPS
    | BOOLEAN_OPS
    | EDGE_OPS
    | SOP_OPS
    | REPETITION_OPS
    | INTEGRATION_OPS
    | WEAR_OPS
    | ZONE_OPS
)


__all__ = [
    "ALL_OPS",
    "BOOLEAN_OPS",
    "EDGE_OPS",
    "INTEGRATION_OPS",
    "REPETITION_OPS",
    "SHAPE_IR_V2_VERSION",
    "SOLID_OPS",
    "SOP_OPS",
    "WEAR_OPS",
    "ZONE_OPS",
]
