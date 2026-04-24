# ADR 0008: Adopt Manifold as the primary geometry kernel

- **Status:** Accepted
- **Date:** 2026-04-24
- **Tickets:** GEO-1 (evaluation, landed in 4f5d900), GEO-2 / GEO-3 / GEO-4 (integration, this ADR)
- **Related:**
  - `docs/geometry_kernel_eval.md` (GEO-1 methodology + results)
  - `research-findings-gpt.MD` (P0 watertightness finding on `courier_drone`)
  - `lathe/adapters/manifold_kernel.py` (original evaluation adapter)
  - `lathe/geometry/` (new subpackage introduced by this ADR)
  - `docs/next_version_roadmap.md` V0.2 E2

## Context

`lathe/geometry_kernel.py` today fuses `ShapeIR` primitives via an SDF voxel
pipeline finished with marching cubes (optionally exact-finalized). The GEO-1
evaluation in `docs/geometry_kernel_eval.md` showed this path reliably produces
watertight output on low-primitive-density heroes but silently falls back to a
constructive-assembly path on dense scenes — `courier_drone` measured at
**watertight_rate = 0.00** on first build before this ADR landed, exactly the
P0 failure pattern called out in `research-findings-gpt.MD`.

manifold3d (Apache-2.0, Google-origin, powering OpenSCAD's next-gen core) is
watertight by construction, deterministic on fixed inputs, and one-to-two
orders of magnitude faster than the SDF path on the heroes that complete
today. GEO-1 shipped a read-only adapter at `lathe/adapters/manifold_kernel.py`
plus a benchmark harness, then recommended **ADOPT**.

## Decision

Introduce a stable **geometry kernel** contract and wire Manifold as the default
backend with the existing trimesh/SDF path retained as an explicit fallback.

1. **Contract.** `lathe/geometry/kernel.py` defines a `GeometryKernel`
   Protocol with methods `probe`, `build_primitive`, `union`, `difference`,
   `intersection`, `hull`, `to_trimesh`, `is_watertight`, `body_count`,
   plus `version` and `name` attributes. Two kernel IDs ship:
   - `lathe.geometry.manifold_v1` — Manifold-backed (Apache-2.0).
   - `lathe.geometry.reference_v1` — trimesh-backed (always available).
2. **Registry.** Entry-point group `lathe.geometry_kernels` surfaces the
   built-ins and lets third parties plug in their own without touching
   core code. The resolver also seeds the two built-ins at import time so
   Lathe works uninstalled-editable.
3. **Selection.** `resolve_geometry_kernel(runtime_config)` applies
   precedence: `LATHE_GEOMETRY_BACKEND` env var → `runtime.geometry.backend`
   in the runtime config → manifold-when-available-else-reference default.
   The shape stage now calls through the resolver; the selected kernel ID
   is recorded in `scaffold_report.geometry_kernel` and in each candidate's
   `integration_report.geometry_kernel` for traceability.
4. **Strict watertightness gate (GEO-4).** The shape stage computes
   `bundle_stats.watertight_rate` on every build and, when
   `build.shape.geometry_strict == true` is set on the asset, raises
   `ShapeBundleError("not_watertight", details)` if `watertight_rate < 1.0`.
   Factory default for `geometry_strict` stays `false` in V0.2 so adoption
   is non-breaking; the V0.3 flip to default-true is tracked as
   follow-up GEO-NEW-1.

## Consequences

### API surface

- New `lathe.geometry` subpackage. `fuse_shape_ir` in `lathe/geometry_kernel.py`
  is retained unchanged — the kernel interface is an additive CSG layer,
  not a replacement for the existing SDF fusion logic.
- New `ShapeBundleError` in `lathe/errors.py` (subclass of `BackendError`).
- `compile_scaffold_candidates` gains an optional `runtime_config` kwarg.
- `bundle["bundle_stats"]["watertight_rate"]` is a new, stable field on the
  shape bundle artifact. Downstream validators and reports can read it.

### Fallback story

- Manifold import failure in the default path is silent and logged at INFO —
  the resolver falls back to `lathe.geometry.reference_v1`. The trace records
  the attempted and actual kernel IDs.
- Explicit kernel requests (via env or runtime config) **do not** fall back:
  an unknown name raises `UnknownGeometryKernel` with the registry listed,
  and an unavailable backing library raises `GeometryKernelUnavailable`.
  This matches the "intent over guess" posture of the shape provider mux.

### Licensing

- manifold3d is Apache-2.0. It ships under `[project.optional-dependencies].geometry`
  and is not a hard install dep — users on the default install path get the
  reference kernel until they opt in.

### Testing

- `tests/unit/test_geometry_kernel_selection.py` covers Protocol conformance,
  registry lookups, and precedence rules.
- `tests/integration/test_manifold_hero_watertight.py` locks in the P0 fix:
  `courier_drone` and `mechanical_door` under Manifold produce
  `watertight_rate == 1.0`, and three back-to-back rebuilds produce
  identical body counts.
- The existing `tests/unit/test_manifold_adapter.py` continues to exercise
  the low-level adapter; the new tests exercise the kernel abstraction.

## Alternatives considered

- **Swap `geometry_kernel.py` out entirely for Manifold.** Rejected for V0.2 —
  the SDF path is still the right tool for blockout fidelity where marching-cubes
  smoothing is a feature (point 5 in GEO-1's open-questions list). The V0.3
  window is the right moment to reconsider, once Manifold has driven real
  certification traffic.
- **Bind Manifold directly from the shape stage with no Protocol.** Rejected
  for plugin symmetry — backends, stacks, providers, and validators already
  surface via entry-point registries (ADR 0004). Geometry kernels join that
  pattern rather than carving out a one-off hook.

## Open questions for V0.3

1. **GEO-NEW-1:** Flip `geometry_strict` factory default to `true` once
   hero coverage under Manifold is confirmed at `watertight_rate == 1.0`
   for the full catalog (hero + non-hero).
2. **Full replacement of `geometry_kernel.py`:** consider collapsing the SDF
   path into the reference kernel (or retiring it) once blockout-tier
   fidelity has a clean Manifold-native story.
3. **Fillet / rounding parity** (GEO-5): Manifold-side filleting is not
   covered by the V0.2 adapter surface.
4. **Learned-mesh repair path** (GEO-7): `shape_providers.py` can emit
   non-watertight learned meshes; a `Manifold.from_trimesh(...)` repair
   path is needed once learned providers feed the strict gate.
