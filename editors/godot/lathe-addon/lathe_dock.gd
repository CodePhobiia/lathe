@tool
extends Control
##
## Bottom-dock panel that lists recently-imported Lathe assets with their
## certification status (PASS/FAIL, score, threshold). Populated as the
## watcher emits asset_imported events.

const MAX_ROWS := 32

var _tree: Tree
var _root: TreeItem
var _rows: Dictionary = {}  # asset_id -> TreeItem


func _init() -> void:
	name = "Lathe"
	custom_minimum_size = Vector2(0, 180)


func _ready() -> void:
	var layout := VBoxContainer.new()
	layout.anchor_right = 1.0
	layout.anchor_bottom = 1.0
	add_child(layout)

	var header := Label.new()
	header.text = "Lathe — recently imported assets (MVP). Point `lathe build` at res://lathe_out/<asset>/ to see entries here."
	layout.add_child(header)

	_tree = Tree.new()
	_tree.columns = 5
	_tree.column_titles_visible = true
	_tree.set_column_title(0, "Asset")
	_tree.set_column_title(1, "Status")
	_tree.set_column_title(2, "Score")
	_tree.set_column_title(3, "Threshold")
	_tree.set_column_title(4, "Scene")
	_tree.hide_root = true
	_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(_tree)

	_root = _tree.create_item()


func on_asset_imported(record: Dictionary) -> void:
	if _tree == null:
		return
	var asset_id: String = record.get("asset_id", "?")
	var item: TreeItem = _rows.get(asset_id)
	if item == null:
		item = _tree.create_item(_root)
		_rows[asset_id] = item

	var certified: bool = record.get("certified", false)
	item.set_text(0, asset_id)
	item.set_text(1, "PASS" if certified else "FAIL")
	item.set_custom_color(1, Color(0.35, 0.8, 0.35) if certified else Color(0.85, 0.35, 0.35))
	item.set_text(2, "%.3f" % float(record.get("score", 0.0)))
	item.set_text(3, "%.3f" % float(record.get("threshold", 0.0)))
	item.set_text(4, String(record.get("scene_path", "")))

	# Cap rows so the dock stays readable in demos.
	if _rows.size() > MAX_ROWS:
		var oldest: String = _rows.keys()[0]
		var oldest_item: TreeItem = _rows[oldest]
		_root.remove_child(oldest_item)
		_rows.erase(oldest)
