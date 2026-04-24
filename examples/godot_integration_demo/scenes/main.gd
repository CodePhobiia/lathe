extends Node3D
##
## Minimal demo scene for the Lathe integration addon.
##
## At runtime, looks for the most recently saved .tscn under res://lathe_out/
## and instances it under AssetPlaceholder. Intended to run from the editor
## after `lathe build` has populated lathe_out/<asset>/ and the addon has
## imported it.

const LATHE_OUT := "res://lathe_out"


func _ready() -> void:
	var scene_path := _find_latest_imported_scene()
	if scene_path.is_empty():
		print("[demo] no lathe_out/<asset>/<asset>.tscn found yet. Run `lathe build ... --out %s` first." % LATHE_OUT)
		return

	var packed: PackedScene = load(scene_path)
	if packed == null:
		push_warning("[demo] failed to load %s" % scene_path)
		return

	var instance := packed.instantiate()
	$AssetPlaceholder.add_child(instance)
	print("[demo] instanced %s" % scene_path)


func _find_latest_imported_scene() -> String:
	if not DirAccess.dir_exists_absolute(LATHE_OUT):
		return ""
	var dir := DirAccess.open(LATHE_OUT)
	if dir == null:
		return ""

	var best_path := ""
	var best_mtime := -1

	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry != "." and entry != ".." and dir.current_is_dir():
			var candidate := "%s/%s/%s.tscn" % [LATHE_OUT, entry, entry]
			if FileAccess.file_exists(candidate):
				var mtime := FileAccess.get_modified_time(candidate)
				if mtime > best_mtime:
					best_mtime = mtime
					best_path = candidate
		entry = dir.get_next()
	dir.list_dir_end()
	return best_path
