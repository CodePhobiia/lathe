"""Phase 1 §5.1 KEY DEMO — boolean -> bevel(seam_group) chain.

Until the source-level ``mesh_program`` block lands (roadmap §5.1 v2),
authors and family-lowering code can invoke the canonical hard-surface
idiom directly through ``lathe.feature_ops``:

    body   = box(...)
    cutout = box(...).translate((0, 0, 4cm))
    result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
    fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)

Run::

    python examples/bevel_demo.py

Outputs ``examples/bevel_demo.glb`` (with bevel) and
``examples/bevel_demo_baseline.glb`` (sharp boolean, no bevel) so the
before/after can be compared in any glTF viewer such as
https://gltf-viewer.donmccurdy.com/.

v1 limitations (roadmap §5.2 risk → v2 follow-ups):

1. Non-watertight output: the ``edge_loop_cutback_strip_v1`` cutback
   pass can leave the bevel band's caps open on simple boolean inputs.
   The bevel is present and visually correct; downstream code that
   needs a closed manifold should run ``trimesh.repair.fill_holes``
   on the result for now.
2. No source-level ``mesh_program`` block yet: authors call the
   helpers in this module directly. The DSL parser path (the literal
   ``boolean(... seam_group: "lip")`` source syntax in the user-facing
   roadmap snippet) is the next deliverable on this thread.
3. Pure-trimesh path only: the Blender-bevel-modifier dispatch with
   edge-mark tagging (roadmap §5.6) is also a v2 follow-up that will
   sit behind the same author-facing helper.
"""
from __future__ import annotations

from pathlib import Path

from lathe.exact_solids import compile_explicit_surface_mesh
from lathe.feature_ops import box_with_seam_group
from lathe.fidelity import _profile_from_tier
from lathe.shape_ir import ShapeIR, ShapePrimitive


def _wrap_in_ir(primitives: list[ShapePrimitive]) -> ShapeIR:
    return ShapeIR(
        asset_name="bevel_demo",
        family="hard_surface_prop",
        blueprint_id="bevel_demo_v1",
        symmetry_axis=None,
        units="cm",
        primitives=primitives,
        regions=[],
        primitives_used=["box"],
        part_graph=[],
        signature={},
    )


def main() -> None:
    body = ShapePrimitive(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 0.0),
        extents=(10.0, 10.0, 10.0),
        blend_mode="union",
    )

    # Baseline: sharp boolean cutout, no seam_group.
    cutout_sharp = ShapePrimitive(
        primitive_type="box",
        part="body",
        center=(0.0, 0.0, 4.0),
        extents=(8.0, 8.0, 4.0),
        blend_mode="subtract",
    )

    # Beveled: same boolean, plus seam_group + fillet_edge in one call.
    cutout_beveled = box_with_seam_group(
        part="body",
        center=(0.0, 0.0, 4.0),
        extents=(8.0, 8.0, 4.0),
        blend_mode="subtract",
        seam_group="lip",
        bevel_radius_cm=1.0,
        bevel_segments=4,
    )

    fid = _profile_from_tier("hero")
    out_dir = Path(__file__).parent

    sharp_mesh, _, _sharp_report = compile_explicit_surface_mesh(
        _wrap_in_ir([body, cutout_sharp]), fid
    )
    beveled_mesh, _, beveled_report = compile_explicit_surface_mesh(
        _wrap_in_ir([body, cutout_beveled]), fid
    )

    sharp_path = out_dir / "bevel_demo_baseline.glb"
    beveled_path = out_dir / "bevel_demo.glb"
    sharp_mesh.export(str(sharp_path))
    beveled_mesh.export(str(beveled_path))

    print("=== boolean -> bevel(seam_group) demo ===")
    print(f"baseline  : {len(sharp_mesh.vertices):>4} verts {len(sharp_mesh.faces):>4} faces  -> {sharp_path}")
    print(f"with bevel: {len(beveled_mesh.vertices):>4} verts {len(beveled_mesh.faces):>4} faces  -> {beveled_path}")
    print()
    print(f"  bevel method      : {beveled_report['post_boolean_polybevel_method']}")
    print(f"  bevel groups      : {beveled_report['post_boolean_polybevel_group_count']}")
    print(f"  bevel edges       : {beveled_report['post_boolean_polybevel_edge_count']}")
    print(f"  bevel faces added : {beveled_report['post_boolean_polybevel_bevel_face_count']}")


if __name__ == "__main__":
    main()
