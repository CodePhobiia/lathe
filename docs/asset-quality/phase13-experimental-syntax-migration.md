# Phase 13 experimental syntax — migration notes

## Audience

Authors of existing `.lth` source moving from Phase 12 baseline to
Phase 13. Phase 13 is purely additive: existing sources keep working
without modification, and adopting the new surface is opt-in per
asset.

## Stable surface unchanged

The Phase 13 grammar change adds a single OPTIONAL `experimental_block`
to the asset rule. Every other public block remains identical:

- `profile`, `contract`, `critic`, `asset`, `variant` declarations
- `refs`, `intent`, `geometry`, `features`, `surface`, `assembly`,
  `fit`, `transfer`, `reuse`, `constraints`, `ingest`,
  `assembly_rules`, `execution`, `space`, `repair_policy`, `build`,
  `validate`, `package`, `publish` blocks
- All build-stage names (`shape`, `topology`, `uv`, `surface`,
  `execution`, `rig`, `interfaces`, `physics`, `optimize`, `validate`,
  `package`)
- The shape-stage contract id `lathe.shape.intent_mesh_handoff_v1`

If your source already validated under Phase 12, it validates under
Phase 13 with no changes.

## What's new

A single optional asset-level wrapper:

```lathe
asset crate: hard_surface_prop {
  // ... stable asset blocks ...
  experimental {
    art_direction { ... }     // optional
    references { ... }        // optional
    kit { ... }               // optional
  }
}
```

The wrapper is the explicit gating mechanism. None of the Phase 13
sub-blocks parse outside it, and removing the wrapper cleanly removes
the surface.

## Stability guarantees

- The four-field `art_direction` whitelist (`style_tags`, `wear`,
  `material_age`, `detail_density`) may be extended additively in
  future minor versions.
- The diagnostic codes `L7100`-`L7105` are stable. Their detail
  payloads (e.g. `details.entry`) are also stable for tooling consumers.
- `experimental` sub-blocks beyond the MVP three (`art_direction`,
  `references`, `kit`) will be added under the same wrapper. Authors
  may write new sub-blocks once a future minor version exposes them.
- The total of 26 top-level validate-report keys is preserved. User
  opt-in surfaces inside the existing `design_brief`, `reference_board`,
  and `kit_library` evidence sections as
  `user_provided_via_experimental` annotations.

## What may change

- `experimental` field names and value types may evolve between minor
  versions. Authors that adopt the surface should expect occasional
  migrations until a sub-block graduates to the stable surface.
- New diagnostic codes may be added in the `L71xx` range as the surface
  grows.

## Opt-in / opt-out

Adopting:

1. Add `experimental { ... }` to the asset.
2. Author the sub-blocks that apply to the asset.
3. Run `lathe check <file>` and inspect `L71xx` diagnostics if any.

Reverting:

1. Remove the `experimental { ... }` block.
2. The asset goes back to the Phase 12 baseline. The
   `user_provided_via_experimental` annotations on the validate report
   become empty (`fields: []`, `False`, `declared_parts: []`).

## Compatibility checklist

When upgrading a project to Phase 13:

- Existing `.lth` sources: no changes required.
- Tests asserting the exact key set of `evaluate_design_brief`,
  `evaluate_reference_board`, or `evaluate_kit_library` payloads should
  switch to `issubset` checks (the additive
  `user_provided_via_experimental` key was added by Phase 13).
- The build-cache version was bumped to `v13_rc1`. Existing local
  caches will be invalidated and rebuilt on the next deterministic
  build — this is expected and intentional.
- The 26 top-level validate-report keys are preserved. CI gates that
  count keys remain green.

## Duplicate sub-block behavior

If a single `experimental { ... }` block contains the same sub-block
name more than once (e.g., two `art_direction { ... }` entries), the
last occurrence silently wins and no diagnostic fires. This matches
the existing Lathe convention for duplicate top-level asset blocks
and is intentional. Authors who want every override to apply should
collapse all fields into a single sub-block.

## Forward-phase hooks

The wrapper is intentionally easy to grow. The following sub-blocks
are reserved for forward phases:

- `construction { ... }` — explicit semantic construction graph hints.
- `material_graph { ... }` — overrides for the Phase 7 wear/material graph.

Authors should NOT depend on these names today. They are documented
here so future phases land cleanly under the same wrapper.

## See also

- `docs/asset-quality/experimental-syntax-v1.md` — Phase 13
  per-feature reference and diagnostic table.
- `docs/asset-quality/llm-authoring-experimental-syntax.md` — LLM
  authoring guidance with bad-output examples.
- `examples/industrial_crate_experimental.lth` — runnable example
  exercising all three MVP sub-blocks.
