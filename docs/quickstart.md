# Quickstart

Three commands to go from fresh checkout to a certified asset package.

## 1. Bootstrap

From the repo root, create a `.venv` and install Lathe editable with dev + export extras:

=== "PowerShell"

    ```powershell
    scripts/bootstrap_local.ps1 -Dev -Export
    ```

=== "bash"

    ```bash
    scripts/bootstrap_local.sh --dev --export
    ```

The expected interpreter after bootstrap is `.venv/Scripts/python.exe` (Windows-first). On POSIX it lands at `.venv/bin/python`. See [Local golden path](local_golden_path.md) for the full first-run story.

## 2. Verify the environment

```powershell
.\.venv\Scripts\python.exe -m lathe.cli doctor
```

`doctor` reports the editable install, Blender availability, xatlas availability, and whether any learned providers (Hunyuan, VGGT) are reachable. Without a `--runtime-config`, the compiler takes a conservative path and explicitly falls back where adapters are unavailable — this is expected for smoke-test ergonomics.

## 3. Build your first asset

Build the reference `courier_drone` asset into `dist/`:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
```

The compiler runs the full stage pipeline (`refs → intent → shape → topology → uv → surface → rig → interfaces → physics → optimize → validate → package`) and writes a certified package:

```text
dist/
└── courier_drone/
    ├── courier_drone.usd
    ├── courier_drone.glb
    ├── manifest.json          # what was produced, with hashes
    ├── trace.json             # what ran at each stage, including attempted vs actual providers
    ├── previews/
    │   ├── turntable.png
    │   ├── wireframe.png
    │   ├── material_ids.png
    │   ├── uv_layout.png
    │   ├── collision.png
    │   └── lod_sheet.png
    └── stages/
        ├── shape/
        ├── topology/
        ├── uv/
        ├── surface/
        └── validate/
```

The exact files depend on which adapters were available — `trace.json` is the authoritative record. `--out` can point anywhere; the `dist/` name is only a convention. Transient output directories (`dist_*`, `tmp_*`, `warm_*`) are ignored by the repo.

## What just happened

- `examples/courier_drone.lth` declared *what* the asset is (parts, materials, interactions), *how* to build it (stage configs), and *what counts as passing* (critic + threshold + repair policy).
- The compiler normalized, resolved, checked, planned, executed, validated, and packaged the result.
- Because you did not pass `--runtime-config`, the shape stage used the deterministic `lathe.provider.shape.reference_conditioned_v1` provider. Topology/UV fell back to reference paths if Blender or xatlas were unavailable.

## Next

- [Author your first `.lth` asset](tutorial/first_asset.md) — ~15 min walkthrough, builds a bookshelf from scratch.
- [Reconstruct from reference views](tutorial/second_asset_reconstruct.md) — ~20 min, compares `generate` vs `reconstruct` flows.
- [Deep dive reading order](tutorial/deep_dive.md) — map of specs and manifestos, in the order that builds mental model fastest.
- [Local golden path](local_golden_path.md) — same loop with real Hunyuan / VGGT runtime configs.
