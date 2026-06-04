# Icarus Audit Remediation Task List - 2026-05-14

Source audit: `docs/asset-quality/icarus-full-audit-2026-05-14.md`

Purpose: convert every audit finding into a strategic, surgical implementation sequence. This is a patch backlog, not a claim of completion.

Current verification constraint: avoid pytest/test-suite/full-build work unless the user explicitly lifts the no-test limit. For each task below, use bounded static probes, direct artifact inspection, manifest/report inspection, and small non-test commands first. When the no-test limit is lifted, add the missing regression tests as a separate hardening pass.

## Operating Rules

1. Preserve public `.lth` compatibility and `lathe.shape.intent_mesh_handoff_v1`.
2. Patch one thin runtime slice at a time: intent -> artifact -> evidence -> judgment -> repair.
3. Never upgrade a status from partial/proxy/unbuilt to ready unless the artifact evidence proves it.
4. Keep Foundry modules as typed contracts only when execution is external or absent; mark those rows partial with `fallback_reason`.
5. Use `industrial_crate` as the primary hard-surface proof and `mechanical_door` as the guardrail before claiming Sprint 0 closure.
6. Keep `docs/research/newresearch.md` aligned: typed morphology graph, lazy feature DAG, batched boolean compiler, material zones, deferred bevels, LOD, visible validators, graph-level repair.
7. Do not spend implementation work on broad refactors. Each patch must close one named audit gap.

## Phase 0 - Re-Baseline The Working Surface

### T0.1 Freeze Current Diff Map

Finding covered: dirty worktree contains unrelated generated artifacts and untracked work.

Steps:

1. Run `git status --short`.
2. Run `git diff --name-only`.
3. Run `git diff --stat`.
4. Record the output in the active evidence doc before editing anything else.
5. Separate known generated evidence roots from source changes.

Target files:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`
- `docs/asset-quality/icarus-full-audit-2026-05-14.md`

Acceptance evidence:

- Evidence doc states tracked source changes, untracked source files, and generated artifact roots separately.
- No unrelated generated artifacts are deleted or rewritten.

### T0.2 Establish A No-Test Verification Matrix

Finding covered: audit used non-test evidence, but future implementation needs a repeatable constrained verification plan.

Steps:

1. Create a small table of allowed commands: AST parse, import probes, JSON sidecar parse, `git diff --check`, package manifest inspection, single-purpose no-mesh probes.
2. Mark explicitly disallowed commands under the current constraint: pytest, full suite, full asset builds, long screenshot/build loops.
3. Add per-phase evidence requirements to this task list as patches land.

Target file:

- `docs/asset-quality/icarus-audit-remediation-tasklist-2026-05-14.md`

Acceptance evidence:

- Every later task has a bounded non-test validation command.

Current no-test verification matrix:

| Check type | Allowed command shape | Covers |
| --- | --- | --- |
| Dirty-state freeze | `git status --short`; `git diff --name-only`; `git diff --stat` | Separates source changes from generated evidence roots before patching. |
| JSON sidecar inspection | Small `python -c` or PowerShell JSON reads of named files only | Validates existing `report.json`, `manifest.json`, `runtime.json`, and package sidecars without building. |
| Static source inspection | `rg`, `Get-Content`, `Select-String` on named files | Confirms wiring, exports, schemas, and report fields. |
| AST/import probe | Bounded `python -c` import/compile probes for named modules | Confirms syntax and importability without test runners. |
| Synthetic pure-data probe | Bounded `python -c` creating in-memory dicts only | Checks diagnostic/repair/package parser behavior without mesh generation. |
| Whitespace diff check | `git diff --check` | Catches trailing whitespace and conflict markers. |

Currently disallowed unless the user lifts the limit:

| Disallowed command family | Reason |
| --- | --- |
| `pytest`, `python -m pytest`, package test scripts | User explicitly banned tests because they slow down or may crash the computer. |
| Full `python -m lathe.cli build ...` loops | Treated as slow/crashy build verification under the current constraint. |
| Long screenshot/render/build loops | May hang or destabilize the machine; use existing artifacts only. |
| Broad recursive generated-artifact scans | Already observed to time out; inspect named roots instead. |

## Phase 1 - Sprint 0 Closure: Fresh Visible Proof

### T1.1 Refresh Industrial Crate Evidence Without Overclaiming

Finding covered: fresh visual proof for `industrial_crate` was not regenerated in the audit pass.

Steps:

1. Inspect existing crate artifact roots named in `visible-geometry-sprint-0-evidence.md`.
2. Identify the newest crate package/export/preview root that already exists in the workspace.
3. If an artifact exists, inspect sidecars only: `build_report.json`, `stages/validate/report.json`, package manifest, preview paths.
4. If no current artifact exists, mark the task blocked under the no-build constraint.
5. Record exact artifact paths and claim labels: `real`, `proxy`, `fallback`, `not verified`, or `blocked`.

Target files:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`
- `docs/asset-quality/icarus-full-audit-2026-05-14.md`

Acceptance evidence:

- The crate section names source fixture, output root, shape/topology/UV/surface/validate/package/preview paths where present.
- Any missing path is labeled `not verified` or `blocked`, not silently ignored.

### T1.2 Refresh Mechanical Door Guardrail Evidence

Finding covered: guardrail fixture was not regenerated or re-inspected in the audit pass.

Steps:

