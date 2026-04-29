# ADR 0013: Keep the Wonder Layer as a contract runtime boundary

- **Status:** Accepted
- **Date:** 2026-04-29
- **Ticket:** Phase 0 Wonder Layer boundary
- **Related:** ADR-0001, ADR-0009, ADR-0010, ADR-0012,
  `docs/wonder-readiness/status.md`, `wonder-tasks.md`

## Context

Project Wonder needs Lathe to represent persistent multi-object scenes, scene
memory, patches, render-inspection reports, curiosity anchors, and export
metadata. Lathe already has a public asset language and a frozen probabilistic
shape handoff contract. Expanding Wonder capability directly inside the asset
compiler core would risk mixing scene orchestration concerns with stable v0.1
asset source behavior.

## Decision

Lathe will keep the Wonder Layer as an additive contract runtime boundary:

- `lathe.core` and the existing parser/checker/build pipeline continue to own
  v0.1 asset source compatibility and the frozen asset-stage contracts.
- `lathe.wonder` owns JSON-first Wonder schemas, schema loading, contract
  validation, capability/status payloads, and LLM-facing repair diagnostics.
- `lathe.scene` owns Scene Graph semantic validation, scene planning, scene
  package helpers, world memory, scene patching, deterministic proxy build,
  render/export artifact contracts, and target-lane manifests.
- Project Wonder app code owns chat UX, users, accounts, payments, galleries,
  product memory, provider routing, and cloud orchestration.

The Wonder Layer may expose CLI and JSON contracts that Project Wonder can call,
but it must not require a Project Wonder app server or product database to
validate, build, patch, render, or export deterministic scene packages.

## Rationale

This split lets Lathe evolve from asset compiler toward scene runtime substrate
without turning the core language into a broad product platform. JSON-first
authoring keeps LLM output constrained while the `.lth` scene language remains
experimental. Deterministic proxy paths let validators and package contracts be
tested before final renderer/export backends are complete.

## Consequences

### Positive

- Existing v0.1 assets remain source-compatible while Wonder contracts grow.
- Scene runtime work can be validated with focused schemas and CLI commands.
- Project Wonder can integrate through files and machine-readable payloads
  before any app service exists.
- The alpha gate can distinguish deterministic proxy readiness from final
  Blender/USD/Roblox execution readiness.

### Negative / accepted risks

- Some Wonder concepts exist twice during the transition: as JSON contracts and
  as future `.lth` scene syntax design.
- The proxy path can prove contracts and packaging, but it cannot prove final
  visual quality by itself.
- Callers must read capability/status payloads instead of assuming all planned
  Wonder runtime lanes are available.

## Re-evaluation criteria

Re-open this decision if:

1. `.lth` scene syntax becomes stable public language surface.
2. The Wonder Layer requires changes to the frozen asset-stage contract.
3. Lathe intentionally absorbs Project Wonder product concerns into this
   repository.
