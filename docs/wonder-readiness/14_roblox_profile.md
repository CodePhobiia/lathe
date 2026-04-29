# Roblox Profile

Phase 24 adds a Roblox export lane as a contract, validator, and deterministic
asset-kit folder. It does not create Roblox Studio files or install a Studio
plugin. The lane records whether a Wonder Scene Graph is ready for a
Roblox-facing downstream exporter and can write local proxy artifacts for handoff.

## Contracts

The profile schema is `schema/roblox_profile.schema.json` and the manifest
schema is `schema/roblox_manifest.schema.json`.

The committed profile ID is `roblox_lowpoly`. It defines:

- units in `studs`
- scene and per-mesh triangle budgets
- texture count and texture resolution budgets
- mesh count and per-object mesh budgets
- collision requirements and allowed collision modes
- material slot budgets
- lower snake-case naming policy
- required pivot metadata
- snap-grid size and tolerance
- mobile score threshold and component weights

## Helpers

`lathe.scene.roblox.validate_roblox_profile(scene_graph, profile)` returns
deterministic diagnostics for a Scene Graph and profile.

`lathe.scene.roblox.build_roblox_manifest(scene_graph, profile)` returns a
`lathe.roblox_manifest.v1` payload. The manifest includes units, echoed budgets,
per-object readiness records, diagnostics, and component scores for triangle,
texture, mesh, collision, material, naming, pivot, snap-grid, and mobile
readiness.

`lathe.scene.roblox.export_roblox_asset_kit(scene_graph, out, profile=profile)`
writes the deterministic `lathe.stack.roblox_asset_kit_v1` folder bundle:

- `exports/roblox/roblox_manifest.json`
- `exports/roblox/glb/<scene_id>_roblox_asset_kit.glb`
- `exports/roblox/thumbnails/scene_thumbnail.png`
- `exports/roblox/thumbnails/object_contact_sheet.png`
- `exports/roblox/import_instructions.md`
- `exports/roblox/fbx/fbx_handoff.json`
- `reports/roblox_export_bundle.json`

The profile and manifest helpers are pure. The asset-kit export helper writes
only local deterministic proxy artifacts. It does not invoke Blender, call
Roblox APIs, write `.rbxmx`, upload assets, or claim Studio import success.

## Diagnostics

Current diagnostics cover:

- unsafe Roblox export names, based on the profile naming policy
- triangle, texture, mesh, and material budget overages when metadata is present
- missing required collision metadata for game-ready objects
- missing required pivot metadata
- unsupported collision or pivot modes
- transform positions that do not land on the profile snap grid

Budget metadata can come from future object metadata blocks. For current
Scene Graph v1 examples, the same primitive values may be carried in an
object's `state` map so the scene remains schema-valid.

## Example

`examples/wonder/abandoned_roblox_mall/` contains a compact Roblox-oriented
Wonder example with:

- `prompt.txt`
- `dream_brief.json`
- `scene_graph.json`
- `roblox_profile.json`
- `roblox_asset_kit.example.json`

Run the deterministic local export with:

```powershell
python -m lathe.cli scene roblox-export examples/wonder/abandoned_roblox_mall/scene_graph.json --profile examples/wonder/abandoned_roblox_mall/roblox_profile.json --out .tmp_tests/roblox_asset_kit/abandoned_roblox_mall
```

The example demonstrates the contract and proxy asset-kit lane without `.rbxmx`
output, Studio automation, asset uploads, or external viewer validation.