1. Inspect existing `mechanical_door` artifact roots.
2. Extract the same evidence categories used for the crate.
3. Compare diagnostic/report fields against crate changes to ensure the new logic is not crate-only.
4. Record whether the door preserves stable public source compatibility.

Target files:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`

Acceptance evidence:

- Mechanical-door section has the same evidence shape as the crate.
- Guardrail status is PASS/WARN/BLOCKED with exact artifact paths.

### T1.3 Make The Evidence Ledger Current

Finding covered: Sprint 0 evidence exists but is dated and not refreshed after recent commits.

Steps:

1. Add a new dated section to `visible-geometry-sprint-0-evidence.md`.
2. Summarize current checkout, current HEAD, and dirty-state caveat.
3. Link exact crate and door evidence paths from T1.1 and T1.2.
4. Add a "claims allowed today" list and a "claims still forbidden" list.

Target file:

- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`

Acceptance evidence:

- The ledger can be read without relying on prior chat context.
- It does not claim product-grade visual quality unless fresh artifacts prove it.

## Phase 2 - Human Visual-Quality Parity

### T2.1 Add Class Anchor Diagnostics For Hard-Surface Fixtures

Finding covered: certification can still pass assets humans judge visually weak.

Steps:

1. Inspect `lathe/asset_quality/diagnostics.py` and existing visual/family diagnostics.
2. Add a class-anchor diagnostic for hard-surface containers:
   - bounded volume present;
   - panel breakup present;
   - corner reinforcement present;
   - lid/access seam present;
   - material separation present;
   - fastener/trim detail count above threshold.
3. Make the diagnostic emit named missing evidence, not only a score.
4. Keep it family-grammar/tag driven rather than `asset_name == "industrial_crate"`.
5. Surface repair recommendations for each missing anchor.

Target files:

- `lathe/asset_quality/diagnostics.py`
- `lathe/asset_quality/family_grammar.py`
- `lathe/asset_quality/construction_graph.py`
- `lathe/core/stages/validate.py` if report wiring is needed

Acceptance evidence:

- Static probe can feed a minimal runtime/report dict and receive missing anchor findings.
- Diagnostic output names repairable evidence gaps.

Current patch status: `class_anchor` evidence is now surfaced through `quality_diagnostics` as `hard_surface_class_anchor_*` metrics/findings, crate/door rubrics include panel-breakup evidence, and missing anchors map to deterministic repair routes.

### T2.2 Distinguish Certified From Visually Approved

Finding covered: validation status is not the same as human-visible quality.

Steps:

1. Add a report field or diagnostic block that separates:
   - `pipeline_certified`;
   - `visual_quality_gate`;
   - `human_review_required`;
   - `visual_claim_level`.
2. Ensure proxy/unbuilt/missing preview evidence prevents `visual_claim_level=approved`.
3. Update package/evidence sidecars to carry the distinction.

Target files:

- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_quality/diagnostics.py`
- `lathe/core/stages/package.py`
- `lathe/asset_foundry/package_writer.py`
- `web/lathe-three/src/types.ts`

Acceptance evidence:

- Sidecar/report inspection shows certification status and visual approval status are different fields.
- `@lathe/three` can surface visual approval separately from package validity.

Current patch status: validate reports now emit `visual_quality_gate` with `pipeline_certified`, `visual_quality_gate`, `human_review_required`, and `visual_claim_level`; package manifests and Foundry `.lthpkg` evidence sidecars preserve the same distinction.

### T2.3 Add Render-Evidence Completeness Checks

Finding covered: render-based visual proof was not generated or checked in the audit.

Steps:

1. Inventory preview fields currently emitted by package and validate stages.
2. Require explicit status for each desired view:
   - turntable;
   - front;
   - side;
   - top;
   - three-quarter;
   - material ID;
   - normal/wireframe if available.
3. Treat missing views as `not_verified`, not failure, under no-build mode.
4. When preview files exist, record resolution and file path.

Target files:

- `lathe/asset_quality/preview_evidence.py`
- `lathe/core/stages/package.py`
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`

Acceptance evidence:

- Preview evidence JSON can state missing/present/proxy per view.
- Evidence doc names preview paths or explains exact blocker.

Current patch status: preview evidence now emits `render_evidence_schema` with `real`, `proxy`, `missing`, and `blocked` status tokens. Validate-stage render previews remain `missing` with `validate_runs_before_package`; bake maps with URIs are `real`.

## Phase 3 - Operational Semantic Repair Loop

### T3.1 Map Each New Visual Diagnostic To A Deterministic Repair Action

Finding covered: semantic repair bridge is partial and not proven current.

Steps:

1. Inventory current diagnostic codes from `diagnostics.py`.
2. Inventory allowlisted operations in `repair_executor.py`.
3. Add mappings:
   - missing panel breakup -> add panel inset / trim bands;
   - missing corner reinforcement -> add corner guards/brackets;
   - missing access seam -> add lid seam / door seam;
   - missing fastener detail -> add fastener grid or strip;
   - weak material separation -> assign trim/body material zones;
   - missing preview evidence -> request preview regeneration, not geometry mutation.
4. Ensure every mapping is allowlisted and deterministic.
5. Emit attempted-vs-actual repair action.

Target files:

- `lathe/repair_loop.py`
- `lathe/repair_policy.py`
- `lathe/repair_executor.py`
- `lathe/asset_quality/semantic_patch.py`

