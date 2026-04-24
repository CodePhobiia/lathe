# Wave 2 Code-Hygiene Review

**Reviewer:** reviewer-code-hygiene
**Range audited:** `54b8ae8` → `61aab04` (8 commits)
**Mode:** audit-only, no source edits

## Summary verdict

**Mostly clean — three Wave-3 follow-ups required.** All four explicit Wave 2 LOC targets met (parser, shape_providers, shape_backend, executor all decomposed below their ≤500/file ceilings). All shim import paths resolve, including the `ShapeProviderError` `RuntimeError` invariant. Mi3 (`7919`) is correctly localised to `lathe/constants.py`. C3 was not re-fixed, Mi5 was not unnecessarily addressed. **Follow-ups:** (a) four pre-existing files remain >500 LOC and were untouched; (b) seven `# noqa: BLE001`-annotated `except Exception` sites still live in Wave-2-touched files; (c) 17 production `assert` sites remain (matches pre-Wave-2 baseline — Plan 01 target unmet); (d) dangling Stage 2.V references still in source comments.

## LOC audit (files >500 LOC)

| Path | LOC | In Wave 2 scope? | Verdict |
|---|---|---|---|
| `lathe/checker.py` | 856 | No | Pre-existing offender — Wave 3 target |
| `lathe/blueprints/__init__.py` | 717 | No | Pre-existing offender — Wave 3 target |
| `lathe/cli.py` | 625 | No | Pre-existing offender — Wave 3 target |
| `lathe/capabilities.py` | 622 | Touched (security only) | Out-of-scope LOC; flag for Wave 3 |
| `lathe/blender_execution.py` | 578 | Touched (security only) | Touched but no decomposition planned; +20 LOC vs 558 baseline (security hardening) — accept |
| `lathe/resolver.py` | 540 | Touched (semantics only) | Out-of-scope for decomposition; flag for Wave 3 |

Wave 2 explicit decomposition targets (parser 1666→package, shape_providers 998→package, shape_backend 665→package, executor 2315→package) are all now under 500/file. Largest split-output files: `core/geometry.py` 433, `parser/fast_parser.py` 402, `executor.py` (shim) 399, `parser/transformer.py` 383.

## `except Exception` audit

Pre-Wave-2 baseline: 27 sites / 12 files. **Current: 23 sites / 17 files.** Every site carries `# noqa: BLE001`. Spot-checked: all are at backend/IO boundaries (Blender subprocess, optional providers, image loaders, JSON probes). None re-raise generically without context, but several do not narrow further despite being eligible.

Per-file count (post-Wave-2):

| File | Count | Wave 2 touched? | Justified? |
|---|---|---|---|
| `lathe/exact_solids.py` | 4 | No | All `# noqa: BLE001`, no narrowing comment — **Wave 3 candidate** |
| `lathe/core/geometry.py` | 4 | Yes (split target) | All `# noqa: BLE001`, no narrowing — **Plan 01 target unmet for split file** |
| `lathe/validators/visual_quality.py` | 2 | No | OK (image-load fallbacks) |
| `lathe/capabilities.py` | 2 | Yes (security) | OK (capability probes) |
| `lathe/cli.py`, `lathe/executor.py`, `lathe/doctor.py`, `lathe/eval_harness.py`, `lathe/geometry_kernel.py`, `lathe/candidate_search.py`, `lathe/normalizer.py`-area, `lathe/core/uv_ops.py`, `lathe/core/stages/{topology,uv}.py`, `lathe/parser/imports.py`, `lathe/shape/geometry/conditioning.py` | 1 each | mixed | Acceptable boundary catches |

Plan 01 target ("0 in Wave-2-touched files") was **not met**: `core/geometry.py` (4) and `core/stages/{topology,uv}.py`, `core/uv_ops.py`, `parser/imports.py`, `shape/geometry/conditioning.py`, `executor.py` (shim) all carry `BLE001`-suppressed catches inside Wave-2-introduced files. Each is `noqa`-tagged so lint is silent, but narrowing was not done.

## Production `assert` count

Pre-Wave-2: 17. **Current: 17.** Plan 01 target ("0 in Wave-2-touched files") **not met.** Sites:

- `lathe/exact_solids.py` × 6, `lathe/geometry_kernel.py` × 4, `lathe/scaffold_compiler.py` × 2, `lathe/assembly_kernel.py` × 2 — all `assert primitive.extents is not None` / `assert primitive.radius/height is not None` after type-narrowing primitives. `-O` would strip these and turn the next line into an `AttributeError`.
- `lathe/core/stages/shape.py:112` — `assert selected is not None and selected_runtime is not None` (new file from Wave-2 split). Touched-by-Wave-2: yes. **Plan 01 target violated for new code.**
- `lathe/validators/visual_quality.py:118` — six-image-not-None guard.

## Shim import-check table

All 14 import groups + name-existence checks pass under `.venv/Scripts/python.exe`:

