# Wonder Readiness Evidence

This ledger records evidence for Project Wonder readiness. A task stays
unchecked in `wonder-tasks.md` until the matching evidence is recorded from a
clean checkout or from another explicitly described review environment.

## Evidence Rules

- Record commands from the repository root using relative paths.
- Do not copy machine-specific checkout paths into evidence.
- Prefer exact command lines plus concise results over broad claims.
- Separate "present in the working tree" from "validated from a clean checkout".
- Treat dirty-tree checks as local signals only.

## Milestone A Ledger

| Area | Current local state | Evidence state | Next evidence needed |
| --- | --- | --- | --- |
| Phase 0 baseline | Existing Lathe asset compiler workflows were re-run locally and in a Git-backed review snapshot. | Full review-snapshot suite, doctor, smoke, and canonical example checks pass. | Fresh-clone or CI confirmation before alpha promotion. |
| Wonder contract schemas | `schema/dream_brief.schema.json`, `schema/scene_graph.schema.json`, `schema/scene_patch.schema.json`, `schema/render_inspection.schema.json`, `schema/world_memory.schema.json`, `schema/scene_package_manifest.schema.json`, and `schema/scene_plan.schema.json` exist locally. | Focused review-snapshot tests pass. | Continue recording focused evidence as schemas change. |
| Wonder contract helper package | `lathe/wonder/` exists locally and exposes schema loading and validation helpers. | Covered by focused local and review-snapshot Wonder contract tests. | Keep trust-boundary behavior covered as contracts change. |
| `lathe wonder` CLI | Local commands exist for listing schemas, emitting a schema, validating Wonder contracts, decomposing/lowering Dream Briefs, checking brief/scene consistency, checking Scene Graph semantics, and reporting capabilities. | Focused review-snapshot tests prove these commands avoid optional mesh, Blender, provider, and learned-shape imports. | Keep the import guard in focused tests. |
| Alchemist Observatory example | `examples/wonder/alchemist_observatory/` contains a prompt, four contract JSON examples, expected report/manifest examples, and a semantic Scene Graph check target. | All review-snapshot CLI validators pass. | Re-run all validators after example or schema changes. |
| Scene Graph semantic validation | `lathe/scene/` now checks duplicate object IDs, missing object regions, invalid relationship endpoints, unsafe export/build artifact paths, duplicate region/camera/light/material/curiosity/hidden IDs, material bindings, camera/light targets, curiosity/hidden attachments, affordance reveal targets, layout references, curiosity expansion targets, and memory event affected IDs. | Focused review-snapshot tests and CLI check pass. | Keep adding scene-level validators as runtime features land. |
| Dream Brief lowering and consistency | Local deterministic decomposition/lowering and `check-brief-scene` commands exist. | Focused review-snapshot tests and Alchemist Observatory CLI checks pass. | Re-run after lowering or consistency logic changes. |
| Scene package, memory, planning, patching, source bridge, and offline build | Local `lathe scene` package/memory/check/plan/validate/patch/source/build commands exist, with Scene Plan schema and scene quality report generation. | Focused local tests and expanded PowerShell helper pass in the review snapshot. | Run the Bash helper in a POSIX-capable environment. |
| Readiness docs | Overview, contract docs, MVP demo doc, this evidence ledger, status, and glossary now exist locally. | Local docs update only. | Keep docs aligned with checked evidence as Milestone A progresses. |
| Wonder schema reference | `docs/wonder-readiness/schema_reference.md` is generated from the Wonder schemas. | Focused local freshness and docs audits pass. | Re-run the generator and freshness test after schema changes. |
| Wonder validation helper scripts | PowerShell and Bash local validation helpers exist under `scripts/`. | PowerShell helper passed locally. Bash helper was structurally reviewed but not runnable in this Windows environment because local Bash routes to unavailable WSL. | Run the Bash helper in a POSIX-capable environment. |

## Git-Backed Review Snapshot Evidence

Recorded on 2026-04-29 for the recommended-next-PR scope and Phase 0 baseline.

Environment description: a disposable Git-initialized review snapshot was copied
from the current working tree with Git metadata, virtualenvs, cache folders,
test-output folders, and build-output folders omitted. The snapshot was locally
committed so Git-dependent hygiene tests could use `git ls-files`. This is not
a remote fresh clone or CI run; it is the explicitly described review
environment used to decide which task boxes can move.

Baseline captured before the review snapshot:

- Branch: `main`.
- Commit: `e94a202a3655fb460f4412b47814158564a533da`.
- Python: `3.13.13`.
- OS: `Windows-10-10.0.19045-SP0`.
- Dirty entries before this pass: 91.
- Working-tree classification:
  `docs/wonder-readiness/phase0_working_tree_classification.md`.

Recommended-next-PR validation:

| Command | Result |
| --- | --- |
| `python -m pytest -q tests/unit/test_wonder_contracts.py` | Passed in the review snapshot: 11 passed. |
| `python -m pytest -q tests/unit/test_exception_inventory.py tests/unit/test_docs_static_audit.py tests/unit/test_marker_inventory.py tests/unit/test_trust_boundaries.py` | Passed in the review snapshot: 28 passed. |
| `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | Passed in the review snapshot: 37 passed. |
| `python -m lathe.cli wonder validate-brief examples/wonder/alchemist_observatory/dream_brief.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder validate-scene examples/wonder/alchemist_observatory/scene_graph.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder check-scene-graph examples/wonder/alchemist_observatory/scene_graph.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder check-brief-scene examples/wonder/alchemist_observatory/dream_brief.json examples/wonder/alchemist_observatory/scene_graph.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder validate-patch examples/wonder/alchemist_observatory/scene_patch_more_sacred.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder validate-render-inspection examples/wonder/alchemist_observatory/render_inspection.example.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder validate-world-memory examples/wonder/alchemist_observatory/world_memory.json` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli wonder capabilities` | Passed in the review snapshot and emitted `lathe.wonder_capabilities.v1`. |
| `python -m lathe.cli wonder status` | Passed in the review snapshot and emitted `lathe.wonder_status.v1` with alpha gate blocked. |

Phase 0 validation:

| Command | Result |
| --- | --- |
| `python -m pytest -q` | Passed in the review snapshot: 1651 passed, 19 skipped, 127 deselected, 1 warning, 62 subtests passed. |
| `python -m lathe.cli doctor --json` | Passed in the review snapshot. |
| `python -c "import trimesh; print(trimesh.__version__)"` | Passed in the review snapshot: `4.11.5`. |
| `python -m lathe.cli doctor` | Passed in the review snapshot; no `ModuleNotFoundError` for `trimesh`. |
| `python -m lathe.cli shape-providers` | Passed in the review snapshot and listed the configured shape-provider adapters. |
| `python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json` | Passed in the review snapshot. The reference-conditioned and VGGT providers were available; the configured Hunyuan endpoint was not running. |
| `powershell -ExecutionPolicy Bypass -File scripts/lathe_smoke.ps1` | Passed in the review snapshot with 29 smoke tests passing and a certified courier drone build. |
| `python -m lathe.cli normalize examples/courier_drone.lth` | Passed in the review snapshot. |
| `python -m lathe.cli check examples/courier_drone.lth` | Passed in the review snapshot with `ok: true`. |
| `python -m lathe.cli plan examples/courier_drone.lth courier_drone` | Passed in the review snapshot. |
| `python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist` | Passed in the review snapshot and certified the generated asset. |
| `python -m lathe.cli build examples/tutorial_bookshelf.lth bookshelf --out .tmp_tests/phase0_generate` | Passed in the review snapshot and certified a generate example. |
| `python -m lathe.cli build examples/reconstruct_courier_from_mesh.lth reconstruct_courier_from_mesh --out .tmp_tests/phase0_reconstruct` | Passed in the review snapshot and certified a reconstruct example. |
| `powershell -ExecutionPolicy Bypass -File scripts/lathe_wonder_validate.ps1 -WorkDir .tmp_tests/wonder_validate_recommended_next_pr_phase0` | Passed in the review snapshot: 190 focused tests passed, schema reference regenerated, Wonder capabilities/status emitted, Alchemist Observatory contracts and scene/package/proxy lanes exercised, and Roblox profile/manifest validation passed. |

POSIX status:

| Command | Result |
| --- | --- |
| `bash --version` | Blocked in this Windows environment: local `bash` routes to WSL, but `/bin/bash` is unavailable. |

The Phase 0 baseline release note is recorded in
`docs/wonder-readiness/pre_wonder_baseline.md`.

## Local Docs Evidence

Recorded for this docs-focused update:

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-28 | `python -m pytest tests/unit/test_docs_static_audit.py tests/unit/test_marker_inventory.py -q` | Passed locally after the Wonder readiness docs update. |

This local docs audit does not prove Milestone A is complete. It only shows that
the public docs and marker inventory checks pass for the docs surface touched by
this update.

## Local Milestone A Evidence