Acceptance evidence:

- Static repair-plan probe maps each diagnostic code to a patch operation without applying broad fallback behavior.

Current patch status: class-anchor diagnostic metrics map to `increase_panel_depth`, `add_secondary_features`, `restore_edge_treatment`, `refit_silhouette_region`, or `reauthor_surface_layer` through `repair_planner`.

### T3.2 Make Repair Mutate Intent/Policy, Not Final Mesh

Finding covered: `newresearch.md` says repair must patch the graph, not post-process the mesh.

Steps:

1. Inspect current patch application path.
2. Ensure repair actions write back to source-level or internal intent/ShapeIR/feature-policy structures.
3. Reject repair actions that only edit final mesh artifacts without provenance.
4. Record `repair_target_layer` in repair output:
   - `source_patch`;
   - `shape_ir_patch`;
   - `feature_policy_patch`;
   - `unsupported`.

Target files:

- `lathe/repair_executor.py`
- `lathe/asset_quality/semantic_patch.py`
- `lathe/asset_quality/shape_ir_v2.py`

Acceptance evidence:

- Repair result includes target layer and does not claim mesh-only edits as semantic repair.

Current patch status: `repair_executor` annotates repair traces and generated primitives with `repair_target_layer="shape_ir_patch"` plus attempted-vs-actual operation fields.

### T3.3 Package Before/After Repair Evidence

Finding covered: full diagnose -> repair -> rebuild -> before/after package loop is not product-complete.

Steps:

1. Define a `repair-history.json` sidecar shape for `.lthpkg`.
2. Record:
   - original package id/path;
   - diagnostic ids;
   - selected repair actions;
   - patched intent/policy identifiers;
   - rebuilt package id/path if available;
   - metric deltas;
   - preview before/after paths.
3. Update `write_lthpkg` to include the sidecar when repair evidence is provided.
4. Update `@lathe/three` types/parser to expose repair history.
5. Update viewer panel to show repair history as read-only evidence.

Target files:

- `lathe/asset_foundry/package_writer.py`
- `web/lathe-three/src/types.ts`
- `web/lathe-three/src/parsers.ts`
- `web/lathe-web-viewer/src/main.ts`

Acceptance evidence:

- A synthetic `.lthpkg` sidecar parse proves before/after metadata surfaces in loader result.
- Missing rebuild path stays `not_verified`.

Current patch status: `.lthpkg` packages can include optional `repair-history.json`; `@lathe/three` parses it as `repairHistory`, and the viewer shows history status, target layer, and rebuild status without claiming a rebuild. `build_repair_history_evidence()` now normalizes real repair traces into before/after sidecar metadata. A bounded no-mesh repair probe generated `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg/repair-history.json` from `hard_surface_class_anchor_panel_breakup`; it records `add_secondary_features`, `repair_target_layer=shape_ir_patch`, six patched ShapeIR operation ids (`op.trim_band` and `op.fastener_grid`), a real metadata package path, primitive-count delta 1 -> 7, and `after_preview_status=not_verified`. The same package's `runtime.json` keeps `render_mesh.status=unbuilt`, so no visual rebuild or mesh approval is implied.

## Phase 4 - Foundry Partial Rows To Real Execution

### T4.1 Audit All Current Partial Capability Rows

Finding covered: Foundry matrix contains partial records that need explicit owners and blockers.

Steps:

1. Print all `CapabilityStatus.PARTIAL` rows from `build_capability_matrix()`.
2. For each row, record:
   - operation id;
   - current code module;
   - fallback reason;
   - missing backend or missing integration;
   - smallest proof asset.
3. Split rows into:
   - can be completed in pure Python now;
   - needs optional dependency/backend;
   - should remain partial by design.

Target file:

- `docs/asset-quality/icarus-audit-remediation-tasklist-2026-05-14.md`

Acceptance evidence:

- Every partial row has an owner task and no generic "future work" bucket.

Current owner table from bounded probe (`build_capability_matrix()`):

