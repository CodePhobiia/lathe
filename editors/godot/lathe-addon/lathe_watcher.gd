@tool
extends Node
##
## Polls res://lathe_out/ for new <asset>/manifest.json files. When a manifest
## is discovered or its mtime changes, invokes LatheImporter and emits
## asset_imported so the dock can refresh.
##
## MVP gap: polling only. Native FileSystem change notifications in the editor
## would remove the 2s interval cost — deferred as BL-44.

const LatheImporter := preload("res://addons/lathe-addon/lathe_importer.gd")

const WATCH_DIR := "res://lathe_out"
const POLL_INTERVAL_SEC := 2.0

signal asset_imported(record: Dictionary)

var _seen: Dictionary = {}
var _timer: Timer


func _ready() -> void:
	_timer = Timer.new()
	_timer.wait_time = POLL_INTERVAL_SEC
	_timer.autostart = true
	_timer.one_shot = false
	_timer.timeout.connect(_scan)
	add_child(_timer)
	_scan()


func _scan() -> void:
	if not DirAccess.dir_exists_absolute(WATCH_DIR):
		return

	var dir := DirAccess.open(WATCH_DIR)
	if dir == null:
		return

	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry != "." and entry != ".." and dir.current_is_dir():
			var manifest_path := "%s/%s/manifest.json" % [WATCH_DIR, entry]
			if FileAccess.file_exists(manifest_path):
				_maybe_import(entry, manifest_path)
		entry = dir.get_next()
	dir.list_dir_end()


func _maybe_import(asset_id: String, manifest_path: String) -> void:
	var mtime := FileAccess.get_modified_time(manifest_path)
	var prev: int = _seen.get(asset_id, -1)
	if mtime == prev:
		return

	var record: Dictionary = LatheImporter.import_from_manifest(manifest_path)
	if record.is_empty():
		return

	_seen[asset_id] = mtime
	record["asset_id"] = asset_id
	record["manifest_path"] = manifest_path
	record["timestamp"] = Time.get_unix_time_from_system()
	asset_imported.emit(record)
	print("[Lathe] imported %s (certified=%s)" % [asset_id, record.get("certified", false)])
