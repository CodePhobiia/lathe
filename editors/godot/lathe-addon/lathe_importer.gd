@tool
extends RefCounted
##
## Reads a Lathe manifest.json (schema: package_manifest.json + companion
## build_report.json) and imports the referenced .glb via Godot's built-in
## GLB loader. Post-import, enriches the scene by:
##   - replacing nodes named socket_* or anchor_* with Marker3D
##   - replacing meshes named collision_* with CollisionShape3D (convex)
##   - wiring MeshInstance3D.lod_bias from the manifest's LOD list
##
## MVP gap: does not yet invoke Godot's ResourceImporter GLB for editor-side
## thumbnail generation; uses runtime GLTFDocument.append_from_file. That
## suffices for the demo path (load into a scene) but is deferred as BL-44
## for AssetLib-quality imports.

const _SOCKET_PREFIXES := ["socket_", "anchor_"]
const _COLLISION_PREFIX := "collision_"


static func import_from_manifest(manifest_path: String) -> Dictionary:
	var manifest := _read_json(manifest_path)
	if manifest.is_empty():
		push_warning("[Lathe] manifest unreadable: %s" % manifest_path)
		return {}

	var asset_dir := manifest_path.get_base_dir()
	var glb_rel: String = _find_glb(manifest)
	if glb_rel.is_empty():
		push_warning("[Lathe] no .glb listed in manifest: %s" % manifest_path)
		return {}

	var glb_abs := "%s/%s" % [asset_dir, glb_rel]
	if not FileAccess.file_exists(glb_abs):
		push_warning("[Lathe] .glb missing on disk: %s" % glb_abs)
		return {}

	var report := _read_json("%s/build_report.json" % asset_dir)

	var scene_root: Node = _load_glb(glb_abs)
	if scene_root == null:
		return {}

	_enrich_sockets(scene_root)
	_enrich_collision(scene_root)
	_apply_lod_bias(scene_root, manifest)

	var scene_out := "%s/%s.tscn" % [asset_dir, manifest.get("asset_id", "lathe_asset")]
	var packed := PackedScene.new()
	packed.pack(scene_root)
	var save_err := ResourceSaver.save(packed, scene_out)
	if save_err != OK:
		push_warning("[Lathe] failed to save scene %s (err=%d)" % [scene_out, save_err])

	return {
		"certified": report.get("certified", false),
		"score": _extract_score(report),
		"threshold": _extract_threshold(report),
		"scene_path": scene_out,
		"glb_path": glb_abs,
		"formats": manifest.get("formats", []),
	}


static func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		return {}
	var parsed: Variant = JSON.parse_string(text)
	if parsed is Dictionary:
		return parsed
	return {}


static func _find_glb(manifest: Dictionary) -> String:
	var outputs: Array = manifest.get("outputs", [])
	for entry in outputs:
		if entry is Dictionary and entry.get("format", "") == "glb":
			return entry.get("uri", "")
	return ""


static func _load_glb(glb_abs_path: String) -> Node:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(ProjectSettings.globalize_path(glb_abs_path), state)
	if err != OK:
		push_warning("[Lathe] GLTFDocument.append_from_file failed (err=%d) for %s" % [err, glb_abs_path])
		return null
	return doc.generate_scene(state)


static func _enrich_sockets(root: Node) -> void:
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.push_back(child)

		if node == root:
			continue
		if not _name_has_any_prefix(node.name, _SOCKET_PREFIXES):
			continue

		var marker := Marker3D.new()
		marker.name = node.name
		if node is Node3D:
			marker.transform = (node as Node3D).transform
		var parent := node.get_parent()
		if parent != null:
			parent.add_child(marker)
			marker.owner = root
			parent.remove_child(node)
			node.queue_free()


static func _enrich_collision(root: Node) -> void:
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.push_back(child)

		if not (node is MeshInstance3D):
			continue
		var mesh_node := node as MeshInstance3D
		if not mesh_node.name.begins_with(_COLLISION_PREFIX):
			continue
		if mesh_node.mesh == null:
			continue

		var body := StaticBody3D.new()
		body.name = mesh_node.name
		var shape_node := CollisionShape3D.new()
		shape_node.shape = mesh_node.mesh.create_convex_shape(true, false)
		body.add_child(shape_node)
		shape_node.owner = root

		var parent := mesh_node.get_parent()
		if parent != null:
			body.transform = mesh_node.transform
			parent.add_child(body)
			body.owner = root
			parent.remove_child(mesh_node)
			mesh_node.queue_free()


static func _apply_lod_bias(root: Node, manifest: Dictionary) -> void:
	var lods: Array = manifest.get("lods", [])
	if lods.is_empty():
		return
	var index := 0
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		for child in node.get_children():
			stack.push_back(child)
		if node is MeshInstance3D and index < lods.size():
			var entry: Variant = lods[index]
			if entry is Dictionary and entry.has("lod_bias"):
				(node as MeshInstance3D).lod_bias = float(entry["lod_bias"])
			index += 1


static func _name_has_any_prefix(name: StringName, prefixes: Array) -> bool:
	var s := String(name)
	for p in prefixes:
		if s.begins_with(p):
			return true
	return false


static func _extract_score(report: Dictionary) -> float:
	if report.is_empty():
		return 0.0
	var cert: Variant = report.get("certification", {})
	if cert is Dictionary and cert.has("score"):
		return float(cert["score"])
	return float(report.get("score", 0.0))


static func _extract_threshold(report: Dictionary) -> float:
	if report.is_empty():
		return 0.0
	var cert: Variant = report.get("certification", {})
	if cert is Dictionary and cert.has("threshold"):
		return float(cert["threshold"])
	return float(report.get("threshold", 0.0))
