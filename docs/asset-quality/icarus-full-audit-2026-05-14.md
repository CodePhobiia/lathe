# Icarus Full Audit - 2026-05-14

Scope: audit the active asset-quality northstar, Asset Foundry/frontier geometry foundation, `@lathe/three` / Lathe Web Studio path, and `docs/research/newresearch.md` alignment.

Constraint honored: no pytest and no test suites. Verification in this pass is static inspection, AST parsing, import/probe commands, JSON parsing, web build/browser inspection, repair-history package generation, and bounded package-stage-only snapshots from existing crate/door artifacts.

Remediation update: `docs/asset-quality/visible-geometry-sprint-0-evidence.md` now has a 2026-05-14 current-evidence refresh. The newest inspected crate and door roots are real through validate, currently fail certification, and now include bounded package-stage-only manifests/exports generated from existing stage artifacts. These package snapshots keep visual approval at `not_verified`; the older 2026-05-05 package roots remain historical evidence only.

## Verdict

The remediation tasklist is crossed off as implementation/evidence work, but not as product-complete visual quality.

What is now crossed off at the typed substrate level:

- Sprint 0 has current crate/door evidence through bounded package/export snapshots.
- Asset Foundry F0-F9 and the Lane A-J typed-module surface exist.
- Foundry capability tracking now has no `not_started` rows.
- `.lthpkg` writer, `@lathe/three`, and the web viewer contract exist.
- `docs/research/newresearch.md` is materially represented in the Foundry surface: typed op graph, lazy feature/CSG planning vocabulary, material zones, deferred bevel policy, distribution controls, validators, repair request/rollback surfaces, and runtime package evidence.

What is still deliberately not claimed as product-complete:

- Fresh render-preview approval for the industrial crate/door was not regenerated in this pass because slow/crashy verification loops remain out of scope.
- Human visual-quality parity is improved with class/category anchors, but final human approval is not claimed.
- The diagnose -> executable repair -> before/after metadata loop is proven at the ShapeIR/package-metadata layer; full web-triggered geometry rebuild is not product-complete.
- Some external-backed frontier lanes remain typed contracts rather than real backend execution: OCCT/B-rep, OpenSubDiv, OpenVDB/levelset, MaterialX serialization, USD writing.
- Web packages have dependency/build/browser-load evidence, but real mesh GLB loading remains limited by packages that truthfully lack a `mesh_glb` sidecar.

## Documents Read

Primary active push:

