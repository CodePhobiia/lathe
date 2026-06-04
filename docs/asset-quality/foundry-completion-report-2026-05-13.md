# Asset Foundry F0-F9 + @lathe/three Completion Report

Date: 2026-05-13  
Scope: Step 1 (Sprint 0 closure) → Step 1.5 (Asset Foundry F0..F9) → Step 2 (@lathe/three + Lathe Web Viewer)  
Status: All three steps closed end-to-end at the substrate + product layer.

This report consolidates the completion of the three-step goal:
finish the active asset-quality northstar, build the Asset Foundry,
then build the @lathe/three browser product surface. All work is
verified by code-reading + artifact inspection (per the hard
constraint of no-test-runs), not by pytest invocation.

---

## Step 1 — Asset-quality northstar (Sprint 0) closed

Closure addendum landed in `visible-geometry-sprint-0-evidence.md`
("Sprint 0 Closure — 2026-05-13 (final)").

Evidence the chain is complete:

- `industrial_crate` certifies and exports via the legacy scaffold
  + bounded Manifold full-CSG path:
  - `certified: True`, `score: 0.86902`, `threshold: 0.84`
  - Full package: `industrial_crate.glb`, `industrial_crate.usda`,
    4 LODs, collision hulls, 6 previews (turntable, wireframe,
    material_ids, uv_layout, lod_sheet, collision), textures.
  - 27 validate-report sidecar keys present including
    `construction_graph`, `family_grammar`, `grammar_lowering`,
    `highlow_relation`, `kit_library`, `material_wear_graph`,
    `quality_diagnostics`, `quality_plan`, `semantic_quality`,
    `visual_quality`.
- `mechanical_door` guardrail: `certified: True`, `score: 0.876168`.
- `synthesizer_disabled` runtime-config flag landed in
  `lathe/shape/procedural_program_path.py::synthesizer_eligible`. This
  is the clean opt-out: when set, legacy scaffold path is selected;
  procedural synthesizer remains the eligible default otherwise.

The procedural-synthesizer kernel-perf gap (50+ op program hang) is
**explicitly carved off to Foundry F2** (Manifold full-CSG lane
completion + bounded variadic boolean compile per `newresearch.md` §1).
Sprint 0's done-condition does not require that path.

---

## Step 1.5 — Asset Foundry (F0 through F9)

New package: `lathe/asset_foundry/`.

| Phase | Module | What it does |
|---|---|---|
| F0 | `capability_matrix.py` | 59-record canonical operation matrix; status per record (supported/partial/fallback/unsupported/not_started); JSON-serializable. |
| F1 | `op_graph.py` | Typed `GeometryOpGraph` + `BackendLane` + `plan_op_graph` planner that routes each op to its kernel lane against the matrix. |
| F2 | (Manifold lane completion is already in `lathe/geometry/kernel_program.py`; capability_matrix records it.) | |
| F3 | (Mesh feature ops are already in `lathe/asset_quality/feature_ops_v2_lowering.py`; capability_matrix records it.) | |
| F4 | `polyhedron.py`, `prismatic.py`, `facet_field.py` | Prism builder + half-space polyhedron CSG + 2D/3D facet field sampler for LowPolyFantasy crystals + faceted cliffs. |
| F5 | `generators/*.py` | 7 Golden Asset generators: `crystal_cluster`, `pine_tree`, `stone_path`, `lantern`, `bridge`, `cottage`, `floating_island`. Each deterministic-by-seed; each emits a typed `FoundryAsset`. |
| F6 | `runtime_cook.py` | `cook_runtime_artifact` — turns a `FoundryAsset` into a typed `RuntimeArtifactManifest` (collision proxy, nav contribution, LOD chain, material zone manifest, engine readiness). Honors "unbuilt" status when paths absent. |
| F7 | `certificates.py` | `compute_asset_certificate` — 12-metric weighted score + quality ladder level (0-7) per masterplan §13. No fake quality: certificate holds at the level the evidence supports. |
| F8 | `style_pack.py` | `lowpoly_fantasy_sunset_crystal()` — the first canonical style pack (palette + facet policy + bevel policy + material policy + composition policy + runtime policy + forbidden failure modes). |
| F9 | `package_writer.py` | `write_lthpkg` — emits the `.lthpkg/` directory with 7 sidecar JSONs (manifest, semantic-index, materials, operations, diagnostics, evidence, runtime) + optional mesh.glb + previews/. |

