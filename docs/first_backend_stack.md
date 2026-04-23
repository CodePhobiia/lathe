# First runnable backend stack

The first executable Lathe backend stack is:

`lathe.stack.hard_surface_game_asset_v1`

It binds:

- `shape -> lathe.shape.intent_mesh_handoff_v1`
- `topology -> lathe.topology.blender_hard_surface_v1`
- `uv -> lathe.uv.xatlas_v1`
- `package -> lathe.package.openusd_gltf_v1`

## What is actually runnable today

This stack now executes end to end for the hard-surface reference lane by using:

- a stable shape handoff contract with a Lathe-owned assembly compiler underneath it
- a native assembly-first internal asset kernel with `AssetGraph`, `ShapeIR`, shared primitives, blueprints, a hard-surface feature grammar, an integrated geometry fusion pass, and an explicit authoritative mesh finalize step for the hero slice
- a built-in heuristic fallback provider
- a learned-provider bridge for Hunyuan3D-2.1 over HTTP
- a learned-provider bridge for VGGT over local Python imports plus deterministic point-map meshing
- a real Blender subprocess topology adapter when Blender is installed, with explicit fallback back to reference cleanup
- a real xatlas UV adapter when the Python bindings are installed, with explicit fallback back to the reference box-atlas path
- deterministic packaging to `usd`, `glb`, `gltf`, and `obj`
- manifests, trace files, and preview image generation

## Why this split is still the right first split

The AI-native uncertainty stays isolated to `shape`. The downstream stages remain deterministic, cacheable, and easy to validate.

The backend IDs are still the stable compiler contracts. The current runtime executors behind them are:

- `lathe.runtime.shape.provider_mux_v2`
- `lathe.runtime.topology.cleanup_v1` plus a Blender adapter path selected at runtime
- `lathe.runtime.uv.box_atlas_v1` plus an xatlas adapter path selected at runtime
- `lathe.runtime.package.bundle_v1`

## Current stage behavior

### Shape

`lathe.shape.intent_mesh_handoff_v1` now resolves refs relative to the `.lth` source file, compiles an authoritative native assembly scaffold, and only then evaluates optional provider proposals while preserving the same Lathe-facing output contract.

Current provider adapters:

- `lathe.provider.shape.hunyuan2_1_http_v1`
  - uses the official Hunyuan3D-2.1 API server
  - returns mesh candidates from an input reference image
- `lathe.provider.shape.vggt_local_v1`
  - uses the official VGGT Python package
  - reconstructs multiview geometry and deterministically triangulates predicted point maps into a mesh candidate
- `lathe.provider.shape.reference_conditioned_v1`
  - heuristic fallback when learned providers are unavailable or not selected

The shape bundle now records the authoritative `blueprint_id`, `primitives_used`, `shape_assessment`, proposal-bank decisions, and `provider_report`.

The provider report now distinguishes between:

- the attempted provider
- the actual provider that produced the candidate bundle
- the reason for fallback when a learned provider was unavailable or rejected

The default no-runtime-config build path prefers the reference-conditioned provider so local smoke tests remain fast and predictable. Learned auto-routing is opt-in through runtime configuration.

The internal execution order for the stable shape backend now follows:

`intent -> AssetGraph -> assembly blueprint -> candidate search -> ShapeIR -> feature grammar -> bounded semantic repair execution -> integrated geometry fusion -> authoritative mesh -> native assembly candidate -> optional provider proposal deltas -> conformance fit`

This keeps the external backend ID stable while moving semantic ownership into Lathe itself and away from provider-specific mesh scripts.

### Topology

`lathe.topology.blender_hard_surface_v1` now prefers a real headless Blender subprocess adapter when Blender is available.

If Blender is unavailable, misconfigured, or produces a non-watertight output, the runtime falls back explicitly to the deterministic reference cleanup path and records:

- the attempted adapter
- the actual adapter used
- the fallback reason
- the Blender execution details that are safe to persist

### UV

`lathe.uv.xatlas_v1` now prefers the Python xatlas bindings when they are installed.

If xatlas is unavailable, the runtime falls back explicitly to the deterministic reference box-atlas pass and records:

- the attempted adapter
- the actual adapter used
- the fallback reason

When xatlas is available, it generates the base UV set and the runtime emits a distinct lightmap UV set metadata path as well.

### Package

`lathe.package.openusd_gltf_v1` currently writes:

- `usd`
- `glb`
- `gltf`
- `obj`

It also writes:

- package manifests
- trace manifests
- normalized source copies
- preview images
- stage execution metadata that shows what actually ran versus what was attempted upstream

## Not implemented in this lane yet

- direct in-process Hunyuan execution
- direct in-process TRELLIS execution
- `usdz`
- `fbx`
- automatic repair loops
- publish registry execution

## Practical consequence

We now have a true executable compiler boundary for:

`shape -> topology -> uv -> package`

with enough structure to swap in real learned generation or reconstruction systems at the shape stage without changing Lathe source or the downstream deterministic pipeline.