| Operation | Class | Blocker/fallback | Owner task |
| --- | --- | --- | --- |
| `solid.swept_profile` | Pure Python possible | `path_non_planar_falls_back_to_linear_extrude` | Implement frame policy, miter joins, and bevel joins; prove with synthetic sweep sidecar. |
| `solid.lofted_solid` | Pure Python/reference now, kernel later | `manifold_lane_coverage_gap` | Keep tessellated approximation partial; add Manifold-lane proof before promotion. |
| `solid.sdf_mesh` | Pure Python partial | `meshing_resolution_dependent` | Add crispness/resolution report before hero hard-surface use. |
| `op.minkowski` | Pure Python partial | `approximated_via_half_space_normal_match_for_non_matching_inputs` | Keep analytic box+box supported subset; add non-matching input diagnostics. |
| `op.bevel` | Pure Python partial | `post_boolean_polybevel_only` | Preserve partial until pre-boolean bevel and seam evidence exist. |
| `op.chamfer` | Pure Python partial | `post_boolean_polychamfer_only` | Pair with bevel seam evidence before promotion. |
| `op.shell` | External/backend needed | `inner_shell_offset_kernel_not_landed` | Requires OCCT/libigl-style offset backend; keep partial. |
| `op.chip_edges` | Pure Python/geometry possible | `mask_only_no_geometry` | Add optional high-poly chip geometry; mask-only remains partial. |
| `style.chunkify_surface` | Pure Python possible | `chunk_grid_only_no_irregular_outline` | Add irregular-outline variant evidence. |
| `runtime.nav_contribution` | Integration/backend needed | `walkable_surface_only` | Needs scene-level navmesh integration; per-asset extraction remains partial. |
| `op.half_edge_bevel` | Backend/planner needed | `polybevel_fallback_when_half_edge_backend_absent` | Requires half-edge backend proof; keep polybevel fallback explicit. |
| `kernel.brep_ir` | External backend needed | `occt_backend_not_configured` | Backend required: `occt_or_build123d`. |
| `kernel.mesh_to_levelset_repair` | External backend needed | `openvdb_backend_not_configured` | Backend required: `openvdb_or_levelset_backend`; output never claims real without it. |
| `material.materialx_serialization` | External serializer needed | `materialx_serializer_not_configured` | Backend required: `materialx_serializer`; typed document lowering remains separate. |
| `authoring.reference_extraction` | External pipeline needed | `vision_pipeline_external` | Keep as typed contract until a vision pipeline is wired. |
| `domain.opensubdiv_refinement` | External backend needed | `opensubdiv_backend_not_configured` | Backend required: `opensubdiv`. |
| `domain.sdf_extraction` | External backend needed | `openvdb_backend_not_configured` | Backend required: `openvdb_or_dual_contouring_backend`. |
| `runtime.usd_generative_stage` | External writer needed | `usd_writer_not_configured` | Backend required: `usd_writer`; typed stage spec remains partial until file-backed output exists. |

Current partial-row count after bounded probe: 18. `op.distribute`, `op.weld_seam`, and `runtime.collision_proxy` are no longer listed as partial rows because T4.2 promoted them with bounded evidence. The explicit `material.materialx_serialization` row remains partial by design because typed MaterialX document lowering and real `.mtlx` serialization are separate claims.

Note: the count briefly rose to 21 after adding an explicit `material.materialx_serialization` boundary. It is now 18 after `op.distribute`, `op.weld_seam`, and `runtime.collision_proxy` were promoted with no-test probes.

### T4.2 Complete Pure-Python Partial Rows First

Finding covered: some partial lanes are typed but not execution-complete.

Steps:

1. Select rows whose missing piece is local logic, not external backends.
2. Patch one operation at a time.
3. Update capability matrix status only after a small non-test probe proves execution evidence.
4. Add evidence requirements that point to concrete report/sidecar fields.

Target files:

- `lathe/asset_foundry/capability_matrix.py`
- relevant `lathe/asset_foundry/kernel_ops/*.py`
- relevant `lathe/asset_foundry/domain/*.py`

Acceptance evidence:

- Capability row status changes are paired with code and a probe result.

Current patch status: `op.distribute` is promoted to `supported` after a no-test ShapeIR v2 probe lowered an `along_path` distribution to a `component_assembly` record with placement/provenance metadata. `op.weld_seam` is promoted to `supported` after a no-test ShapeIR v2 probe lowered a path seam to a visible `weld_seam` record with `weld_bead` tags and seam metadata. `runtime.collision_proxy` is promoted to `supported` after the violet crystal probe wrote `compound_convex_aabb_decomposition` collision evidence with per-crystal convex AABB proxy components and manifest fields `decomposition_strategy=per_prismatic_component_aabb_hulls_v1` plus `proxy_component_count` (4 in the bounded collision probe, 5 in the regenerated runtime package). Remaining pure-Python rows stay partial until their specific missing evidence is generated.

### T4.3 Keep External-Backend Rows Honest

Finding covered: OCCT/B-rep, OpenSubDiv, OpenVDB/levelset, MaterialX serialization, and USD writing remain typed contracts.

Steps:

1. Keep external-backed rows `partial` unless the dependency is wired and probed.
2. Add `backend_required` metadata where missing.
3. Add exact blocker strings:
   - `occt_backend_not_configured`;
   - `opensubdiv_backend_not_configured`;
   - `openvdb_backend_not_configured`;
   - `materialx_serializer_not_configured`;
   - `usd_writer_not_configured`.
4. Ensure package/viewer surfaces these as blockers, not failures or successes.

Target files:

- `lathe/asset_foundry/capability_matrix.py`
- `lathe/asset_foundry/kernel_ops/brep_ir.py`
- `lathe/asset_foundry/domain/opensubdiv.py`
- `lathe/asset_foundry/mesh_levelset_repair.py`
- `lathe/asset_foundry/materialx_lowering.py`
- `lathe/asset_foundry/runtime/usd_generative.py`

Acceptance evidence:

- Capability JSON exposes explicit backend blockers.
- No external-backed feature is labeled `supported` from typed contract alone.

Current patch status: `CapabilityRecord` now exposes `backend_required`, serialized capability JSON includes exact blocker tokens for OCCT/B-rep, OpenSubDiv, OpenVDB/levelset, MaterialX serialization, and USD writing, and `.lthpkg` `evidence.json` now emits `external_backend_evidence` blocker rows for those backend-required capabilities. The viewer diagnostics panel includes those blocker rows instead of hiding them behind package validity.

## Phase 5 - GeometryOpGraph And Batched Boolean Compiler

### T5.1 Add Spatial Broadphase Clustering To GeometryOpGraph Planning

Finding covered: broadphase/clustered many-op execution remains future production work.

