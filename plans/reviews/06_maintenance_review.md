# Review: plans/06_maintenance.md — Maintenance & Activity

## Summary
The plan is comprehensive, ordered, and executable; it maps cleanly onto every finding in the 3/10 audit and sets measurable 90-day KPIs. It correctly sequences git-init hygiene before any remote push, gates CI on a three-OS × two-Python matrix, uses OIDC Trusted Publishing (no long-lived PyPI token), and protects the release environment with a reviewer gate. Phase 1 commit split (scaffolding / compiler / stdlib+examples+docs / tests) holds up against the actual file counts, with two small caveats noted below.

## Coverage vs. findings
| Finding | Addressed | Where |
|---|---|---|
| Not a git repo | Yes | Phase 1 step 1 |
| No `.github/` | Yes | Phases 3, 4 |
| No CI/CD | Yes | Phase 3 (7 workflows) |
| No CHANGELOG | Yes | Phase 5 step 31 |
| No release process / tags / PyPI | Yes | Phase 5 steps 33–35 |
| ~3 days of filesystem activity | Yes (weekly commit cadence KPI) | Success criteria |
| No SECURITY.md | Yes | Phase 4 step 26 |
| No dependabot/renovate | Yes | Phase 4 step 25 |
| No badge wall | Yes | Phase 7 |
| No LICENSE | Yes | Phase 1 step 4 (Apache-2.0) |

All 10 findings covered; Apache-2.0 choice is justified vs. MIT given `external/vggt/` is vendored.

## Citations verified
- `git log --oneline` → `fatal: not a git repository` — confirmed no `.git/`.
- `ls D:/lathe_v0_1/` shows **no** `.github/`, `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.gitignore`, `.gitattributes`, `.travis.yml`, `.circleci/`, `azure-pipelines.yml`, `.pre-commit-config.yaml`, `Jenkinsfile`, `.gitlab-ci.yml`, `renovate.json`, `FUNDING.yml`.
- Filesystem dates on non-transient files: `AGENTS.md` Apr 21, `pyproject.toml` Apr 22, `README.md`/`CLAUDE.md` Apr 23 — confirms ~3-day window.
- `pyproject.toml` has **no** `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest]`, `[tool.coverage]`, or `urls` table — all clean slate.

## Already-done items
**None.** No existing CI config, no release artifacts, no pre-commit config, no formatter config. Every artifact in the plan is greenfield. This is the cleanest intersection with other plans — nothing to reconcile.

## Commit-bucket feasibility (Phase 1 step 5)
File counts at the buckets named in the plan:

- **Scaffolding** (`.gitignore`, `.gitattributes`, `LICENSE`): 3 files — fine.
- **Compiler** (`lathe/` 69, `grammar/` 1, `schema/` 1, `spec/` 1): ~72 files — fine.
- **Stdlib + examples + docs** (`std/` 13 subdirs, `examples/` 22, `docs/` 8, `AGENTS.md`, `CLAUDE.md`, `README.md`): OK.
- **Tests** (`tests/` 17, `scripts/` 8): OK.

**Orphans not covered by any bucket:**
1. `pyproject.toml` / `lathe.egg-info/` — implicitly belongs in the compiler commit; plan should say so explicitly. (`lathe.egg-info/` must be in `.gitignore`, not committed.)
2. `cli/` is present but empty — delete before commit 1 or add a README.
3. `external/vggt/` — large vendored submodule. Plan's `.gitignore` line says "`external/vggt/` weights" (i.e. weights only). Need to decide: vendor the code, git-submodule it, or ignore wholesale. This is ambiguous in the plan and must be resolved **before** Phase 1 step 5 or the scaffolding commit will either leak weights or exclude code the compiler needs.
4. `.codex/` and `.agents/` — belong in stdlib/docs commit per `docs/codex_integration.md` reference in CLAUDE.md; plan doesn't name them.
5. `plans/` (11 files) — these reviews/plans should probably land as their own `docs: v0.1 planning artifacts` commit rather than being bundled into stdlib+examples+docs.

**Recommendation:** promote commit split to 5 commits or explicitly enumerate orphan placement.

