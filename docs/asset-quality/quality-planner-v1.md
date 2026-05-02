# Quality Planner v1

Phase 14C adds `lathe.asset_quality.quality_plan.v1`, a deterministic planning layer that turns art direction and semantic evidence into family-agnostic quality targets.

## Inputs

- `design_brief.json`
- `family_grammar_coverage.json`
- `construction_graph.json`
- `material_wear_graph.json`
- optional reference/style-pack metadata

## Output

`quality_plan.json` records:

- object family;
- art-direction IR;
- `source_art_direction` and `source_family_metadata`;
- `primary_secondary_tertiary` visual reads;
- silhouette requirements;
- proportion requirements;
- `material_requirements`;
- `detail_requirements`;
- `motif_requirements`;
- `surface_story_requirements`;
- platform constraints;
- universal quality metrics;
- semantic critique repair suggestions.

For compatibility with earlier Phase 14C and Phase 16 evidence, the planner also keeps alias fields such as `art_direction_ir`, `visual_hierarchy`, `material_separation_requirements`, `detail_density_zones`, `motif_language`, and `surface_story`.

## Universal Scorecard

The planner delegates scoring to `lathe.asset_quality.universal_quality`. The planner and certificate use these dimensions:

- `silhouette_strength`
- `proportion_intent`
- `material_contrast`
- `detail_hierarchy`
- `motif_coherence`
- `surface_storytelling`
- `functional_readability`
- `style_consistency`
- `procedural_noise_penalty`

For `procedural_noise_penalty`, the raw metric is a penalty where lower is better. Certificate scoring inverts it so higher category score still means better quality.

## Validate-Stage Integration

The planner is registered as a zero-weight additive validator named `quality_plan`. It publishes `runtime["quality_plan"]` and appears in validate-stage reports without changing build certification thresholds or public language syntax.

## Truthfulness Limits

The plan is semantic evidence. It does not prove renderer execution, real high/low baking, engine export, or production-game readiness.
