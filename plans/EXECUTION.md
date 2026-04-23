# Execution Plan

Waves for executing the 10 amended plans. Designed around **file-cluster ownership** rather than plan-number so concurrent agents never touch the same file in the same wave.

## Principles

1. **Foundation first.** Nothing runs until git is initialized and the initial history is clean.
2. **No two concurrent agents touch the same file.** File ownership tables below.
3. **Additive before destructive.** Ship new files before editing existing code.
4. **Contract-first.** Never break the stable `lathe.shape.intent_mesh_handoff_v1` contract. Tests verify after every wave.
5. **Checkpoint after each wave.** Verify repo state (`git status`, `pytest -q`, `lathe doctor`) before moving to the next wave.

## Shared-file registry (conflicting files across plans)

| File | Touched by plans | Wave | Owner |
|---|---|---|---|
| `pyproject.toml` | 01, 02, 05, 06, 07 | 1 | **Wave 1 agent "foundation" serializes all additions** |
| `.gitignore` | 05, 06 | 0 | Plan 06 (single owner confirmed in amendments) |
| `LICENSE` | 02, 06 | 0 | Plan 06 creates; Plan 02 references |
| `CHANGELOG.md` | 02, 06 | 0 | Plan 06 creates |
| `CONTRIBUTING.md` | 02, 06 | 0 | Plan 06 creates |
| `SECURITY.md` | 02, 06, 07 | 0 (stub) / 2 (expand for security) | Plan 06 stubs; Plan 07 expands |
| `CODE_OF_CONDUCT.md` | 02, 06 | 0 | Plan 06 |
| `mkdocs.yml` | 02 | 1 | Plan 02 (Plan 06 CI consumes) |
| `executor.py` | 01 (split), 03 (layering), 07 (subprocess), 10 (M4b) | 2 | Single agent "executor-surgeon" owns cluster |
| `shape_providers.py` | 01 (split), 07 (SSRF), 10 (C1, C2, M1, M5, M6) | 2 | Single agent "shape-providers-surgeon" owns cluster |
| `blender_execution.py` | 07 (subprocess), 10 (M4) | 2 | Single agent "blender-surgeon" |
| `capabilities.py` | 03 (probe dedup), 07 (SSRF) | 2 | Single agent "capabilities-surgeon" |
| `resolver.py` | 01 (comprehensions), 10 (Mi1) | 2 | Single agent "resolver-surgeon" |
| `runtime_config.py` | 05 (env var audit), 07 (validation) | 2 | Single agent "config-surgeon" |
| `parser.py` | 01 (split) | 2 | Single agent "parser-surgeon" (no conflicts) |
| `shape_backend.py` | 01 (decompose), 03 (shape/ subpackage), 10 (M3, Mi2) | 2 | Single agent "shape-backend-surgeon" |

## Waves

### Wave 0 — Foundation (sequential, 1 agent)
Plan 06 Phase 1: git init + `.gitignore` + `.gitattributes` + `LICENSE` (Apache-2.0) + stub `CHANGELOG.md` / `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` / `SECURITY.md` / `CITATION.cff` / `FUNDING.yml` + 4 initial commits + `v0.1.0` tag.

**Do not push to a remote.** Local only.

**Exit criteria:** `git log --oneline` shows 4 commits + tag `v0.1.0`; `git status` clean; `external/vggt/` is ignored; no transient dirs committed.

### Wave 1 — Additive scaffolding (parallel team, 5 agents)
All agents write **new files only**. No edits to existing `lathe/` code.

