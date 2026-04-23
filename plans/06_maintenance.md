# Implementation Plan: Maintenance & Activity 3/10 → 10/10

## Overview
Repo has zero version-control or automation signal. Drive to a fully governed OSS project: git + GitHub + CI matrix + OIDC PyPI release + Dependabot + policy docs + measurable activity KPIs — without perturbing the stable `lathe.shape.intent_mesh_handoff_v1` contract.

---

## Phase 1 — Local git init & hygiene (day 1)

1. `git init -b main`, set `user.email=talmerri@gmail.com`, `core.autocrlf=input`.
2. **`.gitignore` — this plan is the single owner.** Plan 05 (DX) Phase 2 defers to this list; do not duplicate patterns there. Covers: `dist_*/`, `dist/`, `cache_probe_*/`, `warm_*/`, `tmp_*/`, `v05_*/`, `.lathe_lark_cache`, `.venv/`, `.venv_old_broken/`, `.venv*/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `*.pyc`, `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/`, `external/vggt/` (entire directory — see vendoring decision below), `*.blend1`, `node_modules/`. Matches CLAUDE.md.
   - **`external/vggt/` vendoring decision: ignore, not vendor.** The entire `external/vggt/` directory is gitignored. It is an optional, locally-cloned dependency for the VGGT shape provider; fetch instructions live in `docs/providers/vggt.md`. Rationale: repo size and license complexity (custom Meta VGGT License) make vendoring or submoduling worse than documenting a local clone. Initial commit message must state: *"external/vggt/ is an optional, locally-cloned dependency for the VGGT shape provider; documented in `docs/providers/vggt.md`. Not vendored due to size and license complexity (custom Meta VGGT License)."*
3. `.gitattributes` with `* text=auto eol=lf`, `*.lth text eol=lf`, `*.glb binary`, `*.usda text`, `*.png binary`, `*.obj text`.
4. `LICENSE` — **Apache-2.0** (permissive + patent grant; matches vggt posture).
5. Initial commits as four logical commits (not one mega-blob). Every tracked top-level entry is allocated exactly once:
   - **Commit 1 — `chore: repo scaffolding, governance, and plans`**
     Contents: `.gitignore`, `.gitattributes`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `pyproject.toml`, `plans/`, `.codex/`, `.agents/`.
     Commit body must include the `external/vggt/` rationale from item #2.
   - **Commit 2 — `feat: lathe v0.1 reference compiler`**
     Contents: `lathe/`, `cli/`, `grammar/`, `schema/`, `spec/`, `AGENTS.md`, `CLAUDE.md`.
     (Note: `cli/` is currently empty — add a one-line `cli/README.md` stub or delete before commit, don't ship an empty dir.)
   - **Commit 3 — `feat: stdlib, examples, and docs`**
     Contents: `std/`, `examples/`, `docs/`, `README.md`.
   - **Commit 4 — `test: pytest suite, smoke scripts, CI seed`**
     Contents: `tests/`, `scripts/`, `.github/` (seeded empty or with a placeholder; workflows land in Phase 3).
6. Tag `v0.1.0` on the last commit.
6a. **`.pre-commit-config.yaml`** at repo root. Hooks: `ruff` (lint), `ruff-format`, `mypy` (advisory), `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-toml`, `check-added-large-files` (cap ~500 KiB), and `gitleaks` (secret scan). Document `pre-commit install` in `CONTRIBUTING.md`. CI mirrors the same hooks so local + remote stay aligned.

## Phase 2 — Remote + protection (day 1)

7. Create GitHub repo `talmerri/lathe` (public). Enable Issues, Discussions, Projects; Wiki off.
8. Push `main` + tag.
9. Branch protection on `main`: require PR review (1), dismiss stale approvals, require linear history, require signed commits, required status checks (Phase 3), no force-push, no deletion, include admins.
10. Default branch `main`. Auto-delete head branches. Squash-merge only; PR title Conventional Commits.

## Phase 3 — CI/CD on GitHub Actions (day 2)

11. **`.github/workflows/ci.yml`** — on push/PR. Matrix: `{ubuntu-latest, windows-latest, macos-latest} × {3.11, 3.12}`. Jobs: setup-python → `pip install -e .[dev,xatlas,geometry,export]` → `pytest -q` → `lathe doctor` → `lathe check examples/courier_drone.lth`. `fail-fast: false`.
12. **`.github/workflows/lint.yml`** — `ruff check .`, `ruff format --check`, `mypy lathe/` advisory initially. Adds `ruff.toml` + `[tool.mypy]` to pyproject.
13. **`.github/workflows/coverage.yml`** — `pytest --cov=lathe --cov-report=xml`, uploads to Codecov. Fails PR if coverage drops >1%.
14. **`.github/workflows/release.yml`** — on tag `v*.*.*`: build sdist+wheel, publish to PyPI via **Trusted Publishing (OIDC)** — no API token. GitHub Release with auto notes from `CHANGELOG.md`.
15. **`.github/workflows/docs.yml`** — on push to `main` under `docs/**`, `spec/**`, `README.md`. MkDocs build + deploy to `gh-pages`. **`docs.yml` consumes `mkdocs.yml` owned by Plan 02 (Documentation). Coordinate so `mkdocs.yml` lands in Plan 02's first PR before this workflow runs** — otherwise the workflow will fail on first trigger. Until then, this workflow stays as a `workflow_dispatch`-only stub.
16. **`.github/workflows/pip-audit.yml`** — weekly cron + PR on `pyproject.toml`. Opens issue on vuln.
17. **`.github/workflows/lathe-smoke.yml`** — nightly cron runs `scripts/lathe_asset_loop.sh examples/courier_drone.lth courier_drone` + `reconstruct_courier_from_mesh.lth`. Uploads `dist/` manifest.
18. Required status checks in branch protection: `ci (ubuntu, 3.11)`, `ci (ubuntu, 3.12)`, `ci (windows, 3.11)`, `ci (macos, 3.11)`, `lint`, `coverage`, `pip-audit`.

## Phase 4 — Governance surfaces (day 2–3)

19. **`.github/CODEOWNERS`** — `* @talmerri`; `grammar/ spec/ schema/ @talmerri`; `lathe/shape_* lathe/asset_graph.py lathe/assembly_kernel.py @talmerri`.
20. **`.github/ISSUE_TEMPLATE/bug_report.yml`** — Lathe version, OS, Python, failing `.lth`, `lathe doctor` output, stage.
21. **`.github/ISSUE_TEMPLATE/feature_request.yml`** — which stage, public-surface impact, backend-ID impact.
22. **`.github/ISSUE_TEMPLATE/lth_authoring_help.yml`** — source `.lth`, expected vs actual certification, validator that fired.
23. **`.github/ISSUE_TEMPLATE/config.yml`** — disable blank issues, link Discussions Q&A.
24. **`.github/PULL_REQUEST_TEMPLATE.md`** — AGENTS.md checklist: preserved shape-contract ID, updated spec+grammar+schema+parser+normalizer+resolver+checker together, added/updated tests, kept generate+reconstruct example runnable, no weakened validators, ran `pytest -q`, updated CHANGELOG.
25. **`.github/dependabot.yml`** — pip + github-actions, weekly, grouped minor/patch, auto-assign, labels `deps`.
26. **`SECURITY.md`** — supported versions (`0.1.x`), GitHub Security Advisories, 90-day disclosure, `talmerri@gmail.com`. Include explicit note: *"Maintainer account uses 2FA + hardware key."*
27. Enable "Private vulnerability reporting" in repo Security.
28. **`CODE_OF_CONDUCT.md`** — Contributor Covenant 2.1.
29. **`CONTRIBUTING.md`** — AGENTS.md pointers, bootstrap, test invocations, commit convention (`feat|fix|chore|docs|test|refactor|perf|build|ci`), DCO.
30. **`.github/labels.yml`** + `github-label-sync`: `bug`, `enhancement`, `language-contract`, `backend`, `shape-stage`, `stdlib`, `docs`, `good-first-issue`, `help-wanted`, `stale`, `security`, `deps`, `needs-repro`.
30a. **`.github/FUNDING.yml`** — zero-cost signal of maintainership. Initially empty/commented-out; uncomment `github: talmerri` or `ko_fi` / `custom` links when a funding channel exists. File committed as a stub so GitHub surfaces the Sponsor button later without a repo change.
30b. **`CITATION.cff`** at repo root (Citation File Format 1.2.0). Fields: `title: Lathe`, `abstract: Declarative language + reference compiler for 3D asset intent`, `authors: [{given-names: Tal, family-names: Merri, email: talmerri@gmail.com}]`, `version: 0.1.0`, `date-released: 2026-04-23`, `license: Apache-2.0`, `repository-code: https://github.com/talmerri/lathe`. Keep `version` / `date-released` in sync with the release pipeline (step 35a bump script should patch these).

## Phase 5 — Release & changelog discipline (day 3)

31. **`CHANGELOG.md`** — Keep-a-Changelog; `[0.1.0] - 2026-04-23`. Every PR touches `[Unreleased]`.
32. **`.github/release-drafter.yml`** — auto-draft release notes from PR labels.
33. Semver policy: `v0.1.x` for patches; `v0.2.0` when `--runtime-config` surface or validator thresholds change; backend-ID breaks = major bump.
34. **PyPI** — check `lathe` name availability; if taken, reserve `lathe-lang` or `lathe-compiler` and update `[project].name` **before** first tag. Configure Trusted Publisher in PyPI project settings → `talmerri/lathe` + `release.yml` + environment `pypi`. Enable **PyPI attestations / SLSA provenance** by passing `attestations: true` to `pypa/gh-action-pypi-publish@release/v1` in `release.yml` (OIDC-published already; this is an additional flag for signed provenance). PyPI account for `talmerri` must have 2FA (hardware key preferred) enabled before the Trusted Publisher is configured.
35. Protected GitHub Environment `pypi` with required reviewer = `@talmerri`.
35a. **Version-bump tooling** — `scripts/bump_version.sh` (bash) and `scripts/bump_version.ps1` (PowerShell) wrapping [`bump-my-version`](https://github.com/callowayproject/bump-my-version). Single source of truth is `[project].version` in `pyproject.toml`; `.bumpversion.toml` (or `[tool.bumpversion]` in pyproject) configures commit/tag templates matching semver policy from step 33. Commands: `scripts/bump_version.sh patch|minor|major`. Also adds `CHANGELOG.md [Unreleased] → [X.Y.Z] - <date>` promotion as a pre-commit step.

## Phase 6 — Community + triage (week 1)

36. Enable Discussions: Announcements, Q&A, Show & Tell, Language Design RFCs, Backends.
37. **`.github/workflows/stale.yml`** — `actions/stale@v9`: issues idle 60d → stale, close 14d later; PRs idle 30d → stale, close 14d. Exempt: `security`, `language-contract`, `help-wanted`, `good-first-issue`.
38. **`docs/maintainer_handbook.md`** — weekly 30-min triage: label issues, answer Discussions, merge Dependabot, cut patch releases if validator regressions.
39. Seed 10–15 `good-first-issue` tickets from CLAUDE.md scaffold limitations (publish runner, canonical fmt, full repair loops).

## Phase 7 — README badge wall (day 3)

40. Append to README top: CI status, Codecov, PyPI version, PyPI downloads, Python versions, Apache-2.0 license, docs site, pip-audit status, Contributor Covenant, Discussions, "Made with Lathe" badge.

---

## Testing Strategy
- Fork to `talmerri/lathe-ci-dryrun`; run full CI matrix once before inviting contributors.
- Intentionally open failing PR to confirm branch protection blocks merge.
- Dry-run `v0.1.1-rc1` against PyPI Test Index before real `v0.1.1`.

## Risks & Mitigations
- **First push leaks weights or `.venv`** → stage `.gitignore` in commit 1; `git status` empty before commit 2.
- **`lathe` PyPI name taken** → check in Phase 5 step 34 before first tag.
- **Blender/xatlas unavailable in CI** → CI runs conservative path (no `--runtime-config`) per CLAUDE.md; nightly smoke may soft-fail with auto-file.
- **Validator thresholds drift in dep bumps** → nightly `lathe-smoke.yml` catches within 24h.

## 10/10 Success Criteria (90-day window)

- [ ] CI green rate on `main` ≥95% (excluding flaky-infra reruns)
- [ ] Median time-to-first-maintainer-response on issues ≤48h
- [ ] 100% of issues carry ≥1 category label within 72h
- [ ] Weekly commit cadence: ≥1 non-bot commit/week for 12 consecutive weeks
- [ ] Dependabot PRs auto-merged within 7 days: ≥80%
- [ ] ≥3 tagged releases on PyPI via OIDC in the quarter
- [ ] Zero unreviewed open PRs older than 14 days
- [ ] CHANGELOG updated on every merged PR touching `lathe/`, `grammar/`, `schema/`, `spec/`
- [ ] pip-audit: zero unresolved High/Critical CVEs older than 14 days
- [ ] Branch protection on `main` never disabled (quarterly `gh api` audit)

---

## Relevant paths

- `plans/06_maintenance.md`
- `.gitignore`, `.gitattributes`, `LICENSE`
- `.pre-commit-config.yaml`
- `.github/workflows/{ci,lint,coverage,release,docs,pip-audit,lathe-smoke,stale}.yml`
- `.github/CODEOWNERS`, `dependabot.yml`, `SECURITY.md`, `PULL_REQUEST_TEMPLATE.md`, `FUNDING.yml`
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request,lth_authoring_help,config}.yml`
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`
- `pyproject.toml` (add `[tool.ruff]`, `[tool.mypy]`, `[tool.bumpversion]`, possibly rename `name`)
- `scripts/bump_version.{sh,ps1}`
- `README.md` (badge wall)
- `docs/maintainer_handbook.md`, `docs/providers/vggt.md`, `mkdocs.yml` (owned by Plan 02)

---

## Amendment log (2026-04-23)

Applied review `plans/reviews/06_maintenance_review.md` and meta-review cross-cutters:

1. **`external/vggt/` vendoring resolved** (Phase 1 item #2): decision is *ignore, not vendor*. The entire directory is gitignored; fetch instructions live in `docs/providers/vggt.md`. Rationale (repo size + custom Meta VGGT License) to be recorded in Commit 1's message.
2. **4-commit initial history enumerated explicitly** (Phase 1 item #5): every tracked top-level entry allocated to exactly one commit.
   - Commit 1 (chore): `.gitignore`, `.gitattributes`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `pyproject.toml`, `plans/`, `.codex/`, `.agents/`.
   - Commit 2 (feat compiler): `lathe/`, `cli/`, `grammar/`, `schema/`, `spec/`, `AGENTS.md`, `CLAUDE.md`.
   - Commit 3 (feat stdlib+examples+docs): `std/`, `examples/`, `docs/`, `README.md`.
   - Commit 4 (test+ci): `tests/`, `scripts/`, `.github/` (workflows added in Phase 3; this commit seeds the dir).
3. **`.gitignore` single-owner claim** (Phase 1 item #2): this plan owns `.gitignore`. Plan 05 (DX) Phase 2 defers to this list — no duplicate patterns.
4. **`mkdocs.yml` ownership cross-reference** (Phase 3 item #15): owned by Plan 02 (Documentation); `docs.yml` stays as `workflow_dispatch`-only stub until Plan 02's first PR lands `mkdocs.yml`.
5. **Added governance artifacts**:
   - `.pre-commit-config.yaml` (new Phase 1 item 6a): ruff, ruff-format, mypy (advisory), end-of-file-fixer, trailing-whitespace, check-yaml, check-toml, check-added-large-files, gitleaks.
   - `.github/FUNDING.yml` (new Phase 4 item 30a): stub committed, entries uncommented when funding channel exists.
   - `CITATION.cff` (new Phase 4 item 30b): CFF 1.2.0 at repo root.
   - PyPI attestations / SLSA provenance (Phase 5 item #34 updated): add `attestations: true` to `pypa/gh-action-pypi-publish@release/v1`.
   - Version-bump script `scripts/bump_version.{sh,ps1}` (new Phase 5 item 35a) wrapping `bump-my-version`; `.bumpversion.toml` / `[tool.bumpversion]` in pyproject.
   - 2FA + hardware-key maintainer note added to `SECURITY.md` (Phase 4 item #26) and echoed in PyPI setup (Phase 5 item #34).
6. `Relevant paths` updated to include the new artifacts and `docs/providers/vggt.md`.
