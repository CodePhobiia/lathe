"""Import a GLB into Blender, save a .blend, and summarize linked data."""

import argparse
import json
import sys
from contextlib import suppress
from pathlib import Path

import bpy


def _parse_args() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Expected Blender export args after --")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--metadata", default=None)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def _load_metadata(path: str | None) -> dict:
    if not path:
        return {}
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise SystemExit(f"metadata file not found: {metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _safe_name(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in text)[:80] or fallback


def _collection(name: str):
    existing = bpy.data.collections.get(name)
    if existing is not None:
        return existing
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def _object_lookup() -> dict[str, object]:
    lookup = {}
    for obj in bpy.data.objects:
        lookup[obj.name] = obj
        lookup[obj.name.split(".", 1)[0]] = obj
    return lookup


def _apply_metadata(metadata: dict) -> None:
    if not metadata:
        return
    scene_id = str(metadata.get("scene_id") or "scene")
    bpy.context.scene["lathe_scene_id"] = scene_id
    bpy.context.scene["lathe_exporter"] = str(metadata.get("exporter") or "lathe.scene.blender_exporter.v1")
    root_collection = _collection(f"LatheScene_{_safe_name(scene_id, 'scene')}")
    regions = {}
    for region in metadata.get("regions", []):
        region_id = str(region.get("region_id") or "")
        if not region_id:
            continue
        collection = _collection(_safe_name(region_id, "region"))
        collection["lathe_scene_id"] = scene_id
        collection["lathe_region_id"] = region_id
        if all(child.name != collection.name for child in root_collection.children):
            with suppress(RuntimeError):
                root_collection.children.link(collection)
        regions[region_id] = collection

    objects_by_name = _object_lookup()
    for item in metadata.get("objects", []):
        object_id = str(item.get("object_id") or "")
        if not object_id:
            continue
        obj = objects_by_name.get(object_id)
        if obj is None:
            continue
        region_id = str(item.get("region_id") or "")
        obj["lathe_scene_id"] = scene_id
        obj["lathe_object_id"] = object_id
        obj["lathe_region_id"] = region_id
        obj["lathe_role"] = str(item.get("role") or "")
        provenance = item.get("provenance")
        if isinstance(provenance, dict):
            source = provenance.get("source")
            if source is not None:
                obj["lathe_provenance_source"] = str(source)
            license_value = provenance.get("license")
            if license_value is not None:
                obj["lathe_provenance_license"] = str(license_value)
            commercial_use = provenance.get("commercial_use")
            if commercial_use is not None:
                obj["lathe_provenance_commercial_use"] = bool(commercial_use)
        material_id = str(item.get("material_id") or "")
        if material_id:
            obj["lathe_material_id"] = material_id
        instancing = item.get("instancing")
        if isinstance(instancing, dict):
            reuse_group_id = instancing.get("reuse_group_id")
            if reuse_group_id is not None:
                obj["lathe_reuse_group_id"] = str(reuse_group_id)
            asset_signature = instancing.get("asset_signature")
            if asset_signature is not None:
                obj["lathe_asset_signature"] = str(asset_signature)
            shared_asset = instancing.get("shared_asset")
            if shared_asset is not None:
                obj["lathe_shared_asset"] = bool(shared_asset)
            instance_fingerprint = instancing.get("instance_fingerprint")
            if instance_fingerprint is not None:
                obj["lathe_instance_fingerprint"] = str(instance_fingerprint)
        target_collection = regions.get(region_id)
        if target_collection is not None and all(existing.name != obj.name for existing in target_collection.objects):
            target_collection.objects.link(obj)

    for material in metadata.get("materials", []):
        material_id = str(material.get("material_id") or "")
        if not material_id:
            continue
        mat = bpy.data.materials.get(material_id) or bpy.data.materials.new(material_id)
        mat["lathe_scene_id"] = scene_id
        mat["lathe_material_id"] = material_id

    for camera in metadata.get("cameras", []):
        camera_id = str(camera.get("camera_id") or "")
        if not camera_id:
            continue
        cam_data = bpy.data.cameras.new(camera_id)
        cam = bpy.data.objects.new(camera_id, cam_data)
        cam["lathe_scene_id"] = scene_id
        cam["lathe_camera_id"] = camera_id
        cam["lathe_target"] = str(camera.get("target") or "")
        cam["lathe_framing"] = str(camera.get("framing") or "")
        root_collection.objects.link(cam)

    for light in metadata.get("lights", []):
        light_id = str(light.get("light_id") or "")
        if not light_id:
            continue
        light_data = bpy.data.lights.new(light_id, type="POINT")
        light_obj = bpy.data.objects.new(light_id, light_data)
        light_obj["lathe_scene_id"] = scene_id
        light_obj["lathe_light_id"] = light_id
        light_obj["lathe_target"] = str(light.get("target") or "")
        root_collection.objects.link(light_obj)


def _custom_props(item) -> dict:
    keys = item.keys() if hasattr(item, "keys") else []
    return {key: item[key] for key in keys if str(key).startswith("lathe_")}


def main() -> None:
    """Run the Blender export helper."""
    args = _parse_args()
    metadata = _load_metadata(args.metadata)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    _apply_metadata(metadata)
    bpy.ops.wm.save_as_mainfile(filepath=args.output)
    summary = {
        "objects": [obj.name for obj in bpy.data.objects],
        "collections": [item.name for item in bpy.data.collections],
        "materials": [item.name for item in bpy.data.materials],
        "cameras": [item.name for item in bpy.data.cameras],
        "lights": [item.name for item in bpy.data.lights],
        "custom_properties": {
            "scene": _custom_props(bpy.context.scene),
            "objects": {obj.name: _custom_props(obj) for obj in bpy.data.objects},
            "collections": {item.name: _custom_props(item) for item in bpy.data.collections},
            "materials": {item.name: _custom_props(item) for item in bpy.data.materials},
        },
        "node_groups": [item.name for item in bpy.data.node_groups],
        "linked_libraries": [item.filepath for item in bpy.data.libraries],
        "overrides": [item.name for item in bpy.data.objects if getattr(item, "override_library", None)],
    }
    with Path(args.summary).open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
