# Lathe integration demo (Godot 4.x)

Minimal Godot project that demonstrates the Lathe editor addon: run a single
`lathe build` and see the resulting asset appear in-scene with sockets and
collision wired up.

## Layout

```
examples/godot_integration_demo/
├── project.godot           # Godot 4.x project descriptor
├── lathe_out/              # Watched by the addon (empty — populated by `lathe build`)
├── scenes/
│   ├── main.tscn           # Camera + light + AssetPlaceholder
│   └── main.gd             # Loads the most recent imported .tscn
├── addons/lathe-addon/     # NOT in this tree — see "Install the addon" below
└── README.md
```

## Install the addon

Git symlinks don't round-trip on Windows checkouts, so the addon is **not**
committed into this demo's `addons/` subtree. To run the demo:

### Option 1 — copy (portable)

```bash
cp -r editors/godot/lathe-addon examples/godot_integration_demo/addons/lathe-addon
```

### Option 2 — symlink (unix/WSL)

```bash
ln -s ../../../editors/godot/lathe-addon examples/godot_integration_demo/addons/lathe-addon
```

### Option 3 — symlink (Windows, admin PowerShell)

```powershell
New-Item -ItemType SymbolicLink `
  -Path examples\godot_integration_demo\addons\lathe-addon `
  -Target ..\..\..\editors\godot\lathe-addon
```

Then open the project in Godot 4.2+ and enable **Lathe Integration** under
**Project → Project Settings → Plugins**.

## 90-second demo loop

1. From the repo root, build an asset into this project's `lathe_out/`:
   ```bash
   python -m lathe.cli build examples/courier_drone.lth courier_drone \
       --out examples/godot_integration_demo/lathe_out
   ```
2. Open the project in Godot 4.x.
3. Within ~2 seconds, the **Lathe** bottom dock shows the asset with its
   certification status (PASS/FAIL, score, threshold).
4. Press F5 (or the Play button). `main.gd` finds the most recent imported
   scene and instances it under `AssetPlaceholder`.
5. You should see the crate with:
   - `Marker3D` nodes at every `socket_*` / `anchor_*` position (orientation
     preserved).
   - `StaticBody3D` + `CollisionShape3D` for each `collision_*` mesh.
   - LOD bias values applied to mesh instances per the manifest.

## Troubleshooting

- **Dock empty.** Make sure `lathe_out/<asset>/manifest.json` exists on disk
  and the plugin is enabled. Check the Output panel for `[Lathe] imported ...`.
- **No scene appears at runtime.** `main.gd` prints the expected path; if it
  says "no ... .tscn found yet", the watcher hasn't run or the import failed.
- **Godot complains about the plugin.** Confirm the addon ended up at
  `addons/lathe-addon/plugin.cfg`, not at
  `addons/editors/godot/lathe-addon/plugin.cfg`.

## See also

- `docs/integrations/godot.md` — architecture & rationale.
- `editors/godot/lathe-addon/README.md` — addon-level README.
