"""Clean imported GLB topology in Blender and export a normalized GLB."""

import argparse
import sys

import bmesh
import bpy


def _parse_args() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Expected Blender adapter args after --")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def _cleanup_mesh_object(obj: bpy.types.Object) -> None:
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


def main() -> None:
    """Run the Blender topology cleanup helper."""
    args = _parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        raise SystemExit("No mesh objects were imported into Blender")

    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        _cleanup_mesh_object(obj)
        obj.select_set(False)

    bpy.ops.export_scene.gltf(
        filepath=args.output,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_normals=True,
        export_tangents=False,
        export_texcoords=False,
        export_materials="NONE",
    )


if __name__ == "__main__":
    main()