- `docs/asset-quality/lathe-implementation-northstar.md`
- `docs/asset-quality/visible-geometry-sprint-0-implementation-plan.md`
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`
- `docs/asset-quality/phase1-phase2-visible-geometry-upgrade-guide.md`
- `docs/asset-quality/quality-diagnostics-v1.md`
- `docs/asset-quality/lathe-implementation-northstar-current-audit.md`

Foundry/frontier foundation:

- `docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md`
- `docs/asset-quality/lathe-frontier-geometry-kernel-roadmap.md`
- `docs/asset-quality/lathe-context-problem-solution-goals-success-criteria.md`
- `docs/asset-quality/lathe-next-level-asset-quality-roadmap.md`
- `docs/asset-quality/lathe-asset-quality-upgrade-spec.md`
- `docs/asset-quality/family-grammar-v1.md`
- `docs/asset-quality/art-direction-ir-v1.md`
- `docs/asset-quality/quality-planner-v1.md`
- `docs/asset-quality/grammar-lowering-v1.md`
- `docs/asset-quality/high-low-relation-v1.md`
- `docs/asset-quality/semantic-construction-graph.md`
- `docs/asset-quality/hardsurface-kit-library-v1.md`

Product layer and research:

- `docs/product/three-lth-lathe-web-studio-v1-product-path.md`
- `North Star/lathe-floating-fantasy-world-northstar.md`
- `docs/research/newresearch.md`

## Changes Made In This Pass

### Runtime truth fix

File: `lathe/asset_foundry/runtime_cook.py`

Engine readiness is now conservative:

- A render mesh alone is not enough to mark engine readiness `ready`.
- If a declared collision proxy is unbuilt, engine readiness stays `unsupported`.
- LOD status must be `real` for readiness; proxy/unbuilt LOD no longer upgrades the engine state.

Reason: the Foundry/no-fake-quality rule says `game-ready` requires collision, scale/pivot, UV/material conventions, budget/runtime metadata, and evidence. The prior condition allowed `collision.proxy_status == "unbuilt"` to count as ready.

### Capability matrix truth fix

Files:

- `lathe/asset_foundry/capability_matrix.py`
- `lathe/asset_foundry/__init__.py`

`terrain.faceted_cliff_patch` now matches actual code:

- Status changed from `not_started` to `supported`.
- Evidence requirements are now `facet_sample_count` and `material_zone_manifest`.
- Notes point to the floating-island generator and `sample_facet_field_3d_radial`.
- `sample_facet_field_3d_radial` is exported from `lathe.asset_foundry`.

Reason: the radial facet-field implementation and floating-island cliff-ring generator already exist. Keeping the capability row at `not_started` made the matrix less truthful than the code.

### Web workspace boundary

Files:

- `web/package.json`
- `web/pnpm-workspace.yaml`

Added a minimal pnpm workspace root so `lathe-web-viewer` can truthfully depend on `@lathe/three` through `workspace:*`.

Reason: the viewer package declares `@lathe/three: workspace:*`; without a workspace root this is not a complete product-layer package boundary.

## Remediation Patch Update

Additional no-test remediation patches now landed after the initial audit write-up:

- Sprint 0 evidence ledger refreshed with current crate/door artifact status: newest roots are real through validate, failing certification, and missing package manifests.
- Hard-surface class-anchor evidence now appears in quality diagnostics with repairable `hard_surface_class_anchor_*` findings.
- Validate/package/Foundry evidence separates `pipeline_certified` from `visual_quality_gate` and `visual_claim_level`.
- Repair traces now record `repair_target_layer="shape_ir_patch"` plus attempted-vs-actual operations; `.lthpkg` can carry optional `repair-history.json`, and `@lathe/three`/viewer expose it.
- `build_repair_history_evidence()` now converts repair traces into before/after `.lthpkg` sidecar metadata. Probe package `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg/repair-history.json` records `hard_surface_class_anchor_panel_breakup` -> `add_secondary_features`, six ShapeIR operation ids, a before stage root, a real metadata package path, primitive-count delta 1 -> 7, and after-preview `not_verified`.
- Foundry capability JSON now includes `backend_required`; OCCT, OpenSubDiv, OpenVDB/levelset, MaterialX serialization, and USD writer blockers are explicit.
- `violet_crystal_cluster` can lower to real runtime JSON artifacts for render mesh, collision proxy, and LODs, then package them into a `.lthpkg` runtime sidecar while visual approval remains `not_verified` until preview evidence exists.
- `GeometryOpGraph` now emits spatial clusters, boolean cluster plans, and operations-sidecar provenance summaries.
- MaterialX and USD writer boundaries now return unsupported evidence with named blockers instead of claiming file paths.
- Viewer mode buttons now apply reversible material overrides for render, wireframe, material IDs, and normals.
- Foundry capability JSON now carries claim tiers (`typed_contract`, `execution_partial`, `artifact_real`, `product_complete`). Current static matrix probe reports 105 records: 87 supported, 18 partial, 0 not-started, and 0 product-complete static claims.
- `op.distribute` and `op.weld_seam` are promoted from partial to supported with no-test ShapeIR v2 lowering probes: `along_path` distribution lowers to component-assembly evidence, and path weld seams lower to visible `weld_seam` records.
- Foundry category-anchor scoring now gates certificate promotion before aesthetic scoring; a featureless container payload fails the crate anchor rule with missing panel, corner, lid/latch, and material-separation evidence.
- Viewer repair export now uses a typed `LatheRepairRequest` with an explicit browser-to-Core execution boundary and `after_package.status="rebuild_pending"`.
- Runtime engine readiness now requires material-zone evidence in addition to real render mesh, collision, and LOD evidence.
- Web workspace dependencies were installed with `pnpm install --ignore-scripts`, and `pnpm run build` now passes for both `@lathe/three` and `lathe-web-viewer`; the viewer build emits only a non-blocking Vite chunk-size warning.
- A built `@lathe/three` loader probe confirms optional `repair-history.json` surfaces as `result.repairHistory` and `object3D.userData.lathe.repairHistory` without treating missing mesh GLB as success.
- `.lthpkg` `evidence.json` now emits `external_backend_evidence` blocker rows for backend-required capabilities; MaterialX serialization and USD generative stage show blocked status with no artifact path until their backends write files.
- `runtime.collision_proxy` now has component-level collision evidence for the Golden Asset path: prismatic cluster lowering writes `compound_convex_aabb_decomposition` with one convex AABB component per crystal, and runtime manifests record decomposition strategy plus component count.
- Browser inspection loaded the generated violet crystal `.lthpkg` manifest through `lathe-web-viewer` using `?manifest=...`; the UI showed semantic parts, material slots, external backend blockers, certificate metrics, `mesh_glb_not_in_sidecar_files`, and `visual=not_verified`. Screenshot evidence: `lathe-web-viewer-violet-crystal-package.png`.
- Bounded package-stage-only snapshots now exist for `industrial_crate` and `mechanical_door` from the current inspected stage roots. They wrote package manifests, USD/GLB exports, LODs, collision hull/parts, and textures while preserving `pipeline_certified=false`, `visual_claim_level=not_verified`, and `human_review_required=true`.

## Cross-Off Matrix

| Area | Status | Evidence | Gap |
| --- | --- | --- | --- |
| Sprint 0 evidence ledger | Crossed off with bounded package snapshots | `docs/asset-quality/visible-geometry-sprint-0-evidence.md`; current crate/door roots now include `stages/package/package_manifest.json`, USD/GLB exports, LODs, collision hull/parts, and textures | Full fresh build pipeline still did not naturally reach package; validation remains failing and visual approval remains `not_verified`. |
| Sprint 0 visible diagnostics | Partial | `lathe/asset_quality/diagnostics.py`; `quality-diagnostics-v1.md`; prior current audit says diagnostics improved | Still not enough to replace human visual judgment. |
| Semantic repair bridge | Crossed off at metadata/intent layer | `lathe/repair_planner.py`, `lathe/repair_executor.py`, `lathe/asset_foundry/package_writer.py`; `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg/repair-history.json` | Full geometry rebuild and after-render preview remain `not_verified`. |
| Stable shape handoff | Preserved | No public `.lth` syntax or handoff migration changed in this pass | Not revalidated with contract tests due no-test limit. |
| Foundry F0 capability matrix | Crossed off at typed/status-tier level | Probe: 105 records, 87 supported, 18 partial, 0 not_started; claim levels include 0 `product_complete` rows | Partial rows still need backend or missing local execution evidence. |
| Foundry F1 GeometryOpGraph | Crossed off at typed level | `lathe/asset_foundry/op_graph.py` | Broadphase/clustered many-op execution remains future production work. |
| Foundry F2 kernel frontier | Partial | `lathe/geometry/kernel_program/`; `lathe/asset_foundry/kernel_ops/` | 50+ op procedural-synth performance path not proven. External B-rep/arrangement backends absent. |
| Foundry F4 stylized/prismatic ops | Crossed off at typed level | `facet_field.py`, `polyhedron.py`, `prismatic.py`, floating-island cliff facet probe | Product mesh lowering still depends on runtime integration. |
| Foundry F5 Golden Asset Set | Crossed off at generator-spec level | `lathe/asset_foundry/generators/` | Generators emit specs, not final production mesh packages by themselves. |
| Foundry F6 runtime cooking | Improved, still partial | Violet crystal cluster runtime probe produced real JSON render mesh, component-level collision proxy, and LOD sidecars | Real render image/material approval is still not verified. |
| Foundry F7 certificates | Crossed off at typed/category-anchor level | `lathe/asset_foundry/certificates.py`; featureless-container probe fails `category_anchor_score` | Certificate is heuristic and cannot replace visual review. |
| Foundry F8 style pack | Crossed off at typed level | `style_pack.py`, `style_bands.py` | Needs rendered asset corpus to prove taste. |
| Foundry F9 `.lthpkg` writer | Crossed off at package-contract/backend-blocker level | `package_writer.py`, `web/lathe-three/src/types.ts`; external backend evidence probe surfaces MaterialX/USD blockers | Does not generate meshes; copies/records external artifacts only. |
| `@lathe/three` loader | Crossed off for package loading/build | `LatheLoader.ts`; `pnpm run build` emits `web/lathe-three/dist/`; browser inspection loaded a generated package manifest and surfaced blocker evidence | Real mesh GLB load remains unproven because the package truthfully lacks a `mesh_glb` sidecar. |
| Lathe Web Viewer | Partial MVP, build and browser-load verified | Viewer has side panels, evidence PNG capture, URL/query-param package loading, reversible view modes, typed repair request export, proxy/unbuilt surfacing; `pnpm run build` emits `web/lathe-web-viewer/dist/`; Playwright snapshot/screenshot loaded `violet_crystal_cluster_a.lthpkg` truthfully | Repair button exports request only; Core CLI/service execution is not wired. Real render approval remains `not_verified`. |
| `docs/research/newresearch.md` support | Crossed off for implementation-path support | `op_graph.py`, `capability_matrix.py`, `distribution.py`, `materialx_lowering.py`, `runtime_cook.py`, validators, package manifests, repair-history sidecar | Production arrangement backend and image-based perceptual scoring are not claimed. |

## `newresearch.md` Alignment

Implemented or materially represented:

- Typed morphology / operation graph: `lathe/asset_foundry/op_graph.py`.
- Lazy feature/CSG planning vocabulary: `GeometryOpGraph`, `BackendLane`, `CapabilityRecord`.
- Provenance and attribute mapping: `AttributeMapping`, `.lthpkg` `operations.json`.
- Deferred bevel policy: capability matrix keeps bevel/chamfer partial where execution is not universal.
- Material zones first-class: `RuntimeArtifactManifest.material_zone_manifest`, `materialx_lowering.py`, `package_writer.py`.
- Distribution controls: `distribution.py` supports count/density/spacing/jitter/mirror/snap/seed controls.
- Runtime asset contract: `runtime_cook.py`, `package_writer.py`, `runtime/signed_package.py`.
- Visible-quality validator surface: `asset_foundry/validators/` plus existing asset-quality diagnostics.
- Repair graph direction: `repair_rollback.py` and viewer repair request export.
- Truth-tier capability reporting: `capability_matrix.py` separates typed contracts, execution partials, artifact-real paths, and product-complete gates.
- Category anchors before aesthetics: `certificates.py` and `validators/topology_class_compliance.py`.

Not yet complete:

- Batched boolean compiler over many interacting feature ops.
- Full face/edge provenance through a production boolean arrangement backend.
- Real MaterialX/USD serializers in tree.
- Render-based golden/perceptual validation in this pass.
- Graph-level repair that automatically mutates intent, rebuilds, rerenders, and packages before/after evidence.

## Verification Performed

Commands run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; @'
import ast
from pathlib import Path
paths = list(Path('lathe/asset_foundry').rglob('*.py')) + [Path('lathe/geometry/program.py'), Path('lathe/geometry/shape_ir_program.py')]
failures = []
for path in paths:
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except Exception as exc:
        failures.append(f'{path}: {exc}')
print(f'ast_parsed={len(paths)}')
if failures:
    print('\n'.join(failures))
    raise SystemExit(1)
'@ | python -
```