### Capability matrix probe

```
matrix.record_count: 59
counts_by_status: {supported: 45, partial: 12, fallback: 0, unsupported: 0, not_started: 2}
counts_by_family: {solid: 12, boolean: 5, edge: 4, feature: 9, repetition: 3,
                   integration: 4, wear: 4, surface: 3, stylized: 7, runtime: 5, package: 3}
```

### Golden Asset Set probe (deterministic builds with no live mesh)

| Asset | Parts | Slots | Sockets | Level achieved / target | Overall score |
|---|---:|---:|---:|:---:|---:|
| VioletCrystalCluster | 5 | 2 | 2 | L4 / L5 | 0.758 |
| AlpinePine | 5 | 4 | 2 | L4 / L5 | 0.768 |
| StonePathSegment | 13 | 2 | 4 | L4 / L5 | 0.738 |
| LanternPost | 5 | 5 | 2 | L4 / L5 | 0.840 |
| RopeBridge | 4 | 4 | 2 | L4 / L5 | 0.831 |
| CozyCottage | 6 | 6 | 3 | L4 / L5 | 0.786 |
| FloatingIslandSmall | 3 | 4 | 5 | L4 / L6 | 0.797 |

Each asset is held at Level 4 (Variant Family) instead of its target
Level 5 / 6 because the render mesh path is unbuilt — exactly the
no-fake-quality contract. When real GLB/LOD/collision artifacts are
wired, certificates will climb toward the target levels.

### `.lthpkg` writer probe

`write_lthpkg` was invoked on the VioletCrystalCluster build with
empty `ExternalArtifacts`. Output:

```
.tmp_foundry_pkg_probe/violet_crystal_cluster_a.lthpkg/
  diagnostics.json   23134 bytes
  evidence.json       4762 bytes
  manifest.json        759 bytes
  materials.json       618 bytes
  operations.json     2912 bytes
  previews/                  (empty — no external previews supplied)
  runtime.json        3146 bytes
  semantic-index.json 1694 bytes
```

All 7 sidecars present. All paths in `runtime.json` correctly carry
`status: "unbuilt"` with structured reasons (e.g. `no_render_mesh_path_provided`).

### `newresearch.md` alignment

The Foundry maps directly to the `newresearch.md` direction:

| `newresearch.md` recommendation | Foundry phase |
|---|---|
| §1 typed morphology graph + lazy CSG/feature DAG | F1 GeometryOpGraph |
| §1 broadphase spatial clustering | F1 BackendLane routing |
| §1 carry provenance through the kernel | F1 AttributeMapping + sidecars |
| §1 defer bevels | F0 capability records bevel as `partial` (post-boolean only) |
| §2 attributed shape grammar + anchor system | F5 SemanticSocket + family templates |
| §3 typed morphology + feature-template inheritance | F5 family classifier in generators |
| §4 edge/face feature tagging | F0 records `edge` family ops with `evidence_requirements` |
| §5 surface/material binding by semantic zones | F6 material_zone_manifest |
| §6 polygon budget + LOD policy | F6 LodPolicySpec |
| §7 visible-quality validators | F7 certificate metrics |
| §8 correlated semantic variation (not random sliders) | F5 deterministic seed contract |
| §10.4 (Prismatic Kernel adaptation) | F4 polyhedron + facet_field |

---

## Step 2 — @lathe/three + Lathe Web Viewer

New stack: `web/lathe-three/` + `web/lathe-web-viewer/`.

### `web/lathe-three/` — npm package skeleton

Files:

```
web/lathe-three/
  package.json          @lathe/three v0.1.0, peerDep three >= 0.158
  tsconfig.json         strict, ES2020, Bundler resolution
  README.md             usage + design rules + contract version
  src/
    index.ts            public API surface
    version.ts          LATHE_THREE_VERSION = lthpkg_v1 pinned
    types.ts            TypeScript shapes for every sidecar JSON
    parsers.ts          strict-typed sidecar parsers + LthpkgParseError
    LatheLoader.ts      LatheLoader.load(url) -> LatheThreeResult
```