## PyPI name check (step 34)
`pyproject.toml` lines 6 (`name = "lathe"`) and 38–39 (`lathe = "lathe.cli:main"` console script). Renaming the **distribution** to `lathe-lang` would **not** break the console script or imports — the package directory stays `lathe/`, only `[project].name` changes. Safe. Plan is correct to flag this as a pre-first-tag decision. `README.md` install-commands would also need an `s/pip install lathe/pip install lathe-lang/` sweep; call this out in step 34.

## Gaps
1. **`.github/FUNDING.yml`** — one-line config; zero-cost signal of maintainership.
2. **`.github/copilot-instructions.md`** — parallel to `CLAUDE.md`/`AGENTS.md` for GitHub Copilot users; mentioned in findings but not plan.
3. **Pre-commit hooks** — `.pre-commit-config.yaml` with ruff, ruff-format, end-of-file-fixer, trailing-whitespace, check-yaml, check-toml, and a `lathe check examples/courier_drone.lth` local hook. Complements CI; catches issues before push. Currently absent in plan.
4. **SBOM / provenance** — Sigstore/cosign via `pypa/gh-action-pypi-publish@release/v1` with `attestations: true`; one extra flag in `release.yml` and you get SLSA-level attestations. Plan mentions neither.
5. **`CITATION.cff`** — cheap; helps academic citation of the Lathe language.
6. **`.editorconfig`** — pairs with `.gitattributes`; DX plan (05) may own this, but cross-reference.
7. **Release-drafter categorization** — step 32 mentions it but no `.github/release-drafter.yml` template sketch for Lathe-specific labels (`language-contract`, `backend`, `shape-stage`).
8. **Codecov requires token for private forks and some public repos** — step 13 should note fallback to `coverage` comment-bot or `codecov/codecov-action@v4` with `use_oidc: true` to avoid token management.
9. **Version-bump tooling** — neither `bump-my-version`, `commitizen`, nor `setuptools-scm` is specified; manual version edits in `pyproject.toml` are error-prone. Pick one.
10. **PyPI 2FA / account recovery** — before configuring Trusted Publisher, `talmerri` PyPI account should have 2FA enabled; call out in step 34.

## Feasibility — week-1 scope for one maintainer
Day 1 (Phases 1–2): **tight but realistic** (~4h). Day 2 (Phase 3, 7 workflows): **ambitious** — writing 7 correct GitHub Actions YAML files, wiring matrix, OIDC, and Codecov is realistically a full day if each is author-tested via `workflow_dispatch`. Day 2–3 (Phase 4, ~12 governance files): **doable** mostly from templates. Day 3 (Phases 5, 7): realistic. Week 1 total: achievable if you defer `docs.yml` (step 15, MkDocs) and `lathe-smoke.yml` (step 17) to week 2 — they require additional config (`mkdocs.yml`, smoke runbook) that isn't pre-staged.

**Prerequisite crosscut with plan 05 (DX):** `.gitignore` is listed here (Phase 1 step 2) and almost certainly also in plan 05. Make 06 authoritative; DX plan should reference, not duplicate. Same for `.editorconfig`, `pyproject.toml` `[tool.ruff]` block, and `CONTRIBUTING.md` bootstrap instructions.

**Prerequisite crosscut with plan 02 (docs):** `docs.yml` (step 15) assumes MkDocs config exists; that's a docs-plan artifact. Either 06 ships a minimal `mkdocs.yml` or 15 lands after plan 02.

## 10/10 verdict
**Plan is 8.5/10 as written. To reach 10/10:**
1. Resolve `external/vggt/` vendoring policy before Phase 1 step 5 (blocker).
2. Expand commit buckets to explicitly place `pyproject.toml`, empty `cli/`, `.codex/`, `.agents/`, and `plans/`.
3. Add the 10 gap items above (FUNDING, copilot-instructions, pre-commit, attestations, CITATION, version-bump tool, 2FA note, Codecov-OIDC note, release-drafter template, editorconfig cross-ref).
4. Flag cross-plan duplication with plan 05 (DX) and plan 02 (docs) so `.gitignore`, `pyproject.toml` tool tables, and `mkdocs.yml` have a single owner.
5. Defer `docs.yml` and `lathe-smoke.yml` to week 2 explicitly, or document their prerequisites inline.

With those in place, the plan reaches 10/10: every finding is addressed, artifacts are concrete, KPIs are measurable, and the sequencing respects the stable `lathe.shape.intent_mesh_handoff_v1` contract via branch-protection + validator-regression nightly catch.