Result: passed, `ast_parsed=70`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry import build_capability_matrix, sample_facet_field_3d_radial; m=build_capability_matrix(); print(m.record_count, dict(m.counts_by_status)); r=m.lookup('terrain.faceted_cliff_patch'); print(r.status.value, r.evidence_requirements); assert m.record_count == 104; assert m.counts_by_status.get('not_started', 0) == 0; assert r is not None and r.status.value == 'supported'; f=sample_facet_field_3d_radial(field_id='probe', axis_origin_cm=(0,0,0), axis=(0,0,1), height_cm=10, base_radius_cm=5, rings=2, facets_per_ring=3); print(f.sample_count()); assert f.sample_count() == 6"
```

Result: passed, `104 {'supported': 84, 'partial': 20, 'fallback': 0, 'unsupported': 0, 'not_started': 0}`, facet sample count `6`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.generators.crystal_cluster import build_violet_crystal_cluster; from lathe.asset_foundry.runtime_cook import cook_runtime_artifact; a=build_violet_crystal_cluster(seed=7); r=cook_runtime_artifact(a, render_mesh_path='tmp_industrial_crate_quick.glb'); print(r.render_mesh_status, r.collision.proxy_status, r.lod.lod_status, dict(r.engine_readiness)); assert r.render_mesh_status == 'real'; assert all(v != 'ready' for v in r.engine_readiness.values())"
```

