@tool
extends Control
##
## Dockable build-trace viewer (ENG-4, V0.2 E6).
##
## Reads `<build>/build_report.json`, `<build>/selector_manifest.json`, and
## `<build>/.lathe_snapshot.json` for a selected asset, then renders:
##   - Stage timeline: per-stage runtime + status color
##   - Diagnostics list, grouped by severity (collapsible)
##   - Kernel name + watertight_rate
##   - "Open HTML report" button (launches `report.html` in external
##     browser via OS.shell_open)
##
## Updates when the watcher emits asset_imported. An asset drop-down lets
## the user inspect historic builds that are still on disk.

const WATCH_DIR := "res://lathe_out"

const _SEVERITY_COLORS := {
	"info": Color(0.55, 0.75, 1.0),
	"warning": Color(0.95, 0.8, 0.35),
	"error": Color(0.95, 0.4, 0.4),
	"critical": Color(1.0, 0.25, 0.3),
}

var _asset_picker: OptionButton
var _refresh_btn: Button
var _open_report_btn: Button
var _kernel_label: Label
var _watertight_label: Label
var _stage_list: Tree
var _diag_list: Tree

var _current_build_dir: String = ""
var _known_assets: Dictionary = {}  # asset_id -> build_dir


func _ready() -> void:
	name = "Lathe Build Trace"
	_bind_controls()
	if _refresh_btn != null:
		_refresh_btn.pressed.connect(_on_refresh_pressed)
	if _asset_picker != null:
		_asset_picker.item_selected.connect(_on_asset_selected)
	if _open_report_btn != null:
		_open_report_btn.pressed.connect(_on_open_report_pressed)
	_rescan_assets()


func _bind_controls() -> void:
	_asset_picker = get_node_or_null("Layout/Toolbar/AssetPicker") as OptionButton
	_refresh_btn = get_node_or_null("Layout/Toolbar/RefreshButton") as Button
	_open_report_btn = get_node_or_null("Layout/Toolbar/OpenReportButton") as Button
	_kernel_label = get_node_or_null("Layout/Header/KernelLabel") as Label
	_watertight_label = get_node_or_null("Layout/Header/WatertightLabel") as Label
	_stage_list = get_node_or_null("Layout/Split/StagesBox/StageTree") as Tree
	_diag_list = get_node_or_null("Layout/Split/DiagnosticsBox/DiagnosticsTree") as Tree


func on_asset_imported(record: Dictionary) -> void:
	var asset_id: String = record.get("asset_id", "")
	var manifest_path: String = record.get("manifest_path", "")
	if asset_id.is_empty() or manifest_path.is_empty():
		return
	var build_dir := manifest_path.get_base_dir()
	_known_assets[asset_id] = build_dir
	_refresh_asset_picker()
	if _current_build_dir.is_empty() or _current_build_dir == build_dir:
		_load_build(build_dir)


func _on_refresh_pressed() -> void:
	_rescan_assets()


func _on_asset_selected(index: int) -> void:
	if _asset_picker == null or index < 0 or index >= _asset_picker.item_count:
		return
	var asset_id := _asset_picker.get_item_text(index)
	var build_dir: String = _known_assets.get(asset_id, "")
	if not build_dir.is_empty():
		_load_build(build_dir)


func _on_open_report_pressed() -> void:
	if _current_build_dir.is_empty():
		return
	var report_html := "%s/report.html" % _current_build_dir
	if not FileAccess.file_exists(report_html):
		push_warning("[Lathe] report.html not found at %s — generate via RPT-1 first." % report_html)
		return
	OS.shell_open(ProjectSettings.globalize_path(report_html))


func _rescan_assets() -> void:
	if not DirAccess.dir_exists_absolute(WATCH_DIR):
		return
	var dir := DirAccess.open(WATCH_DIR)
	if dir == null:
		return
	_known_assets.clear()
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if entry != "." and entry != ".." and dir.current_is_dir():
			var build_dir := "%s/%s" % [WATCH_DIR, entry]
			if FileAccess.file_exists("%s/manifest.json" % build_dir):
				_known_assets[entry] = build_dir
		entry = dir.get_next()
	dir.list_dir_end()
	_refresh_asset_picker()


func _refresh_asset_picker() -> void:
	if _asset_picker == null:
		return
	var previous_text: String = _asset_picker.text if _asset_picker.item_count > 0 else ""
	_asset_picker.clear()
	var ids: Array = _known_assets.keys()
	ids.sort()
	for asset_id in ids:
		_asset_picker.add_item(String(asset_id))
	if previous_text != "":
		for i in range(_asset_picker.item_count):
			if _asset_picker.get_item_text(i) == previous_text:
				_asset_picker.select(i)
				break


func _load_build(build_dir: String) -> void:
	_current_build_dir = build_dir
	var report := _read_json("%s/build_report.json" % build_dir)
	var selector := _read_json("%s/selector_manifest.json" % build_dir)
	var snapshot := _read_json("%s/.lathe_snapshot.json" % build_dir)
	_render_header(report, snapshot)
	_render_stages(report, snapshot)
	_render_diagnostics(report, selector)


