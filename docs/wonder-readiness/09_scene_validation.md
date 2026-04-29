# Scene Validation

Scene validation extends Lathe's asset-quality posture to persistent Wonder
scenes. The current implementation is intentionally contract-first: it validates
Scene Graph JSON and produces machine-readable diagnostics before the full scene
build and render runtime exists.

## Current Validator Layers

`lathe.scene.validators.run_scene_validators` returns a
`lathe.scene_quality_report.v1` payload with a score, status, per-validator
reports, flattened diagnostics, and a human-readable summary.

`lathe scene check` and `lathe wonder check-scene-graph` also include a compact
`summary` object beside machine diagnostics. The summary preserves the JSON
contract while giving humans a status, counts, and one readable sentence for
semantic validation results.

The current validators are:

| Validator | Checks currently implemented |
|---|---|
| Scene Graph semantics | Duplicate IDs, invalid references, unsafe export/build paths, material bindings, camera/light targets, curiosity/hidden attachments, and affordance reveal targets. |
| Spatial | Objects below the floor, objects outside declared layout bounds, probable identical-position overlap, and non-positive scale. |
| Semantic | Minimum object count, missing focal role, and avoided style terms appearing in object metadata. |
| Style | Empty style bible fields and material-language drift. |
| Composition | Missing or invalid focal point and missing reveal camera. |
| Curiosity | Minimum curiosity anchor count and hidden facts that are not represented in hidden state. |
| Continuity | Memory events that reference missing scene entities. |
| Export | Missing export target, unsafe export path, missing material bindings for export, and optionally missing export artifacts. |
| Platform | Current preview object-count warning and initial Roblox-safe name check when the Roblox target is present. |

## Status Values

- `passed` means no validator produced diagnostics.
- `passed_with_warnings` means validators found non-blocking issues.
- `failed` means at least one diagnostic has error severity.

The score begins at 100. Errors and warnings subtract from that score. The
scoring policy is deliberately simple until the Wonder benchmark suite provides
enough data to tune thresholds.

## Human Summary

Each report includes `human_summary` for product-facing status surfaces:

- `headline` gives a compact score and status such as
  `Scene Quality: 88/100 (failed)`.
- `strengths` lists validators that passed without diagnostics.
- `needs_work` lists the first concrete diagnostics to address, or confirms
  that no blocking scene-quality issues were found.

## Boundary

These validators do not build geometry, run Blender, call vision models, or
repair scenes. They create the contract surface later phases can use for scene
builds, render inspection, patch proposals, and continuity checks.
