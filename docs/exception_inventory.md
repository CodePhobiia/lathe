# Exception And Fallback Inventory

This file tracks broad exception handlers and intentional no-op `pass` nodes in
active Python source under `lathe/` and `scripts/`. The companion test
`tests/unit/test_exception_inventory.py` fails when a new broad catch or no-op
appears without review.

## Rules

- Prefer typed exceptions for expected failure modes.
- Use `except Exception` only at isolation boundaries where third-party plugins,
  optional telemetry, subprocess cleanup, or defensive geometry probes must not
  take down the primary command.
- Do not leave silent failures. If a broad catch remains, it must either log,
  return an explicit degraded state, or be a tightly scoped best-effort probe.
- `pass` is allowed only for explicit no-op branches, optional import fallback,
  or already-documented degraded behavior.

## Tracked Broad Catches

| Path:line | Justification |
|---|---|
| `lathe/backends.py:590` | Plugin entry-point load isolation; logs a warning and keeps built-ins usable. |
| `lathe/cli/build_cmd.py:223` | Optional telemetry isolation; logs debug and does not change build result. |
| `lathe/core/stages/package.py:147` | Optional engine-manifest generation boundary; package still records diagnostics/report details. |
| `lathe/core/stages/package.py:389` | Best-effort preview/report enrichment boundary. |
| `lathe/doctor.py:324` | Doctor plugin probe isolation; stores the error on the record. |
| `lathe/geometry/kernel.py:146` | Geometry kernel plugin isolation; registry discovery must stay usable. |
| `lathe/geometry/reference_kernel.py:106` | Defensive trimesh cleanup boundary for malformed meshes. |
| `lathe/geometry/reference_kernel.py:151` | Defensive trimesh cleanup boundary for malformed meshes. |
| `lathe/publish/__init__.py:390` | Publish driver discovery isolation; failed optional drivers do not hide built-ins. |
| `lathe/publish/signed_repro.py:286` | Optional git metadata probe; receipt still records available fields. |
| `lathe/repair_loop.py:253` | Shape regeneration is probabilistic; failed repair round returns explicit `None`. |
| `lathe/scaffold_compiler.py:93` | Defensive scaffold compilation fallback path. |
| `lathe/scaffold_compiler.py:119` | Defensive scaffold compilation fallback path. |
| `lathe/scaffold_compiler.py:135` | Defensive scaffold compilation fallback path. |
| `lathe/selector_manifest.py:262` | Best-effort sub-part enrichment; manifest remains valid without face/edge detail. |
| `lathe/subproc.py:208` | Subprocess cleanup/logging isolation after the primary result is known. |
| `lathe/validators/geometry_integrity.py:272` | Optional geometry-kernel cross-check; validator records degraded evidence. |
| `lathe/validators/soft_silhouette.py:66` | Defensive trimesh adjacency probe for optional soft-surface evidence. |
| `lathe/validators/soft_silhouette.py:91` | Defensive trimesh edge-length probe for optional soft-surface evidence. |
| `scripts/bench_geometry_kernel.py:128` | Benchmark harness captures run failures as data instead of aborting the suite. |
| `scripts/bench_geometry_kernel.py:147` | Benchmark harness captures run failures as data instead of aborting the suite. |
| `scripts/bench_geometry_kernel.py:269` | Benchmark verification captures comparison failures as data. |

## Tracked No-op Pass Nodes

| Path:line | Justification |
|---|---|
| `lathe/cache_paths.py:38` | Optional `platformdirs` import fallback. |
| `lathe/cli/fmt_cmd.py:74` | Explicit no-op branch for `--check` with no diff requested. |
| `lathe/core/common.py:58` | Optional NumPy conversion fallback. |
| `lathe/core/common.py:102` | Optional NumPy conversion fallback. |
| `lathe/core/geometry.py:38` | Optional mesh cleanup operation may be absent. |
| `lathe/core/geometry.py:48` | Optional mesh cleanup operation may be absent. |
| `lathe/doctor.py:136` | Temporary-file writability probe body. |
| `lathe/exact_solids.py:150` | Typed trimesh smoothing failure fallback on degenerate topology. |
| `lathe/exact_solids.py:207` | Typed trimesh smoothing failure fallback on degenerate topology. |
| `lathe/exact_solids.py:241` | Typed trimesh process failure fallback on malformed topology. |
| `lathe/geometry_kernel.py:246` | Typed trimesh process failure fallback after essential cleanup. |
| `lathe/parser/imports.py:48` | Import-cycle traversal skips already-seen files. |
| `lathe/providers/adapters/vggt.py:255` | Optional CUDA cache cleanup fallback. |
| `lathe/publish/__init__.py:245` | Optional path cleanup fallback after publish staging. |
| `lathe/runtime_config.py:337` | Optional runtime-config redaction branch. |
| `lathe/selector_manifest.py:59` | Relative-path fallback when build dir is outside repo root. |
| `lathe/validators/composition.py:110` | Optional score extraction fallback. |
| `lathe/validators/composition.py:116` | Optional score extraction fallback. |
| `lathe/validators/geometry_integrity.py:269` | Optional geometry-kernel body-count probe skip. |
| `lathe/validators/urdf_validation.py:204` | Avoids double-reporting a diagnostic already emitted as `L6401`. |
| `scripts/run_benchmark.py:153` | Optional `psutil` child-process probe fallback. |
