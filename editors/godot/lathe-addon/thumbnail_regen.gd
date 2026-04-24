@tool
extends Node
##
## Regenerates a per-asset .thumbnail.png next to each imported Lathe build
## whenever the watcher reports a fresh build (mtime changed).
##
## Strategy: instance the saved .tscn into a SubViewport with a perspective
## camera + default lighting, render once, read back as an Image, save to
## disk as <build_dir>/.thumbnail.png. Downstream (FileSystem dock,
## build-trace viewer) can display it directly — Godot's EditorInterface
## also re-scans the file via editor_resource_preview.
##
## ENG-3 (V0.2 E6): first-cut implementation. The render is a single frame
## at 256x256 with framing based on the scene's AABB. Iteration on
## lighting / camera angles is deferred.

const THUMB_SIZE := 256
const THUMB_FILENAME := ".thumbnail.png"

var _pending: Array[Dictionary] = []


func on_asset_imported(record: Dictionary) -> void:
	var scene_path: String = record.get("scene_path", "")
	if scene_path.is_empty():
		return
	var build_dir: String = scene_path.get_base_dir()
	if build_dir.is_empty():
		return

	var build_mtime: int = 0
	var manifest_path: String = record.get("manifest_path", "")
	if not manifest_path.is_empty() and FileAccess.file_exists(manifest_path):
		build_mtime = FileAccess.get_modified_time(manifest_path)

	var thumb_path := "%s/%s" % [build_dir, THUMB_FILENAME]
	if FileAccess.file_exists(thumb_path):
		var thumb_mtime := FileAccess.get_modified_time(thumb_path)
		if build_mtime != 0 and thumb_mtime >= build_mtime:
			return

	_pending.append({
		"scene_path": scene_path,
		"thumb_path": thumb_path,
		"asset_id": record.get("asset_id", ""),
	})
	call_deferred("_process_pending")


func _process_pending() -> void:
	if _pending.is_empty():
		return
	var job: Dictionary = _pending.pop_front()
	_render_thumbnail(job)
	if not _pending.is_empty():
		call_deferred("_process_pending")


func _render_thumbnail(job: Dictionary) -> void:
	var scene_path: String = job.get("scene_path", "")
	var thumb_path: String = job.get("thumb_path", "")
	if not FileAccess.file_exists(scene_path):
		push_warning("[Lathe] thumbnail source scene missing: %s" % scene_path)
		return

	var packed: PackedScene = load(scene_path)
	if packed == null:
		push_warning("[Lathe] thumbnail failed to load scene: %s" % scene_path)
		return

	var scene_root: Node = packed.instantiate()
	if not (scene_root is Node3D):
		scene_root.queue_free()
		return

	var viewport := SubViewport.new()
	viewport.size = Vector2i(THUMB_SIZE, THUMB_SIZE)
	viewport.transparent_bg = true
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE

	var world := World3D.new()
	viewport.world_3d = world

	add_child(viewport)
	viewport.add_child(scene_root)

	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, 45, 0)
	light.light_energy = 1.2
	viewport.add_child(light)

	var camera := Camera3D.new()
	var bounds := _compute_aabb(scene_root as Node3D)
	var center := bounds.get_center()
	var radius := bounds.get_longest_axis_size() * 0.75
	if radius <= 0.0:
		radius = 1.0
	var offset := Vector3(1, 0.8, 1).normalized() * (radius * 2.5)
	camera.transform.origin = center + offset
	camera.look_at(center, Vector3.UP)
	camera.current = true
	viewport.add_child(camera)

	await RenderingServer.frame_post_draw

	var image: Image = viewport.get_texture().get_image()
	if image == null or image.is_empty():
		push_warning("[Lathe] thumbnail render produced empty image for %s" % scene_path)
	else:
		var abs_path: String = ProjectSettings.globalize_path(thumb_path)
		var save_err := image.save_png(abs_path)
		if save_err != OK:
			push_warning("[Lathe] thumbnail save failed (err=%d): %s" % [save_err, abs_path])
		else:
			if Engine.is_editor_hint():
				var fs := EditorInterface.get_resource_filesystem()
				if fs != null:
					fs.scan()

	remove_child(viewport)
	viewport.queue_free()


func _compute_aabb(root: Node3D) -> AABB:
	var combined := AABB()
	var has_any := false
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.push_back(child)
		if node is VisualInstance3D:
			var vi := node as VisualInstance3D
			var box := vi.get_aabb()
			var world_box := vi.global_transform * box if vi.is_inside_tree() else box
			if not has_any:
				combined = world_box
				has_any = true
			else:
				combined = combined.merge(world_box)
	if not has_any:
		combined = AABB(Vector3(-0.5, -0.5, -0.5), Vector3(1, 1, 1))
	return combined
