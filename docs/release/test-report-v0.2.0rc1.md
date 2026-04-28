# Test Report — Lathe v0.2.0rc1

| Field | Value |
|---|---|
| Version | 0.2.0rc1 |
| Branch | worktree-readiness-pass-v020rc1 |
| Base commit | 30f9186 |
| Generated | 2026-04-28 |
| Owner | Tal Merri (@talmerri) |
| Host environment | Windows 10 Home (build 19045); Python from `.venv\Scripts\python.exe` |

---

## Local pytest results

This file is the **template + recorded local Windows result skeleton**. Result columns for all rows are pending the Phase 6 test runner sub-pass, which must be executed from a clean checkout. Non-Windows rows require CI runners and will remain `requires-human` until the branch is pushed and `.github/workflows/ci.yml` is active.

Canonical command:

```
python -m pytest -q
```

| OS | Python | Command | Passed | Failed | Skipped | Deselected | Coverage | Source |
|---|---|---|---|---|---|---|---|---|
| Windows 10 | 3.11 | `python -m pytest -q` | pending Phase 6 run from clean checkout | pending | pending | pending | pending | local |
| Windows 10 | 3.12 | `python -m pytest -q` | requires-human: needs CI run on remote runner; reference workflow `.github/workflows/ci.yml` once branch is pushed | — | — | — | — | — |
| Ubuntu | 3.11 | `python -m pytest -q` | requires-human: needs CI run on remote runner; reference workflow `.github/workflows/ci.yml` once branch is pushed | — | — | — | — | — |
| Ubuntu | 3.12 | `python -m pytest -q` | requires-human: needs CI run on remote runner; reference workflow `.github/workflows/ci.yml` once branch is pushed | — | — | — | — | — |
| macOS | 3.11 | `python -m pytest -q` | requires-human: needs CI run on remote runner; reference workflow `.github/workflows/ci.yml` once branch is pushed | — | — | — | — | — |
| macOS | 3.12 | `python -m pytest -q` | requires-human: needs CI run on remote runner; reference workflow `.github/workflows/ci.yml` once branch is pushed | — | — | — | — | — |

---

## Skipped tests inventory

Tests that are collected but skipped at runtime due to missing optional dependencies or environment conditions.

| Test marker | Reason for skip | When it should re-enable |
|---|---|---|
| `requires_blender` | Blender executable not present in PATH or `.venv`; topology/UV adapter falls back to deterministic reference path | Re-enable when Blender is installed and `lathe.cli doctor` reports `blender: ok` |
| `requires_xatlas` | xatlas Python binding not installed; UV adapter gracefully degrades to reference UV | Re-enable when `pip install xatlas` succeeds in the test environment |
| `requires_torch` | PyTorch not installed; learned shape providers (`vggt_local`, `auto_learned`) unavailable | Re-enable when a torch-capable environment is provisioned; opt-in via runtime config |
| `requires_network` | Network calls are blocked in offline/sandboxed CI; Hunyuan HTTP provider and telemetry ingest are unreachable | Re-enable in an environment with controlled outbound access; mock tests cover the protocol layer |
| `slow` | Wall-clock budget exceeds the default fast lane (intentionally excluded from the main `pytest -q` run) | Runs in the dedicated `slow` CI job; run locally with `-m slow` |
| `fuzz` | Hypothesis / fuzz tests require longer shrink budgets that bloat the default run time | Runs in the dedicated `fuzz` CI job; run locally with `-m fuzz` |

---

## Deselected tests inventory

Tests collected but deselected by the default marker filter. Per README, the default lane intentionally excludes `slow`, `golden`, `property`, and `fuzz` partitions; CI splits each into a separate job.

| Partition | Marker(s) | CI job | When to run locally |
|---|---|---|---|
| Golden / snapshot | `golden` | `golden` CI job | `python -m pytest tests/golden/ -q` |
| Property-based | `property` | `property` CI job | `python -m pytest tests/property/ -q` |
| Slow / benchmark | `slow` | `slow` CI job | `python -m pytest -m slow -q` |
| Fuzz | `fuzz` | `fuzz` CI job | `python -m pytest tests/fuzz/ -q` |
| Examples corpus | (no dedicated marker; separate job) | `examples` CI job | `python -m pytest tests/unit/test_example_corpus.py -q` |
| Visual quality | (no dedicated marker; separate job) | `visual-quality` CI job | `python -m pytest tests/test_visual_quality.py -q` |
| Benchmark regression | (no dedicated marker; separate job) | `benchmark` CI job | `python -m pytest tests/test_benchmarks.py -q` |

---

## Coverage summary

The global coverage threshold is **65%**, set in both `pyproject.toml` (`[tool.coverage.report] fail_under = 65`) and `.coveragerc`. This is a pre-release baseline; BL-39 tracks the long-term **85%** target.

Per-package gates defined in `[tool.lathe.coverage_gates]`:

