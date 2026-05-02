# Semantic Asset Patching v1

Phase 16 adds deterministic semantic patching for asset-quality example fixtures. It is a fixture/evidence lane: patches update JSON evidence, regenerate deterministic proxy previews, and refresh certificates. It does not edit `.lth` source, raw meshes, GLBs, the stable shape handoff contract, or any external renderer output.

## Patch Schema

```json
{
  "schema_version": "lathe.asset_quality.semantic_patch.v1",
  "asset_id": "hero_sword",
  "preserve": ["construction_identity", "overall_silhouette"],
  "operations": [
    {
      "operation": "adjust_proportion",
      "target": "silhouette_plan.proportion_rules.guard_width_to_blade_width",
      "value": 4.1
    }
  ]
}
```

Supported operations:

- `modify_material`
- `adjust_proportion`
- `add_wear`
- `add_detail`
- `set_style`
- `set_platform_profile`

Supported evidence targets:

- `design_brief`
- `silhouette_plan`
- `construction_graph`
- `material_wear_graph`
- `shape_ir_v2`
- `family_grammar_coverage`

## Identity Preservation

The patch validator supports these preserve tokens:

- `construction_identity`
- `overall_silhouette`
- `blade.length`
- `guard.width`

If a patch changes a preserved value, the operation fails before the output fixture is written and returns `patch_conflicts_with_preserve`.

## Rejected Operation Classes

Phase 16 rejects:

- raw mesh, GLB, or source `.lth` edits;
- public language surface edits such as `profile`, `contract`, `critic`, `asset`, or `variant`;
- `lathe.shape.intent_mesh_handoff_v1` edits;
- invalid operation names or evidence targets;
- malformed field paths;
- non-serializable values.

## CLI

```bash
python -m lathe.cli asset-quality patch examples/asset_quality/hero_sword examples/asset_quality/hero_sword/patches/wider_blade.json --out .tmp_tests/hero_sword_patch_wider_blade
python -m lathe.cli asset-quality compare-before-after examples/asset_quality/hero_sword .tmp_tests/hero_sword_patch_wider_blade --out .tmp_tests/hero_sword_patch_wider_blade/comparison.json
```

The patch command copies the source fixture to `--out`, applies the patch, writes `patch_result.json`, regenerates deterministic proxy previews, recomputes `quality_certificate.json`, refreshes `quality_report.md`, and updates snapshot hashes.

The comparison command writes deterministic JSON with certificate deltas, art-direction deltas, semantic node/material/wear-mask deltas, preview SHA-256 changes, and flags for `improved`, `regressed`, `unchanged`, and `requires_human_review`.

## Truthfulness Limits

External renderer used: no.

Real high/low bake used: no.

Patched strict certificates can still fail on `real_bake_not_executed`. That is intentional until Lathe has a real bake lane.