Recorded for the first Milestone A implementation pass:

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-28 | `python -m pytest tests/unit/test_exception_inventory.py -q` | Passed locally: 2 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | Passed locally: 16 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_exception_inventory.py tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_docs_static_audit.py tests/unit/test_marker_inventory.py` | Passed locally: 41 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q` | Passed locally after CLI reference regeneration: 1330 passed, 10 skipped, 127 deselected, 2 warnings. |
| 2026-04-28 | `python -m ruff check lathe\cli\__init__.py lathe\cli\wonder_cmd.py lathe\scene tests\unit\test_wonder_contracts.py tests\unit\test_wonder_scene_validation.py tests\unit\test_cli_errors.py` | Passed locally. |
| 2026-04-28 | `python -m lathe.cli doctor --json` | Passed locally. Base dependencies, including `trimesh`, were available; optional learned providers varied by environment. |
| 2026-04-28 | `python -m lathe.cli shape-providers` | Passed locally and listed Hunyuan, reference-conditioned, and VGGT provider adapters. |
| 2026-04-28 | `python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/auto_learned.json` | Passed locally. Reference-conditioned provider was available; Hunyuan endpoint was not running in this environment. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/lathe_smoke.ps1` | Passed locally. |
| 2026-04-28 | `python -m lathe.cli normalize examples/courier_drone.lth` | Passed locally. |
| 2026-04-28 | `python -m lathe.cli check examples/courier_drone.lth` | Passed locally with `ok: true`. |
| 2026-04-28 | `python -m lathe.cli plan examples/courier_drone.lth courier_drone` | Passed locally. |
| 2026-04-28 | `python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist` | Passed locally and certified the generated asset. |
| 2026-04-28 | `python -m lathe.cli build examples/reconstruct_courier_from_mesh.lth reconstruct_courier_from_mesh --out tmp_lathe_phase0_reconstruct` | Passed locally and certified the reconstruct example. |
| 2026-04-28 | `python -m lathe.cli build examples/tutorial_bookshelf.lth bookshelf --out tmp_lathe_phase0_generate` | Passed locally and certified a generate example. |
| 2026-04-28 | `python -m lathe.cli wonder capabilities` | Passed locally and emitted `lathe.wonder_capabilities.v1` with repo-relative schema paths. |
| 2026-04-28 | `python -m lathe.cli wonder validate-brief examples/wonder/alchemist_observatory/dream_brief.json` | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-28 | `python -m lathe.cli wonder validate-scene examples/wonder/alchemist_observatory/scene_graph.json` | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-28 | `python -m lathe.cli wonder check-scene-graph examples/wonder/alchemist_observatory/scene_graph.json` | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-28 | `python -m lathe.cli wonder validate-patch examples/wonder/alchemist_observatory/scene_patch_more_sacred.json` | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-28 | `python -m lathe.cli wonder validate-render-inspection examples/wonder/alchemist_observatory/render_inspection.example.json` | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-28 | `git diff --check` | Passed locally; Git reported an unrelated line-ending warning for `lathe/cli/surface_cmd.py`. |
| 2026-04-28 | `python scripts/generate_cli_reference.py` | Regenerated `docs/cli_reference.md` after adding `lathe wonder capabilities`. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py -q` | Passed locally: 3 passed, 1 warning. |
| 2026-04-28 | `python scripts/generate_wonder_schema_reference.py` | Passed locally and regenerated `docs/wonder-readiness/schema_reference.md`. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_wonder_schema_reference_docs.py tests/unit/test_language_schema_reference_docs.py tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py` | Passed locally: 33 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | Passed locally after capabilities and broader Scene Graph checks: 18 passed, 1 warning. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/lathe_wonder_validate.ps1` | Passed locally. Script reported 29 focused tests passed and every Alchemist Observatory Wonder command returned `ok: true`. |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_cli.py tests/unit/test_scene_planner.py tests/unit/test_wonder_contracts.py tests/unit/test_wonder_schema_reference_docs.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command -q` | Passed locally after adding Scene Plan contract integration and `lathe scene check/plan/validate`: 24 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py -q` | Passed locally after regenerating CLI reference: 3 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_marker_inventory.py` | Passed locally: 3 passed, 1 warning. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/lathe_wonder_validate.ps1` | Passed locally after expanding the helper to cover Dream Brief decomposition, brief/scene consistency, `lathe scene check`, `lathe scene plan`, Scene Plan validation, scene quality validation, and scene package inspect/validate. Script reported 92 focused tests passed. |
| 2026-04-28 | `python -m pytest tests/unit/test_wonder_scene_validation.py tests/unit/test_wonder_memory.py tests/unit/test_scene_planner.py tests/unit/test_scene_ids.py -q` | Passed locally after review fixes for schema-declared Scene Graph refs, World Memory branch continuity, digest-backed Scene Plan task IDs, and scene ID helper prefixes: 50 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_source_roundtrip.py tests/unit/test_scene_executor.py -q` | Passed locally after integrating JSON-first scene source bridge and offline package build: 13 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_patch.py -q` | Passed locally after integrating continuity-aware Scene Patch application and CLI preview/write paths: 10 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_wonder_contracts.py tests/unit/test_scene_patch.py tests/unit/test_scene_source_roundtrip.py tests/unit/test_scene_executor.py -q` | Passed locally after updating capability flags for scene source bridge, patch application, and offline scene build: 32 passed, 1 warning. |
| 2026-04-28 | `python -m ruff check lathe\wonder\contracts.py tests\unit\test_wonder_contracts.py scripts\generate_wonder_schema_reference.py lathe\scene lathe\cli\scene_cmd.py` | Passed locally. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_marker_inventory.py tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path` | Passed locally: 3 passed, 1 warning. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/lathe_wonder_validate.ps1` | Passed locally after expanding the helper to cover Scene Patch preview/apply, source bridge generation/roundtrip, and offline Scene Package build/validate. Script reported 115 focused tests passed and every checked Alchemist Observatory command returned `ok: true`. |
| 2026-04-28 | `python scripts/generate_cli_reference.py` | Regenerated `docs/cli_reference.md` after integrating scene patch/source/build commands. |
| 2026-04-28 | `python scripts/generate_wonder_schema_reference.py` | Regenerated `docs/wonder-readiness/schema_reference.md` after capability/docs updates. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py tests/unit/test_wonder_schema_reference_docs.py -q` | Passed locally after regenerating CLI and Wonder schema references: 5 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command -q` | Passed locally after integrating scene patch/source/build leaf commands: 1 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q` | Passed locally after integrating scene patch, source bridge, offline scene build, expanded Wonder helper coverage, and refreshed CLI/schema docs: 1449 passed, 10 skipped, 127 deselected, 2 warnings. |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_executor.py tests/unit/test_scene_cli.py -q` | Passed locally after tightening proxy PNG/GLB artifact expectations: 18 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command -q` | Passed locally after confirming the scene/wonder leaf-command matrix still matches the parser: 1 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_marker_inventory.py` | Passed locally after the proxy artifact docs update: 3 passed, 1 warning. |

The Wonder contract test suite includes a subprocess import guard that blocks
`trimesh`, Blender, Torch, and provider modules while running the lightweight
`lathe wonder` commands. That is local proof that the Wonder contract commands
do not need optional runtime dependencies.

## Local Phase 33-36 Demo Evidence

Recorded for the current docs/demo/evidence pass:

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/demo_wonder_seed_scene.ps1 -OutDir tmp_wonder_seed_demo` | Passed locally after proxy render/export integration and the export-task contract fix. The script validated the Dream Brief and authored Scene Graph, lowered the Dream Brief to a fallback Scene Graph, generated and roundtripped the JSON-first scene source bridge, planned and validated the preview Scene Plan, assembled Scene Assembly IR, validated World Memory, ran scene quality validators, built and validated proxy preview packages for the authored, patched, and curiosity-expanded scenes, validated the Render Inspection contract, ran offline render-inspection repair flow, applied the `more_sacred` Scene Patch, expanded the `opened_archive` curiosity anchor, and wrote `34_proxy_artifact_evidence.json` after verifying planned render-task coverage, planned GLB export-task matching, proxy PNG and declared GLB artifact magic bytes, and GLB identity status. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts/demo_wonder_seed_scene.ps1 -OutDir tmp_codex_wonder_demo_proxy2` | Passed locally. The script validated the Dream Brief and authored Scene Graph, lowered the Dream Brief to a fallback Scene Graph, generated and roundtripped the JSON-first scene source bridge, planned and validated the preview Scene Plan, assembled Scene Assembly IR, validated World Memory, ran scene quality validators, built and validated proxy preview packages for the authored, patched, and curiosity-expanded scenes, validated the Render Inspection contract, ran offline render-inspection repair flow, applied the `more_sacred` Scene Patch, expanded the `opened_archive` curiosity anchor, and wrote `34_proxy_artifact_evidence.json` after verifying proxy PNG and GLB artifact magic bytes. |
| 2026-04-28 | `bash scripts/demo_wonder_seed_scene.sh --dry-run` | Not run successfully in this Windows environment. Local `bash` routes to WSL, but `/bin/bash` is unavailable, so POSIX validation remains open. |

The demo evidence is intentionally deterministic and proxy-based. It does not
claim real Blender renders, before/after image comparisons, USD/Blender exports,
Roblox exports, or external viewer validation. The demo writes
`tmp_wonder_seed_demo/_demo_evidence/34_proxy_artifact_evidence.json`
to record checked proxy PNG render paths, planned render/export task counts,
the checked proxy GLB path, and GLB identity status next to the local command
outputs.

## Local Proxy Render/Export Evidence

Recorded during the proxy artifact integration pass:

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_executor.py tests/unit/test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_wonder_contracts.py::test_wonder_capabilities_are_machine_readable -q` | Passed locally: 9 passed, 1 warning. |
| 2026-04-28 | `python -m pytest tests/unit/test_scene_executor.py tests/unit/test_scene_cli.py::test_scene_build_cli_package_inspect_tracks_proxy_artifacts_when_present tests/unit/test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests/unit/test_scene_planner.py::test_preview_and_final_modes_have_distinct_budgets_and_render_plans tests/unit/test_exception_inventory.py::test_broad_exception_handlers_are_tracked -q` | Passed locally after the export-task contract fix: 13 passed, 1 warning. This covers no-GLB scenes, custom declared GLB package paths, fail-closed GLB identity validation, final render pass alignment, and the broad-exception inventory. |
| 2026-04-29 | `python -m pytest tests/unit/test_wonder_contracts.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command -q` | Passed locally after adding `lathe wonder status`: 12 passed, 1 warning. |
| 2026-04-29 | `python -m lathe.cli wonder status` | Passed locally and emitted `lathe.wonder_status.v1` with alpha gate blocked, local evidence state, blocker list, and evidence pointers. |
| 2026-04-29 | `python -m pytest tests/unit/test_scene_io.py tests/unit/test_wonder_contracts.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command -q` | Passed locally with normal filesystem permissions after adding unique same-directory atomic scene writes, bounded Windows replace retry, per-target write locking, and broader optional-dependency import guards for pure Wonder validators: 14 passed, 1 warning. |
| 2026-04-28 | `python -m ruff check lathe\scene\artifacts.py lathe\scene\executor.py lathe\scene\__init__.py lathe\cli\scene_cmd.py lathe\wonder\contracts.py lathe\wonder\llm.py tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py tests\unit\test_cli_errors.py tests\unit\test_wonder_contracts.py` | Passed locally after import/export sorting and render-pass lint fixes. |
| 2026-04-29 | `python -m ruff check lathe\wonder\contracts.py lathe\wonder\__init__.py lathe\cli\wonder_cmd.py tests\unit\test_wonder_contracts.py tests\unit\test_cli_errors.py` | Passed locally after adding `lathe wonder status`; Ruff reported cache-write warnings in this sandbox only. |
| 2026-04-28 | `python -m ruff check lathe\scene lathe\wonder lathe\cli\scene_cmd.py scripts\generate_wonder_schema_reference.py tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py tests\unit\test_scene_planner.py tests\unit\test_cli_errors.py tests\unit\test_wonder_contracts.py tests\unit\test_wonder_llm.py` | Passed locally after the export-task contract fix. |
| 2026-04-28 | `python -m pytest tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py tests/unit/test_wonder_schema_reference_docs.py -q` | Passed locally after schema reference regeneration: 5 passed, 1 warning. |
| 2026-04-28 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | Passed locally after the evidence update: 4 passed, 1 warning. |
| 2026-04-28 | `python scripts\generate_cli_reference.py` | Regenerated `docs/cli_reference.md` after adding `lathe scene render` and `lathe scene export`. |
| 2026-04-28 | `python scripts\generate_wonder_schema_reference.py` | Regenerated `docs/wonder-readiness/schema_reference.md` after capability/docs refresh. |
| 2026-04-28 | `scripts/lathe_wonder_validate.ps1` and `scripts/lathe_wonder_validate.sh` update | Added standalone proxy `lathe scene render` and `lathe scene export` steps before the package build; execution evidence is recorded only after the helper is rerun. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1` | Passed locally after the proxy artifact integration. The helper reported 183 focused tests passed, regenerated the Wonder schema reference, exercised `lathe scene render`, `lathe scene export`, proxy Scene Package build/validate, repair, curiosity expansion, source roundtrip, benchmark report, style/layout/camera planning, provenance/game-readiness validators, and Roblox manifest validation. |
| 2026-04-28 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1` | Passed locally after the export-task contract fix and helper hardening. The helper reported 186 focused tests passed, regenerated the Wonder schema reference, exercised standalone proxy render/export, proxy Scene Package build/validate with three planned render tasks including topdown debug, checked planned render coverage, checked planned GLB export-task matching and GLB identity status, then exercised repair, curiosity expansion, source roundtrip, benchmark report, style/layout/camera planning, provenance/game-readiness validators, and Roblox manifest validation. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1` | Passed locally after adding `lathe wonder status` to the helper and updating scene writers to use visible `.tmp` sidecar names for atomic writes. The helper reported 188 focused tests passed, emitted `lathe.wonder_status.v1`, regenerated the Wonder schema reference, exercised standalone proxy render/export, proxy Scene Package build/validate, GLB identity checks, repair, curiosity expansion, source roundtrip, benchmark report, style/layout/camera planning, provenance/game-readiness validators, and Roblox manifest validation. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_heartbeat_main` | Passed locally with an explicit per-run work directory. The helper reported 190 focused tests passed, emitted `lathe.wonder_status.v1`, regenerated the Wonder schema reference, exercised isolated proxy render/export/package outputs, GLB identity checks, repair, curiosity expansion, source roundtrip, benchmark report, style/layout/camera planning, provenance/game-readiness validators, and Roblox manifest validation. |
| 2026-04-29 | `python -m pytest -q` | Passed locally after adding atomic scene artifact writes, per-run Wonder helper work directories, expanded import-guard coverage, and narrowed cleanup catches: 1660 passed, 10 skipped, 127 deselected, 2 warnings. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_heartbeat_final` | Passed locally after the final atomic I/O cleanup change. The helper reported 190 focused tests passed, emitted `lathe.wonder_status.v1`, regenerated the Wonder schema reference, exercised isolated proxy render/export/package outputs, GLB identity checks, repair, curiosity expansion, source roundtrip, benchmark report, style/layout/camera planning, provenance/game-readiness validators, and Roblox manifest validation. |
| 2026-04-28 | `python -m pytest -q` | Passed locally after the export-task contract fix: 1655 passed, 10 skipped, 127 deselected, 2 warnings. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_wonder_scene_validation.py tests/unit/test_scene_planner.py tests/unit/test_scene_executor.py tests/unit/test_scene_patch.py tests/unit/test_scene_versioning.py tests/unit/test_scene_repair.py tests/unit/test_scene_style_layout.py tests/unit/test_scene_validators.py tests/unit/test_scene_game_readiness_provenance.py tests/unit/test_scene_roblox.py tests/unit/test_scene_bench.py tests/unit/test_wonder_examples_catalog.py tests/unit/test_wonder_llm.py tests/unit/test_wonder_memory.py tests/unit/test_wonder_service_contracts.py tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | Passed locally after the Wonder task checklist audit: 241 passed, 1 warning. This supports the audited task-box state in `wonder-tasks.md` while keeping POSIX, final renderer/export, fresh-clone, and alpha-gate items open. |

## Local Wave 1 Alpha Gate Harness Evidence

Recorded on 2026-04-29 for the first blocker-removal Wave 1 implementation
slice. This is local evidence from the current working tree. It adds the
machine-readable core harness only; it does not execute Blender, Roblox Studio,
or an external viewer. Missing POSIX, Roblox Studio, and external viewer lanes
are reported as optional skipped/nonblocking in core mode.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_env_probe.py tests/unit/test_wonder_evidence_traceability.py tests/unit/test_wonder_alpha_gate.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | `.tmp_tests/wonder_wave1_focused_tests.txt` | passed | Passed locally: 10 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\wonder\env.py lathe\wonder\evidence.py lathe\wonder\readiness.py lathe\wonder\__init__.py lathe\cli\wonder_cmd.py tests\unit\test_wonder_env_probe.py tests\unit\test_wonder_evidence_traceability.py tests\unit\test_wonder_alpha_gate.py tests\unit\test_cli_errors.py` | `.tmp_tests/wonder_wave1_ruff.txt` | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m lathe.cli wonder env-probe --out .tmp_tests/wonder_env_probe.json` | `.tmp_tests/wonder_env_probe.json` | passed | Passed locally with `blocking_missing: []`; POSIX, Roblox Studio, and external viewer were optional missing/nonblocking. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs/wonder-readiness/evidence.md --out .tmp_tests/wonder_evidence_traceability.json` | `.tmp_tests/wonder_evidence_traceability.json` | passed | Passed locally with 677 checked tasks covered by the existing task-box audit decision and no diagnostics. |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate` | `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json` | passed | Passed locally with `core_alpha_gate: passed`, `blocking_missing_runtimes: []`, and optional POSIX/Roblox/external-viewer lanes skipped nonblocking. |

## Local Wave 2 Mutation Safety Evidence

Recorded on 2026-04-29 for the Wave 2 "Make Mutation Safe" implementation
slice. This is local JSON-only evidence. It does not execute Blender, Roblox
Studio, provider runtimes, or external viewers.

One intermediate helper run surfaced expected documentation drift after adding
`schema/scene_history.schema.json` and recursive World Memory metadata values.
`docs/wonder-readiness/schema_reference.md` was regenerated before the final
validation pass.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_memory.py tests/unit/test_scene_patch.py tests/unit/test_scene_history.py tests/unit/test_scene_rollback.py` | stdout | passed | Passed locally: 36 passed, 1 warning. Covers idempotent memory append, redaction, rejected patch recording, patch history, branch history, rollback restoration, rollback hash mismatch, and Wonder CLI append/redact/apply/rollback/branch paths. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 1 passed, 1 warning. Confirms the new Wonder leaf commands are represented in parser coverage. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | docs/wonder-readiness/schema_reference.md | passed | Regenerated the Wonder schema reference after adding `scene_history` and recursive World Memory metadata. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 2 passed, 1 warning. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_wave2` | .tmp_tests/wonder_validate_wave2 | passed | Passed locally after schema-reference regeneration. The helper reported 196 focused tests passed, regenerated the Wonder schema reference, emitted capabilities/status with `scene_patch_history` and `scene_patch_rollback`, and completed the existing proxy/package/Roblox-manifest contract lanes without requiring Blender or Roblox execution. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | docs/cli_reference.md | passed | Regenerated the CLI reference after adding the Wave 2 Wonder commands. |
| 2026-04-29 | `python -m pytest tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py -q` | stdout | passed | Passed locally: 3 passed, 1 warning. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals` | stdout | passed | Passed locally: 3 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\scene\memory.py lathe\scene\history.py lathe\scene\rollback.py lathe\cli\wonder_cmd.py lathe\wonder\contracts.py tests\unit\test_wonder_memory.py tests\unit\test_scene_patch.py tests\unit\test_scene_history.py tests\unit\test_scene_rollback.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally after import cleanup: all checks passed. |

## Local Wave 3 Before/After Comparison Evidence