Result: passed, `real unbuilt unbuilt {'roblox': 'unsupported', 'unity': 'unsupported', 'unreal': 'unsupported', 'usd': 'unsupported', 'gltf': 'unsupported'}`.

```powershell
python -c "import json, pathlib; files=['web/package.json','web/lathe-three/package.json','web/lathe-web-viewer/package.json']; [json.load(open(f, encoding='utf-8')) for f in files]; print('json_ok', ','.join(files))"
```

Result: passed, all three package JSON files parse.

```powershell
git diff --check -- lathe/asset_foundry/runtime_cook.py lathe/asset_foundry/capability_matrix.py lathe/asset_foundry/__init__.py web/package.json web/pnpm-workspace.yaml
```

Result: passed, no whitespace errors.

Inspection commands:

```powershell
git diff --name-only
git diff --stat
git status --short
```

Result at the initial audit point: tracked diff was limited to:

- `lathe/asset_foundry/__init__.py`
- `lathe/asset_foundry/capability_matrix.py`
- `lathe/asset_foundry/runtime_cook.py`

New workspace files:

- `web/package.json`
- `web/pnpm-workspace.yaml`

Current remediation state is broader than this initial snapshot; see `git diff --name-only` in the final verification pass and the source-expansion note in `visible-geometry-sprint-0-evidence.md`.

