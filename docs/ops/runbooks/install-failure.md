# Runbook: Install Failure

`pip install lathe==0.2.0rc1` fails on a supported platform.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `pip install` exits non-zero or install appears to succeed but `python -m lathe.cli --version` fails.
- `scripts/bootstrap_local.ps1` or `scripts/bootstrap_local.sh` errors out.
- User reports missing module, build-tools error, or `xatlas` compile failure.

## First response (≤5 min)

1. Ask user to run `python -m lathe.cli doctor` and paste the full output.
2. Confirm Python version: must be 3.11 or 3.12 (`python --version`).

## Investigation

Rerun install with verbose output to see the actual failure:

```bash
pip install lathe==0.2.0rc1 -vv 2>&1 | tail -80
```

**Windows-specific — `xatlas` compile failure:** `xatlas` requires Visual Studio Build Tools with the "Desktop development with C++" workload. If the error mentions `cl.exe not found` or `MSBuild`, guide the user to install Build Tools from https://visualstudio.microsoft.com/visual-cpp-build-tools/ then retry.

**Write-permission failure:** Check whether `LATHE_SMOKE_OUT` or the install target directory is a path the user cannot write. The default build output is `dist/` relative to cwd; the install itself writes into the active venv's `site-packages`.

**Malicious-package suspicion:** If the reporter suspects a supply-chain or typosquatting attack, treat this as a security report. Direct them to SECURITY.md and open a private GitHub Security Advisory (`gh api repos/talmerri/lathe/security-advisories --method POST`).

**Verify the SHA against PyPI:**

```bash
pip download lathe==0.2.0rc1 --no-deps -d /tmp/lathe_pkg
sha256sum /tmp/lathe_pkg/lathe-0.2.0rc1*.whl
```

Compare against the SHA256SUMS published on the GitHub Release page.

## Mitigation

- For xatlas build failure: guide user to Build Tools install, or install without the `xatlas` extra: `pip install lathe==0.2.0rc1` (no extras).
- For write-permission failure: `pip install lathe==0.2.0rc1 --user` or fix the venv path.
- For genuine package corruption: yank the release per `docs/ops/runbooks/corrupted-release-artifact.md`.

## Communication

- Acknowledge within 24 h (P1) or 24 h (P0 if ≥3 independent reports on same OS+Python).
- Trigger response via Macro: install failure in `docs/support/readiness-checklist.md`.
- If escalated to release blocker, open pinned issue: `gh issue create --label release-blocker --pin`.

## Escalation

Escalates to release blocker when ≥3 independent reports of the same failure on the same OS + Python version land within 72 h (trigger #1 in `docs/support/readiness-checklist.md`).

## Postmortem trigger

Any confirmed build-tools regression, hash mismatch, or supply-chain incident requires a postmortem doc in `docs/postmortems/`.