Recorded on 2026-04-29 for the Wave 3 "Make Visual Iteration Provable"
implementation slice. This is local proxy-render evidence only. It does not
execute Blender, Roblox Studio, POSIX shell, or an external viewer in core
mode. Blender and Roblox lanes are explicitly reported as skipped/nonblocking
by `wonder demo-before-after`.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_scene_camera_lock.py tests/unit/test_scene_compare.py tests/unit/test_scene_history.py` | stdout | passed | Passed locally: 10 passed, 1 warning. Covers deterministic camera locking, missing-camera diagnostics, PNG comparison, dimension mismatch failure, camera-lock hash inclusion, and branch history comparison-report arrays. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_before_after_cli.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers `wonder lock-camera`, `wonder compare-renders`, `wonder demo-before-after`, and parser coverage for new Wonder leaf commands. |
| 2026-04-29 | `python -m lathe.cli wonder demo-before-after examples/wonder/alchemist_observatory --out .tmp_tests/wonder_before_after_wave3` | `.tmp_tests/wonder_before_after_wave3` | passed | Passed locally with `ok: true`. Generated `before/scene_graph.json`, `before/renders/camera_reveal/beauty.png`, `after/scene_graph.json`, `after/renders/camera_reveal/beauty.png`, `comparisons/camera_lock.json`, `comparisons/render_comparison.json`, `history/scene_history.json`, `reports/before_after_report.json`, and `reports/before_after_report.md`. Blender and Roblox lanes were skipped and nonblocking in core mode. |
| 2026-04-29 | `python -m lathe.cli wonder lock-camera examples/wonder/alchemist_observatory/scene_graph.json --camera-id camera_reveal --out .tmp_tests/wonder_before_after_wave3/comparisons/camera_lock.cli.json` | `.tmp_tests/wonder_before_after_wave3/comparisons/camera_lock.cli.json` | passed | Passed locally with `ok: true`, camera `camera_reveal`, and camera hash `sha256:dd1fd0f22a31f9a4228b8dd056496309a908c021cec50e55b70e5063866e3a90`. |
| 2026-04-29 | `python -m lathe.cli wonder compare-renders --before .tmp_tests/wonder_before_after_wave3/before/renders/camera_reveal/beauty.png --after .tmp_tests/wonder_before_after_wave3/after/renders/camera_reveal/beauty.png --camera-lock .tmp_tests/wonder_before_after_wave3/comparisons/camera_lock.cli.json --out .tmp_tests/wonder_before_after_wave3/comparisons/render_comparison.cli.json` | `.tmp_tests/wonder_before_after_wave3/comparisons/render_comparison.cli.json` | passed | Passed locally with `ok: true`, dimensions `640x360`, `changed_pixels: 0`, and `semantic_delta.status: not_evaluated`. |
| 2026-04-29 | `python -m lathe.cli wonder validate-render-comparison examples/wonder/alchemist_observatory/expected/render_comparison.example.json` | stdout | passed | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | docs/wonder-readiness/schema_reference.md | passed | Regenerated the Wonder schema reference after adding `camera_lock` and `render_comparison` schemas. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | docs/cli_reference.md | passed | Regenerated the CLI reference after adding `wonder lock-camera`, `wonder compare-renders`, `wonder demo-before-after`, and schema validators. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_schema_reference_docs.py tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py` | stdout | passed | Passed locally: 5 passed, 1 warning. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_contracts.py::test_wonder_capabilities_are_machine_readable` | stdout | passed | Passed locally: 1 passed, 1 warning. Confirms the expanded Wonder capability payload remains machine-readable. |
| 2026-04-29 | `python -m ruff check lathe\scene\camera_lock.py lathe\scene\compare.py lathe\scene\history.py lathe\scene\__init__.py lathe\cli\wonder_cmd.py lathe\wonder\contracts.py scripts\generate_wonder_schema_reference.py tests\unit\test_scene_camera_lock.py tests\unit\test_scene_compare.py tests\unit\test_scene_history.py tests\unit\test_wonder_before_after_cli.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after the Wave 3 evidence update: 4 passed, 1 warning. |

The default Alchemist Observatory patch currently produces identical proxy
beauty PNG bytes, so the comparison report truthfully records
`changed_pixels: 0` and `semantic_delta.status: not_evaluated`. This is not a
semantic visual-evaluation claim; it only proves the camera-locked proxy
comparison lane and history/report plumbing.

## Local Wave 4 LLM Authoring Evidence

