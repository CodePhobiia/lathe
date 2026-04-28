# Runbooks — v0.2.0rc1

Step-by-step procedures for the most common Lathe failure modes. Each runbook covers: symptoms, first response (≤5 min), investigation commands, mitigation, communication, escalation criteria, and postmortem triggers.

## Index

| Runbook | Failure mode |
|---|---|
| [install-failure.md](install-failure.md) | `pip install lathe==0.2.0rc1` fails on Win/macOS/Linux |
| [lathe-doctor-false-result.md](lathe-doctor-false-result.md) | `lathe doctor` reports a false negative or false positive |
| [canonical-build-failure.md](canonical-build-failure.md) | `lathe build examples/courier_drone.lth courier_drone --out dist` fails |
| [provider-unavailable.md](provider-unavailable.md) | Hunyuan/VGGT/Codex unavailable mid-build |
| [learned-provider-fallback-complaint.md](learned-provider-fallback-complaint.md) | User claims learned provider should have run but Lathe fell back |
| [godot-addon-load-failure.md](godot-addon-load-failure.md) | Godot 4.x fails to load `editors/godot/lathe-addon/` |
| [missing-generated-artifact.md](missing-generated-artifact.md) | Build report says certified but expected artifact is missing on disk |
| [security-vulnerability-report.md](security-vulnerability-report.md) | A reporter contacts via SECURITY.md or GitHub Security Advisory |
| [suspected-secret-exposure.md](suspected-secret-exposure.md) | A secret may be in git history or a published artifact |
| [telemetry-privacy-complaint.md](telemetry-privacy-complaint.md) | User reports data sent without consent |
| [pypi-release-failure.md](pypi-release-failure.md) | `release.yml` workflow fails or partial publish occurred |
| [github-actions-outage.md](github-actions-outage.md) | Required check failing because Actions itself is down |
| [docs-site-broken.md](docs-site-broken.md) | `mkdocs build --strict` fails or pages 404 in production |
| [dependency-cve.md](dependency-cve.md) | A new CVE lands on a runtime or dev dependency |
| [corrupted-release-artifact.md](corrupted-release-artifact.md) | User reports SHA256 hash mismatch on `pip install` |

## Escalation quick-reference

| Condition | Action |
|---|---|
| ≥3 independent install failures on same OS+Python | Release blocker |
| Any reproducible security issue with exploit path | P0 + GHSA |
| Any confirmed telemetry/privacy leak | P0 + rollback candidate |
| Certification passes but engine import broken | Release blocker |
| Hero-family regression on stock config | Release blocker |
| CVSS ≥ 7.0 CVE on a runtime dep | Launch blocker |

Full SLA definitions: `docs/ops/on-call.md`. Rollback procedure: `docs/release/rollback-plan-v0.2.0rc1.md`.
