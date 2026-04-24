# Wave 3 Code Hygiene Review

**Reviewer:** reviewer-code-hygiene
**Branch state:** post Wave 3 (BL-1..BL-16) sweep
**Date:** 2026-04-23

## Summary verdict

**PASS with one flagged carryover.** All 11 hygiene primitives (bare-except, production asserts, stale Stage 2.V TODOs, subproc wrapper adoption, SSRF routing, dead-code deletion, torch pin, import shims) check out at zero / correct. BL-4..BL-7 all landed under the 500-LOC ceiling. Only `blender_execution.py` exceeds 500 LOC (567) — a +9 line regression from the pre-Wave-3 558 figure in the backlog brief. `resolver.py` (540) is the intentional BL-8 deferral.

## LOC table (offenders only)

| File | LOC | Status |
|---|---|---|
| `lathe/blender_execution.py` | 567 | **REGRESSION** vs pre-Wave-3 baseline of 558; expected ≤500 after BL-10. Recommend follow-up carve-out of `_render_mesh_pass` / `_project_mesh` helpers (lines 139–190) or `build_execution_bundle` (247–516) into a submodule. |
| `lathe/resolver.py` | 540 | Known deferral (BL-8). No action. |

BL-4/5/6/7 targets: all well under 500. Largest is `lathe/checker/assets.py` at 397; `lathe/cli/__init__.py` 261; `lathe/blueprints/panels.py` 245; `lathe/capabilities.py` 492 (new ceiling for this module; 8 LOC of headroom, watch in Wave 4).

## Bare-except / assert / stale-TODO counts

| Pattern | Occurrences | Expected |
|---|---|---|
| `except Exception` (no `noqa: BLE001`) | 0 | 0 |
| `# noqa: BLE001` | 0 | — |
| production `assert ` under `lathe/` | 0 | 0 |
| `Stage 2.V` stale markers | 0 | 0 |
| total `TODO(...)` under `lathe/**/*.py` | 1 | — |

The single surviving TODO is `lathe/capabilities.py:424` — the Wave-4-tracked trust-boundary marker for Hunyuan `/health`. Correct per BL-9.

## Subproc wrapper verification (BL-11)

- Import smoke passes: `from lathe.subproc import run_sandboxed, SandboxResult, DEFAULT_STDERR_DENY_PATTERNS` — ok.
- `lathe/subproc.py` is 250 LOC, a proper standalone module.
- `grep "subprocess.run"` in `lathe/blender_execution.py`: 0 hits.
- `grep "subprocess.run"` in `lathe/core/stages/topology.py`: 0 hits.
- Both call sites use `run_sandboxed`: `blender_execution.py:212`, `core/stages/topology.py:55`.
- No other `subprocess.run` regressions surfaced via `grep run_sandboxed`.

## SSRF migration verification (BL-7 + BL-12)

- `grep "urlopen"` in `lathe/capabilities.py` — 2 hits, both legitimate: line 15 imports `safe_urlopen` from `lathe.net`; line 399 calls `safe_urlopen(`.
- No raw `urllib.request.urlopen(` in `capabilities.py`.
- `lathe/net.py` (254 LOC) present, exports `NetGuardError` + `safe_urlopen`.

## JSON audit markers (BL-9)

- `docs/security/json_ingress_audit.md` exists (61 lines).
- Audit reports `Trust-boundary, NOT yet validated | 1`.
- `grep "TODO(security): trust-boundary JSON ingress"` in `lathe/`: 1 hit (`capabilities.py:424`).
- Counts match (1 = 1). Consistent.

## Dead-code deletion (BL-13)

- `lathe/shape/geometry/candidates.py`: **does not exist** (fully deleted).
- `grep "generate_candidate_mesh"` in `lathe/`: only `.pyc` bytecode matches (cached artifacts from prior builds, not source). No source references — confirmed deleted.

Recommend stale `.pyc` cache cleanup but non-blocking.

## BL-15 indent fix (`_build_trace`)

Inspected `lathe/core/stages/package.py:126–201`. Indentation consistent at 8 spaces throughout the returned dict literal; no mixed-indent mismatch. PASS.

## Torch pin status (BL-16)

```
  "torch>=2.11.0",
  "torchvision>=0.26.0",
```

No TODO comment above the pin. Pin sits cleanly in the `vggt` optional group. PASS.

## Shim import matrix (regression guard)

All 10 legacy import paths resolve successfully against `.venv/Scripts/python.exe`:

| Import | Status |
|---|---|
| `from lathe.parser import parse_file, parse_text, LatheParseError` | ok |
| `from lathe.shape_backend import run_shape_backend` | ok |
| `from lathe.shape_providers import maybe_run_shape_provider, ShapeProviderError` | ok |
| `from lathe.errors import LatheError, BuildError` | ok |
| `from lathe.executor import BuildExecutor, STAGE_ORDER` | ok |
| `from lathe.checker import check_program` | ok |
| `from lathe.blueprints import resolve_blueprint` | ok |
| `from lathe.cli import main` | ok |
| `from lathe.capabilities import probe_hunyuan_endpoint` | ok |
| `from lathe.subproc import run_sandboxed` | ok |

No Wave-2 shim regression.

## New anti-patterns introduced in Wave 3

None observed. Specifically:

- No new `except Exception` sites slipped in to silence subproc failures.
- `run_sandboxed` adoption is total (2/2 sites migrated, no mixed usage).
- `safe_urlopen` is the only network primitive in `capabilities.py`.
- No new `assert` statements.
- The single TODO is schema-tracked and audit-documented.

## Actionable follow-ups (non-blocking)

1. **`lathe/blender_execution.py` — 9-LOC regression over pre-Wave-3 baseline.** Either refine the carve-out (split `build_execution_bundle` or the render helpers into a submodule) or update `WAVE3_BACKLOG.md` to acknowledge the new ceiling. Worth flagging to Wave 4.
2. **`lathe/capabilities.py` at 492 LOC** — 8 LOC from the 500 ceiling. Monitor.
3. **Stale `.pyc` caches** still reference `generate_candidate_mesh`. `python -B` or a `find lathe -name __pycache__ -exec rm -rf` in CI setup would prevent resurrection signals.