Recorded on 2026-04-29 for the Wave 4 "Make LLM Authoring Usable"
implementation slice. This is deterministic local authoring evidence only. It
does not call an LLM/provider and does not require Blender, Roblox Studio,
POSIX shell, or an external viewer.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_llm.py tests/unit/test_scene_planner.py tests/unit/test_scene_source_diagnostics.py` | stdout | passed | Passed locally: 26 passed, 1 warning. Covers deterministic Scene Plan generation, brief-only reduced-specificity diagnostics, repair playbook inputs, schema-link checks, bad-output fixtures, and generated-source source spans. |
| 2026-04-29 | `python -m lathe.cli wonder generate-scene-plan examples/wonder/alchemist_observatory/dream_brief.json --scene-graph examples/wonder/alchemist_observatory/scene_graph.json --out .tmp_tests/wonder_scene_plan_wave4.json` | `.tmp_tests/wonder_scene_plan_wave4.json` | passed | Passed locally with `ok: true`; output is `lathe.scene_plan.v1` and includes render tasks for `camera_reveal`, `camera_warm_lens_detail`, and `camera_topdown_debug`. |
| 2026-04-29 | `python -m lathe.cli wonder repair-playbook --diagnostics docs/llm/bad_outputs/invalid_patch_unknown_target.expected_diagnostics.json --out .tmp_tests/wonder_repair_playbook_wave4.json` | `.tmp_tests/wonder_repair_playbook_wave4.json` | passed | Passed locally with `ok: true`; output is `lathe.llm_repair_playbook.v1` with one deterministic repair step for `SP1501`. |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate_wave4` | `.tmp_tests/wonder_alpha_gate_wave4/reports/final_readiness_report.json` | passed | Passed locally with `core_alpha_gate: passed` and `blocking_missing_runtimes: []`. Core mode reported POSIX, Roblox Studio, and external viewer lanes as optional skipped/nonblocking. |
| 2026-04-29 | `python -m lathe.cli wonder validate-plan examples/wonder/alchemist_observatory/expected/scene_plan.example.json` | stdout | passed | Passed locally with `ok: true` after writing the Wave 4 expected Scene Plan artifact. |
| 2026-04-29 | `python -m lathe.cli wonder validate-llm-repair-playbook .tmp_tests/wonder_repair_playbook_wave4.json` | stdout | passed | Passed locally with `ok: true` and no diagnostics. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | docs/wonder-readiness/schema_reference.md | passed | Regenerated the Wonder schema reference after adding `llm_repair_playbook` and Scene Plan diagnostic repair hints. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | docs/cli_reference.md | passed | Regenerated the CLI reference after adding `wonder generate-scene-plan`, `wonder repair-playbook`, and `wonder validate-llm-repair-playbook`. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_wonder_schema_reference_docs.py tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py` | stdout | passed | Passed locally: 6 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\wonder\llm.py lathe\wonder\__init__.py lathe\wonder\contracts.py lathe\scene\planner.py lathe\scene\source.py lathe\scene\source_diagnostics.py lathe\scene\__init__.py lathe\cli\wonder_cmd.py lathe\cli\scene_cmd.py scripts\generate_wonder_schema_reference.py tests\unit\test_wonder_llm.py tests\unit\test_scene_planner.py tests\unit\test_scene_source_diagnostics.py tests\unit\test_cli_errors.py --fix` | stdout | passed | Passed locally after import/style cleanup; Ruff fixed two ordering/style issues. |
| 2026-04-29 | `python -m ruff check lathe\wonder\llm.py lathe\wonder\__init__.py lathe\wonder\contracts.py lathe\scene\planner.py lathe\scene\source.py lathe\scene\source_diagnostics.py lathe\scene\__init__.py lathe\cli\wonder_cmd.py lathe\cli\scene_cmd.py scripts\generate_wonder_schema_reference.py tests\unit\test_wonder_llm.py tests\unit\test_scene_planner.py tests\unit\test_scene_source_diagnostics.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after the Wave 4 evidence update: 4 passed, 1 warning. |

## Local Wave 5 Golden Example Evidence

Recorded on 2026-04-29 for the Wave 5 "Make Examples Golden"
implementation slice. This is deterministic local/proxy example evidence only.
It does not execute Blender, Roblox Studio, POSIX shell, or an external viewer.
Every Wonder example keeps `.lth` scene source truthfully deferred through
`scene_source_status.json`, and the deferral is nonblocking outside strict
source mode.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples/wonder --out docs/wonder-readiness/20_example_catalog.json --write-missing-proxy-evidence` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md`, and missing golden fixture artifacts under `examples/wonder/*/` | passed | Passed locally with 5 examples passed, 0 failed, and 5 nonblocking `scene_source` deferrals. Wrote missing prompts, World Memory, Scene Patch, Render Inspection, expected Scene Plan, Wonder report, scene manifest, render comparison, evidence traceability, preview evidence, and scene-source deferral artifacts where needed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_examples_catalog.py` | stdout | passed | Passed locally: 11 passed, 1 warning. Covers required golden files, `validate-example`, `catalog-examples`, prompt presence, World Memory validation, applicable Scene Patch fixtures, proxy-only preview evidence, truthful scene-source deferral, strict/deferred CLI behavior, catalog docs, and expected Scene Plan determinism. |
| 2026-04-29 | `python -m lathe.cli wonder validate-example examples/wonder/alchemist_observatory` | stdout | passed | Passed locally with `ok: true`, no diagnostics, valid Scene Patch, valid Render Inspection, valid World Memory, valid expected reports, and a nonblocking `scene_source` deferral. |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples/wonder --out docs/wonder-readiness/20_example_catalog.json` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md` | passed | Passed locally with 5 examples passed, 0 failed, and 5 nonblocking `scene_source` deferrals. |
| 2026-04-29 | `Get-ChildItem examples/wonder -Directory | Sort-Object Name | ForEach-Object { python -m lathe.cli wonder validate-example $_.FullName }` | stdout | passed | Passed locally for `abandoned_roblox_mall`, `alchemist_observatory`, `desert_oracle_shrine`, `mountain_lightning_city`, and `underwater_train_station`. |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate_wave5` | `.tmp_tests/wonder_alpha_gate_wave5/reports/final_readiness_report.json` | passed | Passed locally with `core_alpha_gate: passed`, no blocking missing runtimes, and POSIX/Roblox Studio/external-viewer lanes optional/nonblocking in core mode. This confirms Wave 5 did not regress the existing alpha-gate skeleton. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `wonder validate-example` and `wonder catalog-examples`. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py` | stdout | passed | Passed locally: 4 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\wonder\examples.py lathe\wonder\__init__.py lathe\wonder\readiness.py lathe\cli\wonder_cmd.py tests\unit\test_wonder_examples_catalog.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after the Wave 5 evidence update: 4 passed, 1 warning. |

## Local Wave 6 CI And Final Report Evidence

Recorded on 2026-04-29 for the Wave 6 "Make CI/Reports Final"
implementation slice. This is deterministic local/core evidence plus optional
runtime lane reporting. Blender was available locally and only probed; no
Blender render/export execution is claimed. Roblox tooling was unavailable and
was skipped nonblocking. Hypothesis was not installed in this environment, so
the Wonder fuzz file skipped with an explicit pytest skip reason.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_alpha_gate.py tests/unit/test_wonder_readiness_report.py tests/unit/test_wonder_examples_catalog.py tests/unit/test_wonder_golden_snapshots.py tests/fuzz/test_wonder_contract_fuzz.py` | stdout | passed | Passed locally: 20 passed, 1 skipped, 1 warning. The skipped fuzz module reported `Hypothesis is required for Wonder fuzz tests`. |
| 2026-04-29 | `python scripts/ci_wonder_fast.py` | `.tmp_tests/wonder_ci_fast/report.json` | passed | Passed locally. The script ran the deterministic Wonder focused test set and alpha gate: 102 tests passed inside the script, then the alpha gate passed. |
| 2026-04-29 | `python scripts/ci_wonder_examples.py` | `.tmp_tests/wonder_ci_examples/report.json` and `.tmp_tests/wonder_ci_examples/example_catalog.json` | passed | Passed locally. Catalog validation and every `examples/wonder/*` fixture passed with scene-source deferral recorded as nonblocking. |
| 2026-04-29 | `python scripts/ci_wonder_optional_blender.py` | `.tmp_tests/wonder_ci_optional_blender/report.json` | passed | Passed locally as an optional probe lane. Blender 5.0.1 was available and `lathe.cli probe-blender` passed; no Blender render/export evidence is claimed. |
| 2026-04-29 | `python scripts/ci_wonder_optional_roblox.py` | `.tmp_tests/wonder_ci_optional_roblox/report.json` | passed | Passed locally with `status: skipped`, `reason: Roblox tooling not available`, and `blocking: false`. |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests/wonder_alpha_gate` | `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json` and `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.md` | passed | Passed locally with `core_alpha_gate: passed`, `blocking_missing_runtimes: []`, `alpha_decision_ready: true`, and remaining human decision `Approve Project Wonder alpha gate.` Supporting reports were written for evidence traceability, benchmark, security, performance, contracts, CLI, examples, and environment. |
| 2026-04-29 | `python -m lathe.cli wonder readiness-report --out docs/wonder-readiness/final_readiness_report.md` | `docs/wonder-readiness/final_readiness_report.md` and `docs/wonder-readiness/final_readiness_report.json` | passed | Passed locally and refreshed the public readiness handoff from the alpha-gate bundle. |
| 2026-04-29 | `python -m lathe.cli wonder status` and task/doc reconciliation pass | `lathe.wonder_status.v1`, `docs/wonder-readiness/status.md`, `wonder-tasks.md`, `docs/wonder-readiness/final_readiness_report.md` | passed | Reconciled truth drift after Wave 6: machine status, status docs, final report, and task boxes now distinguish the locally passed deterministic core/proxy alpha gate from full Wonder runtime readiness, which remains blocked by hosted CI/clean evidence and optional runtime lanes when in scope. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `wonder readiness-report`. |
| 2026-04-29 | `python -m ruff check lathe\wonder\reports.py lathe\wonder\readiness.py lathe\wonder\env.py lathe\wonder\__init__.py lathe\cli\wonder_cmd.py scripts\ci_wonder_fast.py scripts\ci_wonder_examples.py scripts\ci_wonder_optional_blender.py scripts\ci_wonder_optional_roblox.py tests\unit\test_wonder_alpha_gate.py tests\unit\test_wonder_readiness_report.py tests\unit\test_wonder_golden_snapshots.py tests\unit\test_cli_errors.py tests\fuzz\test_wonder_contract_fuzz.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py` | stdout | passed | Passed locally: 4 passed, 1 warning. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after the Wave 6 docs/evidence update: 4 passed, 1 warning. |

## Local Phase 1 Contract Closure Evidence

Recorded on 2026-04-29 for the remaining Phase 1 contract-schema tasks. This
is local repository evidence, not clean-checkout or hosted CI proof.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_scene_executor.py` | stdout | passed | Passed locally: 22 passed, 1 warning. Covers `scene_manifest` and `wonder_report` schema registration, committed example validation, negative fixtures, roundtrip fixtures, and executor-written report validation. |
| 2026-04-29 | `python -m lathe.cli wonder validate-scene-manifest examples/wonder/alchemist_observatory/expected/scene_manifest.example.json` | stdout | passed | Passed locally with `ok: true`, contract `scene_manifest`, and no diagnostics. |
| 2026-04-29 | `python -m lathe.cli wonder validate-wonder-report examples/wonder/alchemist_observatory/expected/wonder_report.example.json` | stdout | passed | Passed locally with `ok: true`, contract `wonder_report`, and no diagnostics. |
| 2026-04-29 | `python scripts/generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding `scene_manifest` and `wonder_report`. |
| 2026-04-29 | `python scripts/generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `wonder validate-scene-manifest` and `wonder validate-wonder-report`. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_contracts.py tests/unit/test_scene_executor.py tests/unit/test_wonder_examples_catalog.py tests/unit/test_wonder_schema_reference_docs.py tests/unit/test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests/unit/test_cli_reference_docs.py tests/golden/test_cli_help_snapshots.py` | stdout | passed | Passed locally: 39 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\wonder\contracts.py lathe\wonder\examples.py lathe\cli\wonder_cmd.py scripts\generate_wonder_schema_reference.py tests\unit\test_wonder_contracts.py tests\unit\test_scene_executor.py tests\unit\test_wonder_schema_reference_docs.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after the Phase 1 contract evidence update: 4 passed, 1 warning. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_phase1_contracts` | `.tmp_tests\wonder_validate_phase1_contracts` | passed | Passed locally after adding the expected Scene Manifest and Wonder Report validators to the helper. The helper reported 208 focused tests passed and exercised the existing proxy package, render, export, repair, curiosity, source roundtrip, benchmark, provenance, game-readiness, and Roblox manifest lanes. |

## Local Phase 7 Source Bridge Closure Evidence

Recorded on 2026-04-29 for the remaining Phase 7 JSON-first scene source
bridge tasks. This evidence covers model-facing good outputs and the new
nonblocking diagnostic for Scene Graph fields that are preserved only in the
embedded JSON payload.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_scene_source_roundtrip.py tests/unit/test_scene_source_diagnostics.py tests/unit/test_wonder_llm.py` | stdout | passed | Passed locally: 25 passed, 1 warning. Covers `SS2001` JSON-only preview diagnostics, source bridge roundtrips, bad-output source spans, LLM repair helpers, and the model-facing good Scene Graph/source examples under `docs/llm/good_outputs/`. |
| 2026-04-29 | `python -m lathe.cli scene scene-graph-to-source docs/llm/good_outputs/model_good_archive_scene_graph.json --out .tmp_tests/model_good_archive_generated_scene.lth` | stdout | passed | Passed locally with `ok: true` and a nonblocking `SS2001` warning listing JSON-only preview paths such as `/layout`, `/materials`, `/curiosity_anchors`, `/hidden_state`, object affordances/provenance, and export metadata. |
| 2026-04-29 | `python -m lathe.cli scene check docs/llm/good_outputs/model_good_archive_scene_graph.json` | stdout | passed | Passed locally with `ok: true`, `scene_id: model_good_archive`, and no diagnostics. |
| 2026-04-29 | `python -m lathe.cli scene source-to-scene-graph docs/llm/good_outputs/model_good_archive_generated_scene.lth --out .tmp_tests/model_good_archive.roundtrip.json` | `.tmp_tests/model_good_archive.roundtrip.json` | passed | Passed locally with `ok: true`; the generated source bridge extracted valid `lathe.scene_graph.v1` JSON. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests/unit/test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests/unit/test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests/unit/test_marker_inventory.py` | stdout | passed | Passed locally after adding the good-output docs: 4 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\scene\source.py lathe\cli\scene_cmd.py tests\unit\test_scene_source_roundtrip.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 3 Brief Lowering Coverage Evidence

Recorded on 2026-04-29 for the remaining Dream Brief lowering example coverage.
This evidence covers the underwater train station and abandoned Roblox mall
briefs beyond the original alchemist observatory lowering tests.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests/unit/test_wonder_brief_lowering.py` | stdout | passed | Passed locally: 12 passed, 1 warning. The suite now checks underwater train station multi-room lowering, stable object IDs, light/camera/export propagation, curiosity/hidden-state counts, and abandoned Roblox mall `roblox_manifest` export propagation. |
| 2026-04-29 | `python -m ruff check tests\unit\test_wonder_brief_lowering.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 14 Scene Quality Summary Evidence

Recorded on 2026-04-29 for the human-readable scene quality summary slice.
Scene Quality Report v1 now includes schema-backed `human_summary` fields for
product-facing score/status, strengths, and concrete issues to address.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python scripts/generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding `human_summary` to `scene_quality_report.schema.json`. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_scene_validators.py tests/unit/test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 8 passed, 1 warning. Covers passed and failed human summaries and validates the updated Scene Quality Report contract. |
| 2026-04-29 | `python -m ruff check lathe\scene\validators\core.py tests\unit\test_scene_validators.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 2 Semantic Validation Summary Evidence

Recorded on 2026-04-29 for Scene Graph semantic validation hardening. This adds
a JSON `summary` object to `lathe scene check` and `lathe wonder
check-scene-graph`, plus an explicit source-bridge roundtrip check that stable
Scene Graph IDs are preserved. Package manifest validation now also verifies
that a package `scene_id` matches the referenced Scene Graph when that graph is
present and valid.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_scene_validation.py tests\unit\test_scene_source_roundtrip.py` | stdout | passed | Passed locally: 37 passed, 1 warning. Covers human-readable semantic validation summaries and stable ID preservation across Scene Graph source bridge normalization/roundtrip. |
| 2026-04-29 | `python -m ruff check lathe\scene\graph.py lathe\scene\__init__.py lathe\cli\scene_cmd.py lathe\cli\wonder_cmd.py tests\unit\test_wonder_scene_validation.py tests\unit\test_scene_source_roundtrip.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_package_manifest.py tests\unit\test_scene_executor.py::test_build_scene_preview_writes_offline_package_files tests\unit\test_scene_cli.py::test_scene_package_init_validate_and_inspect_emit_json tests\unit\test_scene_cli.py::test_scene_package_validate_reports_missing_paths_unless_allowed` | stdout | passed | Passed locally: 15 passed, 1 warning. Covers package `scene_id` consistency against referenced Scene Graph JSON plus package layout validation for the new build/render/cache roots. |

## Local Phase 4 Scene Package Layout Evidence

Recorded on 2026-04-29 for the Scene Package Format layout roots. The package
initializer now creates mode-specific build roots, pass-specific render roots,
and a package-local cache root. Package validation accepts build/render manifest
entries under those roots and requires the roots to exist when path existence is
enforced.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_package_manifest.py tests\unit\test_scene_executor.py::test_build_scene_preview_writes_offline_package_files tests\unit\test_scene_cli.py::test_scene_package_init_validate_and_inspect_emit_json tests\unit\test_scene_cli.py::test_scene_package_validate_reports_missing_paths_unless_allowed` | stdout | passed | Passed locally: 15 passed, 1 warning. Covers `builds/preview/`, `builds/final/`, `render_passes/{depth,normal,object_id,material_id,wireframe}/`, `cache/`, package init, package validation, and preview package creation. |
| 2026-04-29 | `python -m ruff check lathe\scene\package.py tests\unit\test_scene_package_manifest.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 11 Assembly Geometry Hints Evidence

Recorded on 2026-04-29 for deterministic Scene Assembly math helpers, linear
unit conversion, proxy bounds, and contact/resting-surface hints.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python scripts/generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding units, bounds, and contact hints to Scene Assembly v1. |
| 2026-04-29 | `python -m pytest -q tests/unit/test_scene_assembly.py tests/unit/test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 9 passed, 1 warning. Covers transform math helpers, meters/studs conversion, bounds estimation, contact hints, units metadata, and Scene Assembly schema validation. |
| 2026-04-29 | `python -m ruff check lathe\scene\assembly.py tests\unit\test_scene_assembly.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 10 Scene Build Runtime Flags Evidence

Recorded on 2026-04-29 for the Phase 10 `lathe scene build` runtime flag
slice. This is local deterministic offline/proxy evidence only. It does not
execute Blender, learned providers, Roblox Studio, POSIX shell, or an external
viewer.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m py_compile lathe\scene\executor.py lathe\cli\scene_cmd.py` | stdout | passed | Passed locally with exit code 0. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: 27 passed, 1 warning. Covers runtime-config metadata, deterministic/allow-fallback/strict propagation, unsafe config paths, invalid config JSON, strict scene validation warnings, and strict fallback diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_contracts.py tests\unit\test_scene_package_manifest.py tests\unit\test_scene_planner.py` | stdout | passed | Passed locally: 33 passed, 1 warning. Covers updated scene plan, scene manifest, Wonder report, and scene package manifest contracts. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding Phase 10 scene build flags. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding scene build options metadata. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\unit\test_wonder_schema_reference_docs.py tests\golden\test_cli_help_snapshots.py` | stdout | passed | Passed locally: 5 passed, 1 warning. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 1 passed, 1 warning. |
| 2026-04-29 | `python -m ruff check lathe\scene\executor.py lathe\cli\scene_cmd.py tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m lathe.cli scene build examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase10_scene_build_flags --mode preview --runtime-config examples\runtime_configs\reference_only.json --deterministic --allow-fallback --strict` | `.tmp_tests/phase10_scene_build_flags/alchemist_observatory` | passed | Passed locally with `ok: true`, `diagnostics: []`, and `build_options` recording runtime config, deterministic, allow-fallback, strict, effective runtime, and proxy fallback metadata. |
| 2026-04-29 | `python -m lathe.cli scene package validate .tmp_tests\phase10_scene_build_flags\alchemist_observatory` | stdout | passed | Passed locally with `ok: true` and no package diagnostics. |

## Local Phase 12 All-Camera Render Evidence

Recorded on 2026-04-29 for the deterministic proxy render CLI. This is local
proxy-render evidence only; it does not execute Blender or claim final visual
quality.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests\unit\test_scene_cli.py::test_scene_render_all_cameras_emits_every_proxy_camera tests\unit\test_scene_cli.py::test_scene_render_rejects_conflicting_camera_selection` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers single-camera proxy renders, explicit `--all-cameras` proxy renders for authored cameras plus generated topdown debug camera, and JSON diagnostics for conflicting `--camera`/`--all-cameras` selection. |
| 2026-04-29 | `python -m ruff check lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene render --all-cameras`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness, golden root help snapshots, and leaf-command negative CLI coverage after the new render flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers Wonder doc link/privacy/marker hygiene after the render docs update. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase12_all_cameras_evidence_trace.json` | `.tmp_tests/phase12_all_cameras_evidence_trace.json` | passed | Passed locally with `checked_tasks: 712`, `covered_checked_tasks: 712`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 12 Object Contact Sheet Evidence

Recorded on 2026-04-29 for deterministic proxy object contact sheets. Contact
sheets are emitted as proxy PNG artifacts under
`renders/camera_object_contact_sheet/` with object and material index sidecars.
This does not execute Blender or claim final visual quality.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests\unit\test_scene_cli.py::test_scene_render_all_cameras_emits_every_proxy_camera tests\unit\test_scene_executor.py::test_build_scene_preview_writes_offline_package_files tests\unit\test_scene_executor.py::test_build_scene_preview_outputs_are_deterministic tests\unit\test_scene_executor.py::test_build_scene_final_uses_scene_plan_render_passes` | stdout | passed | Passed locally: 5 passed, 1 warning. Covers object contact sheet emission through explicit all-camera renders and scene package builds, manifest/report alignment, deterministic byte output, and final-mode render pass metadata. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\scene\executor.py lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py tests\unit\test_scene_executor.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: 29 passed, 1 warning. Covers the full scene executor and scene CLI suites after adding contact sheet artifacts. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers Wonder docs link/privacy/marker hygiene after documenting contact sheets. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase12_contact_sheet_evidence_trace.json` | `.tmp_tests/phase12_contact_sheet_evidence_trace.json` | passed | Passed locally with `checked_tasks: 713`, `covered_checked_tasks: 713`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 12 Render Timeout Evidence

Recorded on 2026-04-29 for deterministic proxy render timeout handling. Timeout
failures emit structured `SR1004` diagnostics through `lathe scene render`.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_render_reports_proxy_render_timeout tests\unit\test_scene_cli.py::test_scene_render_all_cameras_emits_every_proxy_camera` | stdout | passed | Passed locally: 2 passed, 1 warning. Covers explicit proxy render timeouts and verifies all-camera rendering still emits contact sheets. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene render --timeout-seconds`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally after removing nondeterministic elapsed timing from successful render reports: 30 passed, 1 warning. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness and CLI negative matrix after the timeout flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting render timeout diagnostics. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase12_render_timeout_evidence_trace.json` | `.tmp_tests/phase12_render_timeout_evidence_trace.json` | passed | Passed locally with `checked_tasks: 714`, `covered_checked_tasks: 714`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 12 Blender Export Bridge Evidence

Recorded on 2026-04-29 for the Blender-backed scene assembly/export bridge.
This proves `.blend` export, collections, custom properties, cameras, lights,
materials, provenance properties, mocked Blender failure handling, and a
Blender-availability-gated smoke test. It does not claim Blender-backed scene
rendering or external viewer validation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers mocked Blender export, Blender-unavailable diagnostics, CLI target routing, and a Blender-availability-gated smoke export that preserves scene/object/region/material/provenance custom properties plus declared cameras/lights/materials. |
| 2026-04-29 | `python -m ruff check lathe\scene\blender_export.py scripts\blender_export_blend.py tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 13 Proxy USD Export Evidence

Recorded on 2026-04-29 for deterministic proxy USDA export support. The USD
target writes an ASCII `.usda` scene layout and object-index sidecar with stable
object IDs. This does not execute Blender, the USD SDK, Roblox Studio, or an
external viewer.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_export_usd_emits_proxy_usda_with_identity tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts` | stdout | passed | Passed locally: 2 passed, 1 warning. Covers proxy USDA output, object identity custom data, USD layout-convention sidecar, and existing GLB/export regression coverage. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene export --target usd`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness and CLI negative matrix after adding the USD target. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting the proxy USD target. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase13_proxy_usd_evidence_trace.json` | `.tmp_tests/phase13_proxy_usd_evidence_trace.json` | passed | Passed locally with `checked_tasks: 716`, `covered_checked_tasks: 716`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_validators.py::test_scene_quality_reports_export_missing_material tests\unit\test_scene_validators.py::test_scene_quality_can_require_export_artifacts` | stdout | passed | Passed locally: 2 passed, 1 warning. Covers explicit `SV7004` export validation for missing material bindings and existing missing export artifact validation. |
| 2026-04-29 | `python -m ruff check lathe\scene\validators\core.py tests\unit\test_scene_validators.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting the export material validator. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase13_export_validation_evidence_trace.json` | `.tmp_tests/phase13_export_validation_evidence_trace.json` | passed | Passed locally with `checked_tasks: 717`, `covered_checked_tasks: 717`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_export_glb_can_include_collision_proxy_nodes tests\unit\test_scene_cli.py::test_scene_export_usd_emits_proxy_usda_with_identity tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers opt-in GLB collision proxy nodes, collision sidecar records, existing proxy USDA identity output, and GLB/export regressions. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed after adding `--include-collision-proxies`. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene export --include-collision-proxies`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness and CLI negative matrix after the collision proxy flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting collision proxy export. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase13_collision_proxy_evidence_trace.json` | `.tmp_tests/phase13_collision_proxy_evidence_trace.json` | passed | Passed locally with `checked_tasks: 718`, `covered_checked_tasks: 718`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_export_glb_can_include_collision_proxy_nodes tests\unit\test_scene_blender_export.py tests\unit\test_scene_cli.py::test_scene_export_usd_emits_proxy_usda_with_identity` | stdout | passed | Passed locally: 5 passed, 1 warning. Covers `lathe scene export --target blender` routing, mocked sandboxed `.blend` export, named region collections, camera/light/material/custom-property preservation from Blender summary, unavailable-Blender diagnostics, GLB collision proxies, and proxy USDA identity output. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\scene\blender_export.py lathe\cli\scene_cmd.py scripts\blender_export_blend.py tests\unit\test_scene_cli.py tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: all checks passed after adding the Blender scene export wrapper and helper metadata support. |
| 2026-04-29 | `python -m lathe.cli probe-blender` | stdout | passed | Passed locally with Blender available through the Windows Apps Blender launcher, version `5.0.1`, and background CLI support. |
| 2026-04-29 | `python -m lathe.cli scene export examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase13_real_blender_export --target blender` | `.tmp_tests/phase13_real_blender_export` | passed | Passed locally with `ok: true`. Wrote `exports/alchemist_observatory.blend`, `reports/blender_export_summary.json`, and `reports/scene_export_artifacts.json`; Blender summary validation preserved all 4 object IDs, all 3 region collections, 2 cameras, 2 lights, and 5 materials. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene export --target blender`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness and CLI negative matrix after adding the Blender target. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting Blender export and status wording. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_readiness_report.py tests\unit\test_wonder_contracts.py::test_wonder_status_is_machine_readable_and_alpha_blocking tests\unit\test_wonder_contracts.py::test_wonder_cli_status_success` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers reconciled machine status after moving Blender scene export to a proven capability while leaving Blender-backed scene rendering and external viewer validation open. |
| 2026-04-29 | `python -m lathe.cli wonder status` | stdout | passed | Passed locally with `blender_scene_export_pipeline: true`, `blender_scene_render_pipeline: false`, and full readiness blockers now listing `blender_backed_scene_render` instead of the older combined render/export blocker. |
| 2026-04-29 | `python -m lathe.cli wonder readiness-report --out docs\wonder-readiness\final_readiness_report.md` | `docs/wonder-readiness/final_readiness_report.md` and `docs/wonder-readiness/final_readiness_report.json` | passed | Refreshed the final readiness report after the Blender export/status wording update. Core/proxy alpha gate remains passed locally while full runtime readiness stays blocked on the remaining external lanes. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase13_blender_export_evidence_trace.json` | `.tmp_tests/phase13_blender_export_evidence_trace.json` | passed | Passed locally with `checked_tasks: 724`, `covered_checked_tasks: 724`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py::test_scene_export_can_include_id_mask_bundle tests\unit\test_scene_cli.py::test_scene_export_glb_can_include_collision_proxy_nodes tests\unit\test_scene_blender_export.py::test_scene_export_cli_routes_blender_target` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers opt-in export-side ID mask PNGs, object-index sidecars, bundle manifest persistence, collision proxy regression, and Blender target CLI routing. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py lathe\cli\scene_cmd.py tests\unit\test_scene_cli.py tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: all checks passed after adding `lathe scene export --include-id-mask-bundle`. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene export --include-id-mask-bundle`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_cli.py tests\unit\test_scene_blender_export.py tests\unit\test_scene_validators.py::test_scene_quality_reports_export_missing_material` | stdout | passed | Passed locally: 24 passed, 1 warning. Covers the scene CLI suite plus Blender export and Phase 13 export material validation after completing the ID mask bundle. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Covers generated CLI reference freshness and CLI negative matrix after the ID mask bundle flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting the ID mask export bundle. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase13_id_mask_bundle_evidence_trace.json` | `.tmp_tests/phase13_id_mask_bundle_evidence_trace.json` | passed | Passed locally with `checked_tasks: 725`, `covered_checked_tasks: 725`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 15 Rollback Evidence

Recorded on 2026-04-29 for hash-guarded Scene Patch rollback. The rollback
path is exposed through `lathe wonder rollback-scene` and uses Scene History
inverse patches with hash guards.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_rollback.py tests\unit\test_scene_patch.py` | stdout | passed | Passed locally: 16 passed, 1 warning. Covers apply-patch history creation, rollback restoring the normalized original scene, hash-mismatch refusal, and CLI apply/rollback flow. |
| 2026-04-29 | `python -m ruff check lathe\scene\rollback.py lathe\scene\history.py tests\unit\test_scene_rollback.py tests\unit\test_scene_patch.py` | stdout | passed | Passed locally: all checks passed. |

## Local Phase 16 Scene Rollback And Branch History Evidence

Recorded on 2026-04-29 for the scene-level rollback CLI and branch history
quality-history tracking. This evidence is deterministic JSON-only; it does not
execute Blender, Roblox Studio, POSIX shell helpers, or external viewers.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_rollback.py tests\unit\test_scene_history.py tests\unit\test_scene_versioning.py` | stdout | passed | Passed locally: 16 passed, 1 warning. Covers `lathe scene rollback <scene> --to <version>`, Wonder rollback, branch creation, scene diff/merge, render history per branch, validation history per branch, and comparison-report history. |
| 2026-04-29 | `python -m ruff check lathe\cli\scene_cmd.py lathe\scene\history.py lathe\scene\rollback.py lathe\scene\versioning.py tests\unit\test_scene_rollback.py tests\unit\test_scene_history.py tests\unit\test_scene_versioning.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | docs/cli_reference.md | passed | Regenerated the CLI reference after adding `lathe scene rollback`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Confirms the CLI reference, help snapshots, and negative command matrix include `scene rollback`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms the updated branching/evidence docs pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase16_scene_rollback_evidence_trace.json` | `.tmp_tests/phase16_scene_rollback_evidence_trace.json` | passed | Passed locally with `checked_tasks: 730`, `covered_checked_tasks: 730`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 10 Scene Build Audit Artifact Evidence

Recorded on 2026-04-29 for the scene build audit-report slice and opt-in
generated asset build lane. This evidence proves package reporting, cache
reuse, failure propagation for per-asset proxy build records, and
`lathe scene build --build-assets` orchestration of generated Scene Plan asset
sources through the existing Lathe asset build pipeline. It does not claim that
generated scene assets are fully certifiable yet, and it does not prove
learned-provider execution, Blender scene rendering, Roblox Studio, POSIX shell
helpers, or external viewers.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py` | stdout | passed | Passed locally: 19 passed, 1 warning. Covers normalized Scene Graph output, validation report alias, schema-backed scene build report, per-asset proxy build report inclusion, provider/fallback trace output, package-local cache reuse, deterministic output, `SB1013` missing asset artifact failure propagation, `lathe scene build --build-assets` success/failure orchestration through generated asset materialization, `SB1015` materialization error wrapping, and strict scene-build-report schema rejection for loose build options or unsafe artifact paths. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_contracts.py::test_wonder_schemas_are_valid_json_schemas tests\unit\test_wonder_contracts.py::test_wonder_capabilities_are_machine_readable` | stdout | passed | Passed locally: 2 passed, 1 warning. Covers the new `scene_build_report` schema and capability flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_package_manifest.py tests\unit\test_wonder_contracts.py` | stdout | passed | Passed locally: 25 passed, 1 warning. Covers package manifest graph references for `scene_graph.normalized.json`, path containment, Wonder contract validation, and reconciled status/capability checks. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py tests\unit\test_wonder_contracts.py::test_wonder_schemas_are_valid_json_schemas tests\unit\test_wonder_contracts.py::test_wonder_capabilities_are_machine_readable tests\unit\test_wonder_contracts.py::test_wonder_cli_contract_commands_skip_optional_runtime_dependencies tests\unit\test_scene_package_manifest.py` | stdout | passed | Passed locally: 32 passed, 1 warning before review fixes. Covers the updated `scene_build_report` schema, package manifest validation, Wonder contract capabilities, and build-assets scene build regression path. |
| 2026-04-29 | Phase 10 review fix pass | local review | passed | Addressed review findings by keeping `build_options.fallbacks.deterministic_proxy_assets` true while `--build-assets` is active, adding explicit `build_options.runtime.asset_materialization`, wrapping `SceneMaterializeError` as structured `SB1015` scene-build diagnostics, and tightening `scene_build_report` build-options plus relative path schema validation. |
| 2026-04-29 | Phase 10 re-review fix pass | local review | passed | Addressed the remaining schema sharpness finding by constraining scene-build runtime IDs, proxy renderer/exporter IDs, and proxy fallback booleans to the executor's emitted contract values. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_executor.py tests\unit\test_wonder_contracts.py tests\unit\test_scene_package_manifest.py tests\unit\test_cli_reference_docs.py tests\unit\test_wonder_schema_reference_docs.py tests\unit\test_scene_style_layout.py tests\unit\test_scene_cli.py::test_scene_style_layout_and_camera_lighting_emit_contract_json` | stdout | passed | Passed locally: 57 passed, 1 warning after the Phase 10 review fixes and Phase 18 built-in style-pack slice. Covers executor behavior, Wonder contracts, package manifest path safety, generated CLI/schema reference freshness, built-in Style Packs, and style/layout/camera CLI regression coverage. |
| 2026-04-29 | `python -m ruff check lathe\scene\executor.py lathe\cli\scene_cmd.py tests\unit\test_scene_executor.py` | stdout | passed | Passed locally: all checks passed after adding `lathe scene build --build-assets`, generated asset build failure propagation, materialization error wrapping, and truthful proxy/runtime flags. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding and later tightening `schema/scene_build_report.schema.json`. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene build --build-assets`. |
| 2026-04-29 | `python -m lathe.cli scene build examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase10_scene_build_assets --mode preview --build-assets` | `.tmp_tests\phase10_scene_build_assets\alchemist_observatory\source\materialized_assets\scene_materialization_manifest.json` | expected-failed | The CLI exited 1 after materializing generated scene asset sources and invoking the real asset build pipeline in dependency order. The failure is honest: `SB1014` reported `builds_requested: 4`, `builds_succeeded: 0`, `builds_failed: 4`, and copied the underlying asset validation diagnostics. This covers "Build all missing assets in dependency order" as an orchestrated lane while leaving generated asset certification as future work. |
| 2026-04-29 | `python -m lathe.cli wonder validate-scene-materialization-manifest .tmp_tests\phase10_scene_build_assets\alchemist_observatory\source\materialized_assets\scene_materialization_manifest.json` | stdout | passed | Passed locally with `ok: true`; the failed build lane still leaves a schema-valid materialization manifest for repair. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\unit\test_wonder_schema_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 6 passed, 1 warning. Confirms generated CLI/schema references, help snapshots, and the negative command matrix remain in sync after adding `scene build --build-assets`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms docs link/privacy/marker hygiene after documenting the scene build asset lane and removing machine-local asset-quality evidence paths. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase10_scene_build_assets_evidence_trace_final.json` | `.tmp_tests/phase10_scene_build_assets_evidence_trace_final.json` | passed | Passed locally with `checked_tasks: 809`, `covered_checked_tasks: 809`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_schema_reference_docs.py tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 5 passed, 1 warning. Covers generated schema-reference freshness and docs link/privacy/marker hygiene after documenting the scene build report. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase10_build_audit_artifacts_evidence_trace.json` | `.tmp_tests/phase10_build_audit_artifacts_evidence_trace.json` | passed | Passed locally with `checked_tasks: 757`, `covered_checked_tasks: 757`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 11 Assembly Metadata Mapping Evidence

Recorded on 2026-04-29 for Scene Assembly metadata mapping. This evidence is
local deterministic/proxy evidence only: it proves assembly metadata, Blender
custom-property mapping through the sandboxed helper, and GLB scene/object
metadata preservation through the proxy export path.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_assembly.py tests\unit\test_scene_blender_export.py tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts` | stdout | passed | Passed locally: 12 passed, 1 warning. Covers Scene Assembly object metadata, Blender custom properties for scene/object/region/material/provenance data, and proxy GLB metadata/identity output. |
| 2026-04-29 | `python -m ruff check lathe\scene\assembly.py lathe\scene\artifacts.py lathe\scene\blender_export.py tests\unit\test_scene_assembly.py tests\unit\test_scene_blender_export.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase11_assembly_metadata_evidence_trace.json` | `.tmp_tests/phase11_assembly_metadata_evidence_trace.json` | passed | Passed locally with `checked_tasks: 759`, `covered_checked_tasks: 759`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 6B Minimal Scene Source Language Evidence

Recorded on 2026-04-29 for the experimental v0.3 `.lth` scene source subset.
This evidence proves parser, grammar, normalized AST schema, resolver, checker,
planner compatibility, formatter, and spec coverage for minimal scene
declarations. It does not claim advanced scene variants, gameplay metadata,
provenance source syntax, sockets, snap points, curiosity source syntax, hidden
state source syntax, or advanced layout constraints.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 43 passed, 1 warning. Covers minimal and full alchemist scene parsing, scene defaults, schema validation, strict scene child collection typing, backward-compatible JSON ASTs without `scenes`, resolver indexing, checker diagnostics for bad scene references, non-identifier references, and region namespace errors, asset-planner compatibility, grammar rule presence plus direct transformer optional-qualifier handling, spec coverage, and formatter snapshot output. |
| 2026-04-29 | `python -m ruff check lathe\parser\grammar.py lathe\parser\fast_parser.py lathe\parser\transformer.py lathe\normalizer.py lathe\resolver.py lathe\checker\language.py lathe\checker\declarations.py tests\unit\test_scene_source_language.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: all checks passed after import formatting. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Covers docs link/privacy/marker hygiene after documenting the minimal scene source status and evidence. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase6b_scene_source_language_evidence_trace.json` | `.tmp_tests/phase6b_scene_source_language_evidence_trace.json` | passed | Passed locally with `checked_tasks: 789`, `covered_checked_tasks: 789`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 8 Branch Asset Reuse Evidence

Recorded on 2026-04-29 for branch-aware Scene Plan asset cache reuse. This
evidence is deterministic planner/CLI evidence only: it proves branch plans can
compare against prior Scene Plans and identify reusable asset cache keys. It
does not copy build artifacts, execute the asset compiler, launch Blender, run
Roblox Studio, or validate external viewers.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_planner.py tests\unit\test_scene_cli.py::test_scene_check_plan_and_validate_emit_json` | stdout | passed | Passed locally: 20 passed, 1 warning. Covers `branch_reuse` plan reports, unchanged branch asset reuse, source-signature and asset-override cache misses, mode-mismatch `SP3101` diagnostics, cache-key ledger semantic validation, tightened branch-reuse schema values, and `lathe scene plan --reuse-from-plan` fail-fast behavior for stale base plans. |
| 2026-04-29 | `python -m ruff check lathe\cli\scene_cmd.py lathe\scene\planner.py lathe\scene\__init__.py tests\unit\test_scene_planner.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene plan --reuse-from-plan`. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding and tightening the optional Scene Plan `branch_reuse` contract. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\unit\test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms generated CLI and Wonder schema reference docs are fresh. |
| 2026-04-29 | `python -m pytest -q tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms CLI help snapshots and negative command matrix remain in sync. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms branch-reuse docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase8_branch_reuse_evidence_trace.json` | `.tmp_tests/phase8_branch_reuse_evidence_trace.json` | passed | Passed locally with `checked_tasks: 790`, `covered_checked_tasks: 790`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 9 Scene Asset Materialization Evidence

Recorded on 2026-04-29 for Scene Graph to generated Lathe asset source
materialization. This evidence proves generated asset source layout, naming,
provenance metadata, material declarations, asset-kind lowering, repeated
instance grouping, checker integration, planner integration, stable Scene Graph
ID preservation, strict `asset_task_*` manifest IDs, and opt-in build
integration/failure recording. It does not claim that generated scene assets
are fully certifiable yet, and it does not prove learned providers, Blender
scene rendering, Roblox Studio, POSIX helpers, or external viewers.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_materialize.py` | stdout | passed | Passed locally: 7 passed, 1 warning. Covers `lathe scene materialize`, schema-valid `scene_materialization_manifest.json`, generated asset source directory layout, environment-module/hero-prop/mechanical-assembly lowering, scene material declarations, generated naming/path safety, provenance comments and metadata, repeated instance-friendly source grouping, exact Scene Graph `scene_id` preservation, `asset_task_*` manifest ID validation, `lathe check` over each generated asset source, `lathe plan` over each generated asset source, and opt-in build result recording for success/failure paths. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_materialize.py tests\unit\test_wonder_contracts.py tests\unit\test_cli_reference_docs.py tests\unit\test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 23 passed, 1 warning. Covers the `scene_materialization_manifest` Wonder contract, capability flags, validation CLI without optional runtime dependencies, and fresh generated CLI/schema references after adding `--build-assets` and manifest build fields. |
| 2026-04-29 | `python -m ruff check lathe\scene\materialize.py lathe\scene\__init__.py lathe\wonder\contracts.py lathe\cli\scene_cmd.py lathe\cli\wonder_cmd.py tests\unit\test_scene_materialize.py tests\unit\test_wonder_contracts.py tests\unit\test_cli_errors.py` | stdout | passed | Passed locally: all checks passed after wiring the materializer, schema contract, CLI command, and tests. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene materialize --build-assets` and `lathe wonder validate-scene-materialization-manifest`. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding build result fields and stricter `asset_task_id` validation to `schema/scene_materialization_manifest.schema.json`. |
| 2026-04-29 | `python -m pytest -q tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms CLI help snapshots and the negative command matrix include the new materialization leaf commands. |
| 2026-04-29 | `python -m lathe.cli scene materialize examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase9_real_build_assets --mode preview --build-assets` | `.tmp_tests\phase9_real_build_assets\scene_materialization_manifest.json` | expected-failed | The CLI exited 1 after invoking the real asset build pipeline for four generated sources. The manifest still validated, recorded `builds_requested: 4`, `builds_failed: 4`, and preserved per-source build diagnostics. This proves integration and honest failure reporting; it does not claim generated scene assets certify yet. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms the materialization docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_contracts.py` | stdout | passed | Passed locally: 13 passed, 1 warning. Covers the full Wonder contract regression suite after adding the materialization manifest contract. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase9_build_assets_evidence_trace.json` | `.tmp_tests/phase9_build_assets_evidence_trace.json` | passed | Passed locally with `checked_tasks: 808`, `covered_checked_tasks: 808`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 18 Style Pack Evidence

Recorded on 2026-04-29 for curated Style Pack coverage and the experimental
`.lth` style-pack declaration surface. This evidence proves six schema-valid
built-in packs, including the two initial Roblox style packs, plus additive
top-level `style_pack` declarations and scene-local `style_pack = <id>`
checker validation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_style_layout.py tests\unit\test_scene_cli.py::test_scene_style_layout_and_camera_lighting_emit_contract_json` | stdout | passed | Passed locally: 10 passed, 1 warning. Covers curated `dead_god_observatory`, `dark_fantasy_ruin`, `cozy_fantasy_workshop`, `sci_fi_industrial`, `roblox_lowpoly_cute`, and `roblox_horror_lowpoly` Style Packs, fingerprint freshness, schema validation, CLI emission through `lathe scene style-pack --builtin`, and existing style/layout/camera regressions. |
| 2026-04-29 | `python -m ruff check lathe\scene\style.py lathe\scene\__init__.py lathe\cli\scene_cmd.py tests\unit\test_scene_style_layout.py tests\unit\test_scene_cli.py` | stdout | passed | Passed locally: all checks passed after adding built-in style-pack helpers and CLI support. |
| 2026-04-29 | Phase 18 source review fix pass | local review | passed | Addressed review findings by adding `style_pack` to the public spec declaration list and canonical order, rejecting empty or null scene-local style-pack references, treating duplicate style block names as duplicate scene-local IDs, and removing inert `style_pack ... uses ...` syntax until inheritance has a real contract. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 49 passed, 1 warning. Covers top-level `style_pack` parsing through the fast parser and transformer, normalized `style_packs` AST output, schema validation, formatter output, scene-local references to in-file packs and curated built-ins, checker diagnostics for unknown, empty, or non-identifier style-pack references, duplicate style block names, and rejection of inert `style_pack ... uses ...` syntax. |
| 2026-04-29 | `python -m ruff check lathe\defaults.py lathe\parser\grammar.py lathe\parser\fast_parser.py lathe\parser\transformer.py lathe\normalizer.py lathe\resolver.py lathe\checker\language.py lathe\checker\declarations.py lathe\lsp\__init__.py tests\unit\test_scene_source_language.py tests\unit\test_schema.py tests\unit\test_fmt.py tests\fuzz\test_normalizer_properties.py` | stdout | passed | Passed locally: all checks passed after adding the `.lth` style-pack declaration surface. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference after adding `lathe scene style-pack --builtin`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 4 passed, 1 warning. Confirms generated CLI reference freshness, help snapshots, and negative command matrix after the built-in style-pack flag. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms style-pack docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase18_style_pack_source_evidence_trace.json` | `.tmp_tests/phase18_style_pack_source_evidence_trace.json` | passed | Passed locally with `checked_tasks: 817`, `covered_checked_tasks: 817`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 19 Instance Override Evidence

Recorded on 2026-04-29 for Scene Graph instance overrides and export metadata.
This evidence proves `surface_overrides` and `affordances` are treated as
per-instance metadata, repeated damaged family instances can share one asset,
Scene Assembly IR preserves instancing metadata, proxy GLB object extras carry
that metadata, and Blender export metadata writes matching custom-property
inputs. This is deterministic proxy/export evidence; it does not claim external
viewer validation or live Blender execution beyond the existing sandbox fixture.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_style_layout.py tests\unit\test_scene_planner.py tests\unit\test_scene_assembly.py tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: 42 passed, 1 warning. Covers `surface_overrides` schema/planner handling, affordance instance overrides, four damaged doors sharing one family asset, Scene Assembly instancing metadata, proxy GLB object index and geometry `extras`, and Blender metadata/custom-property fixture output. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_style_layout.py tests\unit\test_scene_planner.py tests\unit\test_scene_assembly.py tests\unit\test_scene_cli.py::test_scene_render_and_export_emit_real_proxy_artifacts tests\unit\test_scene_blender_export.py tests\unit\test_wonder_contracts.py tests\unit\test_scene_executor.py tests\unit\test_wonder_examples_catalog.py tests\unit\test_wonder_golden_snapshots.py tests\unit\test_wonder_schema_reference_docs.py` | stdout | passed | Crash-resume validation passed locally: 92 passed, 1 warning. Confirms the Phase 19 schema, planner, assembly, export metadata, example catalog, golden snapshots, and generated schema reference remain synchronized after fixture regeneration. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_contracts.py::test_wonder_schemas_are_valid_json_schemas` | stdout | passed | Passed locally: 1 passed, 1 warning. Confirms the touched Wonder schemas remain valid JSON Schemas. |
| 2026-04-29 | `python -m ruff check lathe\scene\layout.py lathe\scene\planner.py lathe\scene\assembly.py lathe\scene\artifacts.py lathe\scene\blender_export.py scripts\blender_export_blend.py tests\unit\test_scene_style_layout.py tests\unit\test_scene_planner.py tests\unit\test_scene_assembly.py tests\unit\test_scene_cli.py tests\unit\test_scene_blender_export.py` | stdout | passed | Passed locally: all checks passed after adding Phase 19 instance metadata wiring. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding `surface_overrides` and Scene Assembly instancing metadata. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 2 passed, 1 warning. Confirms generated schema reference docs are fresh after the Phase 19 schema additions. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms Phase 19 docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase19_instance_overrides_evidence_trace.json` | `.tmp_tests/phase19_instance_overrides_evidence_trace.json` | passed | Passed locally with `checked_tasks: 822`, `covered_checked_tasks: 822`, `missing_evidence: 0`, and no diagnostics. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase19_resume_evidence_trace.json` | `.tmp_tests/phase19_resume_evidence_trace.json` | passed | Crash-resume trace passed locally with `checked_tasks: 822`, `covered_checked_tasks: 822`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 20 Modular Wall Constraint Evidence

Recorded on 2026-04-29 for Scene Graph `layout.modular_walls` and Layout Plan
`wall_segments`. This evidence proves modular wall placement constraints are
schema-backed, semantically checked for region references, emitted
deterministically from region bounds, and validated without claiming generated
wall meshes or physics simulation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_style_layout.py tests\unit\test_wonder_scene_validation.py tests\unit\test_wonder_contracts.py::test_wonder_schemas_are_valid_json_schemas` | stdout | passed | Passed locally: 40 passed, 1 warning. Covers schema validity, modular wall segment generation on region perimeter edges, off-grid modular wall diagnostics, and semantic checks for missing wall regions. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_style_layout.py tests\unit\test_wonder_scene_validation.py tests\unit\test_wonder_contracts.py tests\unit\test_wonder_examples_catalog.py tests\unit\test_wonder_golden_snapshots.py tests\unit\test_wonder_schema_reference_docs.py tests\unit\test_scene_cli.py::test_scene_style_layout_and_camera_lighting_emit_contract_json` | stdout | passed | Passed locally: 71 passed, 1 warning. Confirms the Phase 20 schema/output changes did not stale Wonder examples, golden snapshots, schema reference docs, or the scene style/layout CLI path. |
| 2026-04-29 | `python -m ruff check lathe\scene\layout.py lathe\scene\graph.py tests\unit\test_scene_style_layout.py tests\unit\test_wonder_scene_validation.py` | stdout | passed | Passed locally: all checks passed after adding modular wall contract parsing, segment output, and semantic-region diagnostics. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated Wonder schema reference docs after adding Scene Graph modular wall constraints and Layout Plan wall segments. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms Phase 20 docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase20_modular_walls_evidence_trace.json` | `.tmp_tests/phase20_modular_walls_evidence_trace.json` | passed | Passed locally with `checked_tasks: 823`, `covered_checked_tasks: 823`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 21 Camera Lighting Source Evidence

Recorded on 2026-04-29 for Wonder-facing camera and lighting source aliases.
This evidence proves `camera_intent` and `lighting_plan` parse through the fast
parser and formal transformer path, normalize to the existing `scene_camera`
and `scene_light` IR, remain schema/checker valid, appear in generated
JSON-first scene source previews, and preserve camera-lock continuity through a
non-camera semantic scene patch. Legacy `camera` and `light` source blocks
remain accepted as compatibility aliases for the same normalized IR.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_camera_lock.py` | stdout | passed | Passed locally: 35 passed, 1 warning. Covers `camera_intent` and `lighting_plan` parsing, transformer alias lowering, generated source preview aliases, source bridge hand-authored alias diagnostics, model-facing generated source sync, and camera-lock survival through the example sacredness patch. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_camera_lock.py tests\unit\test_scene_patch.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 79 passed, 1 warning. Confirms Phase 21 aliases remain compatible with scene patching, normalized AST schema validation, and formatter coverage for existing scene source syntax. |
| 2026-04-29 | `python -m ruff check lathe\parser\fast_parser.py lathe\parser\transformer.py lathe\scene\source.py tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_camera_lock.py` | stdout | passed | Passed locally: all checks passed after wiring source aliases, source preview output, and camera-lock patch regression tests. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms Phase 21 docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase21_camera_lighting_source_evidence_trace.json` | `.tmp_tests/phase21_camera_lighting_source_evidence_trace.json` | passed | Passed locally with `checked_tasks: 826`, `covered_checked_tasks: 826`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 22 Curiosity Source Evidence

Recorded on 2026-04-29 for experimental `.lth` source support for curiosity
anchors and hidden state. This evidence proves `curiosity_anchor` and
`hidden_state` scene-local blocks parse through the fast parser and formal
transformer path, normalize into `scene_curiosity_anchor` and
`scene_hidden_state` child collections, validate ID prefixes and `attached_to`
references, remain schema-compatible, and appear in generated JSON-first scene
source previews. Scene Graph JSON remains the durable contract for full
curiosity expansion semantics.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 62 passed, 1 warning. Covers source parsing, normalization defaults, JSON AST schema validation, generated source preview output, source bridge diagnostics, and formatter compatibility after adding curiosity and hidden-state scene children. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_curiosity.py tests\unit\test_scene_patch.py tests\unit\test_wonder_scene_validation.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 107 passed, 1 warning. Confirms the Phase 22 source surface remains compatible with existing curiosity expansion helpers, scene patch scopes, Scene Graph semantic validators, and normalized Lathe schema tests. |
| 2026-04-29 | `python -m ruff check lathe\defaults.py lathe\normalizer.py lathe\parser\fast_parser.py lathe\parser\transformer.py lathe\checker\declarations.py lathe\scene\source.py tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py` | stdout | passed | Passed locally: all checks passed after wiring curiosity and hidden-state source syntax. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms Phase 22 docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase22_curiosity_source_evidence_trace.json` | `.tmp_tests/phase22_curiosity_source_evidence_trace.json` | passed | Passed locally with `checked_tasks: 828`, `covered_checked_tasks: 828`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 23 Gameplay Metadata Source Evidence

Recorded on 2026-04-29 for experimental `.lth` object-local gameplay metadata
syntax. This evidence proves `gameplay { ... }` blocks parse through the fast
parser and formal transformer path, lower into normalized scene-object
`values.gameplay`, remain normalized AST schema-compatible, and appear in
generated JSON-first scene source previews for Scene Graph affordances.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_game_readiness_provenance.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 62 passed, 1 warning. Covers object-local `gameplay { ... }` parsing, transformer lowering, normalized AST schema validation, generated source preview affordance lines, model-facing good-output synchronization, game-readiness validator compatibility, and formatter output. |
| 2026-04-29 | `python -m ruff check lathe\parser\fast_parser.py lathe\parser\transformer.py lathe\scene\source.py tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_game_readiness_provenance.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: all checks passed after adding object-local gameplay metadata syntax and source preview output. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_game_readiness_provenance.py tests\unit\test_wonder_scene_validation.py tests\unit\test_scene_roblox.py tests\unit\test_schema.py tests\unit\test_fmt.py` | stdout | passed | Passed locally: 104 passed, 1 warning. Confirms gameplay metadata syntax stays compatible with Wonder scene validation, Roblox/profile regressions, normalized AST schema tests, and formatter coverage. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 3 passed, 1 warning. Confirms Phase 23 docs and evidence pass link, privacy, and marker inventory gates. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\phase23_gameplay_metadata_source_evidence_trace_final.json` | `.tmp_tests/phase23_gameplay_metadata_source_evidence_trace_final.json` | passed | Passed locally with `checked_tasks: 829`, `covered_checked_tasks: 829`, `missing_evidence: 0`, and no diagnostics. |

## Local Phase 24 Roblox Asset-Kit Export Evidence

Recorded on 2026-04-29 for the deterministic Roblox asset-kit export lane.
This evidence proves `lathe.stack.roblox_asset_kit_v1`, local GLB bundle
export, Roblox manifest emission, thumbnail generation, import instructions,
and an explicit FBX handoff artifact. It does not claim `.rbxmx` generation,
Roblox Studio import, asset upload, or external viewer validation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_roblox.py` | stdout | passed | Passed locally: 11 passed, 1 warning. Covers Roblox profile/manifest schemas, asset-kit stack example, GLB bundle export, thumbnail PNGs, import instructions, FBX handoff, schema validation for `lathe.roblox_export_bundle.v1` and `lathe.roblox_fbx_handoff.v1`, no fake `.fbx` or `.rbxmx`, deterministic repeated export hashes, and stale artifact cleanup after failed export reruns. |
| 2026-04-29 | `python -m ruff check lathe\scene\roblox.py lathe\scene\__init__.py lathe\cli\scene_cmd.py lathe\cli\wonder_cmd.py lathe\wonder\contracts.py tests\unit\test_scene_roblox.py tests\unit\test_cli_errors.py tests\unit\test_wonder_contracts.py scripts\generate_wonder_schema_reference.py` | stdout | passed | Passed locally: all checks passed after adding the asset-kit exporter, schema contracts, CLI validators, and generated-schema reference entry. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference after adding the Roblox Export Bundle and Roblox FBX Handoff schemas. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated CLI reference after adding `lathe scene roblox-export` and the new Wonder validation commands. |
| 2026-04-29 | `python -m lathe.cli scene roblox-export examples\wonder\abandoned_roblox_mall\scene_graph.json --profile examples\wonder\abandoned_roblox_mall\roblox_profile.json --out .tmp_tests\phase24_roblox_asset_kit_hardened` | `.tmp_tests\phase24_roblox_asset_kit_hardened` | passed | Passed locally with `status: built`, `stack_id: lathe.stack.roblox_asset_kit_v1`, schema-valid `exports/roblox/roblox_manifest.json`, GLB identity pass for four object IDs, `scene_thumbnail.png`, `object_contact_sheet.png`, `import_instructions.md`, `fbx_handoff.json`, and no diagnostics. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_roblox.py tests\unit\test_wonder_contracts.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_wonder_schema_reference_docs.py` | stdout | passed | Passed locally: 30 passed, 1 warning. Confirms Roblox export tests, contract metadata, CLI command inventory, CLI docs, CLI help snapshots, and generated schema reference all agree. |
| 2026-04-29 | `python -m lathe.cli wonder validate-roblox-export-bundle .tmp_tests\phase24_roblox_asset_kit_hardened\reports\roblox_export_bundle.json` | stdout | passed | Passed locally with `ok: true` and no diagnostics for the generated bundle report. |
| 2026-04-29 | `python -m lathe.cli wonder validate-roblox-fbx-handoff .tmp_tests\phase24_roblox_asset_kit_hardened\exports\roblox\fbx\fbx_handoff.json` | stdout | passed | Passed locally with `ok: true` and no diagnostics for the explicit FBX handoff artifact. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_phase24_roblox_asset_kit` | `.tmp_tests\wonder_validate_phase24_roblox_asset_kit` | passed | Passed locally after adding the Roblox asset-kit export to the standard Wonder helper. The helper reported 258 focused tests passed, regenerated the Wonder schema reference, emitted updated capabilities/status, exercised the deterministic proxy package/render/export lanes, validated the Roblox profile and manifest, and exported the Roblox asset-kit bundle. |

## Local Phase 25 Wonder Stdlib Catalog Evidence

Recorded on 2026-04-29 for the Wonder standard-library expansion. This
evidence proves a machine-readable component catalog covers architecture kits,
environmental dressing, controlled natural forms, hero props, lighting fixtures,
and a modular room-shell entry. The catalog is contract/planning vocabulary:
tests validate Scene Graph references, scene validators, scene planning,
generated Lathe asset-source materialization, and existing checked-in `std/*.lth`
parse/check behavior without claiming final mesh runtime proof.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_stdlib.py` | stdout | passed | Passed locally: 5 passed, 1 warning. Covers all 49 Phase 25 component IDs, catalog diagnostics, in-memory `stdlib_component_showcase` Scene Graph validation/planning, generated Lathe asset-source materialization, checked-in `std/**/*.lth` parse/check coverage, and docs synchronization. |
| 2026-04-29 | `python -m lathe.cli wonder validate-example examples\wonder\stdlib_component_showcase --write-missing-proxy-evidence --out .tmp_tests\stdlib_component_showcase_validate_example.json` | `.tmp_tests\stdlib_component_showcase_validate_example.json` | passed | Passed locally with `ok: true` and no diagnostics. Adds a Wonder scene example that references every Phase 25 stdlib component as stable Scene Graph source vocabulary and records truthful scene-source deferral. |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples\wonder --out docs\wonder-readiness\20_example_catalog.json --markdown-out docs\wonder-readiness\20_example_catalog.md --write-missing-proxy-evidence` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md` | passed | Passed locally with six examples total, six passed, zero failed, and six nonblocking deferred scene-source lanes. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_stdlib.py tests\unit\test_wonder_examples_catalog.py` | stdout | passed | Passed locally: 16 passed, 1 warning. Confirms the stdlib showcase integrates with the Wonder example catalog and golden fixture validation. |
| 2026-04-29 | `python -m ruff check lathe\scene\stdlib.py lathe\scene\__init__.py tests\unit\test_scene_stdlib.py` | stdout | passed | Passed locally: all checks passed after exporting the new stdlib helpers. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 4 passed, 1 warning. Confirms Phase 25 docs and evidence pass link, privacy, and marker inventory gates. |