Steps:

1. Extend `GeometryOpNode` with optional bounds/anchor metadata if not already present.
2. Add a pure planner function that groups nodes by overlapping bounds.
3. Preserve topological order within each cluster.
4. Emit `cluster_id`, `cluster_op_count`, and `cluster_reason`.
5. Do not change kernel execution yet.

Target files:

- `lathe/asset_foundry/op_graph.py`
- `lathe/geometry/kernel_program/_semantic.py` if handoff metadata is needed

Acceptance evidence:

- Static probe on synthetic graph returns multiple non-overlapping clusters.

Current patch status: `GeometryOpNode` accepts optional bounds, `plan_spatial_clusters()` emits `cluster_id`, `cluster_op_count`, and `cluster_reason`, and `OpGraphPlan` carries `spatial_clusters`.

### T5.2 Compile Boolean Clusters As A Single Planned Unit

Finding covered: lazy batched boolean compiler is not implemented.

Steps:

1. Add a `BooleanClusterPlan` model.
2. For each cluster, collect union/difference/intersection/hull operations.
3. Record boolean expression and input primitive ids.
4. Choose backend lane:
   - manifold/reference for current execution;
   - arrangement backend as `unsupported_backend` until implemented.
5. Emit a fallback diagnostic when cluster must execute serially.

Target files:

- `lathe/asset_foundry/op_graph.py`
- `lathe/geometry/kernel_program/boolean.py`
- `lathe/geometry/kernel_program/_common.py`

Acceptance evidence:

- Plan output shows cluster-level boolean expression and actual execution mode.

Current patch status: `plan_boolean_clusters()` emits `BooleanClusterPlan` records with boolean expressions, input primitive ids, preferred backend, and `actual_execution_mode="serial_reference_plan_only"`.

### T5.3 Preserve Face/Edge Provenance Through Cluster Outputs

Finding covered: full face/edge provenance through production boolean arrangement backend is not complete.

Steps:

1. Define minimal provenance fields:
   - `source_part_id`;
   - `source_face_role`;
   - `material_class`;
   - `uv_policy`;
   - `feature_role`;
   - `zone_id`.
2. Ensure current reference/manifold metadata records attempted preservation and dropped fields.
3. Add diagnostics for provenance loss.
4. Surface provenance summary in `.lthpkg` `operations.json`.

Target files:

- `lathe/geometry/kernel_program/_semantic_handoff.py`
- `lathe/geometry/kernel_program/_serialize.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- Operations sidecar records preserved/transformed/dropped provenance counts per operation or cluster.

Current patch status: `.lthpkg` `operations.json` now includes `op_graph.provenance_summary` with preserved/transformed/split/merged/generated/dropped counts and dropped-field diagnostics.

## Phase 6 - Runtime Mesh Lowering For Foundry Generators

### T6.1 Convert One Golden Asset Spec Into A Real Mesh Artifact

Finding covered: Golden Asset generators emit specs, not final production mesh packages by themselves.

Steps:

1. Choose smallest generator: `violet_crystal_cluster`.
2. Add a runtime lowering function from `FoundryAsset.geometry_payload` to a mesh artifact.
3. Preserve material zones and semantic part ids.
4. Feed the mesh path into `cook_runtime_artifact`.
5. Write `.lthpkg` with `render_mesh.status == "real"`.

Target files:

- `lathe/asset_foundry/runtime_cook.py`
- `lathe/asset_foundry/generators/crystal_cluster.py`
- `lathe/asset_foundry/polyhedron.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- Package runtime sidecar reports real render mesh for one Golden Asset.
- Certificate still holds below target if collision/LOD is missing.

Current patch status: `lower_foundry_asset_runtime_artifacts()` writes deterministic Lathe mesh JSON for `violet_crystal_cluster` render geometry; `cook_generated_runtime_artifact()` feeds that path into runtime cooking. Probe path: `.tmp_foundry_runtime_probe/pkg/violet_crystal_cluster_a.lthpkg/runtime.json` reports `render_mesh.status=real`.

### T6.2 Add Collision Proxy Cooking For One Golden Asset

Finding covered: runtime cooking reports collision unbuilt.

Steps:

1. Implement a simple hull/box proxy artifact path for the chosen Golden Asset.
2. Keep proxy strategy explicit.
3. Record collision status as `real` only when artifact exists.
4. Ensure engine readiness remains unsupported until LOD/material requirements are satisfied.

Target files:

