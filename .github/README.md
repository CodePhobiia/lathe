# CI workflows

The contributor-facing local equivalents are:

| Workflow area | Local command |
| --- | --- |
| Fresh bootstrap | `scripts/bootstrap_local.ps1 -Dev -Export` on Windows, or `scripts/bootstrap_local.sh --dev --export` from bash |
| Smoke gate | `scripts/lathe_smoke.ps1` on Windows, or `bash scripts/lathe_smoke.sh` from bash |
| Fast pytest default | `python -m pytest -q` |
| Coverage ratchet | `python -m pytest --cov=lathe --cov-report=xml --cov-report=term` |
| Lint ratchet | `python -m ruff check .` |
| Docs build | `mkdocs build --strict` after installing `.[docs]` |
| Release preflight | Tag workflow runs tests, docs, security scans, package checks, and SBOM generation before publish |

The smoke scripts write build output under `tmp_lathe_smoke/` by default, which
is ignored by the repository. Set `-OutDir tmp_name` in PowerShell or
`LATHE_SMOKE_OUT=tmp_name` in bash to avoid reusing a local smoke output
directory.

Issue triage, labels, milestones, dependency-update review gates, and stale
handling are documented in `docs/maintenance.md`. The tracked 10/10 scorecard
lives in `docs/quality_dashboard.md`.