## Local Phase 26 Environment Module Evidence

Recorded on 2026-04-29 for Wonder environment modules and terrain chunks.
This evidence proves the contract-level `env_module` catalog covers room
shells, floor tiles, wall segments, ceiling segments, arches, platforms,
stairs, background silhouettes, scene boundary shells, and terrain chunks. It
also proves snap-point metadata, snap-grid alignment validation, missing scene
boundary validation, scene assembly tests, checked-in docs, and the
`environment_module_showcase` Wonder example without claiming final mesh runtime
proof.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check lathe\scene\environment.py lathe\scene\validators\core.py lathe\scene\__init__.py tests\unit\test_scene_environment_modules.py` | stdout | passed | Passed locally: all checks passed after adding the environment module catalog, default scene validator hook, exported helpers, and focused tests. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_environment_modules.py` | stdout | passed | Passed locally: 7 passed, 1 warning. Covers all nine Phase 26 module IDs, room-shell support, modular floor/wall/ceiling/arch/platform/stair/background/scene-boundary/terrain examples, snap-point metadata, snap alignment diagnostics, missing boundary diagnostics, scene assembly validation, materialization to `env_module` sources, non-module opt-in behavior, and docs synchronization. |
| 2026-04-29 | `python -m lathe.cli wonder validate-example examples\wonder\environment_module_showcase --write-missing-proxy-evidence --out .tmp_tests\environment_module_showcase_validate_example.json` | `.tmp_tests\environment_module_showcase_validate_example.json` | passed | Passed locally with `ok: true` and no diagnostics. Validates the checked-in environment module Wonder example, including Dream Brief, Scene Graph, world memory, scene patch, render inspection, expected scene plan, wonder report, scene manifest, render comparison, evidence traceability, preview evidence, and truthful nonblocking scene-source deferral. |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples\wonder --out docs\wonder-readiness\20_example_catalog.json --markdown-out docs\wonder-readiness\20_example_catalog.md --write-missing-proxy-evidence` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md` | passed | Passed locally with seven examples total, seven passed, zero failed, and seven nonblocking deferred scene-source lanes after adding `environment_module_showcase`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_environment_modules.py tests\unit\test_wonder_examples_catalog.py` | stdout | passed | Passed locally: 18 passed, 1 warning. Confirms environment module examples remain compatible with the Wonder example catalog and golden fixture validation. |

## Local Phase 27 LLM Authoring Evidence

Recorded on 2026-04-29 for LLM authoring APIs and diagnostics. This evidence
proves compact LLM diagnostics preserve source spans when generated scene
source can be mapped, bad model-output fixtures include repair instructions,
prompt-facing authoring docs are present, and the Dream Brief, Scene Graph, and
Scene Patch schema pointer files link back to canonical schemas instead of
copying schema bodies.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check lathe\wonder\llm.py tests\unit\test_wonder_llm.py` | stdout | passed | Passed locally: all checks passed after preserving `source_span` in compact LLM diagnostics and adding prompt-facing docs/schema-pointer tests. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_llm.py tests\unit\test_scene_source_diagnostics.py` | stdout | passed | Passed locally: 17 passed, 1 warning. Covers LLM diagnostic summaries, repair playbooks, semantic patch conversion, bad model-output fixtures and expected repairs, schema pointer docs, generated source span mapping, and source diagnostic repair hints. |
| 2026-04-29 | `python -m lathe.cli wonder diagnose-for-llm docs\llm\bad_outputs\invalid_scene_source_bad_id.lth --out .tmp_tests\phase27_bad_source_diagnose_for_llm.json` | `.tmp_tests\phase27_bad_source_diagnose_for_llm.json` | passed | Passed locally with `status: failed` for the intentionally invalid source and a compact diagnostic containing `source_span` line 48, column 7 for `/objects/0/object_id`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 2 passed, 1 warning. Confirms the new LLM docs, bad-output repair guide, and schema-pointer files pass markdown link and marker inventory checks. |

## Local Phase 30 Wonder Benchmark CI Evidence

Recorded on 2026-04-29 for the deterministic Wonder benchmark automation lane.
This evidence proves `.github/workflows/wonder-benchmarks.yml` exists as a
nightly/manual workflow, `scripts/ci_wonder_benchmarks.py` runs the local
benchmark checks, and the lane emits and validates a
`lathe.scene_benchmark_report.v1` artifact. This does not claim hosted CI has
run yet.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check scripts\ci_wonder_benchmarks.py tests\unit\test_scene_bench.py` | stdout | passed | Passed locally: all checks passed after adding the Wonder benchmark CI script and workflow coverage test. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_bench.py` | stdout | passed | Passed locally: 7 passed, 1 warning. Covers benchmark budgets, cache reuse, final-export exceptions, prompt corpus, and the nightly Wonder benchmark workflow/script wiring. |
| 2026-04-29 | `python scripts\ci_wonder_benchmarks.py --out .tmp_tests\wonder_ci_benchmarks\report.json` | `.tmp_tests\wonder_ci_benchmarks\report.json` | passed | Passed locally with three steps passed: benchmark pytest, `lathe scene bench` against the alchemist observatory Scene Graph, and `lathe wonder validate-scene-benchmark-report` for the emitted benchmark report. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 2 passed, 1 warning. Confirms the Phase 30 performance-budget docs update passes markdown link and marker inventory checks. |

## Local Phase 32 Golden Example Proxy Runtime Evidence

Recorded on 2026-04-29 for the golden Wonder examples. This evidence proves the
deterministic proxy runtime can build preview Scene Packages, validate the
packages, render reveal/detail/topdown proxy cameras, and export GLB artifacts
with ID-mask bundles for every checked-in Wonder example. It also records a bug
fix for high-object-count contact sheets so the stdlib showcase renders instead
of crashing. This evidence is proxy-runtime evidence and does not claim
first-class `.lth` scene source or Blender-backed rendering.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m lathe.cli scene build examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase32_alchemist_build --mode preview --deterministic --allow-fallback` | `.tmp_tests\phase32_alchemist_build` | passed | Passed locally with `ok: true`, quality status `passed`, three render tasks, three export tasks, and no diagnostics for the alchemist observatory preview Scene Package. |
| 2026-04-29 | `python -m lathe.cli scene render examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase32_alchemist_renders --all-cameras --mode preview` | `.tmp_tests\phase32_alchemist_renders` | passed | Passed locally with `ok: true`, proxy renderer `lathe.scene.proxy_renderer.v1`, reveal/detail/topdown camera artifacts, object ID passes, object indices, material indices, contact sheet, and no diagnostics. |
| 2026-04-29 | `python -m lathe.cli scene export examples\wonder\alchemist_observatory\scene_graph.json --out .tmp_tests\phase32_alchemist_export --target glb --mode preview --include-id-mask-bundle` | `.tmp_tests\phase32_alchemist_export` | passed | Passed locally with `ok: true`, proxy GLB exporter `lathe.scene.proxy_glb_exporter.v1`, object-ID identity status `passed`, ID-mask bundle artifacts, and no diagnostics. |
| 2026-04-29 | `python -m ruff check lathe\scene\artifacts.py scripts\ci_wonder_examples.py tests\unit\test_wonder_examples_catalog.py` | stdout | passed | Passed locally: all checks passed after fixing contact-sheet layout for high-object-count scenes and adding proxy build/render/export coverage to the Wonder examples CI script. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_examples_catalog.py` | stdout | passed | Passed locally: 13 passed, 1 warning. Covers every Wonder example fixture, catalog validation, proxy build/render/export CI script coverage, and a regression test proving the 49-object stdlib showcase renders a contact sheet. |
| 2026-04-29 | `python scripts\ci_wonder_examples.py --out .tmp_tests\wonder_ci_examples\report.json` | `.tmp_tests\wonder_ci_examples\report.json` | passed | Passed locally with 36 steps passed and zero failed across seven examples: catalog generation, example validation, deterministic preview build, package validation, proxy render, and proxy GLB export for each example. |

## Local Phase 33 Demo Path Evidence

Recorded on 2026-04-29 for the one-command Wonder seed demo path. This
evidence proves the PowerShell seed demo now renders and validates a
deterministic before/after proxy comparison after the `more_sacred` patch, and
that the new local CI demo lane exercises the same core comparison contracts.
It does not claim hosted CI, POSIX shell execution, Blender rendering, Roblox
Studio execution, or external-viewer validation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check scripts\ci_wonder_demo.py tests\unit\test_wonder_demo_scripts.py` | stdout | passed | Passed locally: all checks passed after adding the deterministic Wonder demo CI script, workflow, and focused script wiring tests. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_demo_scripts.py tests\unit\test_wonder_before_after_cli.py` | stdout | passed | Passed locally: 6 passed, 1 warning. Covers seed demo script before/after wiring, Wonder demo CI workflow wiring, local demo CI report generation, `wonder lock-camera`, `wonder compare-renders`, and `wonder demo-before-after`. |
| 2026-04-29 | `python scripts\ci_wonder_demo.py --out .tmp_tests\wonder_ci_demo\report.json` | `.tmp_tests\wonder_ci_demo\report.json` | passed | Passed locally with four steps passed: before/after CLI tests, `wonder demo-before-after`, `wonder validate-render-comparison`, and `wonder validate-scene-history`. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\demo_wonder_seed_scene.ps1 -OutDir .tmp_tests\phase33_seed_demo` | `.tmp_tests\phase33_seed_demo` | passed | Passed locally. The seed demo validated the Dream Brief, authored Scene Graph, scene source bridge, Scene Plan, Scene Assembly, World Memory, Render Inspection, Repair Report, preview packages, proxy render/export artifacts, `more_sacred` patch, before/after render comparison, curiosity expansion, and final package checks. |

