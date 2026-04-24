@tool
extends EditorPlugin

const LatheDock := preload("res://addons/lathe-addon/lathe_dock.gd")
const LatheWatcher := preload("res://addons/lathe-addon/lathe_watcher.gd")

var _dock: Control
var _watcher: Node


func _enter_tree() -> void:
	_dock = LatheDock.new()
	add_control_to_bottom_panel(_dock, "Lathe")

	_watcher = LatheWatcher.new()
	_watcher.name = "LatheWatcher"
	_watcher.asset_imported.connect(_dock.on_asset_imported)
	add_child(_watcher)


func _exit_tree() -> void:
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
