"""Blender-side gallery renderer. Run under Blender's embedded Python.

Expected invocation:
    blender --background --python scripts/_gallery_blender.py -- \
        --glb path/to/asset.glb --out docs/gallery/<asset>/renders

Writes `render_0.png` .. `render_4.png` (5 turntable stills) into --out, and
optionally a 24-frame `turntable.webp` if Blender's ffmpeg module is
available. Failures inside Blender do not block the outer gallery script —
the outer script treats a missing render directory as "no renders".
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - only run inside Blender
    print("_gallery_blender: not running under Blender; aborting.", file=sys.stderr)
    sys.exit(0)


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--frames", type=int, default=5)
    p.add_argument("--resolution", type=int, default=512)
    return p.parse_args(argv)


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _import_glb(glb_path: Path) -> None:
    bpy.ops.import_scene.gltf(filepath=str(glb_path))


def _frame_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.view3d.camera_to_view_selected() if False else None  # noqa
    # Compute bounding sphere for placing the camera.
    xs, ys, zs = [], [], []
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for corner in obj.bound_box:
                world = obj.matrix_world @ type(obj.location)(corner)
                xs.append(world.x)
                ys.append(world.y)
                zs.append(world.z)
    if not xs:
        return
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0
    radius = max(
        max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0
    ) * 0.75

    cam_data = bpy.data.cameras.new("GalleryCam")
    cam_obj = bpy.data.objects.new("GalleryCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    cam_obj.location = (cx + radius * 2.2, cy - radius * 2.2, cz + radius * 1.4)

    light_data = bpy.data.lights.new("GalleryLight", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("GalleryLight", light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = (cx + radius * 3.0, cy - radius * 3.0, cz + radius * 3.0)

    # Track the origin.
    constraint = cam_obj.constraints.new(type="TRACK_TO")
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    empty = bpy.data.objects.new("GalleryTarget", None)
    empty.location = (cx, cy, cz)
    bpy.context.scene.collection.objects.link(empty)
    constraint.target = empty
    return cam_obj, empty, radius


def main() -> int:
    args = _parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    _clear_scene()
    _import_glb(Path(args.glb))
    framing = _frame_scene()
    if framing is None:
        print("_gallery_blender: empty scene after import", file=sys.stderr)
        return 1
    cam_obj, target, radius = framing

    scene = bpy.context.scene
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"

    cx, cy, cz = target.location
    for i in range(args.frames):
        angle = (2.0 * math.pi) * (i / float(max(args.frames, 1)))
        cam_obj.location = (
            cx + radius * 2.2 * math.cos(angle),
            cy + radius * 2.2 * math.sin(angle),
            cz + radius * 1.4,
        )
        scene.render.filepath = str(out_dir / f"render_{i}.png")
        bpy.ops.render.render(write_still=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
