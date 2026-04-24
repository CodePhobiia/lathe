extends Node
##
## Manual smoke for fsnotify_watcher (ENG-5).
##
## Instantiates the watcher under this test node, listens for
## `build_updated`, and prints each emission. To exercise it, re-save
## any `res://lathe_out/<asset>/.lathe_snapshot.json` or
## `selector_manifest.json` while this scene is running.

const LatheFsnotifyWatcher := preload("res://addons/lathe-addon/fsnotify_watcher.gd")

var _watcher: Node


func _ready() -> void:
	_watcher = LatheFsnotifyWatcher.new()
	_watcher.name = "SmokeFsnotifyWatcher"
	add_child(_watcher)
	_watcher.build_updated.connect(_on_build_updated)
	print("[smoke_fsnotify] watcher running — touch a sidecar under res://lathe_out/<asset>/ to trigger")
	# Kick an immediate scan so first-pass baseline prints show up.
	_watcher.call_deferred("force_scan")


func _on_build_updated(asset_id: String, snapshot_hash: String) -> void:
	var short := snapshot_hash.substr(0, 10) if snapshot_hash.length() >= 10 else snapshot_hash
	print("[smoke_fsnotify] build_updated asset=%s snapshot=%s" % [asset_id, short])
