# Architecture Decision Records

This directory holds the ADR trail for Lathe's architectural choices.
Each ADR records one decision with its context, rationale,
consequences, and re-evaluation criteria. New ADRs start at the next
free number and are never renumbered.

## How to add one

1. Copy [`0000-template.md`](0000-template.md) to `NNNN-short-title.md`.
2. Fill in Context, Decision, Consequences, Alternatives, Re-evaluation.
3. Set `Status: Proposed` if the decision is still in flight, or
   `Accepted` if it is already implemented in shipping code.
4. Add a row to the index below.

Status values: `Proposed` | `Accepted` | `Superseded by NNNN` |
`Deprecated`.

## Index

| ADR | Title | Status | Adopted |
|---|---|---|---|
| [0000](0000-template.md) | ADR template | — | — |
| [0001](0001-shape-handoff-contract.md) | Freeze `lathe.shape.intent_mesh_handoff_v1` as the single probabilistic seam | Accepted | 2026-04-23 |
| [0002](0002-blender-and-xatlas-fallback-policy.md) | Blender / xatlas adapters degrade to deterministic reference paths with attempted-vs-actual tracing | Accepted | 2026-04-23 |
| [0003](0003-provider-mux-design.md) | Shape-provider selection via mux with probe-then-fallback | Accepted | 2026-04-23 |
| [0004](0004-plugin-entry-points.md) | Plugin extension points via `importlib.metadata.entry_points` | Proposed | 2026-04-23 |
| [0005](0005-layering-enforcement.md) | Enforce package layering via `import-linter` contracts | Proposed | 2026-04-23 |
| [0006](0006-validator-composition.md) | Validator protocol and topological composition via `ValidatorPipeline` | Proposed | 2026-04-23 |
| [0007](0007-resolver-loc-exception.md) | Accept `lathe/resolver.py` 540 LOC as a file-size exception | Accepted | 2026-04-23 |

## Notes

- **0001** pins the shape handoff contract; any edit that moves the
  SHA-256 in `tests/contract/test_shape_handoff_v1.py` is the
  maintainer's signal to re-read 0001 before touching the hash.
- **0002** and **0003** together describe how Lathe preserves
  reproducibility across variable environments: fallback paths exist
  but are always traced in the build report.
- **0004**, **0005**, **0006** depend on Plan 03 Phase 2 / 3 / 5
  landing. Each flips from Proposed to Accepted when the
  implementing commit lands; the implementing commit SHA is recorded
  in the ADR's cross-references.
- **0007** is the template for file-size-cap exceptions — follow its
  shape if a future module needs the same treatment.
