# ADR 0010: Use experimental v0.3 scene source syntax for Wonder scenes

- **Status:** Proposed
- **Date:** 2026-04-28
- **Ticket:** `wonder-tasks.md` Phase 6A
- **Related:** ADR-0009, `docs/wonder-readiness/06_scene_language_design.md`,
  `schema/scene_graph.schema.json`

## Context

Project Wonder needs a human-editable and model-authorable source surface for
multi-object scenes. Lathe already has a stable asset-oriented `.lth` language,
and the Wonder work has started with JSON contracts so scene identity,
validation, and artifacts can be defined before parser changes.

Changing `.lth` too broadly would risk destabilizing v0.1 asset source,
especially `profile`, `contract`, `critic`, `asset`, `variant`, and build-stage
semantics. Waiting for a complete scene runtime before naming the source shape
would leave the parser implementation phase without a clear compatibility target.

## Decision

Adopt minimal additive `.lth` scene syntax as an experimental v0.3 design that
lowers to `lathe.scene_graph.v1`, while preserving all existing v0.1 asset
source compatibility and keeping the Scene Graph JSON contract as the durable
truth model until the scene parser/runtime is implemented and validated.

## Rationale

This decision gives Phase 6B a bounded implementation target without pretending
the scene runtime exists today. It also keeps the JSON-first Wonder contract
strategy intact: Project Wonder can continue to exchange Dream Brief, Scene
Graph, Scene Patch, and Render Inspection JSON with Lathe while scene source
becomes an authoring convenience rather than a product boundary.

The additive shape keeps new keywords scene-local wherever possible. `scene`
becomes a top-level declaration only for scene-aware source, while `region`,
`object`, `relationship`, `camera`, `light`, `style`, and `export` are scoped
inside a scene declaration. Existing asset declarations do not gain scene
behavior.

## Consequences

### Positive

- Phase 6B has a concrete syntax target with explicit Scene Graph field mapping.
- v0.1 asset source compatibility remains the hard boundary for parser work.
- The Project Wonder app stays outside Lathe core; it consumes contracts and
  artifacts rather than chat or account features living in Lathe.
- JSON remains the source of durable scene truth while `.lth` scene syntax is
  experimental.

### Negative / accepted risks

- v0.3 scene source will not cover every Scene Graph field. Some data remains
  JSON or runtime metadata until validators and package flows mature.
- Scene source and Scene Graph JSON will need roundtrip tests before the syntax
  can become more than an authoring surface.
- The word `object` becomes scene-local syntax. The implementation must prove
  that it does not interfere with existing asset identifiers or declarations.

## Alternatives considered

- **Keep scenes JSON-only through v0.3.** Rejected because human-editable scene
  review and source roundtrips are a stated Milestone C exit criterion.
- **Add full scene syntax in one pass.** Rejected because branches, gameplay
  metadata, provenance, sockets, snap points, and advanced layout constraints
  do not yet have validated runtime contracts.
- **Hide scene syntax behind a general feature flag.** Rejected because the
  compatibility boundary should be architectural and command/surface-specific,
  not a global switch that can silently change asset behavior.
- **Fold scenes into existing `asset` declarations.** Rejected because scenes
  need stable multi-object identity, relationships, cameras, lights, exports,
  memory, and package history that are broader than a single asset build target.

## Re-evaluation criteria

Re-open this decision if:

1. Scene Graph v1 changes in a way that invalidates the field mapping in
   `docs/wonder-readiness/06_scene_language_design.md`.
2. Parser implementation proves that `scene` or scene-local keywords cannot be
   added without breaking existing asset source.
3. Project Wonder requires app-owned chat, user, account, gallery, or payment
   concerns to be represented inside Lathe source.
4. The first Scene Graph to source to Scene Graph roundtrip cannot preserve
   stable IDs without adding broader syntax than this ADR permits.