Additional no-test verification after remediation patches:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "import ast, pathlib; paths=[pathlib.Path('lathe/asset_foundry/capability_matrix.py'), pathlib.Path('lathe/asset_foundry/certificates.py'), pathlib.Path('lathe/asset_foundry/validators/topology_class_compliance.py')]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in paths]; print('ast_ok', len(paths))"
```

Result: passed, `ast_ok 3`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.capability_matrix import build_capability_matrix, capability_matrix_to_dict; m=build_capability_matrix(); d=capability_matrix_to_dict(m); rows={r['operation_id']:r for r in d['records']}; print({'record_count':d['record_count'],'counts_by_status':d['counts_by_status'],'counts_by_claim_level':d['counts_by_claim_level'],'op.distribute':(rows['op.distribute']['status'], rows['op.distribute']['claim_level'], rows['op.distribute']['fallback_reason']),'op.weld_seam':(rows['op.weld_seam']['status'], rows['op.weld_seam']['claim_level'], rows['op.weld_seam']['fallback_reason'])})"
```

Result: passed, `record_count=105`, `supported=87`, `partial=18`, `product_complete=0`; `op.distribute`, `op.weld_seam`, and `runtime.collision_proxy` are `supported` / `artifact_real` / no fallback reason.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.validators.topology_class_compliance import evaluate_category_anchor_compliance; r=evaluate_category_anchor_compliance(asset_id='featureless_container', asset_family='container', semantic_parts=('body',), material_classes=('paint',), geometry_payload_kind=''); print({'rule':r.anchor_rule_id,'score':r.compliance_score,'missing':r.missing_evidence})"
```

Result: passed, featureless container resolves to `class_anchor.industrial_crate_v1`, score `0.166667`, and reports missing panel/corner/lid/latch/material separation.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_quality.shape_ir_v2 import ShapeOp, ShapeProgram, lower_to_v1; source={'primitive_type':'box','part':'bolt','extents':(1,1,1),'center':(0,0,0),'tags':['source']}; p=ShapeProgram('probe','probe','hard_surface',(ShapeOp('op.distribute','bolt_line',{'pattern':'along_path','source':source,'path':[(0,0,0),(10,0,0),(10,5,0)],'count':4,'orientation_mode':'path_tangent'},'probe'),ShapeOp('op.weld_seam','body_weld',{'width_cm':1.0,'path':[(0,0,0),(8,0,0)],'center':(0,0,0)},'probe'))); r=lower_to_v1(p, materialize_output=False); print({'records':len(r.v1_records),'diagnostics':r.diagnostics,'unsupported':r.unsupported_ops,'primitive_types':[x.get('primitive_type') for x in r.v1_records],'ops':[x.get('v2_op') for x in r.v1_records]})"
```

