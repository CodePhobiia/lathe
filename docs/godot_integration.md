# Godot integration — user guide

This is the **user-facing** walkthrough for the Lathe Godot addon. For
architectural background (why Godot, how the watcher pipeline fits together,
failure modes) see `docs/integrations/godot.md`.

## What you get

Once the addon is enabled in your Godot 4.x project:

1. **Drag-drop import** of Lathe build snapshots — the `.lathe_snapshot.json`
   sidecar reimports as a typed Godot `Resource` carrying certification status,
   kernel identity, and per-stage hashes.
2. **Auto-regenerated thumbnails** — a `.thumbnail.png` is written next to each
   imported asset whenever the build's manifest changes, so the FileSystem dock
   stays visually fresh.
3. **Build-trace viewer dock** — stage timeline, diagnostics (grouped by
   severity), watertightness %, and one-click "Open HTML Report" for any build
   under `res://lathe_out/`.

The existing MVP surfaces (the `res://lathe_out/` watcher, socket / collision /
LOD enrichment, the PASS/FAIL bottom dock) keep working unchanged.

## Installing the addon

1. Copy `editors/godot/lathe-addon/` from this repo to
   `<your-godot-project>/addons/lathe-addon/`.
2. Open the Godot editor.
3. **Project → Project Settings → Plugins → Lathe Integration → Enable**.

You should see:

- A "Lathe" tab in the bottom panel (PASS/FAIL table).
- A "Lathe Build Trace" tab in the right-side docks.
- Godot's FileSystem dock now recognizes `.lathe_snapshot.json` as an
  importable resource.

## Drag-drop import (ENG-2)

Whenever you copy a Lathe build directory into `res://lathe_out/<asset>/`,
Godot's editor auto-imports the `.lathe_snapshot.json` file:

- Recognized as type **Lathe Build Snapshot**.
- Imported to a lightweight `Resource` whose metadata includes:
  `asset_id`, `snapshot_hash`, `lathe_version`, `stage_hashes`,
  `certified` (bool), `score`, `threshold`, and `glb_uri` (the build's
  primary `.glb` path resolved from `manifest.json`).
- Available at runtime via `load("res://lathe_out/<asset>/.lathe_snapshot.json")`.

Full `.glb` drag-drop continues to use Godot's stock glTF importer; the
scene enrichment (Position3D / Marker3D sockets, StaticBody3D collision,
LOD bias) is then layered on by `lathe_importer.gd`.

## Thumbnail auto-regen (ENG-3)

`thumbnail_regen.gd` listens for `asset_imported` signals from the watcher.
When a build's manifest is newer than the cached `.thumbnail.png`, it:

1. Loads the saved `.tscn` into an offscreen `SubViewport` (256x256).
2. Frames the scene's combined AABB with a perspective camera + single
   directional light.
3. Renders one frame, reads the texture back as an `Image`, and saves to
   `<build_dir>/.thumbnail.png`.
4. Kicks `EditorInterface.get_resource_filesystem().scan()` so the editor
   picks up the new image without a reload.

Thumbnails are skipped when their mtime is newer than the manifest — so
re-imports of unchanged builds are cheap.

## Build-trace viewer (ENG-4)

The "Lathe Build Trace" dock reads three files from the selected build
directory:

| File                        | Source                     | Purpose                             |
|-----------------------------|----------------------------|-------------------------------------|
| `build_report.json`         | compiler (`lathe build`)   | Stage runtimes, diagnostics, kernel |
| `selector_manifest.json`    | REF-5 writer               | Additional diagnostics              |
| `.lathe_snapshot.json`      | RPT-4 snapshot writer      | Per-stage hashes + schema version   |

The dock renders:

- **Header**: kernel name + short snapshot hash; watertightness % (green
  ≥ 99%, amber otherwise).
- **Stage timeline**: one row per stage (`refs`, `intent`, `shape`,
  `topology`, …), with a status color and runtime. A short hash from
  `stage_hashes` is shown as the fourth column to help reproducibility
  audits.
- **Diagnostics**: grouped by severity (critical / error / warning / info);
  info is collapsed by default. Each row shows the diagnostic code +
  human message.
- **Open HTML Report** button: shells out to the default browser with
  `<build>/report.html` (requires RPT-1 `report.html` output).

Use the **Asset** drop-down to switch between builds under
`res://lathe_out/`; **Refresh** rescans the directory if you copied in a
new asset while the editor was open.

## Troubleshooting

- **Dock shows nothing.** Verify `res://lathe_out/<asset>/manifest.json`
  exists and is well-formed JSON. The watcher polls every 2 seconds; give
  it a moment after copying files in.
- **"Open HTML Report" warns about missing `report.html`.** Generate one
  with the RPT-1 reporter (`python -m lathe.cli report <build-dir>`).
- **Thumbnail never appears.** Check the Output log for `[Lathe]
  thumbnail …` warnings. A common cause is the `.tscn` failing to load
  because the `.glb` it references was moved or renamed.
- **Snapshot import produces an empty Resource.** The
  `.lathe_snapshot.json` is malformed, zero-length, or the file perms
  blocked reading. Verify with `python -m json.tool <path>`.

## Files reference

```
editors/godot/lathe-addon/
├── plugin.cfg
├── plugin.gd                   # registers dock, watcher, importer, trace viewer, thumb regen
├── editor_import_plugin.gd     # ENG-2: native EditorImportPlugin for .lathe_snapshot.json
├── thumbnail_regen.gd          # ENG-3: render-to-PNG thumbnail regenerator
├── build_trace_viewer.gd       # ENG-4: dock logic
├── build_trace_viewer.tscn     # ENG-4: dock scene layout
├── lathe_dock.gd               # (unchanged) PASS/FAIL bottom panel
├── lathe_importer.gd           # (unchanged) scene enrichment on loaded .glb
├── lathe_watcher.gd            # (unchanged) manifest.json poller
├── README.md
└── icons/lathe.svg

editors/godot/tests/
├── README.md                   # manual verification steps
├── smoke_import.tscn           # smoke scene for snapshot import
└── smoke_import.gd             # prints resolved snapshot metadata
```

## Scope — still out

- No AssetLib submission (tracked as BL-44 / GTM-5).
- `.glb` **ingest** still uses Godot's stock importer plus post-load
  enrichment. Typed Position3D sockets at *import-time* (instead of
  post-load) is the next tier for ENG-2.
- Per-node certified-state badges (ENG-6) are planned but not in this
  milestone.
- No headless / GUT-backed automated tests yet (tracked with ENG-5/6).
