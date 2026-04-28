# Contributor guide

Lathe contributions should keep the language contract, compiler pipeline, and
asset outputs predictable. Use this page with the root
[`CONTRIBUTING.md`](../CONTRIBUTING.md), [`review_requirements.md`](review_requirements.md),
and [`error_codes.md`](error_codes.md).

## Code style

- Follow the existing module boundaries before adding a new abstraction. Parser,
  normalizer, resolver, checker, planner, backend, provider, executor, and
  validator behavior each has its own layer.
- Use Python 3.11-compatible code, explicit type annotations for new functions,
  and the formatting/lint rules in `pyproject.toml`. Ruff is the formatter and
  lint entry point; do not introduce a second style tool.
- Prefer small pure helpers over hidden global state. Keep IO, subprocess,
  network, and filesystem writes at the existing boundary modules.
- Keep public IDs stable unless the change is explicitly a migration:
  `lathe.shape.intent_mesh_handoff_v1`, backend IDs, provider IDs, stage names,
  diagnostic codes, and the public language names `profile`, `contract`,
  `critic`, `asset`, and `variant`.
- Do not log secrets, provider tokens, absolute private checkout paths, or
  user data. Public docs and source are statically audited for common leaks.

## Error style

- Lathe-originating exceptions should inherit from `LatheError` in
  `lathe/errors.py` or from one of its existing subclasses. Keep compatibility
  with historical exception classes that are still re-exported.
- User-facing CLI failures should go through `lathe.cli._common._emit_error`
  when the command can recover enough context to emit a structured message. The
  terminal form is `lathe error [code]: message`, followed by an optional
  source citation and a `Next step:` hint.
- Every new user-facing CLI failure code belongs in `docs/error_codes.md` with
  its exit code, description, next step, and raising location.
- Keep exit codes stable. A changed exit code can break CI scripts even when
  the English message still looks harmless.
- Avoid broad catches and success-shaped fallbacks. If a fallback is intended,
  make it explicit in the result, diagnostics, trace, or report.

## Diagnostic style

- Semantic diagnostics should use the checker helper shape from
  `lathe.checker.diag`: `code`, `name`, `severity`, `phase`, optional `asset`,
  optional `stage`, optional `path`, `message`, `details`, and
  `suggested_repairs`.
- Use `severity` values that downstream tools already understand: `error`,
  `warning`, or `info`. Do not invent a severity without updating readers and
  tests.
- Keep diagnostic `code` values stable and machine-readable. Keep `message`
  human-readable, specific, and actionable; scripts should rely on `code`, not
  on parsing prose.
- Use `phase` and `stage` to identify where the problem was detected. Use
  `path` for the smallest useful source or artifact location.
- Put structured facts in `details`, not in ad hoc message suffixes. Use
  `suggested_repairs` only for concrete actions the contributor or tool can
  attempt.

## Test expectations

- For bug fixes, reproduce the issue first when feasible, then add the
  narrowest regression test that would have failed before the fix.
- For behavior changes, update tests in the affected layer: unit tests for
  local helpers, contract tests for stable public shapes, golden tests for
  artifact snapshots, property/fuzz tests for parser or normalizer invariants,
  and integration tests for multi-stage flows.
- Provider and external-service changes should use mocked tests by default.
  Network tests must stay behind the existing opt-in markers.
- Documentation-only changes should run the relevant static docs audit or
  `mkdocs build --strict` when the docs nav or rendered site is affected.
- Use the repository virtual environment when it exists:
  `.venv\Scripts\python.exe -m pytest ...` on Windows, otherwise
  `python -m pytest ...`.

## Validation commands

Pick the smallest command that covers the changed surface first, then broaden
only when behavior changed:

```sh
python -m pytest -q tests/unit/test_docs_static_audit.py
python -m pytest -q tests/unit/test_cli_errors.py
python -m pytest -q tests/contract
python -m pytest -q
mkdocs build --strict
```

Pre-commit and CI enforce the same required quality gates: `ruff check .`,
`ruff-format` on changed Python files, and the typed mypy surface listed in
`.pre-commit-config.yaml` / `.github/workflows/lint.yml`. Whole-tree
`ruff format --check .` and `mypy lathe/` are broader cleanup targets until the
existing backlog is paid down.

Use `python -m lathe.cli` from the repository root for CLI checks, for example:

```sh
python -m lathe.cli check examples/courier_drone.lth
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
python -m lathe.cli shape-providers
```

## Update checklist

When behavior changes, update every affected public surface in the same PR:

- Language contract changes: `spec/lathe-v0.1.md`, `grammar/lathe.lark`,
  `schema/lathe.schema.json`, parser/normalizer/resolver/checker behavior,
  examples, and tests.
- CLI errors: `docs/error_codes.md`, CLI tests, and any JSON/terminal output
  snapshots or examples.
- Backend or provider behavior: backend/provider docs, runtime-config schema or
  examples, mocked tests, and trace/report expectations.
- Asset examples: catalog/tutorial/gallery docs plus the narrow `check`,
  `plan`, `materialize`, or `build` command that proves the example still runs.
- Release-visible behavior: `CHANGELOG.md`, release docs, support matrix, and
  review evidence where applicable.
