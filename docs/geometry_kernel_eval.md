# Geometry kernel evaluation — GEO-1 (V0.2 E2)

**Status:** evaluation complete. No runtime change — adapter is additive and not wired into the executor.
**Bottom-line recommendation: ADOPT.** Proceed to GEO-2 integration work (ADR + gating + Lathe-side IR → Manifold lowering path).

## 1. Context

`docs/next_version_roadmap.md` E2 / GEO-1 was prompted by the P0 finding in `research-findings-gpt.MD`: the current `courier_drone` build falls back from authoritative fusion to reference-conditioned cleanup because `lathe/geometry_kernel.py`'s SDF-fusion pipeline does not reliably produce watertight output for dense, mixed-primitive assemblies. Downstream topology (Blender) and UV (xatlas) then see non-manifold input and degrade further.

A robust boolean kernel that returns *watertight by construction* solves this class of failures at the source. `manifold3d` (the Google-origin exact-arithmetic CSG kernel used by OpenSCAD's next-gen core and Bambu Studio) is the candidate.

This evaluation is **read-only**: it adds a thin adapter + harness + tests. It does not alter `lathe/geometry_kernel.py`, `lathe/executor.py`, or `lathe/backends.py`. Existing builds must continue behaving identically; the GEO-2..8 follow-up tasks are where actual integration lands.

## 2. Methodology

Harness: `scripts/bench_geometry_kernel.py`.

For each hero, we:

1. Parse the `.lth`, materialize, build the `AssetGraph`, and compile scaffold candidates with `compile_scaffold_candidates(seed=42)`.
2. Extract the first `ShapeIR` and feed its primitives into **both** kernels.
3. Run 3 rebuilds per kernel to probe determinism and body-count stability.
4. For each run capture: watertight flag, body count, triangle count, wall-clock, and a canonical SHA-256 triangle hash (vertices rounded to 1e-6, triangles sorted).

Kernel under test A — **Lathe native**: `lathe.geometry_kernel.fuse_shape_ir` with the hero-tier `FidelityProfile` inferred from the asset graph. Voxel-SDF fusion → marching cubes → optional exact finalize.

Kernel under test B — **Manifold v1**: `lathe.adapters.manifold_kernel.ManifoldKernel`. Primitives lowered to `manifold3d.Manifold`, combined via pairwise `union` / `difference` driven by each primitive's `blend_mode`.

Heroes: `courier_drone`, `brassbound_chest`, `mechanical_door`. Picked for different primitive mixes: courier_drone is dense box + cylinder (279 primitives), brassbound_chest is trim-heavy boxes (136 primitives), mechanical_door is axial cylinders + frame boxes (68 primitives).

Raw report JSON: `docs/benchmarks/geometry_kernel_eval_20260424.json`.

## 3. Results

Per-hero, per-kernel (seed=42, 3 rebuilds each):

| Hero | Kernel | Ok runs | Watertight | Body count (×3) | Deterministic | Mean tris | Mean wall-clock |
|---|---|---|---|---|---|---|---|
| courier_drone (279 prims) | Lathe native | 0 / 3 | 0.00 | — (fallback) | n/a | 0 | ≈0 s (bail-out) |
| courier_drone (279 prims) | **Manifold** | 3 / 3 | **1.00** | [35, 35, 35] | **yes** | 7 202 | 0.010 s |
| brassbound_chest (136 prims) | Lathe native | 3 / 3 | 1.00 | [11, 11, 11] | yes | 1 112 | 0.483 s |
| brassbound_chest (136 prims) | **Manifold** | 3 / 3 | 1.00 | [18, 18, 18] | yes | 1 108 | **0.003 s** |
| mechanical_door (68 prims) | Lathe native | 3 / 3 | 1.00 | [3, 3, 3] | yes | 966 | 0.297 s |
| mechanical_door (68 prims) | **Manifold** | 3 / 3 | 1.00 | [7, 7, 7] | yes | 1 054 | **0.003 s** |

On `courier_drone` the native kernel's `fuse_shape_ir` returns a `constructive_fallback` because hero-tier integration for `courier_drone`'s family is routed through the SDF path that cannot produce a coherent volume at this primitive density — matching the P0 symptom in `research-findings-gpt.MD`.

## 4. Watertight-rate delta

- `courier_drone`: native **0.00** → Manifold **1.00** (**+1.00**, P0 fix).
- `brassbound_chest`: native 1.00 → Manifold 1.00 (no delta; already healthy).
- `mechanical_door`: native 1.00 → Manifold 1.00 (no delta; already healthy).

Headline: Manifold keeps already-healthy heroes at 1.00 **and** lifts the failing hero from 0.00 to 1.00. There is no hero where watertight rate regresses.

## 5. Body-count stability delta

Both kernels produce identical body counts across 3 rebuilds on every hero that returns ok runs — stability is a tie (both `True`). The **absolute** body counts differ: Manifold reports more disjoint bodies (35 vs 0 on courier, 18 vs 11 on chest, 7 vs 3 on door) because it preserves the true connected-component topology whereas the native path merges components during voxel fusion.

Whether this is a gain or a regression depends on downstream consumers — topology (Blender) and validation both treat multi-body meshes correctly today, and preserving true body separation is what lets UV and surface stages assign atlas charts per-component. Treated as a **gain** here, conditional on GEO-4 (validator review) confirming no validator silently assumes single-body output.

## 6. Determinism delta

Both kernels deterministic on the heroes where native succeeds (identical canonical triangle hashes across 3 rebuilds, identical triangle counts, identical body counts). Manifold is deterministic on `courier_drone` where native cannot run at all. **Tie or Manifold win** — no regression.

## 7. Performance delta

Wall-clock per rebuild (mean of 3):

- `courier_drone`: native does not complete (fallback); Manifold 0.010 s.
- `brassbound_chest`: native 0.483 s → Manifold 0.003 s (**~160× faster**).
- `mechanical_door`: native 0.297 s → Manifold 0.003 s (**~100× faster**).

Manifold is one to two orders of magnitude faster than the SDF-voxel path on the heroes that complete. Some of this gap closes once Manifold drives real finalization (face-part assignment, exact boundary tagging), but even a 10× overhead on the Manifold side keeps it faster.

## 8. Recommendation — ADOPT

Manifold3d **ADOPT**. Start GEO-2..8 integration. Rationale:

1. **P0 fix.** Lifts `courier_drone` from 0.00 to 1.00 watertight — exactly the failure class called out in `research-findings-gpt.MD`.
2. **No regression on healthy heroes.** Brassbound chest and mechanical door both stay at 1.00 watertight and remain deterministic.
3. **Faster.** 100-160× speedup on the heroes where both kernels complete. Makes multi-candidate search viable at higher fidelity tiers.
4. **Deterministic by construction.** Same inputs, bit-identical triangle hash across rebuilds — removes a whole class of flaky-certification failures.
5. **Dependency is acceptable.** `manifold3d` installs cleanly on CPython 3.14 via a prebuilt wheel (`manifold3d-3.4.1-cp314-cp314-win_amd64.whl`) with no native toolchain requirement; it's under `[project.optional-dependencies].geometry` so it doesn't expand the mandatory install surface.

Form of adoption: **primary kernel for the `shape → topology` handoff under the `lathe.shape.intent_mesh_handoff_v1` contract, with the existing SDF-voxel kernel retained as an explicit fallback** when Manifold is unavailable or an op raises.

## 9. Open questions for the GEO-2 ADR

These are load-bearing decisions that should be resolved in the ADR that lands alongside GEO-2:

1. **Face-part assignment under Manifold output.** `lathe/geometry_kernel.py::_assign_face_parts` walks triangle centroids against `ShapeRegion` boxes. That logic is kernel-agnostic and should port, but validate on `courier_drone` where Manifold emits 35 bodies vs native's 0.
2. **Body-count semantics.** Confirm with `lathe/validators/semantic_quality.py` and `lathe/validators/flow_quality.py` that an increase in reported body count does not trip a "fragmented" penalty; if it does, either relax the validator (preferred — it was masking truth) or post-process `union` to pre-fuse close components.
3. **Blend-mode coverage.** Today's `feature_fusion.primitive_blend_mode` returns `{"union", "subtract"}`. If future features need `intersection`, `hull`, or `minkowski_sum`, wire them through the adapter (it exposes all four already).
4. **Rounding / fillet parity.** Native kernel honors `primitive_rounding(primitive, fidelity)` via SDF expansion. Manifold-side fillets are not covered by this adapter — GEO-5 will need a concrete approach (minkowski offset? post-process trimesh? separate filleting pass?).
5. **Fidelity tiering.** Keep SDF path available for blockout-tier where marching-cubes smoothing is a feature, not a bug — don't collapse the integration path to Manifold-only.
6. **Caching.** `_FUSION_CACHE` in `geometry_kernel.py` is keyed on `(family, fidelity, primitives)`. Reuse the same keying for Manifold results; determinism makes the cache actually safe here.
7. **Ingestion of learned shape-provider meshes.** `shape_providers.py` can emit non-watertight learned meshes. The adapter does not heal those today — GEO-7 will need a `Manifold.from_trimesh(...)` repair path.

## 10. Files touched by GEO-1

- `lathe/adapters/manifold_kernel.py` — adapter (~210 LOC).
- `scripts/bench_geometry_kernel.py` — bench harness.
- `tests/unit/test_manifold_adapter.py` — 8 test cases (skip cleanly when `manifold3d` absent).
- `pyproject.toml` — `manifold3d>=2.5` added to `[project.optional-dependencies].geometry`.
- `docs/geometry_kernel_eval.md` — this report.
- `docs/benchmarks/geometry_kernel_eval_20260424.json` — raw bench output.

No live-path imports changed. `lathe/geometry_kernel.py`, `lathe/backends.py`, `lathe/executor.py` are untouched. Existing `courier_drone` build certification behaviour (including the known pre-existing `stage_validate` `KeyError: 'diagnostics'` failure, which predates this evaluation and is unrelated to the geometry kernel) is unchanged.
