extends Node
##
## Manual smoke test for the Lathe EditorImportPlugin (ENG-2).
##
## Expects `res://lathe_out/courier_drone/.lathe_snapshot.json` to exist
## and to have been imported by the addon. Prints the resolved Resource's
## metadata to the Output log.

const SNAPSHOT_RES := "res://lathe_out/courier_drone/.lathe_snapshot.json"


func _ready() -> void:
	if not ResourceLoader.exists(SNAPSHOT_RES):
		print("[smoke_import] no snapshot at %s — skip" % SNAPSHOT_RES)
		return
	var res: Resource = load(SNAPSHOT_RES)
	if res == null:
		push_error("[smoke_import] load() returned null for %s" % SNAPSHOT_RES)
		return
	print("[smoke_import] asset_id=%s certified=%s score=%s hash=%s" % [
		res.get_meta("asset_id", "?"),
		res.get_meta("certified", false),
		res.get_meta("score", 0.0),
		res.get_meta("snapshot_hash", "?"),
	])
	print("[smoke_import] glb_uri=%s" % res.get_meta("glb_uri", ""))
