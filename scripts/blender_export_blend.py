"""Import a GLB into Blender, save a .blend, and summarize linked data."""

import argparse
import json
import sys
from pathlib import Path

import bpy


def _parse_args() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Expected Blender export args after --")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def main() -> None:
    """Run the Blender export helper."""
    args = _parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    collection = bpy.context.scene.collection
    collection.name = "AssetRoot"
    bpy.ops.wm.save_as_mainfile(filepath=args.output)
    summary = {
        "objects": [obj.name for obj in bpy.data.objects],
        "collections": [item.name for item in bpy.data.collections],
        "materials": [item.name for item in bpy.data.materials],
        "node_groups": [item.name for item in bpy.data.node_groups],
        "linked_libraries": [item.filepath for item in bpy.data.libraries],
        "overrides": [item.name for item in bpy.data.objects if getattr(item, "override_library", None)],
    }
    with Path(args.summary).open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