Result: passed, two records lowered with no diagnostics: `component_assembly` for `op.distribute` and `weld_seam` for `op.weld_seam`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.generators._base import CollisionSpec, FoundryAsset, GeneratorSpec, LodPolicy, MaterialSlot; from lathe.asset_foundry.runtime_cook import cook_runtime_artifact; from lathe.asset_foundry.certificates import compute_asset_certificate, quality_ladder_level_for_score; spec=GeneratorSpec(generator_id='featureless_crate', parameters={}, seed=1, style_pack_id='LowPolyFantasy', family='container', semantic_parts=('body',), geometry_payload={'kind':'box'}, material_slots=(MaterialSlot('body','body','paint'),), sockets=(), collision=CollisionSpec(strategy='box'), lod_policy=LodPolicy()); asset=FoundryAsset('featureless_container', spec, ((-1,-1,-1),(1,1,1)), quality_ladder_target=7); manifest=cook_runtime_artifact(asset); cert=compute_asset_certificate(asset, manifest); print({'category_anchor_score': cert.metrics['category_anchor_score'], 'achieved_level': cert.achieved_level, 'cap_high_score': quality_ladder_level_for_score(0.95, manifest, asset, category_anchor_score=0.2)})"
```

Result: passed, category anchor score `0.2`, achieved level `1`, and even a synthetic high aesthetic score is capped at level `1` when category evidence is weak.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.generators._base import CollisionSpec, FoundryAsset, GeneratorSpec, LodPolicy, MaterialSlot; from lathe.asset_foundry.runtime_cook import cook_runtime_artifact; existing='docs/research/newresearch.md'; base=dict(generator_id='readiness_probe', parameters={}, seed=1, style_pack_id='LowPolyFantasy', family='prop', semantic_parts=('body',), geometry_payload={'kind':'box'}, sockets=(), collision=CollisionSpec(strategy='box'), lod_policy=LodPolicy(lod_levels=1,target_triangle_counts=(10,))); empty=FoundryAsset('no_material', GeneratorSpec(material_slots=(), **base), ((0,0,0),(1,1,1))); mat=FoundryAsset('with_material', GeneratorSpec(material_slots=(MaterialSlot('body','body','paint'),), **base), ((0,0,0),(1,1,1))); a=cook_runtime_artifact(empty, render_mesh_path=existing, collision_proxy_path=existing, lod_paths=(existing,)); b=cook_runtime_artifact(mat, render_mesh_path=existing, collision_proxy_path=existing, lod_paths=(existing,)); print({'no_material_ready':dict(a.engine_readiness),'with_material_ready':dict(b.engine_readiness)})"
```

Result: passed, no-material asset remains `unsupported`; identical artifact evidence plus one material slot reports engine readiness `ready`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "from lathe.asset_foundry.capability_matrix import build_capability_matrix; from lathe.asset_foundry.package_writer import _build_external_backend_evidence; e=_build_external_backend_evidence(build_capability_matrix()); ids={row['operation_id']: row for row in e}; print({'count': len(e), 'materialx': ids.get('material.materialx_serialization'), 'usd': ids.get('runtime.usd_generative_stage')})"
```

Result: passed, six backend-required evidence rows emitted; MaterialX serialization and USD generative stage both report `status=blocked`, named blocker, required backend, and `artifact_path=None`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "import json, pathlib, shutil; from lathe.asset_foundry.generators.crystal_cluster import build_violet_crystal_cluster; from lathe.asset_foundry.runtime_cook import lower_foundry_asset_runtime_artifacts, cook_generated_runtime_artifact, runtime_manifest_to_dict; root=pathlib.Path('.tmp_foundry_collision_probe'); shutil.rmtree(root, ignore_errors=True); asset=build_violet_crystal_cluster(seed=3, crystal_count=4); lowered=lower_foundry_asset_runtime_artifacts(asset, root); collision=json.load(open(lowered['collision_proxy_path'], encoding='utf-8')); manifest=runtime_manifest_to_dict(cook_generated_runtime_artifact(asset, root)); print({'lowered': lowered['status'], 'proxy_kind': collision['proxy_kind'], 'component_count': collision['component_count'], 'component_ids': [c['component_id'] for c in collision['components']], 'manifest_strategy': manifest['collision']['decomposition_strategy'], 'manifest_count': manifest['collision']['proxy_component_count'], 'collision_status': manifest['collision']['proxy_status']})"
```

