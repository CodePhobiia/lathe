# Lathe test suite

This directory hosts the pytest suite for the Lathe compiler and runtime.
The full coverage plan lives at [`plans/04_test_coverage.md`](../plans/04_test_coverage.md).

## Taxonomy

Tests are organized by the kind of property they verify rather than by
the module under test:

| Directory | Purpose |
|---|---|
| `unit/` | Single-module, deterministic, no external deps. Exercise happy path + boundary + malformed inputs. Target ≥85% line coverage per module. |
| `integration/` | Multi-module pipelines (parser → executor → package) or CLI-level flows. May depend on mocked externals. |
| `contract/` | Pin stable IDs and interface shapes. Any change here is a public-API change and requires explicit migration notes. Currently covers `lathe.shape.intent_mesh_handoff_v1`. |
| `property/` | Hypothesis-driven invariants: boolean-algebra laws over geometry, parse/serialize round-trips, normalizer idempotence, grammar fuzz. |
| `golden/` | Snapshot tests for hero examples. Snapshots live under `__snapshots__/`. See Plan 04 Phase 8 for the normalization rules (timestamps, absolute paths, probe latencies, repr ids all stripped before hashing). |
| `fuzz/` | Grammar/parser fuzzing driven by Hypothesis strategies derived from `grammar/lathe.lark`. |
| `bugs/` | One test file per fixed regression, named after the issue/PR. |
| `fixtures/` | Shared fixtures (mocks for Hunyuan/VGGT/Blender/xatlas/Codex ImageGen; hero-AST factories). |

The flat `test_*.py` files at the top of `tests/` are the Wave 0 suite and
remain green throughout; Wave 3 may migrate individual cases into the
taxonomy above, but no wave touches them without intent.

## Skip markers

Capability-gated tests are marked via custom markers declared in
`conftest.py`:

- `@pytest.mark.requires_blender` — needs a Blender executable (looks at
  `LATHE_BLENDER_PATH` first, then `PATH`).
- `@pytest.mark.requires_xatlas` — needs the `xatlas` Python package.
- `@pytest.mark.requires_torch` — needs the `torch` Python package.
- `@pytest.mark.requires_network` — opt-in via
  `LATHE_TESTS_ALLOW_NETWORK=1`.

When a capability is absent, the test is auto-skipped with a
human-readable reason. Running with `pip install -e .[dev]` and no
optional extras should leave every hard-required test runnable.

Other non-capability markers:

- `@pytest.mark.property` — Hypothesis-driven test; runs with reduced
  example budget in PR CI and full budget in nightly.
- `@pytest.mark.golden` — snapshot test; PRs that intentionally modify a
  snapshot must update it via `pytest --snapshot-update`.
- `@pytest.mark.contract` — stable-contract test; failures must not be
  silenced.

## CI `full` matrix enforcement

Setting `LATHE_CI_FULL=1` flips auto-skip into a hard failure: if any
capability-gated test would skip, the test run aborts with the missing
capability names listed. This is how the `full` leg of the CI matrix
ensures that every extras-gated code path actually runs somewhere. Local
development (no env var) keeps the friendly auto-skip behavior.

## Shared fixtures

Declared in `tests/conftest.py`:

- `tmp_workspace` — per-test scratch directory (thin wrapper over
  pytest's `tmp_path`, kept as a fixture so Wave 3 can attach structure
  without churning call sites).
- `lathe_env` — snapshot of a clean, deterministic env-var subset; also
  unsets `LATHE_*` and proxy vars so the build runs reproducibly.
- `repo_root` — absolute path to the repo root.

Declared in `tests/fixtures/`:

- `hunyuan_server` (`mock_hunyuan.py`) — in-process mock of the Hunyuan
  GLB-generation HTTP endpoint.
- `vggt_stub_point_cloud`, `vggt_stub_factory` (`mock_vggt.py`) —
  deterministic pure-numpy point-map generator.
- `mock_blender_adapter`, `blender_subprocess_stub` (`mock_blender.py`) —
  adapter-level and subprocess-level Blender mocks.
- `mock_xatlas_atlas` (`mock_xatlas.py`) — monkeypatched
  `xatlas.parametrize`.
- `mock_codex_bridge` (`mock_codex_imagegen.py`) — Codex ImageGen bridge
  stubbed with the placeholder PNG at
  `fixtures/codex_imagegen_samples/placeholder.png`.
- `sample_program(name)`, `hero_sample_program` (`sample_programs.py`) —
  hero `.lth` AST factory.

Wave 3 will register these modules as pytest plugins through
`conftest.py` once Wave 2's code surgery settles; for now they are
importable by tests that opt in explicitly.

## Running

```bash
# Full suite.
python -m pytest -q

# Only skip-safe tests (no optional extras expected):
python -m pytest -q -m "not requires_blender and not requires_xatlas and not requires_torch"

# CI-full matrix leg (fails loudly if extras are missing):
LATHE_CI_FULL=1 python -m pytest -q
```

Coverage is configured via `.coveragerc` at the repo root. The
`fail_under` gate is at `0` today and will be raised to `85` in Wave 3
(Plan 04 Phase 2).
