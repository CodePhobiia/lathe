# Contributing to Lathe

Thanks for your interest in Lathe. This file is a short stub for Wave 0; it will be
expanded in Wave 1+ with full workflow, review, and release documentation.

## Bootstrap

Use the bootstrap scripts to create a working `.venv`:

- `scripts/bootstrap_local.sh --dev --export` (bash)
- `scripts/bootstrap_local.ps1 -Dev -Export` (PowerShell)

Canonical invocation is `python -m lathe.cli ...` from the repo root.

## Test gate

Before opening a PR, run:

- `python -m pytest -q` — full Python test suite
- `python -m lathe.cli test` — Lathe-level tests declared inside `.lth` sources
- `python -m lathe.cli bench` — Lathe-level benchmarks

## Coordinated-change rule

Changes to the language contract (grammar, schema, parser, normalizer, resolver,
checker, spec, examples, and tests) must land together in a single coordinated
update. Do not change `grammar/lathe.lark` without also updating
`schema/lathe.schema.json`, `spec/lathe-v0.1.md`, the relevant pipeline stage, and
the tests and examples that exercise them. See AGENTS.md for the full
coordinated-change rule.

## Commits

Conventional Commits: `feat | fix | chore | docs | test | refactor | perf | build | ci`.
Include a DCO sign-off: `Signed-off-by: Your Name <you@example.com>`.
