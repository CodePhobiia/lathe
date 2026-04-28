# Runbook: Dependency CVE

A new CVE lands on a runtime or dev dependency of Lathe.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- Dependabot opens a PR with a security update.
- `pip-audit` flags a CVE on a dep in `requirements.txt` or `pyproject.toml`.
- A CVE database (OSV, NVD) publishes a new entry affecting a package Lathe depends on.

## First response (≤5 min)

1. Run `pip-audit --strict --no-deps` to confirm the finding and get the CVSS score.
2. Check whether the vulnerable package is a runtime dep (shipped to users) or a dev-only dep (affects CI/dev environments only).

## Investigation

```bash
pip-audit --strict --no-deps
```

Assess exposure:
- **Is it a runtime dep?** Check `pyproject.toml` `[project.dependencies]`. If yes, all users of the published wheel are affected.
- **Is a patched version available?** `pip index versions <package>` — if a patched version exists and is compatible, upgrade immediately.
- **What is the CVSS score?** CVSS ≥ 7.0 is a launch blocker per Phase 18. CVSS 4.0–6.9 is P1 (3 business days). CVSS < 4.0 is P2.
- **What is the actual exploit path in Lathe's usage?** A CVE on a transitive dep may have no reachable exploit surface in Lathe's usage pattern. Document the analysis explicitly.

For Dependabot PRs: review the PR diff, confirm the version bump does not break any existing tests, and merge if safe.

## Mitigation

**Patched version available:**
```bash
# Update the dep in pyproject.toml to the patched version
# Then verify:
python -m pytest -q
pip-audit --strict --no-deps
```

**No patched version available:**
- Pin to the last non-vulnerable version if the patched version is not yet released.
- Or replace the dep if a safe alternative exists.
- Document the decision in `docs/release/decision-log-v0.2.0rc1.md`:
  ```
  | <date> | CVE-YYYY-NNNN | <package>@<version> | CVSS <score> | <decision> | <owner> |
  ```

**If the CVE requires a patch release:** follow `docs/ops/runbooks/pypi-release-failure.md` publish flow for the patched release.

## Communication

For CVSS ≥ 7.0: open a GitHub Security Advisory per `docs/ops/runbooks/security-vulnerability-report.md`. For lower severity: a labeled issue (`security`, `deps`) with the `pip-audit` output is sufficient.

## Escalation

CVSS ≥ 7.0 on a runtime dep is a **launch blocker**. Escalate to `requires-human` if a patched version is not available and the dep cannot be pinned safely.

## Postmortem trigger

Any CVSS ≥ 7.0 CVE that shipped in a published release without mitigation, or any case where Dependabot alerts were suppressed and a CVE was missed.
