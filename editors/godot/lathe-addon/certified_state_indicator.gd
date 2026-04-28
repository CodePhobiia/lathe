@tool
extends Control
##
## Certified-state indicator (ENG-6, V0.2 E6).
##
## Bottom-bar widget that reads the most recent .lathe_snapshot.json + its
## co-located build_report.json for the "current" asset and renders:
##   * green dot + "certified true @ <score>"  — certified
##   * red dot  + "certified false @ <score>"  — not certified
##   * gray dot + "no build"                   — no snapshot on disk
##
## Click opens the build_trace_viewer dock and focuses the asset.
##
## Refreshes on `build_updated` from fsnotify_watcher. Also refreshes on
## `asset_imported` from lathe_watcher so it tracks a fresh build even
## without snapshot mtime advancing.

const WATCH_DIR := "res://lathe_out"
const CURRENT_MANIFEST_REL := "stages/package/package_manifest.json"

const _GREEN := Color(0.45, 0.85, 0.45)
const _RED := Color(0.95, 0.4, 0.4)
const _GRAY := Color(0.65, 0.65, 0.7)

signal asset_focus_requested(asset_id: String)

var _dot: ColorRect
var _label: Label
var _button: Button
var _current_asset: String = ""
var _current_build_dir: String = ""


func _ready() -> void:
	name = "LatheCertifiedState"
	custom_minimum_size = Vector2(220, 22)
	_build_ui()
	refresh()


func _build_ui() -> void:
	var row := HBoxContainer.new()
	row.anchor_right = 1.0
	row.anchor_bottom = 1.0
	row.add_theme_constant_override("separation", 6)
	add_child(row)

	_dot = ColorRect.new()
	_dot.custom_minimum_size = Vector2(10, 10)
	_dot.color = _GRAY
	_dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_dot)

	_label = Label.new()
	_label.text = "Lathe: no build"
	_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_label)

	_button = Button.new()
	_button.text = "Open"
	_button.flat = true
	_button.tooltip_text = "Open the Lathe Build Trace dock for this asset"
	_button.pressed.connect(_on_open_pressed)
	row.add_child(_button)


func on_build_updated(asset_id: String, _snapshot_hash: String) -> void:
	_current_asset = asset_id
	_current_build_dir = "%s/%s" % [WATCH_DIR, asset_id]
	refresh()


func on_asset_imported(record: Dictionary) -> void:
	var asset_id: String = record.get("asset_id", "")
	if asset_id.is_empty():
		return
	_current_asset = asset_id
	var manifest_path: String = record.get("manifest_path", "")
	if not manifest_path.is_empty():
		_current_build_dir = _build_dir_for_manifest(manifest_path)
	else:
		_current_build_dir = "%s/%s" % [WATCH_DIR, asset_id]
	refresh()


func _build_dir_for_manifest(manifest_path: String) -> String:
	var current_suffix := "/%s" % CURRENT_MANIFEST_REL
	if manifest_path.ends_with(current_suffix):
		return manifest_path.substr(0, manifest_path.length() - current_suffix.length())
	return manifest_path.get_base_dir()


func refresh() -> void:
	var latest: Dictionary = {}
	if not _current_build_dir.is_empty():
		var snapshot_path := "%s/.lathe_snapshot.json" % _current_build_dir
		if FileAccess.file_exists(snapshot_path):
			latest = {"asset_id": _current_asset, "build_dir": _current_build_dir}
	if latest.is_empty():
		latest = _find_latest_snapshot()

	if latest.is_empty():
		_render_state(_GRAY, "Lathe: no build", "")
		return

	var asset_id: String = latest.get("asset_id", "")
	var build_dir: String = latest.get("build_dir", "")
	_current_asset = asset_id
	_current_build_dir = build_dir

	var report_path := "%s/build_report.json" % build_dir
	var certified := false
	var score := 0.0
	if FileAccess.file_exists(report_path):
		var text := FileAccess.get_file_as_string(report_path)
		var parsed: Variant = JSON.parse_string(text)
		if parsed is Dictionary:
			var report := parsed as Dictionary
			certified = bool(report.get("certified", false))
			var cert: Variant = report.get("certification", {})
			if cert is Dictionary:
				score = float((cert as Dictionary).get("score", 0.0))

	var color := _GREEN if certified else _RED
	var label := "%s: certified %s @ %.3f" % [asset_id, "true" if certified else "false", score]
	_render_state(color, label, build_dir)


func _render_state(color: Color, text: String, _build_dir: String) -> void:
	if _dot != null:
		_dot.color = color
	if _label != null:
		_label.text = text
	if _button != null:
		_button.disabled = _current_asset.is_empty()


func _on_open_pressed() -> void:
	if _current_asset.is_empty():
		return
	asset_focus_requested.emit(_current_asset)


func _find_latest_snapshot() -> Dictionary:
	if not DirAccess.dir_exists_absolute(WATCH_DIR):
		return {}
	var dir := DirAccess.open(WATCH_DIR)
	if dir == null:
		return {}
	var latest_mtime: int = -1
	var latest: Dictionary = {}
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry != "." and entry != ".." and dir.current_is_dir():
			var build_dir := "%s/%s" % [WATCH_DIR, entry]
			var snap := "%s/.lathe_snapshot.json" % build_dir
			if FileAccess.file_exists(snap):
				var m := FileAccess.get_modified_time(snap)
				if m > latest_mtime:
					latest_mtime = m
					latest = {"asset_id": entry, "build_dir": build_dir}
		entry = dir.get_next()
	dir.list_dir_end()
	return latest


## Public helper for tests.
func get_current_state() -> Dictionary:
	return {
		"asset_id": _current_asset,
		"build_dir": _current_build_dir,
		"label": _label.text if _label != null else "",
		"color": _dot.color if _dot != null else Color(0, 0, 0, 0),
	}
