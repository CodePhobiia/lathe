# Contributing to Lathe

Thanks for considering a contribution. Lathe is an AI-native 3D build language
with a reference compiler and a stable contract surface. Start by reading
[AGENTS.md](AGENTS.md) — it describes the coordinated-change rule that governs
every PR touching the language, the schema, or the compiler pipeline. Then
continue below for setup, tests, and workflow.

For code style, error style, diagnostic shape, and test expectations, see the
[docs contributor guide](https://github.com/talmerri/lathe/blob/main/docs/contributing.md).

## Bootstrap

Use the bootstrap scripts to create a working `.venv` (Windows-first — the
expected interpreter path is `.venv/Scripts/python.exe`):

- Bash: `scripts/bootstrap_local.sh --dev --export`
- PowerShell: `scripts/bootstrap_local.ps1 -Dev -Export`

Canonical invocation is `python -m lathe.cli ...` from the repo root. Once the
editable install is active (`pip install -e .[dev]`) the `lathe` console script
is also available.

## Test gates

Before opening a PR, run:

- `python -m pytest -q` — full Python test suite.
- `python -m lathe.cli test` — Lathe-level tests declared inside `.lth` sources.
- `python -m lathe.cli bench` — Lathe-level benchmarks.

For quick iteration on a single file or test:

- `python -m pytest tests/test_build.py -q`
- `python -m pytest tests/test_language_v13.py::TestName::test_case -q`
- `scripts/lathe_smoke.ps1` on Windows, or `bash scripts/lathe_smoke.sh` from bash
- `scripts/lathe_asset_loop.sh <file.lth> <asset> [out_dir]`

The CI partitions also have local mirrors in `Justfile` and the `Makefile`
wrapper. Run the matching target before touching a workflow:

- `just ci-fast-test` / `make ci-fast-test` mirrors the fast pytest, doctor,
  and courier-drone check job.
- `just ci-contract-golden` / `make ci-contract-golden` mirrors contract and
  golden tests.
- `just ci-property` / `make ci-property` mirrors property tests.
- `just clean-clone-readme` / `make clean-clone-readme` mirrors the README
  bootstrap and smoke-test job.
- `just devcontainer-validate` / `make devcontainer-validate` mirrors
  devcontainer configuration validation.

## First issue workflow

1. Pick an issue labeled `good-first-issue` or `help-wanted` unless a maintainer
   has already invited you into a larger change.
2. Comment that you are investigating it and wait for maintainer confirmation
   when the issue touches language contracts, providers, security, release
   automation, or public examples.
3. Reproduce the issue locally before editing. For bugs, capture the failing
   command, smallest `.lth` file or fixture, and expected behavior.
4. Make the smallest change that fixes the root cause, then add or update the
   narrowest reliable regression test.
5. Run the relevant narrow test first, then the smoke or full gate requested by
   the PR template.
6. Open the PR with the exact validation commands and any remaining risk.

If you are unsure where to start, open an `.lth authoring help` issue with the
source file and validator output. Maintainers can convert it into a scoped bug
or docs task once the failure mode is clear.

## Pre-commit setup

Install [`pre-commit`](https://pre-commit.com) and enable the hooks on first
clone so lint / format / large-file / secret checks run before every commit:

```sh
pip install pre-commit
pre-commit install
pre-commit run --all-files   # optional: sweep the tree once
```

CI runs the same hook set so local and remote stay aligned.

The required quality gates are:

- Ruff lint: `ruff check .`.
- Ruff format: `ruff-format` in pre-commit, with CI enforcing changed Python
  files while the historical full-tree format backlog is paid down.
- Mypy: `mypy --follow-imports=silent` over the currently typed IR, stage
  budget, and validator surface listed in `.pre-commit-config.yaml` and
  `.github/workflows/lint.yml`.

## Coordinated-change rule

Language-contract changes must land as **a single coordinated PR** across all
layers:

- `spec/lathe-v0.1.md`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`
- parser, normalizer, resolver, and checker behavior
- examples and tests

Do not change `grammar/lathe.lark` without also updating
`schema/lathe.schema.json`, `spec/lathe-v0.1.md`, the relevant pipeline stage,
and the tests and examples that exercise them.

Backend and provider changes must preserve stable backend IDs, the stable
`lathe.shape.intent_mesh_handoff_v1` shape-bundle contract, and the downstream
topology/UV/packaging contracts unless the PR is explicitly and intentionally a
migration — in which case call that out in the description.

The public language surface treated as stable: `profile`, `contract`, `critic`,
`asset`, `variant`, plus the build-stage names.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat` — new functionality
- `fix` — bug fix
- `chore` — tooling / housekeeping
- `docs` — documentation only
- `test` — test-only changes
- `refactor` — internal structure with no behavior change
- `perf` — performance
- `build` — build system or packaging
- `ci` — CI / automation

Example: `feat(shape): add conformance fit for noisy provider proposals`.

## DCO sign-off

All commits must include a Developer Certificate of Origin sign-off:

```
Signed-off-by: Your Name <you@example.com>
```

This certifies you have the right to submit the contribution under the
repository's license. Use `git commit -s` to append automatically.

## PR checklist

Every pull request must satisfy the checklist in
[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) —
coordinated-change rule, preserved validators, updated CHANGELOG, ran
`pytest -q`. The template loads automatically when you open a PR on GitHub.

## Review response SLA

Maintainer-best-effort, not a guarantee:

- **First response on a new issue or PR:** within 48 hours on weekdays.
- **Full review on a focused PR (<300 lines changed):** within 7 days.
- **Contract-change PRs or backend-ID migrations:** additional review time is
  expected; a prior RFC in GitHub Discussions shortens review.

If a PR is stuck, ping the maintainer in the thread or open a Discussion.