| Agent | Scope | Files |
|---|---|---|
| `wave1-ci` | Plan 06 Phases 2–7 | `.github/workflows/*.yml`, `.github/ISSUE_TEMPLATE/*`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/dependabot.yml`, `.github/labels.yml`, `.github/FUNDING.yml`, `.pre-commit-config.yaml`, `scripts/bump_version.{sh,ps1}` |
| `wave1-docs` | Plan 02 Phases 3, 4, 6 | `mkdocs.yml`, `requirements-docs.txt`, `docs/architecture/*.md` (4 diagrams), `docs/gen_stdlib_index.py`, `docs/api/*.md` stubs |
| `wave1-dx` | Plan 05 Phases 1, 3, 4 | `uv.lock`, `Justfile`, `Makefile`, `Dockerfile`, `docker/Dockerfile.blender`, `.devcontainer/devcontainer.json`, `docker-compose.yml`, `.env.example`, `scripts/clean_workspace.{sh,ps1}` |
| `wave1-tests` | Plan 04 Phases 1–3 | `.coveragerc`, `tests/conftest.py`, `tests/fixtures/*`, `tests/{unit,integration,contract,property,golden}/` directories, `requirements-lock.txt` |
| `wave1-vision` | Plan 09 Phases 1, 3 | `docs/personas.md`, `docs/icp.md`, `docs/jtbd.md`, `docs/competitive_landscape.md`, `docs/roadmap_public.md`, `docs/walkthroughs/*.md` (3 synthetic scenarios) |

**Shared file coordination:** `pyproject.toml` needs updates from multiple wave-1 agents (ruff/mypy from 01, license field from 02, dev extras from 04, uv/dep-groups from 05, entry points from 03). **Serialize**: only `wave1-ci` edits `pyproject.toml` in Wave 1; it pulls in a consolidated diff representing all plans' pyproject additions. Other agents must NOT touch `pyproject.toml`.

**Exit criteria:** all new files present; `pytest -q` still green (no regressions from additive work); `git status` shows only new files, no edits to existing `lathe/` code.

### Wave 2 — Code surgery (parallel team, file-cluster owners)
Each agent owns one file cluster and applies the full set of changes from ALL plans that touch those files. No cross-agent file contention.

| Agent | File cluster | Plans aggregated |
|---|---|---|
| `wave2-executor` | `lathe/executor.py` → `lathe/core/stages/*`, `lathe/core/runtime.py`, `lathe/core/seeding.py`, `lathe/core/bake_helpers.py` | 01 Phase 4b + 03 layering + 07 Phase 4 (exec 1548 subprocess) + 10 M4b |
| `wave2-shape-providers` | `lathe/shape_providers.py` → `lathe/providers/*` | 01 Phase 5 + 03 shape subpackage + 07 Phase 3 SSRF + 10 C1, C2, M1, M5, M6 |
| `wave2-shape-backend` | `lathe/shape_backend.py` → `lathe/shape/*` | 01 Phase 7 + 03 shape subpackage + 10 M3, Mi2 |
| `wave2-parser` | `lathe/parser.py` → `lathe/parser/*` | 01 Phase 4 (no conflicts) |
| `wave2-blender-cap` | `lathe/blender_execution.py`, `lathe/capabilities.py` | 07 Phase 3 (capabilities SSRF) + 07 Phase 4 (blender subprocess) + 10 M4 + 03 capability-probe dedup |
| `wave2-config-resolver` | `lathe/runtime_config.py`, `lathe/resolver.py` | 05 env-var audit + 07 Phase 1 validation + 10 Mi1 resolver comprehensions |
| `wave2-errors` | `lathe/errors.py` (new) + import-shim re-exports everywhere | 01 Phase 3 + 10 Phase 4.5 hierarchy reconciliation. **Must run AFTER wave2-executor/shape-providers/shape-backend land** because those split files; shims need to know the new locations. |
| `wave2-constants` | `lathe/constants.py` (new) | 01 Phase 7 (RNG_PRIME_OFFSET) — tiny, can run first to unblock other surgeons |

**Coordination:** wave2-errors is serialized AFTER the other 7. All other 7 can run in parallel.

**Exit criteria:** all bare-excepts narrowed; parser/executor/shape_providers/shape_backend split into subpackages with LOC ≤ 500 per file; shims re-export old paths; `pytest -q` green; `lathe build examples/courier_drone.lth courier_drone` succeeds; hero `.lth` files still pass certification; `intent_mesh_handoff_v1` hash unchanged (verified by Plan 04 contract test).

### Wave 3 — Hardening + coverage (parallel team)

| Agent | Scope | Dependencies |
|---|---|---|
| `wave3-security` | Plan 07 remaining phases (5–12): SBOM, CodeQL, Bandit, Semgrep, Trivy, threat model doc, SECURITY.md full content, gitleaks | Wave 0+1 (CI exists), Wave 2 (code stable) |
| `wave3-tests-backfill` | Plan 04 Phases 4–11: zero-coverage backfill, property tests, golden snapshots, contract tests, error paths, mutation testing | Wave 2 (code stable) |
| `wave3-docs-content` | Plan 02 Phases 5 (tutorials), 7 (stdlib audit), 8 (cookbook), 9 (docstrings) | Wave 1 (mkdocs scaffold) |
| `wave3-dx-polish` | Plan 05 Phases 5 (doctor upgrades), 6 (completion), 7 (LSP + VS Code), 8 (optional deps install scripts), 9 (error messages), 9b (flags) | Wave 2 (code stable) |

**Exit criteria:** 85%+ coverage; `pip-audit` clean; docs site builds; VS Code extension usable on one hero; `lathe doctor --strict` green.

### Wave 4 — Product polish + launch prep (parallel team)

| Agent | Scope |
|---|---|
| `wave4-publish` | Plan 08 Phase 1 publish runner |
| `wave4-fmt` | Plan 08 Phase 2 canonical formatter |
| `wave4-repair` | Plan 08 Phase 3 autonomous repair loop |
| `wave4-second-stack` | Plan 08 Phase 4 `soft_surface_prop_v1` + Plan 03 Phase 6b deep-proof validation |
| `wave4-gallery` | Plan 08 Phases 5, 5b (hero gallery + benchmark scoreboard) |
| `wave4-reports-viewer` | Plan 08 Phases 6 (rich reports), 7 (artifact viewer) |
| `wave4-playground` | Plan 08 Phase 12 (Pyodide playground) |
| `wave4-vision-gtm` | Plan 09 Phases 2 (`lathe-godot` addon), 2b (Persona-C channels), 4 (benchmark study), 7 (community), 8 (monetization docs), 10 (distribution), 11 (content marketing) |

**Exit criteria:** every README-scaffolded item shipped; two backend stacks; public demo live; ≥3 LOIs outreach sent.

## Global coordination rules

1. **Every agent runs `git status` before starting** and refuses to proceed if the tree is dirty with files it's about to touch.
2. **Every agent commits its own work** with a conventional-commit message (`feat(stages):`, `fix(bug-C1):`, etc.) — not bulk commits at wave end.
3. **Every agent runs `pytest -q` before its final commit.** If failing, fix before commit or open a follow-up task; do not mask.
4. **Contract-frozen tests (`tests/contract/test_shape_handoff_v1.py`) must stay green every wave.** If any agent breaks the contract hash, immediate rollback + discussion.
5. **File-ownership is exclusive per wave.** If an agent discovers it needs to touch a file outside its cluster, it STOPS and coordinates via the team lead (me) rather than editing anyway.
6. **No push to remote yet.** Remote setup happens when the user explicitly approves (Wave 1 `wave1-ci` prepares `.github/` locally but does not push).

## Rough effort (from reviewer-revised estimates)

- Wave 0: 0.5 day
- Wave 1: 2 days (parallel) → ~1 day wall-clock
- Wave 2: 8 days (parallel) → ~2–3 days wall-clock
- Wave 3: 15 days (parallel) → ~4–5 days wall-clock
- Wave 4: 20 days (parallel) → ~5–7 days wall-clock

Total ≈ 45 days of work; ~13–17 days wall-clock with good parallelism.

---

## Current status

**Wave 0 in progress.**
