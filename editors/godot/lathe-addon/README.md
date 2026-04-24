# Lathe Integration (Godot addon, v0.1 MVP)

A minimal Godot 4.x `EditorPlugin` that watches a project-local directory for
new Lathe build outputs, imports the `.glb`, enriches the scene graph from the
Lathe manifest, and surfaces certification status in a bottom dock.

This is the **v0.1 in-repo MVP**. Real AssetLib submission, proper
`EditorImportPlugin` integration, build-trace viewing, and per-asset previews
are deferred — see BL-44.

## Install

Copy the entire folder into a Godot 4.x project:

```
<project>/addons/lathe-addon/
```

Then in **Project → Project Settings → Plugins**, enable **Lathe Integration**.

The demo project under `examples/godot_integration_demo/` is already wired up —
its `README.md` explains the 90-second loop.

## How it works

```
lathe build  →  dist/<asset>/ (manifest.json + .glb + build_report.json)
       └─ copy/symlink to res://lathe_out/<asset>/
                                   │
                                   ▼
            lathe_watcher.gd   (polls res://lathe_out/ every 2s)
                                   │
                                   ▼
            lathe_importer.gd  (loads .glb via GLTFDocument, enriches scene)
                                   │
                                   ├─ nodes named socket_*, anchor_* → Marker3D
                                   ├─ meshes named collision_*       → StaticBody3D + CollisionShape3D (convex)
                                   └─ manifest.lods[].lod_bias       → MeshInstance3D.lod_bias
                                   │
                                   ▼
            lathe_dock.gd      (bottom panel: PASS/FAIL + score + threshold)
```

## Manifest fields consumed

- `asset_id` — used as the saved scene filename.
- `outputs[].format == "glb"` → `outputs[].uri` — the mesh to import.
- `lods[].lod_bias` — applied to `MeshInstance3D` nodes in traversal order.

From the sibling `build_report.json`:

- `certified` (bool) — drives the PASS/FAIL pill in the dock.
- `certification.score` / `certification.threshold` — shown as numeric columns.

## Files

| File                 | Purpose                                                         |
|----------------------|-----------------------------------------------------------------|
| `plugin.cfg`         | Godot addon manifest.                                           |
| `plugin.gd`          | `EditorPlugin` entry — registers dock + watcher.                |
| `lathe_watcher.gd`   | Polls `res://lathe_out/` for manifest changes.                  |
| `lathe_importer.gd`  | Loads `.glb`, runs the socket/collision/LOD enrichment passes.  |
| `lathe_dock.gd`      | Bottom-panel status table.                                      |
| `icons/lathe.svg`    | 16×16 plugin icon.                                              |

## MVP gaps (tracked in BL-44)

- No native `EditorImportPlugin` — uses runtime `GLTFDocument` and saves a
  `.tscn`. Thumbnails/preview in the FileSystem dock won't regenerate until
  the user reloads.
- No AssetLib submission pipeline.
- No build-trace viewer (`trace_manifest.json` is listed in the manifest but
  not yet opened in-editor).
- Polling-based watcher; a real filesystem-watcher hook would remove the
  2s interval.
- Single-project demo only — no workspace/multi-project routing.
