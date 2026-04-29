# ADR 0011: Add a contract-first Roblox export lane

- **Status:** Proposed
- **Date:** 2026-04-28
- **Ticket:** Phase 24 Roblox Profile And Export Lane
- **Related:** ADR-0009, `docs/wonder-readiness/14_roblox_profile.md`,
  `schema/roblox_profile.schema.json`, `schema/roblox_manifest.schema.json`

## Context

Wonder scenes need a Roblox-facing readiness surface before Lathe owns any
Roblox Studio integration. The existing Scene Graph contract already carries
stable object identity, transforms, materials, exports, and primitive state
metadata. The missing boundary is a target profile that can say whether a scene
is safe for Roblox-style low-poly, mobile-friendly export.

Jumping straight to Studio automation would mix two concerns: validating the
scene contract and authoring a Roblox place/model file. Lathe needs the first
concern now so downstream work can make explicit decisions about names, units,
budgets, collision, pivots, grid placement, and mobile readiness.

## Decision

Add a contract-first Roblox lane composed of:

- `schema/roblox_profile.schema.json`
- `schema/roblox_manifest.schema.json`
- `lathe.scene.roblox.validate_roblox_profile(scene_graph, profile)`
- `lathe.scene.roblox.build_roblox_manifest(scene_graph, profile)`
- `lathe.scene.roblox.export_roblox_asset_kit(scene_graph, out, profile=profile)`
- a text-only Wonder example at
  `examples/wonder/abandoned_roblox_mall/`

The profile ID is `roblox_lowpoly`. It uses `studs` as the unit contract and
defines budgets and rules for triangles, textures, meshes, collision,
materials, naming, pivots, snap-grid placement, and mobile score thresholds.

The manifest records per-object readiness and scene-level scores. It is a JSON
artifact that downstream exporters can consume without depending on Lathe's
Python implementation details.

The deterministic asset-kit stack ID is `lathe.stack.roblox_asset_kit_v1`. It
writes a local proxy GLB, the Roblox manifest, preview thumbnails, import
instructions, and an FBX handoff manifest under `exports/roblox/`. The FBX lane
is represented as a real handoff artifact, not a generated `.fbx` file, until a
downstream Blender or Studio conversion integration owns that format.

## Deferred Scope

Native `.fbx` generation, `.rbxmx` generation, Roblox Studio plugin work, and
asset upload automation are outside this decision. Those integrations should be
designed after the JSON manifest proves stable enough to act as their input
contract.

## Rationale

The contract-first lane gives Phase 24 useful validation without binding Lathe
to Roblox Studio APIs, plugin packaging, asset upload semantics, or file-format
edge cases before the readiness rules are settled.

It also preserves existing Wonder boundaries. Scene Graph JSON remains the
source of scene identity, while the Roblox manifest becomes a target-specific
derived artifact with deterministic diagnostics and scores.

## Consequences

### Positive

- Roblox readiness can be tested without external services or Studio.
- The profile and manifest are schema-backed public artifacts.
- Diagnostics are deterministic and can be surfaced by a later CLI or UI.
- Downstream exporters get an explicit input contract for units, budgets,
  names, collision, pivots, snap-grid placement, and mobile score.

### Negative / accepted risks

- The manifest cannot prove that a Roblox place/model import succeeds.
- Some budget checks only run when upstream stages provide object metrics.
- The current profile is intentionally narrow: it targets low-poly,
  mobile-friendly Roblox scenes rather than every possible Roblox workflow.

## Alternatives considered

- **Generate `.rbxmx` immediately.** Rejected because Studio import semantics
  should consume a validated manifest rather than define the readiness contract.
- **Build a Studio plugin first.** Rejected because plugin UX, upload flows, and
  authentication are separate product surfaces from Lathe's scene contracts.
- **Fold Roblox checks into generic scene validators only.** Rejected because
  Roblox needs target-specific budgets, units, collision, pivots, and mobile
  score fields that should be versioned independently.

## Re-evaluation criteria

Re-open this decision if:

1. A downstream Roblox exporter cannot consume `lathe.roblox_manifest.v1`
   without adding non-derivable fields.
2. The low-poly profile rules conflict with a required Roblox production
   workflow.
3. Lathe starts owning Studio file generation or plugin distribution and needs a
   separate ADR for that integration boundary.
