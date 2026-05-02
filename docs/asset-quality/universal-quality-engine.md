# Universal Quality Engine

Phase 14C turns the hero-sword quality work into a reusable art-direction quality layer. The sword remains a benchmark concept, not a hardcoded generator.

## What Changed

Lathe now has a deterministic quality stack:

```text
design brief
  -> art_direction.json
  -> art direction IR
  -> quality plan
  -> universal quality scorecard
  -> semantic repair suggestions
  -> certificate/report evidence
```

The validate stage publishes `quality_plan` as additive evidence. Material/wear and critique code can read it when present and continue using prior behavior when it is absent.

## Proof Fixtures

Four proof fixtures live under `examples/asset_quality/quality_engine/`:

- `fantasy_weapon`
- `sci_fi_crate`
- `roblox_tycoon_machine`
- `environment_shop_counter`

Each fixture includes semantic evidence, deterministic proxy previews, a quality plan, a certificate, a report, and snapshots.

## Certification

Certificates can include `universal_quality`, with per-dimension scores, diagnostics, repair suggestions, warning gates, and strict gates. Overall strict certification remains blocked when truthfulness blockers are present, especially `real_bake_not_executed`.

Quality-engine fixtures require `design_brief.json`, `art_direction.json`, `quality_plan.json`, `semantic_critique.example.json`, semantic construction/material/high-low/preview evidence, deterministic proxy previews, certificates, reports, and snapshot hashes.

## Non-Claims

Phase 14C does not:

- add public `.lth` syntax;
- edit raw meshes or GLBs;
- change `lathe.shape.intent_mesh_handoff_v1`;
- run Blender, Roblox, USD viewers, or external renderers;
- run a real high/low bake;
- certify assets for production-game use.
