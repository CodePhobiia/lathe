# Godot integration (v0.1 MVP)

> **Status.** In-repo scaffold. The addon works locally against a Godot 4.x
> project; AssetLib submission is **not** part of this milestone and is tracked
> as BL-44.

## Why Godot is the wedge engine

Plan 09 Phase 2 (amended) picks Godot ahead of Unity/Unreal for the first
engine-side integration because:

- **Permissive licensing + open plugin API** — no per-seat cost or NDA on the
  editor; the `EditorPlugin` surface is stable across the 4.x line and
  documented.
- **GDScript auth-time cost is low** — the MVP is six GDScript files. Unity
  (C# + asset processor) and Unreal (C++ editor module + UAT) both require
  multi-day scaffolds before a first round-trip.
- **glTF is the native interchange format** — Godot ships a first-party
  `GLTFDocument`. Lathe's packaging stack emits `.glb` + USD; the `.glb` path
  loads without conversion.
- **Indie/student distribution matches the Lathe early-adopter profile** —
  Persona C (solo hobbyist / small studio, per `docs/personas.md`) overlaps
  heavily with Godot AssetLib users.

Unity and Unreal remain on the roadmap; the pipeline contract (manifest.json +
`.glb` + `build_report.json`) was chosen to keep those ports thin.

## How the addon works

The addon lives in `editors/godot/lathe-addon/` in this repo. When installed
into a Godot project at `res://addons/lathe-addon/`:

1. **`plugin.gd`** registers a bottom-dock control (`lathe_dock.gd`) and a
   `Node`-based watcher (`lathe_watcher.gd`) when the editor starts.
2. **`lathe_watcher.gd`** polls `res://lathe_out/` every 2 seconds. For each
   child directory that contains a `manifest.json`, it tracks the file's
   modified time; when it changes, it hands the manifest path to the importer.
3. **`lathe_importer.gd`** reads `manifest.json`, resolves the `.glb` entry in
   `outputs[]`, and loads it via `GLTFDocument.append_from_file`. It then
   performs three enrichment passes on the loaded scene:
   - Nodes whose names begin with `socket_` or `anchor_` become `Marker3D`
     (transform preserved).
   - `MeshInstance3D` nodes named `collision_*` are converted to a
     `StaticBody3D` with a `CollisionShape3D` holding a convex hull of the
     source mesh.
   - `MeshInstance3D` nodes receive `lod_bias` values from `manifest.lods[]`
     (traversal order).
   It then packs and saves a `.tscn` alongside the `.glb` so the scene can be
   dropped into other scenes as a `PackedScene`.
4. The importer emits a record (`certified`, `score`, `threshold`,
   `scene_path`) which the dock renders as a PASS/FAIL table.

Certification status is read from the sibling `build_report.json`
(`certification.score` / `certification.threshold` / top-level `certified`),
matching the fields produced by `lathe.executor` after the `validate` stage.

## Installation

1. Build a Lathe asset and make sure the manifest is on disk:
   ```bash
   python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
   ```
2. In your Godot 4.x project, copy (or symlink) the addon folder:
   ```
   <godot-project>/addons/lathe-addon/       ← editors/godot/lathe-addon/
   ```
3. In Godot, open **Project → Project Settings → Plugins** and tick
   **Lathe Integration**.
4. Point Lathe at the project's `lathe_out/` folder, e.g.:
   ```bash
   python -m lathe.cli build examples/courier_drone.lth courier_drone \
       --out <godot-project>/lathe_out
   ```
   The dock should update within ~2 seconds of the build completing.

The demo project under `examples/godot_integration_demo/` has the directory
layout and a minimal scene already prepared.

## MVP gaps

These are known limits; do not file them as bugs. They are tracked on BL-44.

- **No AssetLib submission.** `plugin.cfg` is AssetLib-shaped, but we have not
  produced the release zip, screenshots, or required license metadata.
- **No build-trace opening.** `manifest.trace_path` (and the
  `trace_manifest.json` it points at) are not yet rendered in-editor. A real
  build-trace view needs a tree widget the MVP deliberately skips.
- **No per-asset preview/thumbnail.** The addon saves a `.tscn` but doesn't
  pre-render a 3D thumbnail for the FileSystem dock.
- **Polling watcher.** The 2s polling loop is good enough for the demo;
  a proper filesystem hook is out of scope here.
- **Runtime GLTF loader** (`GLTFDocument.append_from_file`) rather than a real
  `EditorImportPlugin`. Consequence: Lathe imports do not participate in
  Godot's standard `.import` pipeline, so re-importing through the FileSystem
  dock ignores the Lathe enrichment passes. AssetLib-quality imports require
  promoting this to `EditorImportPlugin`.
- **Single-project pathing.** The watcher is hard-coded to
  `res://lathe_out/`. Multi-project routing (one Lathe repo → N engines) is
  future work.

## See also

- `editors/godot/lathe-addon/README.md` — addon-level README.
- `examples/godot_integration_demo/README.md` — 90-second demo loop.
- Plan 09 Phase 2 — the amendment that picked Godot as the wedge engine.
- BL-44 — full-scope Godot integration ticket (AssetLib submission, real
  EditorImportPlugin, trace viewer).
