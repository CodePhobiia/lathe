# JSON Ingress Audit (BL-9, Plan 07 Phase 1)

Classifies every `json.loads` / `json.load(` site under `lathe/` as trust-boundary (must route through `validate_json` with a schema in Wave 4) or internal-controlled (Lathe produced it). Annotation only; no schemas added.

## Summary

| Metric | Count |
|---|---|
| Total sites in `lathe/` | 27 |
| Sites in this audit's scope (editable files) | 25 |
| Sites out of scope (excluded cluster: `blender_execution.py`) | 2 |
| Trust-boundary, NOT yet validated | 1 |
| Trust-boundary, already validated | 1 |
| Internal-controlled | 23 |

Only `runtime_config.py:165` is schema-validated today (in `8e70aa3`). `capabilities.py:423` is newly annotated with `TODO(security)` pending Wave 4.

## Per-site table

| Path:Line | Category | Source | Action |
|---|---|---|---|
| `lathe/capabilities.py:63` | internal | `importlib.metadata` `direct_url.json` (pip-written) | none |
| `lathe/capabilities.py:423` | trust-boundary | Hunyuan HTTP `/health` response body | Wave 4: `hunyuan_probe.schema.json` |
| `lathe/cli/inspect_cmd.py:42` | internal | Our own `build_report.json` | none |
| `lathe/cli/inspect_cmd.py:43` | internal | Our own shape `bundle.json` | none |
| `lathe/cli/inspect_cmd.py:44` | internal | Our own validate `report.json` | none |
| `lathe/cli/inspect_cmd.py:70` | internal | Our own shape `bundle.json` | none |
| `lathe/cli/inspect_cmd.py:71` | internal | Our own validate `report.json` | none |
| `lathe/cli/build_cmd.py:56` | internal | Our own execution `bundle.json` (just emitted) | none |
| `lathe/executor.py:283` | internal | Cached `build_report.json` copytree'd from prior build | none |
| `lathe/bridge/blender_plan.py:140` | internal | Our own execution `bundle.json` | none |
| `lathe/eval_harness.py:22` | internal | `lathe/benchmarks/catalog.json` package fixture | none |
| `lathe/eval_harness.py:36` | internal | Our own shape `bundle.json` (just built) | none |
| `lathe/eval_harness.py:37` | internal | Our own validate `report.json` (just built) | none |
| `lathe/eval_harness.py:57` | internal | Snapshot fixture in `lathe/benchmarks/` | none |
| `lathe/eval_harness.py:59` | internal | Our own shape `bundle.json` | none |
| `lathe/eval_harness.py:60` | internal | Our own topology `bundle.json` | none |
| `lathe/eval_harness.py:61` | internal | Our own interfaces `bundle.json` | none |
| `lathe/eval_harness.py:62` | internal | Our own surface `bundle.json` | none |
| `lathe/eval_harness.py:118` | internal | Our own shape `bundle.json` | none |
| `lathe/bench_runtime.py:32` | internal | Our own validate `report.json` (just built) | none |
| `lathe/bench_runtime.py:33` | internal | Our own shape `bundle.json` (just built) | none |
| `lathe/schema.py:21` | internal | `schema/lathe.schema.json` (this IS the schema) | none |
| `lathe/geometry_kernel.py:191` | internal | In-memory `dumps`/`loads` deep-copy of `_FUSION_CACHE` (no I/O) | none |
| `lathe/runtime_config.py:28` | internal | `schema/runtime_config.schema.json` (this IS the schema) | none |
| `lathe/runtime_config.py:165` | validated | User-supplied runtime_config file; validated via `_validate_runtime_config` | none |
| `lathe/blender_execution.py:424` | out of scope | surgeon-subproc cluster | re-audit Wave 4 |
| `lathe/blender_execution.py:530` | out of scope | surgeon-subproc cluster | re-audit Wave 4 |

## Why internal sites are safe without schemas

"Our own stage bundle" sites read files `executor.py` and the stage modules just wrote under a Lathe-owned `out_dir` or tempdir. Anyone with write access there already has code execution on the build host; a schema at the choke point does not raise the security bar. Schemas there would serve contract stability, not security — out of scope for BL-9.

## Appendix: Wave 4 schemas

New schemas from this audit:

1. **`hunyuan_probe.schema.json`** — validates the Hunyuan HTTP `/health` JSON body at `capabilities.py:423`. Network trust boundary.

Re-audit alongside BL-10/BL-11: `blender_execution.py:424` (Blender subprocess summary) and `blender_execution.py:530` (execution `bundle.json`). The subprocess boundary plus `allow_autoexec`/`trusted` modes arguably make :424 a defensible trust boundary — flag for reclassification.