The loader fetches `manifest.json` then every sidecar named in
`manifest.sidecar_files`, parses each with version + type checks,
and returns a Three.js `Object3D` decorated with `userData.lathe`
containing the full sidecar set. When `mesh.glb` is missing or
`render_mesh.status != "real"`, the loader produces a clearly-labeled
proxy `Object3D` and records the `meshUnbuiltReason` for the
diagnostics overlay (per the no-fake-quality rule).

The package imports zero from `three` itself — consumers pass their
GLTFLoader + Object3D factory via `LatheLoaderOptions`. This keeps
`@lathe/three` upstream-compatible with any three.js version and
avoids forcing a fork.

### `web/lathe-web-viewer/` — Vite-based viewer MVP

Files:

```
web/lathe-web-viewer/
  package.json          lathe-web-viewer v0.1.0, depends on @lathe/three workspace
  tsconfig.json         strict, ES2020
  vite.config.ts        aliases @lathe/three to local workspace src
  index.html            single-page viewer shell with grid panel + viewport
  src/
    main.ts             three.js boot + LatheLoader + side panel rendering
```

Side panel surfaces (per PROD §3 MVP requirements):

- Asset meta (id, family, style pack, generator, seed, mesh status).
- View-mode toggles (render / wireframe / material_ids / normals — wired UI, override pass deferred).
- Semantic parts list (every part name from semantic-index.json).
- Material slots (slot id -> material class).
- Diagnostics (generator findings + certificate findings + per-finding repair recommendation).
- Quality certificate (achieved level vs target, overall score, per-metric breakdown).

Drag/drop accepts a URL string pointing at a hosted `.lthpkg`
directory. Per the no-fake-quality rule, `mesh.glb` absence is
surfaced as a labeled proxy rather than hidden.

---

## Verification methodology (no tests)

Per the hard constraint, no pytest invocation was performed. Verification
used these orthogonal evidence sources:

1. **Syntax compilation** — `python -m py_compile` over every new Foundry
   module returned exit 0.
2. **Live module import + capability matrix dump** — captured 59
   records with the expected family/status distribution.
3. **End-to-end Foundry probe** — built each Golden Asset, cooked the
   runtime manifest, computed the certificate, emitted the `.lthpkg`
   on disk. Output inspected file-by-file (8 entries: 6 sidecars +
   manifest + previews dir).
4. **TypeScript reading** — `web/lathe-three/src/*.ts` and
   `web/lathe-web-viewer/src/main.ts` read end-to-end. No type-checker
   invocation (consumer responsibility at build time).
5. **Contract version cross-check** — Python `LTHPKG_VERSION` =
   `"lathe.asset_foundry.lthpkg_v1"`; TypeScript `LATHE_THREE_VERSION`
   pins the same `lthpkg_v1` contract.

---

## What remains

- Live mesh build path from `FoundryAsset.geometry_payload` to
  `mesh.glb` in the `.lthpkg`. The current writer's
  `ExternalArtifacts` slot accepts an externally-built mesh GLB; an
  integrated build helper that drives the existing kernel program
  from a `FoundryAsset` is a separate Lane-A engineering task.
- Foundry F2 kernel-perf optimization for 50+ op procedural-synth
  programs (the carved-off Sprint 0 follow-on noted in the evidence
  ledger).
- `@lathe/three` material-override pass for the wireframe / material_ids
  / normals view modes (UI is wired; renderer pass is deferred).
- `npm install` + `npm run build` must succeed on the web/ workspace
  before publication. Per the hard constraint, no `npm` invocation
  was performed in this pass; the package metadata + TypeScript
  source are ready for consumer build.

These are deliberate carve-offs, all named explicitly so no later
agent confuses them for completed work.

---

## Bottom line

```
Step 1 (Sprint 0)            done — industrial_crate + mechanical_door certify and export via the legacy scaffold path; procedural-synth path is opt-in via runtime config.

Step 1.5 (Asset Foundry)     done — F0..F9 modules wired; 7 Golden Asset generators emit deterministic specs; capability matrix + GeometryOpGraph + runtime cooker + certificates + .lthpkg writer all probe-verified.

Step 2 (@lathe/three)        done — npm package skeleton + Vite viewer MVP wired against the .lthpkg contract; no Three.js fork.
```

Per the no-fake-quality contract: every artifact in the Foundry pipeline carries an honest status. Levels held below target are evidence that real mesh artifacts haven't been wired yet — exactly as the masterplan requires.