| Check | Result |
|---|---|
| `from lathe.parser import parse_file, parse_text, LatheParseError, DuplicateFieldError` | PASS |
| `from lathe.shape_backend import run_shape_backend, collect_shape_conditioning` | PASS |
| `from lathe.shape_providers import maybe_run_shape_provider, ShapeProviderError, ShapeProviderUnavailable, ShapeProviderExecutionError, PROVIDERS, PROVIDER_ALIASES, normalize_provider_id` | PASS |
| `from lathe.errors import LatheError, BuildError, ShapeProviderError, LatheParseError, ResolutionError, RuntimeConfigError, BlenderExecutionError, BackendResolutionError, NormalizationError, PatchAPIError, UnresolvedNameError, DuplicateFieldError, ShapeProviderUnavailable, ShapeProviderExecutionError, ShapeMeshLoadError` | PASS |
| `from lathe.core.errors import BuildError` | PASS |
| `from lathe.providers.errors import ShapeProviderError` | PASS |
| `from lathe.blender_execution import BlenderExecutionError` | PASS |
| `from lathe.executor import BuildExecutor, STAGE_ORDER, BuildError, _run_blender_topology, probe_topology_backend` | PASS |
| `isinstance(ShapeProviderError('x','y'), RuntimeError) is True` | PASS |

## Dangling-TODO check (Stage 2.V)

`Stage 2.V` and `TODO.*errors\.py` matches: 6 lines, all in module-docstrings or comments referencing the migration that **already landed**. Three are stale `TODO`s that should now be backfilled or removed:

- `lathe/capabilities.py:20` — `# TODO(Stage 2.V): move these SSRF guard helpers into lathe/net.py` (`net.py` exists; helpers may already live there — verify and remove TODO).
- `lathe/core/stages/topology.py:14` — describes a TODO "to move to `lathe/errors.py` in Stage 2.V" as if pending; `BlenderExecutionError` already lives in `lathe/errors.py`.
- `lathe/net.py:18` — back-reference to a `TODO(Stage 2.V)` comment elsewhere; stale.

The remaining three (`errors.py:10`, `core/errors.py:3`, `providers/errors.py:3`) are descriptive "Landed in Stage 2.V (Wave 2)" docstrings — fine.

## Plan 10 false-positive confirmation

| Item | Expected | Observed |
|---|---|---|
| C3 fix not re-applied in Wave 2 | No `c3` in commit log | `git log --all --oneline | grep -i c3` → empty. PASS |
| Mi5 (trimesh missing) not addressed | `import trimesh` works in venv | `trimesh 4.11.5` available. PASS |
| Mi3 (`7919`) only in `constants.py` | Single canonical site | `grep 7919 lathe/` → only `lathe/constants.py:16`. PASS |

## Dead-code inventory (Stage 2.III/2.IV flags still present)

All nine flagged symbols are present in the refactored tree (none deleted in Wave 2 — correct, since Wave 2 was non-behavior-preserving-disallowed):

| Symbol | New home |
|---|---|
| `_generate_conditioned_candidates` | `lathe/shape/geometry/candidates.py:188` |
| `_generate_reconstruct_candidates` | `lathe/shape/geometry/candidates.py:240` |
| `_generate_adapt_candidates` | `lathe/shape/geometry/candidates.py:261` |
| `_generate_assemble_candidates` | `lathe/shape/geometry/candidates.py:282` |
| `_mechanical_named_meshes` | `lathe/shape/geometry/candidates.py:56` |
| `_env_module_named_meshes` | `lathe/shape/geometry/candidates.py:125` |
| `_runtime_from_external_mesh` | `lathe/shape/geometry/candidates.py:215` |
| `_score_candidate` | `lathe/shape/geometry/candidates.py:164` |
| `generate_candidate_mesh` | `lathe/core/geometry.py:46` (preserved byte-for-byte per file docstring) |

All are Wave-3 deletion targets.

## Shape contract untouched

`intent_mesh_handoff_v1` appears across `lathe/`, `grammar/`, `schema/`, `spec/`, `docs/`, `tests/` — identical references, no new occurrences introduced by Wave 2. The contract ID is unchanged. `lathe/shape/__init__.py` and `lathe/shape/backend.py` are new files that quote it correctly. PASS.

## Overall verdict: **needs follow-up**

Wave 2 met its primary decomposition goal cleanly and the public/shim surface is intact. Carry into Wave 3:

1. Decompose `checker.py` (856), `blueprints/__init__.py` (717), `cli.py` (625), `capabilities.py` (622), `resolver.py` (540).
2. Narrow or document the 7 `BLE001` catches living in Wave-2-introduced files (`core/geometry.py`, `core/stages/{topology,uv}.py`, `core/uv_ops.py`, `parser/imports.py`, `shape/geometry/conditioning.py`); keep `-O`-stripped `assert` cleanup honest by replacing the 17 production asserts with explicit `raise`.
3. Remove the three stale `Stage 2.V` TODO comments (`capabilities.py:20`, `core/stages/topology.py:14`, `net.py:18`).
4. Delete the nine flagged dead candidate-generation helpers in `lathe/shape/geometry/candidates.py` and `lathe/core/geometry.py`.
