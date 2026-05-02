# Art Direction IR v1

Phase 14C adds explicit `art_direction.json` fixture evidence plus the normalized internal `lathe.asset_quality.art_direction_ir.v1` shape. Both describe design intent before quality planning. They do not add public `.lth` syntax and do not mutate geometry.

## Purpose

The IR gives Lathe a shared art-direction vocabulary across object families:

- style intent;
- visual hierarchy;
- silhouette goals;
- proportion policy;
- material contrast policy;
- motif language;
- surface storytelling;
- platform target;
- forbidden visual failure modes.

## Inputs

The IR is built from either:

- explicit `art_direction.json` evidence; or
- `design_brief.json`, family metadata, and optional reference-board evidence.

Runtime validation can also derive it from the existing validate-stage `design_brief` payload.

## Required Fixture Fields

Quality-engine fixtures must include:

- `schema_version`
- `asset_id`
- `object_family`
- `style_intent`
- `visual_hierarchy`
- `silhouette`
- `materials`
- `motifs`
- `surface_story`
- `platform`
- `forbidden_failure_modes`

Malformed or missing required fields are certification errors for `quality_engine` fixtures.

## Object Families

The broad family classifier is deliberately general:

- `weapon`
- `container`
- `machine`
- `furniture`
- `architecture`
- `environment_piece`
- `prop`

The classifier uses family, style, keywords, and required features. It is not a sword generator or a family-specific mesh recipe.

## Truthfulness Limits

The IR is planning evidence only. It does not claim external rendering, real high/low baking, engine export, or production-game certification.
