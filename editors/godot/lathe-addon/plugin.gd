@tool
extends EditorPlugin

const LatheDock := preload("res://addons/lathe-addon/lathe_dock.gd")
const LatheWatcher := preload("res://addons/lathe-addon/lathe_watcher.gd")
const LatheImportPlugin := preload("res://addons/lathe-addon/editor_import_plugin.gd")
const LatheThumbnailRegen := preload("res://addons/lathe-addon/thumbnail_regen.gd")
const BuildTraceViewerScene := preload("res://addons/lathe-addon/build_trace_viewer.tscn")

var _dock: Control
var _watcher: Node
var _import_plugin: EditorImportPlugin
var _thumbnail_regen: Node
var _trace_viewer: Control


func _enter_tree() -> void:
	_dock = LatheDock.new()
	add_control_to_bottom_panel(_dock, "Lathe")

	_watcher = LatheWatcher.new()
	_watcher.name = "LatheWatcher"
	_watcher.asset_imported.connect(_dock.on_asset_imported)
	add_child(_watcher)

	_import_plugin = LatheImportPlugin.new()
	add_import_plugin(_import_plugin)

	_thumbnail_regen = LatheThumbnailRegen.new()
	_thumbnail_regen.name = "LatheThumbnailRegen"
	add_child(_thumbnail_regen)
	if _watcher.has_signal("asset_imported"):
		_watcher.asset_imported.connect(_thumbnail_regen.on_asset_imported)

	_trace_viewer = BuildTraceViewerScene.instantiate()
	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_BL, _trace_viewer)
	if _watcher.has_signal("asset_imported") and _trace_viewer.has_method("on_asset_imported"):
		_watcher.asset_imported.connect(_trace_viewer.on_asset_imported)


func _exit_tree() -> void:
	if _trace_viewer != null:
		if _watcher != null and _watcher.asset_imported.is_connected(_trace_viewer.on_asset_imported):
			_watcher.asset_imported.disconnect(_trace_viewer.on_asset_imported)
		remove_control_from_docks(_trace_viewer)
		_trace_viewer.queue_free()
		_trace_viewer = null

	if _thumbnail_regen != null:
		if _watcher != null and _watcher.asset_imported.is_connected(_thumbnail_regen.on_asset_imported):
			_watcher.asset_imported.disconnect(_thumbnail_regen.on_asset_imported)
		remove_child(_thumbnail_regen)
		_thumbnail_regen.queue_free()
		_thumbnail_regen = null

	if _import_plugin != null:
		remove_import_plugin(_import_plugin)
		_import_plugin = null

	if _watcher != null:
		if _watcher.asset_imported.is_connected(_dock.on_asset_imported):
			_watcher.asset_imported.disconnect(_dock.on_asset_imported)
		remove_child(_watcher)
		_watcher.queue_free()
		_watcher = null

	if _dock != null:
		remove_control_from_bottom_panel(_dock)
		_dock.queue_free()
		_dock = null


func _get_plugin_name() -> String:
	return "Lathe Integration"


func _get_plugin_icon() -> Texture2D:
	var icon_path := "res://addons/lathe-addon/icons/lathe.svg"
	if ResourceLoader.exists(icon_path):
		return load(icon_path)
	return null