| Package | Gate | Paths |
|---|---|---|
| parser | 60% | `lathe/parser` |
| resolver | 90% | `lathe/resolver.py` |
| checker | 70% | `lathe/checker` |
| planner | 90% | `lathe/planner.py` |
| provider_config | 75% | `lathe/runtime_config.py`, `lathe/providers/registry.py`, `lathe/providers/selection.py` |
| sandboxing | 55% | `lathe/sandbox`, `lathe/subproc.py` |
| cache | 70% | `lathe/cache.py` |
| cli | 35% | `lathe/cli` |
| telemetry | 80% | `lathe/telemetry.py` |
| security | 75% | `lathe/parser/prompt_injection.py`, `lathe/net.py`, `lathe/publish/signed_repro.py` |

Actual coverage result: **pending Phase 6 run from clean checkout**.

---

## Test partition details

### Contract tests — `tests/contract/`

Directory confirmed: `tests/contract/` (contains `test_shape_handoff_v1.py`, `test_stable_backend_contracts.py`).

These tests assert the stability of the public shape-stage contract `lathe.shape.intent_mesh_handoff_v1` and backend IDs. They must pass in every lane.

Result: pending Phase 6 run.

### Golden / snapshot tests — `tests/golden/`

Directory confirmed: `tests/golden/` (contains `test_artifact_contract_snapshots.py`, `test_cli_help_snapshots.py`, `test_geometry_fixtures.py`, `test_hero_bundles.py`; snapshot store at `tests/golden/__snapshots__/`).

Snapshot mismatches indicate a change to CLI output or artifact shape. Update snapshots intentionally with `--snapshot-update`.

Result: pending Phase 6 run (deselected from default lane; run in `golden` CI job).

### Property-based tests — `tests/property/`

Directory confirmed: `tests/property/` (contains `test_exact_solids_properties.py`, `test_feature_grammar_properties.py`, `test_geometry_kernel_properties.py`, `test_resolver_properties.py`, `test_shape_ir_properties.py`).

Uses Hypothesis. Deselected from the default lane; run in the `property` CI job.

Result: pending Phase 6 run.

### Fuzz tests — `tests/fuzz/`

Directory confirmed: `tests/fuzz/` (contains `test_ingress_fuzz.py`, `test_normalizer_properties.py`, `test_parser_fuzz.py`).

Result: pending Phase 6 run (deselected from default lane; run in `fuzz` CI job).

### Slow / benchmark / visual-quality tests

- `tests/test_benchmarks.py` — confirmed present. Runs in `benchmark` CI job.
- `tests/test_visual_quality.py` — confirmed present. Runs in `visual-quality` CI job.
- Hand-authored perf budgets documented at `docs/perf_budgets.md` (confirmed present); per-hero timing targets sourced from `lathe/hero_manifest.py`.

Result: pending Phase 6 run.

### Example corpus build + certification — `tests/unit/test_example_corpus.py`

File confirmed present. Exercises `lathe check` + `lathe plan` + `lathe materialize` + `lathe build` across the checked-in `.lth` examples. Runs in the `examples` CI job.

Result: pending Phase 6 run.

### Bug regression tests — `tests/bugs/`

Directory confirmed: `tests/bugs/` (contains `test_parser_budgets.py`).

Result: pending Phase 6 run.

### Integration tests — `tests/integration/`

Directory confirmed: `tests/integration/` (contains `test_manifold_hero_watertight.py`).

Result: pending Phase 6 run.

### Godot addon manual smoke

**requires-human:** The Godot addon lives at `editors/godot/lathe-addon/`. The integration demo project is at `examples/godot_integration_demo/`. Manual procedure: open the demo project in Godot 4, verify the addon loads without errors, confirm the certified-state indicator updates after a `lathe build` run, and verify the fsnotify watcher detects file changes. No automated harness exists for this; record pass/fail in the release evidence packet.

### External GLB/USD viewer validation

**requires-human:** Open one representative GLB and one USD output from the example corpus in an external viewer (e.g., Babylon.js sandbox, Apple Preview, or USD viewer of choice). Confirm mesh integrity, material channels, and no visible corruption. Record viewer name and asset name in the release evidence packet.

### Load and performance testing

**requires-human:** Full load testing is out of scope for 0.2.0rc1 per Phase 8 scope decision. Hand-authored perf budgets are documented at `docs/perf_budgets.md`. If automated perf regression is required, run `python -m pytest tests/test_benchmarks.py -q` and compare against the budgets in that file.

### Security scan

- **Bandit / semgrep:** requires-human — run locally with `bandit -r lathe/` and `semgrep --config=auto lathe/`. Record findings in the security section of the evidence packet.
- **CodeQL:** requires-human — CodeQL URL not yet provisioned; enable via GitHub Advanced Security once branch is pushed and CI is active.

### Penetration testing

**requires-human:** No automated pen-test harness. Manual review of prompt-injection surface (`lathe/parser/prompt_injection.py`) and network surface (`lathe/net.py`) required. Record findings in the security section of the evidence packet.
