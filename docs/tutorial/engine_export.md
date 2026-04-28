# Engine Export Workflow

**Time:** about 15 minutes. **Prerequisite:** a passing build from
[Fallback provider workflow](fallback_provider.md).

This tutorial verifies that a Lathe build produces the sidecars an engine import
flow needs.

## 1. Build the engine-oriented gallery asset

```bash
python -m lathe.cli build examples/console_terminal_mobile_adapt.lth console_terminal_mobile --out dist_engine
```

The asset is small enough for a quick local check and emits mobile-oriented LOD
and collision metadata.

## 2. Inspect the package manifest

Open:

- `dist_engine/console_terminal_mobile/stages/package/package_manifest.json`
- `dist_engine/console_terminal_mobile/console_terminal_mobile.lathe_for_godot.json`
- `dist_engine/console_terminal_mobile/console_terminal_mobile.lathe_for_unity.yaml`
- `dist_engine/console_terminal_mobile/console_terminal_mobile.lathe_for_unreal.json`

The package manifest lists the `.glb`, `.usda`, LOD, and collision outputs. The
engine manifests point to those package outputs without absolute local paths.

## 3. Check previews and validation

Review:

- `dist_engine/console_terminal_mobile/stages/package/previews/turntable.png`
- `dist_engine/console_terminal_mobile/stages/package/previews/lod_sheet.png`
- `dist_engine/console_terminal_mobile/stages/validate/report.json`

For release evidence, pair this with the Godot addon walkthrough in
[`docs/godot_integration.md`](../godot_integration.md) or the engine-specific
manifests your downstream tool consumes.