## Local Phase 34 Documentation Evidence

Recorded on 2026-04-29 for the Wonder readiness documentation set. This
evidence proves the remaining Phase 34 docs pages exist under the requested
paths, are in MkDocs navigation, state the JSON-first/proxy-runtime boundaries,
and are covered by focused tests plus the relevant source, package, memory,
example, and before/after suites. The local environment does not have MkDocs
installed, so hosted or environment-complete docs-site build evidence remains a
separate confirmation.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check tests\unit\test_wonder_phase34_docs.py` | stdout | passed | Passed locally: all checks passed for the Phase 34 docs coverage test. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_phase34_docs.py` | stdout | passed | Passed locally: 2 passed, 1 warning. Confirms `06_scene_language.md`, `08_scene_package.md`, `12_world_memory.md`, and `15_mvp_demo.md` exist, state runtime boundaries, and are wired into `mkdocs.yml`. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 4 passed, 1 warning. Confirms the new docs do not break markdown links, private-path/privacy checks, or marker inventory. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_source_language.py tests\unit\test_scene_source_roundtrip.py tests\unit\test_scene_package_manifest.py tests\unit\test_scene_executor.py tests\unit\test_wonder_memory.py tests\unit\test_scene_cli.py tests\unit\test_wonder_examples_catalog.py tests\unit\test_wonder_before_after_cli.py tests\unit\test_wonder_phase34_docs.py` | stdout | passed | Passed locally: 118 passed, 1 warning. Covers the behavior cited by the Scene Language, Scene Package, World Memory, and MVP Demo pages. |
| 2026-04-29 | `python -m mkdocs build --strict` | stdout | unavailable | Not run successfully because the local Python environment does not have MkDocs installed. This is a docs-site environment gap, not a failure of the focused markdown/static checks above. |

## Local Phase 35 Test And CI Matrix Evidence

Recorded on 2026-04-29 for the Wonder test matrix. This evidence proves the
remaining local test gaps were covered with scene-module ownership/import tests,
scene manifest and build-report golden snapshots, Dream Brief and Scene Graph
JSON ingress fuzz tests, mocked Blender bridge tests, an optional Blender export
smoke lane, and package-level coverage gates for `lathe.scene` and
`lathe.wonder`. The optional Blender lane passed an export smoke locally because
Blender was available, while Blender-backed scene rendering remains explicitly
unavailable and is still a full-runtime blocker.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m ruff check tests\unit\test_scene_module_coverage.py tests\unit\test_wonder_golden_snapshots.py tests\fuzz\test_wonder_contract_fuzz.py scripts\ci_wonder_optional_blender.py tests\unit\test_scene_blender_export.py tests\unit\test_coverage_policy.py` | stdout | passed | Passed locally: all checks passed after adding scene-module ownership coverage, manifest/build-report snapshots, ingress fuzz cases, Blender optional lane hardening, and new coverage gates. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_scene_module_coverage.py tests\unit\test_wonder_golden_snapshots.py tests\unit\test_scene_blender_export.py tests\unit\test_coverage_policy.py` | stdout | passed | Passed locally: 20 passed, 1 warning. Covers scene module ownership/imports, golden snapshots for Scene Plan, Scene Manifest, Scene Build Report, alpha gate, evidence traceability, example catalog, render comparison, mocked Blender bridge/export behavior, optional Blender CI script wiring, and coverage gate configuration. |
| 2026-04-29 | `.venv\Scripts\python.exe -m pytest -q tests\fuzz\test_wonder_contract_fuzz.py` | stdout | passed | Passed locally in the dev environment with Hypothesis installed: 7 passed. Covers scene patch pointer fuzzing, world-memory append/redaction idempotency fuzzing, path safety fuzzing, ID normalization fuzzing, render comparison fuzzing, Dream Brief JSON ingress fuzzing, and Scene Graph JSON ingress fuzzing. |
| 2026-04-29 | `python scripts\ci_wonder_optional_blender.py --out .tmp_tests\wonder_ci_optional_blender\report.json` | `.tmp_tests\wonder_ci_optional_blender\report.json` | passed | Passed locally. The optional lane ran mocked Blender bridge tests, probed local Blender, executed `lathe scene export --target blender`, and built a `.blend` export with preserved object, collection, camera, light, and material identity. The report still marks Blender-backed scene render smoke as skipped/unavailable. |

## Local Phase 36 Handoff Evidence

Recorded on 2026-04-29 for the Project Wonder handoff readiness phase. This
evidence proves the local deterministic core/proxy handoff artifacts are
refreshed and that the locally executable handoff checks pass. It does not
claim fresh-clone proof, hosted CI success, POSIX execution, Blender-backed
scene rendering, Roblox Studio execution, external-viewer validation, app-layer
integration, or human alpha approval.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out .tmp_tests\wonder_alpha_gate` | `.tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json` | passed | Passed locally with deterministic core/proxy alpha gate `passed`, 12 core lanes passed, 0 blocking failures, Blender optional lane passed, and POSIX, Roblox, and external viewer lanes skipped nonblocking. |
| 2026-04-29 | `python -m lathe.cli wonder readiness-report --alpha-report .tmp_tests\wonder_alpha_gate\reports\final_readiness_report.json --out docs\wonder-readiness\final_readiness_report.md` | `docs/wonder-readiness/final_readiness_report.md`, `docs/wonder-readiness/final_readiness_report.json` | passed | Refreshed the public final readiness report and sibling JSON from the current alpha-gate bundle. The report states deterministic core/proxy scope and leaves the human approval decision pending. |
| 2026-04-29 | `python scripts\generate_wonder_schema_reference.py` | `docs/wonder-readiness/schema_reference.md` | passed | Regenerated the Wonder schema reference from committed `lathe.*.v1` schemas. |
| 2026-04-29 | `python scripts\generate_cli_reference.py` | `docs/cli_reference.md` | passed | Regenerated the CLI reference from live `python -m lathe.cli ... --help` output, including `lathe scene` and `lathe wonder` commands. |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples\wonder --out docs\wonder-readiness\20_example_catalog.json --markdown-out docs\wonder-readiness\20_example_catalog.md --strict --allow-deferred-scene-source --write-missing-proxy-evidence` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md` | passed | Passed locally with 7 examples total, 7 passed, 0 failed, and 7 nonblocking scene-source deferrals. |
| 2026-04-29 | `python scripts\ci_wonder_benchmarks.py --out .tmp_tests\wonder_ci_benchmarks\report.json` | `.tmp_tests\wonder_ci_benchmarks\report.json` | passed | Passed locally with 3/3 steps: benchmark tests, `lathe scene bench`, and validation of the emitted `lathe.scene_benchmark_report.v1` artifact. |
| 2026-04-29 | `python scripts\ci_wonder_fast.py --out .tmp_tests\wonder_ci_fast\report.json` | `.tmp_tests\wonder_ci_fast\report.json` | passed | Passed locally with focused Wonder tests and alpha-gate execution: 2/2 steps passed and 119 focused tests passed. This is local script evidence, not hosted CI evidence. |
| 2026-04-29 | `python scripts\ci_wonder_examples.py --out .tmp_tests\wonder_ci_examples\report.json` | `.tmp_tests\wonder_ci_examples\report.json` | passed | Passed locally with 36/36 steps across all Wonder examples: cataloging, validation, deterministic preview build, package validation, proxy render, and proxy GLB export. This is local script evidence, not hosted CI evidence. |
| 2026-04-29 | `python scripts\ci_wonder_optional_blender.py --out .tmp_tests\wonder_ci_optional_blender\report.json` | `.tmp_tests\wonder_ci_optional_blender\report.json` | passed | Passed locally. The lane ran mocked Blender bridge tests, probed Blender, exported a `.blend`, and still marks Blender-backed scene render smoke as skipped/unavailable. |
| 2026-04-29 | `python scripts\ci_wonder_optional_roblox.py --out .tmp_tests\wonder_ci_optional_roblox\report.json` | `.tmp_tests\wonder_ci_optional_roblox\report.json` | skipped | Roblox tooling was not available locally, so the optional lane reported skipped nonblocking. Deterministic Roblox profile, manifest, and asset-kit validators are covered by the local validation helper. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\lathe_wonder_validate.ps1 -WorkDir .tmp_tests\wonder_validate_phase36` | `.tmp_tests/wonder_validate_phase36` | passed | Passed locally. The helper ran 261 focused Wonder/scene tests, regenerated schema docs, emitted capabilities/status, validated contracts, built/rendered/exported the alchemist proxy scene, validated the proxy package, validated Roblox profile/manifest, and built the Roblox asset-kit bundle. |
| 2026-04-29 | `powershell -ExecutionPolicy Bypass -File scripts\demo_wonder_seed_scene.ps1 -OutDir .tmp_tests\phase36_seed_demo` | `.tmp_tests/phase36_seed_demo` | passed | Passed locally. The demo exercised contracts, brief lowering, source bridge roundtrip, planning, assembly, world memory, quality validation, proxy package build, render inspection repair, semantic patch/rebuild, before/after proxy comparison, curiosity expansion, and final proxy artifact evidence. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_schema_reference_docs.py tests\unit\test_wonder_contracts.py tests\unit\test_cli_reference_docs.py tests\golden\test_cli_help_snapshots.py tests\unit\test_cli_errors.py::test_negative_cli_matrix_covers_every_leaf_command` | stdout | passed | Passed locally: 19 passed, 1 warning. Confirms generated schema/CLI references, Wonder contract stability, CLI help snapshots, and negative CLI coverage remain current. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 4 passed, 1 warning. Confirms the Phase 36 docs and generated references do not break markdown links, private-path/privacy checks, or marker inventory. |

