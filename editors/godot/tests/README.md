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

## Smoke 4.5 — fsnotify watcher (ENG-5)

1. Open `smoke_fsnotify.tscn` and press Play (F6 for this scene).
2. In a separate shell, re-save a sidecar inside any Lathe build:
   ```bash
   touch <godot-project>/lathe_out/courier_drone/.lathe_snapshot.json
   # or: touch .../selector_manifest.json
   ```
3. Within ~2 seconds the Output log prints:
   ```
   [smoke_fsnotify] build_updated asset=courier_drone snapshot=<10-char>
   ```
4. Toggle **Editor Settings → Lathe → fsnotify enabled = off** and touch
   the sidecar again — no new `build_updated` line should appear.

## Smoke 4.6 — Certified-state indicator (ENG-6)

1. Ensure `res://lathe_out/courier_drone/` contains a recent build with a
   populated `build_report.json` (`certified: true`, score ≈ 0.88 for
   the reference courier_drone fixture).
2. Open `smoke_certified.tscn` and press Play (F6).
3. The centered widget should render a **green** dot and a label like:
   ```
   courier_drone: certified true @ 0.880
   ```
4. Output log prints `[smoke_certified] asset=courier_drone label=...`.
5. Click **Open**; `[smoke_certified] asset_focus_requested courier_drone`
   appears in the log (in the editor at runtime, this routes to
   `build_trace_viewer.focus_asset`).
6. Negative path: rename `.lathe_snapshot.json` temporarily — the
   indicator should fall back to a **gray** dot and `Lathe: no build`.

## Smoke 5 — Build-trace viewer

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

| File                    | Purpose                                                     |
|-------------------------|-------------------------------------------------------------|
| `smoke_import.tscn`     | Loads a snapshot Resource and prints its meta (ENG-2).      |
| `smoke_import.gd`       | Script driving the above.                                   |
| `smoke_fsnotify.tscn`   | Instances fsnotify watcher, logs each `build_updated` (ENG-5). |
| `smoke_fsnotify.gd`     | Script driving the above.                                   |
| `smoke_certified.tscn`  | Instances certified-state indicator and logs its state (ENG-6). |
| `smoke_certified.gd`    | Script driving the above.                                   |
| `README.md`             | You are here.                                               |

These tests are intentionally manual. Automating them would require GUT
or headless Godot CI; both remain follow-up items.
