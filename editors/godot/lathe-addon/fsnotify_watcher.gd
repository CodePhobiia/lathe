@tool
extends Node
##
## fsnotify watcher (ENG-5, V0.2 E6).
##
## Polls each known build directory under res://lathe_out/ for mtime changes
## on two reproducibility-critical sidecars:
##   - .lathe_snapshot.json  (RPT-4 snapshot writer — per-stage hashes)
##   - selector_manifest.json (REF-5 selector writer — diagnostics)
##
## When either mtime advances, emits `build_updated(asset_id, snapshot_hash)`
## so downstream surfaces (build_trace_viewer, certified_state_indicator,
## thumbnail_regen) can refresh without re-parsing manifest.json.
##
## Rationale: lathe_watcher.gd already polls manifest.json but fires only on
## that file's mtime. Surface-level reproducibility audits key off the
## snapshot hash — when it changes but manifest.json happens to keep the
## same mtime (e.g. a re-run with identical outputs but a fresh validation
## pass), lathe_watcher would miss it. fsnotify_watcher closes that gap.
##
## Gated by an editor setting `lathe/fsnotify_enabled` (default true). Poll
## interval is tuned to 2s to match lathe_watcher; this is OS-portable via
## FileAccess.get_modified_time rather than a native inotify/ReadDirW hook.

const WATCH_DIR := "res://lathe_out"
const POLL_INTERVAL_SEC := 2.0
const SETTING_ENABLED := "lathe/fsnotify_enabled"

const _SIDECARS := [
	".lathe_snapshot.json",
	"selector_manifest.json",
]

signal build_updated(asset_id: String, snapshot_hash: String)

var _timer: Timer
var _seen: Dictionary = {}  # "<asset>/<sidecar>" -> mtime int
var _enabled: bool = true


func _ready() -> void:
	_enabled = _read_setting_default_true(SETTING_ENABLED)
	_timer = Timer.new()
	_timer.wait_time = POLL_INTERVAL_SEC
	_timer.autostart = true
	_timer.one_shot = false
	_timer.timeout.connect(_scan)
	add_child(_timer)
	if _enabled:
		_scan()


func set_enabled(enabled: bool) -> void:
	_enabled = enabled
	if _timer != null:
		if enabled and _timer.is_stopped():
			_timer.start()
		elif not enabled and not _timer.is_stopped():
			_timer.stop()


func is_enabled() -> bool:
	return _enabled


func _read_setting_default_true(key: String) -> bool:
	if not Engine.is_editor_hint():
		return true
	if not Engine.has_singleton("EditorInterface"):
		return true
	var ei: EditorSettings = EditorInterface.get_editor_settings()
	if ei == null:
		return true
	if ei.has_setting(key):
		return bool(ei.get_setting(key))
	return true


func _scan() -> void:
	if not _enabled:
		return
	if not DirAccess.dir_exists_absolute(WATCH_DIR):
		return
	var dir := DirAccess.open(WATCH_DIR)
	if dir == null:
		return

	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry != "." and entry != ".." and dir.current_is_dir():
			_scan_asset(entry)
		entry = dir.get_next()
	dir.list_dir_end()


func _scan_asset(asset_id: String) -> void:
	var build_dir := "%s/%s" % [WATCH_DIR, asset_id]
	var changed := false
	for sidecar in _SIDECARS:
		var path := "%s/%s" % [build_dir, sidecar]
		if not FileAccess.file_exists(path):
			continue
		var mtime := FileAccess.get_modified_time(path)
		var key := "%s/%s" % [asset_id, sidecar]
		var prev: int = _seen.get(key, -1)
		if mtime != prev:
			_seen[key] = mtime
			changed = true
	if not changed:
		return

	var snapshot_hash := _read_snapshot_hash(build_dir)
	build_updated.emit(asset_id, snapshot_hash)
	print("[Lathe] fsnotify build_updated %s (snapshot=%s)" % [
		asset_id, snapshot_hash.substr(0, 10) if snapshot_hash.length() >= 10 else snapshot_hash,
	])


func _read_snapshot_hash(build_dir: String) -> String:
	var path := "%s/.lathe_snapshot.json" % build_dir
	if not FileAccess.file_exists(path):
		return ""
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		return ""
	var parsed: Variant = JSON.parse_string(text)
	if parsed is Dictionary:
		return String((parsed as Dictionary).get("snapshot_hash", ""))
	return ""


## Public helper for tests: force a scan cycle without waiting on the timer.
func force_scan() -> void:
	_scan()