func _render_header(report: Dictionary, snapshot: Dictionary) -> void:
	if _kernel_label != null:
		var kernel := ""
		var geometry: Variant = report.get("geometry", {})
		if geometry is Dictionary:
			kernel = String((geometry as Dictionary).get("kernel", ""))
		if kernel.is_empty():
			kernel = String(report.get("kernel", ""))
		if kernel.is_empty():
			kernel = "(unknown)"
		var snap_hash := String(snapshot.get("snapshot_hash", ""))
		var hash_suffix := ""
		if not snap_hash.is_empty():
			hash_suffix = "  ·  snapshot %s" % snap_hash.substr(0, 10)
		_kernel_label.text = "Kernel: %s%s" % [kernel, hash_suffix]

	if _watertight_label != null:
		var rate := _find_float(report, ["validation", "watertight_rate"])
		if rate < 0:
			rate = _find_float(report, ["watertight_rate"])
		if rate >= 0:
			_watertight_label.text = "Watertight: %.1f%%" % (rate * 100.0)
			var ok := rate >= 0.99
			_watertight_label.modulate = Color(0.55, 0.9, 0.55) if ok else Color(0.95, 0.7, 0.3)
		else:
			_watertight_label.text = "Watertight: n/a"
			_watertight_label.modulate = Color(0.8, 0.8, 0.8)


func _render_stages(report: Dictionary, snapshot: Dictionary) -> void:
	if _stage_list == null:
		return
	_stage_list.clear()
	var root := _stage_list.create_item()
	var stages := _collect_stage_rows(report, snapshot)
	for stage in stages:
		var item := _stage_list.create_item(root)
		item.set_text(0, String(stage.get("name", "?")))
		var status := String(stage.get("status", "unknown"))
		item.set_text(1, status)
		item.set_custom_color(1, _status_color(status))
		var runtime_ms := float(stage.get("runtime_ms", -1))
		item.set_text(2, "—" if runtime_ms < 0 else "%.1f ms" % runtime_ms)
		item.set_text(3, String(stage.get("hash_short", "")))


func _render_diagnostics(report: Dictionary, selector: Dictionary) -> void:
	if _diag_list == null:
		return
	_diag_list.clear()
	var root := _diag_list.create_item()
	var diagnostics := _collect_diagnostics(report, selector)
	var groups: Dictionary = {}
	for d in diagnostics:
		var sev := String(d.get("severity", "info")).to_lower()
		if not groups.has(sev):
			groups[sev] = []
		groups[sev].append(d)

	var severities: Array = ["critical", "error", "warning", "info"]
	for sev in severities:
		if not groups.has(sev):
			continue
		var group_item := _diag_list.create_item(root)
		group_item.set_text(0, "%s (%d)" % [sev.to_upper(), (groups[sev] as Array).size()])
		group_item.set_custom_color(0, _SEVERITY_COLORS.get(sev, Color.WHITE))
		group_item.collapsed = sev == "info"
		for d in groups[sev]:
			var child := _diag_list.create_item(group_item)
			child.set_text(0, String(d.get("code", "?")))
			child.set_text(1, String(d.get("message", "")))


func _collect_stage_rows(report: Dictionary, snapshot: Dictionary) -> Array:
	var rows: Array = []
	var stage_hashes: Variant = snapshot.get("stage_hashes", {})
	var stages_section: Variant = report.get("stages", null)
	var runtime_by_stage: Dictionary = {}
	var status_by_stage: Dictionary = {}

	if stages_section is Array:
		for entry in stages_section:
			if entry is Dictionary:
				var nm := String((entry as Dictionary).get("name", ""))
				if nm.is_empty():
					continue
				runtime_by_stage[nm] = float((entry as Dictionary).get("runtime_ms", -1.0))
				status_by_stage[nm] = String((entry as Dictionary).get("status", "ok"))
	elif stages_section is Dictionary:
		for nm in (stages_section as Dictionary).keys():
			var v: Variant = (stages_section as Dictionary)[nm]
			if v is Dictionary:
				runtime_by_stage[String(nm)] = float((v as Dictionary).get("runtime_ms", -1.0))
				status_by_stage[String(nm)] = String((v as Dictionary).get("status", "ok"))

	var ordered: Array = []
	if stage_hashes is Dictionary:
		for nm in (stage_hashes as Dictionary).keys():
			ordered.append(String(nm))
	if ordered.is_empty():
		ordered = runtime_by_stage.keys()

	for nm in ordered:
		var h := ""
		if stage_hashes is Dictionary:
			var val: Variant = (stage_hashes as Dictionary).get(nm, "")
			if val is String and (val as String).length() >= 10:
				h = (val as String).substr(0, 10)
		rows.append({
			"name": nm,
			"runtime_ms": runtime_by_stage.get(nm, -1.0),
			"status": status_by_stage.get(nm, "ok"),
			"hash_short": h,
		})
	return rows


func _collect_diagnostics(report: Dictionary, selector: Dictionary) -> Array:
	var out: Array = []
	var report_diags: Variant = report.get("diagnostics", [])
	if report_diags is Array:
		for d in report_diags:
			if d is Dictionary:
				out.append(d)
	var selector_diags: Variant = selector.get("diagnostics", [])
	if selector_diags is Array:
		for d in selector_diags:
			if d is Dictionary:
				out.append(d)
	return out


func _status_color(status: String) -> Color:
	match status.to_lower():
		"ok", "pass", "passed", "success":
			return Color(0.45, 0.85, 0.45)
		"warn", "warning":
			return Color(0.95, 0.8, 0.35)
		"fail", "failed", "error":
			return Color(0.95, 0.4, 0.4)
		"skip", "skipped":
			return Color(0.65, 0.65, 0.7)
		_:
			return Color(0.8, 0.8, 0.8)


func _find_float(data: Dictionary, keys: Array) -> float:
	var cursor: Variant = data
	for k in keys:
		if cursor is Dictionary and (cursor as Dictionary).has(k):
			cursor = (cursor as Dictionary)[k]
		else:
			return -1.0
	if cursor is float or cursor is int:
		return float(cursor)
	return -1.0


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		return {}
	var parsed: Variant = JSON.parse_string(text)
	if parsed is Dictionary:
		return parsed
	return {}