- `lathe/asset_foundry/runtime_cook.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- Runtime manifest has `collision.proxy_status == "real"` with path.

Current patch status: the same probe reports `collision.proxy_status=real` and writes `.tmp_foundry_runtime_probe/violet_crystal_cluster_a/collision_proxy.lathe-collision.json`. A follow-up collision probe at `.tmp_foundry_collision_probe/` writes a `compound_convex_aabb_decomposition` proxy with one convex AABB component per crystal and records the decomposition strategy/component count into `runtime.json`.

### T6.3 Add LOD Chain Cooking For One Golden Asset

Finding covered: runtime cooking reports LOD unbuilt.

Steps:

1. Implement deterministic LOD artifact generation or a truthful blocker if the mesh path cannot be simplified safely.
2. Record target vs actual triangle counts.
3. Preserve silhouette flag.
4. Only mark engine readiness `ready` when render mesh, collision, LOD, and material evidence are real enough for the target engine.

Target files:

- `lathe/asset_foundry/runtime_cook.py`
- `lathe/asset_foundry/certificates.py`

Acceptance evidence:

- Runtime manifest has LOD paths and target/actual counts.
- Readiness transitions only after all required evidence exists.

Current patch status: runtime LOD sidecar now includes `actual_triangle_counts`; the violet crystal cluster probe reports `lod_status=real` with four LOD JSON files. Engine readiness turns `ready` only when render mesh, collision, LOD, and material-zone evidence are real/present.

## Phase 7 - MaterialX, USD, And External Serializer Honesty

### T7.1 Add MaterialX Serialization Boundary

Finding covered: real MaterialX serializer is not in tree.

Steps:

1. Keep current MaterialX lowering as typed document generation.
2. Add an explicit `serialize_materialx_document` function that returns:
   - `real` when serializer backend exists;
   - `unsupported` with blocker when absent.
3. Wire result into package evidence.

Target files:

- `lathe/asset_foundry/materialx_lowering.py`
- `lathe/asset_foundry/package_writer.py`
- `lathe/asset_foundry/capability_matrix.py`

Acceptance evidence:

- No MaterialX file path is claimed unless a file is written and exists.

Current patch status: `serialize_materialx_document()` returns `status=unsupported`, `blocker=materialx_serializer_not_configured`, and `artifact_path=None` when no serializer backend is passed. Package evidence also surfaces `material.materialx_serialization` as `status=blocked`, `backend_required=materialx_serializer`, `artifact_path=None`.

### T7.2 Add USD Writer Boundary

Finding covered: real USD writer is not in tree.

Steps:

1. Keep `usd_generative.py` as typed stage spec.
2. Add a writer boundary that emits `unsupported` when USD writer is absent.
3. Carry exact blocker to runtime/package sidecar.

Target files:

- `lathe/asset_foundry/runtime/usd_generative.py`
- `lathe/asset_foundry/runtime_cook.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- USD evidence is path-backed or explicitly blocked.

Current patch status: `write_usd_stage()` returns `status=unsupported`, `blocker=usd_writer_not_configured`, and `artifact_path=None` when no USD writer is configured. Package evidence also surfaces `runtime.usd_generative_stage` as `status=blocked`, `backend_required=usd_writer`, `artifact_path=None`.

## Phase 8 - Web Product Hardening

### T8.1 Build The Web Workspace When Constraint Allows

Finding covered: web packages have workspace boundary, but no install/build was run.

Steps:

1. From `web/`, run package manager install only when allowed.
2. Build `@lathe/three`.
3. Build `lathe-web-viewer`.
4. Record exact dependency/tool blockers if build cannot run.

Target files:

- `web/package.json`
- `web/pnpm-workspace.yaml`
- `web/lathe-three/package.json`
- `web/lathe-web-viewer/package.json`

Acceptance evidence:

- Build output exists or blocker is named.

Current patch status: `pnpm install --ignore-scripts` completed for the `web/` workspace after sandbox approval and generated `web/pnpm-lock.yaml`. `pnpm run build` completed: `@lathe/three` emitted `web/lathe-three/dist/`, and `lathe-web-viewer` emitted `web/lathe-web-viewer/dist/`. Vite reported a non-blocking chunk-size warning for the viewer bundle (`573.23 kB` minified after URL-loader and external-backend evidence patches). The local dev server also served the viewer after fixing Windows path handling in `vite.config.ts`; port `5173` was already occupied, so Vite used `http://127.0.0.1:5174/`.

### T8.2 Complete Viewer Mode Overrides

Finding covered: viewer mode buttons are wired, but material/wireframe/normal overrides are incomplete.

Steps:

1. Inspect loaded Three.js scene traversal.
2. Implement mode manager:
   - render;
   - wireframe;
   - material IDs;
   - normals/debug normals if possible.
3. Preserve original materials for reversible mode switching.
4. Surface proxy/unbuilt state in viewport and panel.

Target file:

- `web/lathe-web-viewer/src/main.ts`

Acceptance evidence:

- Manual/browser or static mode probe shows scene traversal changes material state.

Current patch status: viewer mode buttons now traverse loaded meshes and apply reversible material overrides for render, wireframe, material IDs, and normals. The viewer also has a manifest/package URL field and supports `?package=` / `?manifest=` autoload for direct package inspection without relying on drag/drop. Browser inspection loaded `.tmp_foundry_runtime_probe/pkg/violet_crystal_cluster_a.lthpkg/manifest.json` through the viewer and showed the package metadata, semantic parts, material slots, external backend blockers, certificate metrics, `mesh_glb_not_in_sidecar_files`, and `visual=not_verified` truthfully. Screenshot evidence: `lathe-web-viewer-violet-crystal-package.png`.

### T8.3 Connect Repair Request To A Lathe Execution Boundary

Finding covered: viewer repair request export does not execute rebuild.

Steps:

1. Define a local API/CLI boundary for applying repair requests.
2. Keep browser as requester, not source of truth.
3. Add status states:
   - request exported;
   - rebuild pending;
   - rebuild blocked;
   - repaired package loaded.
4. Record before/after package links when available.

Target files:

