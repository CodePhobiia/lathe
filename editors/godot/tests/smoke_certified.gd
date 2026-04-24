extends Node
##
## Manual smoke for certified_state_indicator (ENG-6).
##
## Spawns the indicator as a child of a CenterContainer and calls refresh().
## Expects a prebuilt snapshot at res://lathe_out/courier_drone/. If present
## with certified=true, dot should render green and the label should include
## "certified true @ <score>". If absent, label shows "Lathe: no build".

const LatheCertifiedStateIndicator := preload("res://addons/lathe-addon/certified_state_indicator.gd")

var _indicator: Control


func _ready() -> void:
	_indicator = LatheCertifiedStateIndicator.new()
	_indicator.name = "SmokeCertifiedIndicator"
	var root := get_node("CenterRoot") as CenterContainer
	if root == null:
		root = CenterContainer.new()
		root.name = "CenterRoot"
		add_child(root)
	root.add_child(_indicator)
	_indicator.asset_focus_requested.connect(_on_focus)
	_indicator.refresh()
	var state: Dictionary = _indicator.get_current_state()
	print("[smoke_certified] asset=%s label=%s" % [state.get("asset_id", ""), state.get("label", "")])


func _on_focus(asset_id: String) -> void:
	print("[smoke_certified] asset_focus_requested %s" % asset_id)
