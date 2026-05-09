"""Clean imported GLB topology in Blender and export a normalized GLB.

Phase 1 §5.6 expansion: when a sidecar ``--config <path>`` JSON file is
provided, the adapter applies a Subdivision Surface + Bevel + Decimate
modifier stack configured from the topology bundle, with optional
GeometryNodes scatter for surface-projected greeble patterns.

Backwards compatibility: when no ``--config`` flag is passed (or the
config file is missing / empty), the adapter falls back to the legacy
``remove_doubles + triangulate + recalc_face_normals`` cleanup so older
callers continue to work.

Sidecar JSON schema (all keys optional)::

    {
        "subsurf_level": int,            # 0 disables; clamped to [0, 3]
        "bevel_width": float,            # default global bevel width (cm)
        "bevel_segments": int,           # default 2
        "bevel_seam_groups": [           # edge marks for the BEVEL modifier
            {
                "name": str,
                "width": float,
                "edge_world_pairs": [    # vertex coordinate pairs (cm)
                    [[x0, y0, z0], [x1, y1, z1]],
                    ...
                ]
            },
            ...
        ],
        "decimate_target_quads": int,    # 0 disables
        "instance_pattern_records": [    # optional GN scatter, OK to omit
            {"slot": str, "count": int, "spacing_cm": float, ...}
        ],
        "tris_to_quads": bool,           # default True; merge coplanar tri pairs
        "tris_to_quads_face_threshold": float,   # radians; default 0.698 (~40°)
        "tris_to_quads_shape_threshold": float,  # radians; default 0.698 (~40°)
        "skip_subsurf_for_terrain": bool,        # when true, subsurf is bypassed
                                                 # for meshes whose face-count
                                                 # signature matches a terrain
                                                 # heightfield (avoids blowing up
                                                 # an already-fine grid).
        "use_auto_smooth": bool          # default True; enables custom split
                                         # normals at sharp edges so subsurf
                                         # respects bevel-marked seams.
    }

The per-object report records pre/post polygon counts for every
modifier (subsurf/bevel/decimate) and the tris->quads pass so callers
can see exactly what each step did to the mesh density.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import bmesh
import bpy


def _parse_args() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Expected Blender adapter args after --")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", required=False, default=None)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def _load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _legacy_cleanup_mesh(obj: bpy.types.Object) -> None:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _normalize_only(obj: bpy.types.Object) -> None:
    """Weld coincident verts and recalc normals without forcing triangulation.

    Used as the entry-step before modifier stacks: subsurf/bevel both expect
    a consistent quad/poly topology, so we want welds + normals but no
    eager triangulation. The DECIMATE_PLANAR / DECIMATE_TRIANGULATE step
    handles triangulation later.
    """
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _coord_key(value: Any, scale: float = 100000.0) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return tuple(int(round(float(coord) * scale)) for coord in value)
    except (TypeError, ValueError):
        return None


def _mark_bevel_edges(
    obj: bpy.types.Object,
    bevel_seam_groups: list[dict[str, Any]],
    *,
    default_width: float,
) -> tuple[int, dict[str, int]]:
    """Mark edges matching seam-group vertex pairs as bevel-weighted.

    Returns ``(matched_edge_count, per_group_match)`` for diagnostic use.
    """
    if not bevel_seam_groups:
        return 0, {}

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    bevel_layer = bm.edges.layers.bevel_weight.verify()

    coord_to_vert: dict[tuple[int, int, int], int] = {}
    for vert_index, vert in enumerate(bm.verts):
        key = _coord_key((vert.co.x, vert.co.y, vert.co.z))
        if key is not None and key not in coord_to_vert:
            coord_to_vert[key] = vert_index

    edge_lookup: dict[frozenset[int], bmesh.types.BMEdge] = {}
    for edge in bm.edges:
        a, b = edge.verts[0].index, edge.verts[1].index
        edge_lookup[frozenset((a, b))] = edge

    matched = 0
    per_group: dict[str, int] = {}
    for group in bevel_seam_groups:
        if not isinstance(group, dict):
            continue
        name = str(group.get("name") or "unnamed")
        width = float(group.get("width", default_width) or default_width)
        if width <= 0.0:
            continue
        normalized_weight = max(0.0, min(1.0, width / max(default_width, 1e-6)))
        pairs = group.get("edge_world_pairs") or []
        group_count = 0
        for pair in pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            key_a = _coord_key(pair[0])
            key_b = _coord_key(pair[1])
            if key_a is None or key_b is None:
                continue
            vert_a = coord_to_vert.get(key_a)
            vert_b = coord_to_vert.get(key_b)
            if vert_a is None or vert_b is None or vert_a == vert_b:
                continue
            edge = edge_lookup.get(frozenset((vert_a, vert_b)))
            if edge is None:
                continue
            edge[bevel_layer] = max(edge[bevel_layer], normalized_weight)
            edge.smooth = False  # mark sharp -- helps bevel respect the seam
            group_count += 1
        per_group[name] = group_count
        matched += group_count

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return matched, per_group


def _enable_auto_smooth(obj: bpy.types.Object, angle_rad: float = 0.5236) -> None:
    """Turn on Auto-Smooth so subsurf/bevel respect bevel-marked sharp edges.

    Without Auto-Smooth, Catmull-Clark subdivision averages normals across
    every edge regardless of the sharp/seam flag, smearing the very seams
    we marked with ``edge.smooth = False`` in :func:`_mark_bevel_edges`.
    Setting ``use_auto_smooth = True`` and a tight split angle keeps
    sharp edges sharp through the modifier stack.
    """
    mesh = obj.data
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = float(angle_rad)
    except AttributeError:
        # Blender 4.1+ removed mesh.use_auto_smooth in favor of a node-based
        # workflow; the bevel-weight + edge.smooth flags are still honored.
        pass


def _add_subsurf(obj: bpy.types.Object, level: int) -> bool:
    if level <= 0:
        return False
    mod = obj.modifiers.new(name="lathe_subsurf", type="SUBSURF")
    mod.levels = max(0, min(int(level), 3))
    mod.render_levels = mod.levels
    mod.subdivision_type = "CATMULL_CLARK"
    return True


def _add_bevel(
    obj: bpy.types.Object,
    *,
    width: float,
    segments: int,
    use_edge_marks: bool,
) -> bool:
    """Add a Bevel modifier; returns True if added."""
    if width <= 0.0:
        return False
    mod = obj.modifiers.new(name="lathe_bevel", type="BEVEL")
    mod.width = float(width)
    mod.segments = max(1, int(segments))
    mod.profile = 0.7
    mod.limit_method = "WEIGHT" if use_edge_marks else "ANGLE"
    if mod.limit_method == "ANGLE":
        # Default to ~30deg so we only bevel real hard edges.
        mod.angle_limit = 0.5236
    mod.miter_outer = "MITER_ARC"
    mod.miter_inner = "MITER_SHARP"
    return True


def _add_decimate(obj: bpy.types.Object, target_quads: int) -> tuple[bool, str]:
    """Add a Decimate modifier driven by ``target_quads``.

    Trimesh-side stages count triangles, so we treat ``target_quads`` as
    a quad-equivalent face budget and convert to a tri ratio against the
    current face count. Returns ``(added, reason)`` so the report can
    explain why a budget didn't take effect (e.g. mesh already under
    budget vs. budget set to 0).
    """
    if target_quads <= 0:
        return False, "no_target"
    current_faces = max(1, len(obj.data.polygons))
    target_tris = max(1, int(target_quads) * 2)
    if target_tris >= current_faces:
        return False, "already_under_budget"
    ratio = max(0.05, min(1.0, target_tris / float(current_faces)))
    mod = obj.modifiers.new(name="lathe_decimate", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    return True, "applied"


def _try_add_geometry_nodes_scatter(
    obj: bpy.types.Object, records: list[dict[str, Any]]
) -> bool:
    """Best-effort GeometryNodes scatter for instance_pattern records.

    We attach a NODES modifier with an empty group placeholder. Wiring a
    real Distribute Points on Faces network is version-specific
    (Blender 3.x vs 4.x have different node IDs); the helper records the
    record count on a custom property and degrades silently if anything
    in the bpy node API is unavailable. This keeps the optional GN pass
    from blocking the rest of the pipeline.
    """
    if not records:
        return False
    try:
        node_group = bpy.data.node_groups.new(
            name=f"lathe_scatter_{obj.name}", type="GeometryNodeTree"
        )
    except (RuntimeError, AttributeError, TypeError):
        return False
    try:
        mod = obj.modifiers.new(name="lathe_scatter", type="NODES")
        mod.node_group = node_group
        obj["lathe_instance_pattern_record_count"] = len(records)
        return True
    except (RuntimeError, AttributeError, TypeError):
        return False


def _tris_to_quads_pass(
    obj: bpy.types.Object,
    *,
    face_threshold: float,
    shape_threshold: float,
) -> dict[str, Any]:
    """Merge coplanar triangle pairs into quads via ``mesh.tris_convert_to_quads``.

    Hard-surface boolean output often produces fan triangulations across
    flat panels — many tris meeting at a single pole vertex. The
    topology-class validator penalises both the low quad-domination ratio
    and the resulting high-valence pole. Running Blender's tris→quads
    operator collapses those tri-pairs back into quads, eliminating the
    artificial pole. The downstream triangulate step will re-cut the new
    quads along a single diagonal, yielding clean coplanar tri-pairs that
    the validator detects as quads (dot ≥ 0.99).

    Returns a small report dict for downstream telemetry.
    """
    before_polys = len(obj.data.polygons)
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.tris_convert_to_quads(
            face_threshold=float(face_threshold),
            shape_threshold=float(shape_threshold),
        )
        bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError as exc:
        return {"applied": False, "reason": f"runtime_error: {exc}"}
    after_polys = len(obj.data.polygons)
    return {
        "applied": True,
        "polys_before": int(before_polys),
        "polys_after": int(after_polys),
        "face_threshold": float(face_threshold),
        "shape_threshold": float(shape_threshold),
    }


def _apply_named_modifier(obj: bpy.types.Object, name: str) -> dict[str, Any]:
    """Apply a single modifier by name, returning a pre/post-count report.

    Captures the polygon count before and after so callers can attribute
    density changes to a specific modifier (e.g. subsurf 4x, decimate 0.5x).
    Failed applies (e.g. NODES modifier with empty group) remove the
    modifier instead of failing the whole stack.
    """
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    polys_before = len(obj.data.polygons)
    mod = obj.modifiers.get(name)
    if mod is None:
        return {"applied": False, "reason": "not_added"}
    try:
        bpy.ops.object.modifier_apply(modifier=name)
    except RuntimeError as exc:
        # Best-effort: remove so the stack proceeds.
        try:
            obj.modifiers.remove(mod)
        except (RuntimeError, ReferenceError):
            pass
        return {"applied": False, "reason": f"runtime_error: {exc}"}
    polys_after = len(obj.data.polygons)
    return {
        "applied": True,
        "polys_before": int(polys_before),
        "polys_after": int(polys_after),
    }


def _drop_remaining_modifiers(obj: bpy.types.Object) -> None:
    """Best-effort cleanup of any modifiers left after the apply pass."""
    for mod in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except RuntimeError:
            try:
                obj.modifiers.remove(mod)
            except (RuntimeError, ReferenceError):
                pass


def _looks_like_terrain_heightfield(obj: bpy.types.Object) -> bool:
    """Heuristic: does this mesh look like a heightfield grid?

    A terrain heightfield from ``terrain_heightfield`` lowering produces a
    regular triangulated grid: face count is roughly ``2 * (N-1) * (N-1)``
    for a square ``N`` resolution and the per-face XY footprint is uniform.
    Subdividing such a mesh adds vertex count without curvature -- the
    surface is already a smooth triangulated surface. We detect by:
      * face count >= 1500 (small props don't trip this),
      * vertex_count / face_count ratio close to 0.5 (regular grid),
      * AABB Z-extent < 50% of XY-extent (a flat-ish ground plane).
    All three conditions must hold to skip subsurf.
    """
    mesh = obj.data
    face_count = len(mesh.polygons)
    vert_count = len(mesh.vertices)
    if face_count < 1500 or vert_count == 0:
        return False
    ratio = vert_count / float(face_count)
    if not (0.45 <= ratio <= 0.65):
        return False
    if not mesh.vertices:
        return False
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    xy_extent = max(max(xs) - min(xs), max(ys) - min(ys))
    z_extent = max(zs) - min(zs)
    if xy_extent <= 0.0:
        return False
    return (z_extent / xy_extent) < 0.5


def _process_object(obj: bpy.types.Object, config: dict[str, Any]) -> dict[str, Any]:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    if not config:
        _legacy_cleanup_mesh(obj)
        return {"mode": "legacy_cleanup"}

    initial_polys = int(len(obj.data.polygons))
    _normalize_only(obj)

    subsurf_level = int(config.get("subsurf_level", 0) or 0)
    default_bevel_width = float(config.get("bevel_width", 0.0) or 0.0)
    bevel_segments = int(config.get("bevel_segments", 2) or 2)
    bevel_seam_groups = config.get("bevel_seam_groups") or []
    decimate_target_quads = int(config.get("decimate_target_quads", 0) or 0)
    instance_records = config.get("instance_pattern_records") or []
    skip_subsurf_for_terrain = bool(config.get("skip_subsurf_for_terrain", False))
    use_auto_smooth = bool(config.get("use_auto_smooth", True))

    matched_edges, per_group = _mark_bevel_edges(
        obj, bevel_seam_groups, default_width=max(default_bevel_width, 0.05)
    )
    use_edge_marks = matched_edges > 0

    # Auto-smooth keeps marked sharp edges sharp through Catmull-Clark.
    if use_auto_smooth and (subsurf_level > 0 or use_edge_marks):
        _enable_auto_smooth(obj)

    # Subsurf -- skip when caller flagged a terrain heightfield. The
    # topology stage detects the heightfield primitive in shape_ir, so
    # this flag is authoritative. We additionally double-check the mesh
    # signature when the flag is NOT set (defense against missing
    # provenance), in case a heightfield slipped through without the
    # primitive type tag.
    subsurf_skip_reason = ""
    effective_subsurf_level = subsurf_level
    if subsurf_level > 0:
        skip_for_terrain = False
        if skip_subsurf_for_terrain:
            skip_for_terrain = True
            subsurf_skip_reason = "terrain_heightfield_flag"
        elif _looks_like_terrain_heightfield(obj):
            skip_for_terrain = True
            subsurf_skip_reason = "terrain_heightfield_signature"
        if skip_for_terrain:
            effective_subsurf_level = 0
    subsurf_added = _add_subsurf(obj, effective_subsurf_level)

    # Bevel -- prefer caller-supplied global width; fall back to max width
    # from seam groups if global was 0.
    effective_bevel_width = default_bevel_width
    if effective_bevel_width <= 0.0 and bevel_seam_groups:
        widths = [float(g.get("width", 0.0) or 0.0) for g in bevel_seam_groups if isinstance(g, dict)]
        if widths:
            effective_bevel_width = max(widths)
    bevel_added = False
    if effective_bevel_width > 0.0:
        bevel_added = _add_bevel(
            obj,
            width=effective_bevel_width,
            segments=bevel_segments,
            use_edge_marks=use_edge_marks,
        )

    decimate_added, decimate_reason = _add_decimate(obj, decimate_target_quads)
    scatter_added = _try_add_geometry_nodes_scatter(obj, instance_records)

    # Apply per-modifier so we can attribute pre/post poly counts.
    subsurf_report: dict[str, Any] = {"applied": False}
    if subsurf_added:
        subsurf_report = _apply_named_modifier(obj, "lathe_subsurf")
        subsurf_report["level"] = effective_subsurf_level
    elif subsurf_level > 0:
        subsurf_report = {
            "applied": False,
            "reason": "skipped",
            "skip_reason": subsurf_skip_reason or "level_zero_after_clamp",
            "requested_level": subsurf_level,
        }

    bevel_report: dict[str, Any] = {"applied": False}
    if bevel_added:
        bevel_report = _apply_named_modifier(obj, "lathe_bevel")
        bevel_report["width"] = effective_bevel_width
        bevel_report["segments"] = bevel_segments
        bevel_report["use_edge_marks"] = use_edge_marks
        bevel_report["matched_edge_count"] = matched_edges
    elif default_bevel_width > 0.0 or bevel_seam_groups:
        bevel_report = {"applied": False, "reason": "no_effective_width"}

    decimate_report: dict[str, Any] = {"applied": False, "reason": decimate_reason}
    if decimate_added:
        decimate_report = _apply_named_modifier(obj, "lathe_decimate")
        decimate_report["target_quads"] = decimate_target_quads
    elif decimate_target_quads > 0:
        decimate_report["target_quads"] = decimate_target_quads

    scatter_report: dict[str, Any] = {"applied": False}
    if scatter_added:
        scatter_report = _apply_named_modifier(obj, "lathe_scatter")
        scatter_report["instance_pattern_record_count"] = len(instance_records)

    # Drop any modifiers that may still be attached (defense in depth).
    _drop_remaining_modifiers(obj)

    tris_to_quads_enabled = bool(config.get("tris_to_quads", True))
    tris_to_quads_report: dict[str, Any] = {"applied": False, "reason": "disabled"}
    if tris_to_quads_enabled:
        face_threshold = float(config.get("tris_to_quads_face_threshold", 0.698) or 0.698)
        shape_threshold = float(config.get("tris_to_quads_shape_threshold", 0.698) or 0.698)
        tris_to_quads_report = _tris_to_quads_pass(
            obj,
            face_threshold=face_threshold,
            shape_threshold=shape_threshold,
        )

    # After the modifier stack we still want a final triangulation pass so
    # the downstream contract receives a triangle mesh. When tris->quads ran,
    # this re-cut yields clean coplanar tri-pairs the validator detects as
    # quads via face_adjacency. We also re-weld coincident verts because
    # subsurf + bevel can introduce duplicates that, combined with custom
    # split normals, blow up vertex_count and shatter the watertight test
    # downstream (a non-watertight Blender output triggers the reference
    # cleanup fallback and discards the modifier-stack work).
    polys_before_triangulate = int(len(obj.data.polygons))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    if bm.faces:
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    final_polys = int(len(obj.data.polygons))

    obj.select_set(False)
    return {
        "mode": "modifier_stack",
        "fidelity_tier": config.get("fidelity_tier"),
        "auto_smooth_enabled": use_auto_smooth and (subsurf_level > 0 or use_edge_marks),
        "subsurf": subsurf_report,
        "bevel": bevel_report,
        "decimate": decimate_report,
        "scatter": scatter_report,
        "subsurf_level": effective_subsurf_level,
        "subsurf_requested_level": subsurf_level,
        "subsurf_skip_reason": subsurf_skip_reason or None,
        "bevel_added": bevel_added,
        "bevel_width": effective_bevel_width,
        "bevel_segments": bevel_segments,
        "bevel_use_edge_marks": use_edge_marks,
        "bevel_matched_edge_count": matched_edges,
        "bevel_per_group_match": per_group,
        "decimate_added": decimate_added,
        "decimate_target_quads": decimate_target_quads,
        "scatter_added": scatter_added,
        "instance_pattern_record_count": len(instance_records),
        "tris_to_quads": tris_to_quads_report,
        "polys_initial": initial_polys,
        "polys_before_triangulate": polys_before_triangulate,
        "polys_final": final_polys,
    }


def main() -> None:
    """Run the Blender topology cleanup helper."""
    args = _parse_args()
    config = _load_config(args.config)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        raise SystemExit("No mesh objects were imported into Blender")

    reports = []
    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        report = _process_object(obj, config)
        report["object"] = obj.name
        reports.append(report)
        obj.select_set(False)

    # Strip custom split normals before export. We enabled auto_smooth so
    # subsurf/bevel respected sharp seams during the modifier stack, but
    # the GLB exporter encodes per-corner split normals as duplicate
    # vertices in the output mesh -- which inflates vertex_count and
    # shatters the downstream watertight test (each split-normal corner
    # becomes its own connected body, dropping the result back to the
    # reference_cleanup fallback). Downstream stages recompute face
    # normals from geometry anyway, so it is safe to drop the custom
    # normals layer here.
    for obj in mesh_objects:
        mesh = obj.data
        try:
            mesh.use_auto_smooth = False
        except AttributeError:
            pass
        try:
            mesh.free_normals_split()
        except (AttributeError, RuntimeError):
            pass
        try:
            mesh.calc_normals_split()
        except (AttributeError, RuntimeError):
            pass

    bpy.ops.export_scene.gltf(
        filepath=args.output,
        export_format="GLB",
        use_selection=False,
        # We already applied modifiers per-step in _process_object; running
        # the exporter's own apply pass on top can re-duplicate vertices.
        export_apply=False,
        export_normals=False,
        export_tangents=False,
        export_texcoords=False,
        export_materials="NONE",
    )

    if args.config:
        sidecar_report = Path(args.config).with_suffix(".report.json")
        try:
            with open(sidecar_report, "w", encoding="utf-8") as handle:
                json.dump({"objects": reports}, handle, indent=2)
        except OSError:
            pass


if __name__ == "__main__":
    main()