- `web/lathe-web-viewer/src/main.ts`
- `web/lathe-three/src/types.ts`
- `lathe/repair_executor.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- Viewer can carry a repair request id and show blocked/pending/repaired truthfully.

Current patch status: the viewer exports a typed `LatheRepairRequest` with `request_id`, `status="request_exported"`, an explicit browser-to-Core execution boundary, before-package evidence, and `after_package.status="rebuild_pending"`. The browser still does not execute rebuilds; that remains a truthful CLI/service boundary.

## Phase 9 - Render-Based Golden And Perceptual Validation

### T9.1 Define Golden Render Evidence Schema

Finding covered: render-based golden/perceptual validation was not performed.

Steps:

1. Define schema for deterministic render evidence:
   - image path;
   - view/camera;
   - renderer/backend;
   - resolution;
   - material mode;
   - source package id;
   - hash;
   - status.
2. Add status tokens: `real`, `proxy`, `missing`, `blocked`.
3. Do not require image generation under no-build/no-test constraint.

Target files:

- `lathe/asset_quality/preview_evidence.py`
- `lathe/asset_foundry/package_writer.py`

Acceptance evidence:

- Package/evidence sidecar can represent complete and missing render evidence.

Current patch status: `preview_evidence` emits a render-evidence schema with explicit status tokens and does not promote validate-stage preview declarations to real files.

### T9.2 Add Category Anchor Scoring Before Aesthetic Scoring

Finding covered: validators must test category evidence, not only geometry/aesthetic polish.

Steps:

1. Add class anchor validator payloads for crate/door/golden fantasy assets.
2. Require category anchors before high aesthetic scores can promote.
3. Return repair suggestions, not just penalties.
4. Keep golden-image regression separate from improvement scoring.

Target files:

- `lathe/asset_quality/diagnostics.py`
- `lathe/asset_foundry/validators/topology_class_compliance.py`
- `lathe/asset_foundry/certificates.py`

Acceptance evidence:

- A featureless cube-like hard-surface payload fails missing category anchors.

Current patch status: Foundry certificates now compute `category_anchor_score` before ladder promotion and cap weak category evidence below high quality levels. `topology_class_compliance` exposes `evaluate_category_anchor_compliance`; a featureless `container` payload resolves to the crate anchor rule and fails missing panel, corner, lid/latch, and material-separation evidence.

## Phase 10 - Final Strategic Closure Gates

### T10.1 Reconcile Audit, Task List, And Evidence Ledger

Finding covered: docs can overstate completion unless reconciled with artifacts.

Steps:

1. Update `icarus-full-audit-2026-05-14.md` with resolved tasks only after patches land.
2. Keep unresolved tasks here until evidence exists.
3. Update `visible-geometry-sprint-0-evidence.md` with exact current artifacts.
4. Add a final "allowed claims" section.

Target files:

- `docs/asset-quality/icarus-full-audit-2026-05-14.md`
- `docs/asset-quality/icarus-audit-remediation-tasklist-2026-05-14.md`
- `docs/asset-quality/visible-geometry-sprint-0-evidence.md`

Acceptance evidence:

- No doc says product-complete unless artifact evidence exists.

### T10.2 Promote From Typed Substrate To Product-Complete Only At Evidence Gates

Finding covered: typed substrate is mostly present, but product-complete visual quality is partial.

Steps:

1. For each area, require all three:
   - execution code;
   - generated artifact/report/sidecar;
   - visual or runtime inspection evidence.
2. Mark status:
   - `typed_contract`;
   - `execution_partial`;
   - `artifact_real`;
   - `product_complete`.
3. Update capability matrix/report docs to use these distinctions.

Target files:

- `lathe/asset_foundry/capability_matrix.py`
- `docs/asset-quality/icarus-full-audit-2026-05-14.md`

Acceptance evidence:

- Future audits can tell whether a feature is a type, an execution path, a real artifact, or a product-ready capability.

Current patch status: capability matrix records now serialize `claim_level` and matrix-level `counts_by_claim_level` using `typed_contract`, `execution_partial`, `artifact_real`, and `product_complete`. Current bounded probe reports `typed_contract=6`, `execution_partial=12`, `artifact_real=87`, and `product_complete=0`; no static capability row is allowed to imply product-complete visual quality.

## Immediate Patch Order

1. T0.1/T0.2: freeze evidence and allowed verification.
2. T1.1/T1.2/T1.3: refresh crate and guardrail evidence from existing artifacts first.
3. T2.1/T2.2: add class-anchor diagnostics and separate certification from visual approval.
4. T3.1/T3.2: map diagnostics to deterministic graph-level repair actions.
5. T3.3: add `.lthpkg` repair history sidecar and loader exposure.
6. T4.1: enumerate all current partial rows and assign owner tasks.
7. T6.1: make one Golden Asset produce a real render mesh package.
8. T6.2/T6.3: add collision and LOD evidence for that one Golden Asset.
9. T5.1/T5.2/T5.3: start the many-op compiler path after the one-asset loop proves value.
10. T8.1/T8.2/T8.3: harden the web layer after package evidence is meaningful.
11. T9.1/T9.2: add render/category validation evidence once assets and packages exist.
12. T10.1/T10.2: reconcile docs and promote claims only where evidence supports them.

## Definition Of Done For This Remediation Program

All of the following must be true:

1. `industrial_crate` has current before/after evidence with exact artifact paths.
2. `mechanical_door` guardrail evidence proves changes are not crate-only.
3. Hard-surface class-anchor diagnostics can fail weak visual outputs that generic validation would otherwise certify.
4. At least one diagnostic maps to a deterministic graph/intent repair and produces before/after package metadata.
5. The Foundry capability matrix has no misleading statuses: supported rows have execution evidence; partial rows name backend/integration blockers.
6. One Golden Asset produces real `.lthpkg` render mesh evidence, not only a spec.
7. Runtime readiness never reports `ready` without render mesh, collision, LOD, material, and package evidence.
8. `@lathe/three` can load package evidence and expose semantic index, operations, diagnostics, runtime evidence, repair history, and proxy/unbuilt blockers.
9. The viewer can inspect meaningful packages and export evidence without making weak geometry look falsely complete.
10. `docs/research/newresearch.md` is supported by real implementation paths for typed op graph, lazy/batched geometry planning, material-zone preservation, render/category validation, and graph-level repair.

## Completion Audit - Current State 2026-05-14

Objective: patch and implement every finding in this remediation tasklist without running tests. Completion requires each definition-of-done row to have code plus artifact/report/inspection evidence, or to remain explicitly blocked under the current no-test/no-build constraint.

| DOD | Current status | Concrete evidence | Remaining blocker |
| --- | --- | --- | --- |
| 1. `industrial_crate` current before/after evidence | PASS | Section 0 of `visible-geometry-sprint-0-evidence.md` names current crate artifacts through package/export. Bounded package-stage snapshot wrote `.tmp_tests/p0_wedge_crate_2026_05_13_v3/industrial_crate/stages/package/package_manifest.json`, USD/GLB, LODs, collision hull/parts, and textures; quick before/final preview paths are named. | Snapshot was generated from existing stage artifacts with previews/trace disabled; validation remains failing and visual approval remains `not_verified`. |
| 2. `mechanical_door` guardrail evidence | PASS | Section 0 names the same evidence shape for mechanical door through package/export. Bounded package-stage snapshot wrote `.tmp_tests/p0_wedge_door_2026_05_13_v3/mechanical_door/stages/package/package_manifest.json`, USD/GLB, LODs, collision hull/parts, and textures. | Snapshot was generated from existing stage artifacts with previews/trace disabled; validation remains failing and visual approval remains `not_verified`. |
| 3. Weak hard-surface outputs fail class anchors | PASS | `lathe/validators/class_anchor.py`, `lathe/asset_quality/diagnostics.py`, crate/door rubrics, and featureless-container category-anchor probe. | Needs regression tests later when test constraint is lifted. |
| 4. Diagnostic maps to graph/intent repair with before/after metadata | PASS | `repair_planner` maps class-anchor diagnostics; `repair_executor` records `repair_target_layer`; `build_repair_history_evidence()` generated `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg/repair-history.json` from `hard_surface_class_anchor_panel_breakup` with `add_secondary_features`, six ShapeIR operation ids, before root, rebuilt metadata package path, and primitive-count delta 1 -> 7. | This proves metadata/intent repair only; full geometry rebuild and after-preview render remain `not_verified`. |
| 5. Capability matrix statuses are truthful | PASS | Capability probe: 105 records, 87 supported, 18 partial, 0 not-started, 0 product-complete; backend rows expose exact blockers and package `external_backend_evidence`. | Remaining partial rows are intentionally not promoted without their named backend/local evidence. |
| 6. One Golden Asset produces real `.lthpkg` render mesh evidence | PASS | `.tmp_foundry_runtime_probe/pkg/violet_crystal_cluster_a.lthpkg/runtime.json` reports real render mesh; runtime lowering writes deterministic JSON mesh artifacts. | Visual preview approval remains `not_verified`. |
| 7. Runtime readiness requires all required evidence | PASS | Runtime readiness probe shows no-material asset remains unsupported; matching artifact evidence plus material zone can report ready. | Package-level external engine import evidence is not generated. |
| 8. `@lathe/three` loads package evidence and blockers | PASS | `pnpm run build` passes; built-loader probe exposes semantic package fields, `repairHistory`, proxy/unbuilt reason, and backend blocker evidence types; browser inspection loaded the generated package manifest via `?manifest=`. | Real mesh GLB loading remains unproven because the generated package truthfully has no `mesh_glb` sidecar. |
| 9. Viewer inspects meaningful packages truthfully | PASS | Browser inspection at `http://127.0.0.1:5174/?manifest=...` loaded `.tmp_foundry_runtime_probe/pkg/violet_crystal_cluster_a.lthpkg/manifest.json`, showed semantic parts, material slots, external backend blockers, certificate metrics, `mesh_glb_not_in_sidecar_files`, and `visual=not_verified`; screenshot: `lathe-web-viewer-violet-crystal-package.png`. | Real rendered-preview approval is still not verified. |
| 10. `newresearch.md` support | PASS | `newresearch.md` snapshot maps typed op graph, boolean cluster planning, material-zone package evidence, render-evidence schema, category-anchor validation, runtime cooking, and graph repair package evidence to code paths and artifacts. | Production arrangement backend and image-based perceptual scoring remain future product-complete work, not claimed by this remediation. |

Conclusion: the remediation tasklist is patched end-to-end under the no-test/no-full-build constraint. This does not mean the assets are visually approved, product-complete, game-ready, or backed by a production arrangement/perceptual-render backend; it means every audit finding now has code plus truthful artifact/report/inspection evidence or an explicit non-claim boundary.
