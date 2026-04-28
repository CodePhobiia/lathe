# Ops — v0.2.0rc1

## Scope of ops in v0.2.0rc1

Lathe v0.2.0rc1 is a **local-CLI-only pre-release**. There are no hosted services to operate.
Operational effort for this release consists of:

- Release publication (PyPI wheel + GitHub Release + docs site update).
- Support intake via GitHub Issues.
- Security disclosure handling per SECURITY.md.
- Dependency CVE response (pip-audit, Dependabot alerts).
- Godot addon breakage triage (manual smoke tests; requires macOS/Linux human).

The "service" is the published Python package on PyPI, the GitHub repository at
`https://github.com/talmerri/lathe`, and the docs site generated from this repo.
There is no backend, no database, and no SaaS endpoint to monitor.

## Where things live

| Artifact | Path / location |
|---|---|
| Runbooks | `docs/ops/runbooks/` — see [runbooks/README.md](runbooks/README.md) for the full index |
| On-call roster and SLAs | `docs/ops/on-call.md` |
| Risk register | `docs/risk_register.md` |
| Launch plan | `docs/release/launch-plan-v0.2.0rc1.md` |
| Rollback plan | `docs/release/rollback-plan-v0.2.0rc1.md` |
| Incident comms | `docs/release/rollback-plan-v0.2.0rc1.md` (GitHub issue + GHSA sections) |
| Security policy | `SECURITY.md` |
| Release checklist | `docs/release/release-checklist.md` |
| Evidence packet | `docs/release/evidence-v0.2.0rc1.md` |

## What to do first when something is wrong

1. **Identify severity** — is this a P0 (broken install, security, legal) or P1 (degraded feature, docs error)?  
   See `docs/ops/on-call.md` for SLA definitions.
2. **Check the risk register** — `docs/risk_register.md` lists known risks, owners, and mitigations.
3. **Run the relevant runbook** — `docs/ops/runbooks/` contains 15 step-by-step procedures. Quick index: [install-failure](runbooks/install-failure.md) · [doctor-false-result](runbooks/lathe-doctor-false-result.md) · [canonical-build-failure](runbooks/canonical-build-failure.md) · [provider-unavailable](runbooks/provider-unavailable.md) · [fallback-complaint](runbooks/learned-provider-fallback-complaint.md) · [godot-addon](runbooks/godot-addon-load-failure.md) · [missing-artifact](runbooks/missing-generated-artifact.md) · [security-report](runbooks/security-vulnerability-report.md) · [secret-exposure](runbooks/suspected-secret-exposure.md) · [telemetry-complaint](runbooks/telemetry-privacy-complaint.md) · [pypi-failure](runbooks/pypi-release-failure.md) · [actions-outage](runbooks/github-actions-outage.md) · [docs-broken](runbooks/docs-site-broken.md) · [dep-cve](runbooks/dependency-cve.md) · [corrupt-artifact](runbooks/corrupted-release-artifact.md)
4. **Decide if a rollback is needed** — consult `docs/release/rollback-plan-v0.2.0rc1.md` for kill-switch authority, PyPI yank procedure, and GitHub release withdrawal.
5. **Communicate** — open a pinned GitHub issue (`gh issue create --pin`) and, if a security issue, create a GitHub Security Advisory per `SECURITY.md`.
