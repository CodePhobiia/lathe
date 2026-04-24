@tool
extends EditorImportPlugin
##
## Native EditorImportPlugin for Lathe build-snapshot sidecars
## (.lathe_snapshot.json). Recognizing this sidecar gives Godot's FileSystem
## a typed handle on a build: the import produces a small Resource that
## records the snapshot hash, the asset_id, the stage hashes, and a trust
## flag (certified PASS / FAIL) so other addon surfaces (dock, trace viewer)
## can query it without re-parsing JSON.
##
## For .lth.glb / plain .glb the stock Godot GLB importer is used; our
## scene enrichment (sockets, collision hulls, LOD bias) happens via
## lathe_importer.gd which is invoked by the watcher after Godot finishes
## importing. Keeping import and enrichment separate avoids fighting the
## stock pipeline and preserves AssetLib-compatibility.
##
## V0.2 MVP: supports .lathe_snapshot.json as a recognized import type
## (ENG-2 minimum viable). Full .glb override with typed Position3D
## socket injection at import time (rather than after) is the next tier.

const _SNAPSHOT_EXT := "lathe_snapshot.json"


func _get_importer_name() -> String:
	return "lathe.snapshot.v1"


func _get_visible_name() -> String:
	return "Lathe Build Snapshot"


func _get_recognized_extensions() -> PackedStringArray:
	return PackedStringArray([_SNAPSHOT_EXT])


func _get_save_extension() -> String:
	return "res"


func _get_resource_type() -> String:
	return "Resource"


func _get_priority() -> float:
	return 1.0


func _get_import_order() -> int:
	return 0


func _get_preset_count() -> int:
	return 1


func _get_preset_name(preset_index: int) -> String:
	return "Default"


func _get_import_options(path: String, preset_index: int) -> Array[Dictionary]:
	return [
		{
			"name": "verify_stage_hashes",
			"default_value": true,
			"property_hint": PROPERTY_HINT_NONE,
			"hint_string": "",
		},
		{
			"name": "resolve_glb_path",
			"default_value": true,
			"property_hint": PROPERTY_HINT_NONE,
			"hint_string": "",
		},
	]


func _get_option_visibility(path: String, option_name: StringName, options: Dictionary) -> bool:
	return true


func _import(
	source_file: String,
	save_path: String,
	options: Dictionary,
	platform_variants: Array[String],
	gen_files: Array[String],
) -> Error:
	var text := FileAccess.get_file_as_string(source_file)
	if text.is_empty():
		push_warning("[Lathe] snapshot file empty or unreadable: %s" % source_file)
		return ERR_PARSE_ERROR

	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		push_warning("[Lathe] snapshot JSON root is not an object: %s" % source_file)
		return ERR_PARSE_ERROR

	var snapshot := parsed as Dictionary

	var resource := Resource.new()
	resource.set_meta("lathe_snapshot_version", snapshot.get("snapshot_schema_version", 1))
	resource.set_meta("asset_id", snapshot.get("asset_id", ""))
	resource.set_meta("snapshot_hash", snapshot.get("snapshot_hash", ""))
	resource.set_meta("lathe_version", snapshot.get("lathe_version", ""))
	resource.set_meta("stage_hashes", snapshot.get("stage_hashes", {}))
	resource.set_meta("source_path", source_file)

	var build_dir := source_file.get_base_dir()
	resource.set_meta("build_dir", build_dir)

	var report_path := "%s/build_report.json" % build_dir
	var certified := false
	var score := 0.0
	var threshold := 0.0
	if FileAccess.file_exists(report_path):
		var report_text := FileAccess.get_file_as_string(report_path)
		var report_parsed: Variant = JSON.parse_string(report_text)
		if report_parsed is Dictionary:
			var report := report_parsed as Dictionary
			certified = bool(report.get("certified", false))
			var cert_dict: Variant = report.get("certification", {})
			if cert_dict is Dictionary:
				score = float((cert_dict as Dictionary).get("score", 0.0))
				threshold = float((cert_dict as Dictionary).get("threshold", 0.0))

	resource.set_meta("certified", certified)
	resource.set_meta("score", score)
	resource.set_meta("threshold", threshold)

	if bool(options.get("resolve_glb_path", true)):
		var manifest_path := "%s/manifest.json" % build_dir
		if FileAccess.file_exists(manifest_path):
			var mtext := FileAccess.get_file_as_string(manifest_path)
			var mparsed: Variant = JSON.parse_string(mtext)
			if mparsed is Dictionary:
				var outputs: Array = (mparsed as Dictionary).get("outputs", [])
				for entry in outputs:
					if entry is Dictionary and (entry as Dictionary).get("format", "") == "glb":
						resource.set_meta("glb_uri", (entry as Dictionary).get("uri", ""))
						break

	var save_to := "%s.%s" % [save_path, _get_save_extension()]
	return ResourceSaver.save(resource, save_to)
