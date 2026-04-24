# Godot addon — manual smoke tests

Lightweight manual verification for the `lathe-addon` surfaces added in
ENG-2/3/4 (V0.2 E6). No GUT dependency: these are plain `.tscn` + `.gd`
scenes meant to be opened in the Godot editor.

## Prerequisites

- Godot 4.2+ (tested on 4.3).
- A Lathe build directory copied into `res://lathe_out/<asset>/` inside
  whichever Godot project you're testing against. You can produce one via:
  ```bash
  python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
  cp -R dist/courier_drone <godot-project>/lathe_out/
  ```

## Smoke 1 — Addon loads, dock appears

1. Enable **Lathe Integration** under **Project → Project Settings →
   Plugins**.
2. Expected: "Lathe" bottom-panel tab appears; "Lathe Build Trace" dock
   appears in the right docks.
3. The editor **Output** log shows no GDScript parse errors.

## Smoke 2 — Snapshot import

1. With the addon enabled, copy any build's `.lathe_snapshot.json` into
   the project (e.g. `res://lathe_out/courier_drone/.lathe_snapshot.json`).
2. Godot reimports the file via `LatheImportPlugin`.
3. Click the file in the FileSystem dock; the inspector shows a Resource
   with meta `asset_id`, `snapshot_hash`, `certified`, `score`,
   `threshold`, `glb_uri`.
4. Open `smoke_import.tscn` in this folder and press Play (F5). The
   script prints the resolved snapshot metadata.

## Smoke 3 — Thumbnail regen

1. With the watcher running, touch a build's `manifest.json` (re-save it
   or re-run `lathe build`). The watcher emits `asset_imported`.
2. Within a few seconds, `<build_dir>/.thumbnail.png` appears (256×256).
3. Re-importing an unchanged build does **not** produce a new thumbnail
   (mtime check).

## Smoke 4 — Build-trace viewer

1. Open the "Lathe Build Trace" dock.
2. The asset drop-down lists every `res://lathe_out/<asset>/` that has a
   `manifest.json`.
3. Picking an asset refreshes:
   - Kernel label + snapshot-hash suffix.
   - Watertight % (green if >= 99%).
   - Stage timeline (name / status color / runtime / short hash).
   - Diagnostics grouped by severity.
4. Clicking **Open HTML Report** opens `<build>/report.html` in the
   default browser (requires RPT-1 report.html output).

## Files in this folder

| File                  | Purpose                                                       |
|-----------------------|---------------------------------------------------------------|
| `smoke_import.tscn`   | Loads a snapshot Resource and prints its meta.                |
| `smoke_import.gd`     | Script driving the above.                                     |
| `README.md`           | You are here.                                                 |

These tests are intentionally manual. Automating them would require GUT
or headless Godot CI, both tracked as follow-up items under ENG-5/6.