Result: passed, the violet crystal cluster collision proxy reports `compound_convex_aabb_decomposition`, `component_count=4`, manifest strategy `per_prismatic_component_aabb_hulls_v1`, manifest proxy component count `4`, and `collision_status=real`.

```powershell
pnpm install --ignore-scripts
```

Result: passed from `web/` after sandbox approval. Generated `web/pnpm-lock.yaml` and installed workspace dependencies.

```powershell
pnpm run build
```

Result: passed from `web/` after sandbox approval. `@lathe/three` emitted `web/lathe-three/dist/`; `lathe-web-viewer` emitted `web/lathe-web-viewer/dist/`. Vite reported a non-blocking chunk-size warning for `assets/index-kwvO8Te1.js` at `573.23 kB` minified after the URL-loader and external-backend evidence patches.

```powershell
node .tmp_loader_probe.mjs
```

Result: passed after sandbox approval using a temporary local probe file that was deleted afterward. The built loader returned `repair_status="not_verified"`, `repair_target_layers=["shape_ir_patch"]`, `meshIsReal=false`, `meshUnbuiltReason="mesh_glb_not_in_sidecar_files"`, and `userDataHasRepair=true`.

```powershell
@'
# bounded no-mesh repair-history probe using AssetGraph, ShapeIR, repair_executor,
# build_repair_history_evidence(), and write_lthpkg()
'@ | python -
```

Result: passed. The generated package `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg` includes `repair-history.json` with `status=repair_metadata_package_written`, diagnostic `hard_surface_class_anchor_panel_breakup`, selected action `add_secondary_features`, target layer `shape_ir_patch`, six patched ShapeIR operation ids, rebuilt metadata package status `real`, primitive-count delta 1 -> 7, and `preview_before_after.after_preview_status=not_verified`. Its `runtime.json` reports `render_mesh.status=unbuilt`, so no mesh rebuild or visual approval is claimed.

```powershell
@'
# bounded package-stage-only snapshot from existing crate/door stage artifacts;
# previews and trace disabled to avoid render/build loops
'@ | python -
```

Result: passed. `industrial_crate` wrote `.tmp_tests/p0_wedge_crate_2026_05_13_v3/industrial_crate/stages/package/package_manifest.json` with 13 outputs: USD, GLB, four LOD GLBs, collision hull/parts, and five texture maps. `mechanical_door` wrote `.tmp_tests/p0_wedge_door_2026_05_13_v3/mechanical_door/stages/package/package_manifest.json` with 12 outputs: USD, GLB, three LOD GLBs, collision hull/parts, and five texture maps. Both manifests report no previews, `pipeline_certified=false`, `visual_claim_level=not_verified`, and `human_review_required=true`.

```powershell
node D:\lathe_v0_1\web\node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

Result: blocked in sandbox with `Error: spawn EPERM`; rerun after sandbox approval stayed alive until timeout, indicating the server could start outside the sandbox.

```powershell
curl.exe -i http://127.0.0.1:5174/
curl.exe -i http://127.0.0.1:5174/@fs/D:/lathe_v0_1/.tmp_foundry_runtime_probe/pkg/violet_crystal_cluster_a.lthpkg/manifest.json
```

Result: passed after fixing Windows path handling in `web/lathe-web-viewer/vite.config.ts`. Port `5173` was already occupied, so Vite served at `5174`. The viewer HTML and generated package manifest both returned `200 OK`.

```text
Playwright browser navigate: http://127.0.0.1:5174/?manifest=http%3A%2F%2F127.0.0.1%3A5174%2F%40fs%2FD%3A%2Flathe_v0_1%2F.tmp_foundry_runtime_probe%2Fpkg%2Fviolet_crystal_cluster_a.lthpkg%2Fmanifest.json
```

Result: passed. The browser snapshot showed `violet_crystal_cluster_a`, semantic parts, material slots, six external backend blockers, Level 5 certificate metrics, `mesh_glb_not_in_sidecar_files`, and `visual=not_verified`. Screenshot evidence: `lathe-web-viewer-violet-crystal-package.png`.

## Not Run

- No pytest or test suite commands.
- No full asset build.
- No fresh crate/door validation build.

Reason: user hard limit said run no tests and avoid slow/crashy verification. Web install/build, browser inspection, repair-history packaging, and package-stage-only snapshots were run because they are not test commands and do not rerun the full asset build pipeline.