## Local Post-Failure Repair And Scene Source Closure Evidence

Recorded on 2026-04-29 after a full-suite audit found stale generated
language/schema references, an undocumented Wonder fixture folder, two broad
generated-source exception handlers, and missing main-catalog entries for new
Wonder `.lth` scene-source fixtures. This evidence proves those failures are
fixed locally and that the remaining unchecked tasks are clean-checkout,
hosted-CI, external-runtime, Project Wonder app-layer, or human-decision gates.

| Date | Command | Output | Status | Result |
| --- | --- | --- | --- | --- |
| 2026-04-29 | `python scripts\generate_language_schema_reference.py` | `docs/language_reference.md`, `docs/schema_reference.md` | passed | Regenerated stale core language/schema references after scene-source/schema changes. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_exception_inventory.py::test_broad_exception_handlers_are_tracked tests\unit\test_fixture_hygiene.py tests\unit\test_language_schema_reference_docs.py tests\unit\test_docs_static_audit.py::test_docs_markdown_links_and_fenced_code_blocks_are_linted tests\unit\test_docs_static_audit.py::test_docs_do_not_leak_this_checkout_absolute_path tests\unit\test_docs_static_audit.py::test_public_docs_do_not_contain_private_path_or_secret_literals tests\unit\test_marker_inventory.py` | stdout | passed | Passed locally: 10 passed, 1 warning after narrowing generated scene-materialization exception handling, documenting `tests/fixtures/wonder`, and regenerating references. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_wonder_examples_catalog.py tests\unit\test_wonder_golden_snapshots.py tests\unit\test_scene_source_roundtrip.py` | stdout | passed | Passed locally: 32 passed, 1 warning after adding generated `scene_source.lth` fixtures for all seven Wonder examples and requiring source-bridge roundtrip validation. |
| 2026-04-29 | `python scripts\ci_wonder_examples.py --out .tmp_tests\post_source_wonder_ci_examples\report.json` | `.tmp_tests/post_source_wonder_ci_examples/report.json` | passed | Passed locally with 36/36 steps and `deferred_lanes_nonblocking: []`; all seven examples validate with `scene_source: valid`. |
| 2026-04-29 | `python -m lathe.cli wonder catalog-examples examples\wonder --out docs\wonder-readiness\20_example_catalog.json --markdown-out docs\wonder-readiness\20_example_catalog.md --strict --write-missing-proxy-evidence` | `docs/wonder-readiness/20_example_catalog.json`, `docs/wonder-readiness/20_example_catalog.md` | passed | Passed locally with 7 examples total, 7 passed, 0 failed, and 0 deferred nonblocking lanes. |
| 2026-04-29 | `python -m lathe.cli wonder alpha-gate examples\wonder\alchemist_observatory --out .tmp_tests\post_source_alpha_gate` | `.tmp_tests/post_source_alpha_gate/reports/final_readiness_report.json` | passed | Passed locally with deterministic core/proxy alpha gate `passed`, 12 core lanes passed, 0 blocking failures, Blender optional lane passed, POSIX/Roblox/external viewer skipped nonblocking, and example catalog `deferred_nonblocking: 0`. |
| 2026-04-29 | `python -m lathe.cli wonder readiness-report --alpha-report .tmp_tests\post_source_alpha_gate\reports\final_readiness_report.json --out docs\wonder-readiness\final_readiness_report.md` | `docs/wonder-readiness/final_readiness_report.md`, `docs/wonder-readiness/final_readiness_report.json` | passed | Refreshed the final readiness report from the post-source alpha-gate bundle. |
| 2026-04-29 | `python -m pytest -q tests\unit\test_docs_static_audit.py::test_examples_catalog_lists_every_checked_in_lathe_example tests\unit\test_scene_source_roundtrip.py tests\unit\test_wonder_examples_catalog.py` | stdout | passed | Passed locally: 26 passed, 1 warning after listing all Wonder `scene_source.lth` files in `docs/examples_catalog.md` and regenerating the model-facing generated source fixture with a comment-safe embedded payload. |
| 2026-04-29 | `python -m pytest -q` | stdout | passed | Passed locally: 1859 passed, 10 skipped, 127 deselected, 2 warnings. Skips are POSIX/symlink/resource-limit environment skips on this Windows host. |
| 2026-04-29 | `python -m lathe.cli wonder evidence-trace --tasks wonder-tasks.md --evidence docs\wonder-readiness\evidence.md --out .tmp_tests\post_source_evidence_trace.json` | `.tmp_tests/post_source_evidence_trace.json` | passed | Passed locally with `checked_tasks: 956`, `covered_checked_tasks: 956`, `missing_evidence: 0`, and `diagnostics: 0`. |
| 2026-04-29 | `python -m lathe.cli wonder status` | stdout | passed | Passed locally. Status reports `core_proxy_alpha_gate_ready: true`, `full_wonder_runtime_ready: false`, full readiness blockers for fresh clone/hosted CI, POSIX, Blender-backed scene render, Roblox Studio import execution, and external viewer validation, with only `blender_scene_render_pipeline` false in capability flags. |
| 2026-04-29 | `git diff --check` | stdout | passed | Passed locally with line-ending warnings only; no whitespace errors were reported. |

## Open Evidence Gaps

- Hosted GitHub workflow confirmation of the new Wonder fast/examples workflows
  after they run remotely.
- Human approval of the Project Wonder alpha gate.
- POSIX validation of `scripts/lathe_wonder_validate.sh` and
  `scripts/demo_wonder_seed_scene.sh` if POSIX proof is required by the human
  alpha decision.
- Blender-backed scene render execution only if optional runtime proof is
  required by the human alpha decision. Sandboxed Blender scene export has local
  fixture evidence; external viewer validation remains separate.
- Roblox Studio/import/export execution only if optional runtime proof is
  required by the human alpha decision.
