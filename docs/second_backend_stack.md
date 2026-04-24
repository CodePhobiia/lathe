# Second backend stack: `lathe.stack.soft_surface_prop_v1`

**Status:** proof of plugin model (BL-34 / Plan 08 Phase 4, scoped down
for Wave 4.IV.e)

## Why it exists

The Lathe v0.1 compiler shipped with a single production stack
(`lathe.stack.hard_surface_game_asset_v1`). Plan 08 Phase 4 calls for a
second backend stack to prove the plugin model: that a new stack can be
registered, selected, and run end-to-end without touching the shape
contract or the hard-surface code path.

The full Plan 08 Phase 4 scope estimates a 2-week engineering effort.
This landing delivers a *scoped-down* version that demonstrates the
plugin model works, ships a runnable hero (`examples/satchel_bag.lth`),
and documents the gap to the full implementation so a follow-up ticket
can pick it up without re-discovering the design.

## What is implemented

### Stack registration (`lathe/backends.py`)

`lathe.stack.soft_surface_prop_v1` is registered in the `STACKS` dict
alongside `hard_surface_game_asset_v1`:

| Stage    | Soft-surface binding                       | Behavior                 |
|----------|--------------------------------------------|--------------------------|
| shape    | `lathe.shape.intent_mesh_handoff_v1`       | **Reused**, contract stable |
| topology | `lathe.topology.blender_subdiv_v1`         | **New**, scaffold adapter |
| uv       | `lathe.uv.xatlas_v1`                       | **Reused** (soft-padding mode hook) |
| package  | `lathe.package.openusd_gltf_v1`            | **Reused**                |

The `intent_mesh_handoff_v1` contract bytes are unchanged. The contract
hash pin in `tests/contract/test_shape_handoff_v1.py` still matches, and
`tests/test_stack_soft_surface.py` re-asserts the same pin as part of
the BL-34 regression guard.

### Stack selection

`select_stack()` in `lathe/backends.py` now prefers the stack whose
default stage bindings best match an asset's explicit
`build.<stage>.backend` overrides. An asset opts into the soft stack
by pinning the topology backend:

```lth
build {
  topology {
    backend = lathe.topology.blender_subdiv_v1
    ...
  }
}
```

No grammar or schema changes were required. Assets that do not set an
explicit topology backend keep routing onto the legacy hard-surface
stack, so none of the existing heroes shift stacks under the change.

### Topology adapter (`lathe/adapters/blender_subdiv.py`)

The new `lathe.topology.blender_subdiv_v1` adapter currently:

* Delegates to the existing Blender hard-surface adapter when Blender
  is available on the host. The resulting mesh is deterministic
  end-to-end but does not yet honor soft-surface-specific curvature
  continuity constraints.
* Falls back to the reference topology cleanup path when Blender is
  absent, identical to the hard-surface stack's graceful degradation.

Both behaviors are tagged in the topology bundle's `adapter_report` so
downstream callers can see the attempted-vs-actual adapter.

### Soft-silhouette validator (`lathe/validators/soft_silhouette.py`)

Three tripwire checks, each with a documented threshold:

1. **Sample density** -- triangle and vertex counts must clear a floor
   (`MIN_TRIANGLE_SAMPLES = 24`, `MIN_VERTEX_SAMPLES = 16`). Below the
   floor we emit `soft_silhouette_too_jagged` (L6701/L6702).
2. **Fold-crease avoidance** -- max dihedral angle across face
   adjacencies must stay under `MAX_DIHEDRAL_DEGREES = 150`. A sharper
   fold emits `soft_silhouette_too_jagged` (L6703).
3. **Too-smooth tripwire** -- normalized edge-length variance must be
   at least `MIN_READABLE_EDGE_VARIANCE = 1e-4`. Below that the
   silhouette is featureless and we emit
   `soft_silhouette_too_smooth` (L6704, severity=warning).

The composite score blends all three and is exported as
`report["score"]` for critic composition.

### Hero asset (`examples/satchel_bag.lth`)

A minimal two-part satchel (body + strap) using the new
`std/families/soft/satchel.lth` family and
`std/components/soft/satchel.lth` components. Threshold is set to `0.60`
so it certifies under the scoped validator; the full Phase 4 validator
will raise the bar.

## What is *not* implemented (gap to full Plan 08 Phase 4)

* **Real subdivision-surface topology.** The `blender_subdiv_v1` adapter
  delegates to the hard-surface Blender script. A follow-up must add a
  dedicated Blender script that applies a Catmull-Clark subdivision
  modifier with explicit crease tags, honors
  `build.topology.preserve = [soft_folds]`, and emits a `subdiv_report`
  with per-edge curvature-continuity metrics.
* **Soft-padding UV mode.** The UV stage reuses `lathe.uv.xatlas_v1` as
  a hook point (`uv.soft_padding=true`) but the packer does not yet
  implement non-planar UV padding that accounts for curved
  silhouettes.
* **Full curvature-continuity validation.** The `soft_silhouette`
  validator uses proxy metrics (triangle count, dihedral angle, edge
  variance) rather than per-vertex principal curvatures, per-edge
  C^1/C^2 continuity, or silhouette-edge ray casts from canonical
  camera angles. The `# TODO(BL-34-followup)` comment in the validator
  documents the shape of the real algorithm.
* **Calibrated thresholds.** Current thresholds were tuned empirically
  so the minimal hero certifies and crafted-bad inputs fail. The full
  implementation should derive thresholds from a reference corpus of
  known-good and known-bad soft-surface silhouettes.

## How to swap topology/UV adapters in a new stack

The pattern proven by BL-34 is:

1. **Add a backend entry** under `BACKENDS` in `lathe/backends.py` with
   the new stage-specific ID, contract inputs/outputs, and
   `supported_*` feature lists.
2. **Add a stack entry** under `STACKS` binding the new backend at the
   target stage. Reuse existing backends for the stages you are not
   swapping.
3. **Write the adapter module** under `lathe/adapters/` that either
   provides the real runtime behavior or delegates to an existing
   adapter while the real one is under construction.
4. **Opt in via explicit backend pinning**. No language-surface change
   is needed -- the asset sets `build.<stage>.backend = <new_id>` and
   `select_stack()` ranks the matching stack above the legacy one.
5. **Add a validator (optional)** under `lathe/validators/` if the
   stack has contract-specific quality constraints the core
   validators don't cover.
6. **Pin the shape contract hash** in your new test file alongside the
   BL-25 pin in `tests/contract/test_shape_handoff_v1.py`; the hash
   must not drift under a stack addition.

## Related

* Plan 08 Phase 4 (full spec): `plans/08_product_quality.md`
* Plan 03 Phase 6b (deep-proof validation): `plans/03_architecture.md`
* BL-25 contract pin: `tests/contract/test_shape_handoff_v1.py`
* BL-34 test suite: `tests/test_stack_soft_surface.py`
