# Runbook: Suspected Secret Exposure

A secret (API token, signing key, `.env` value) may be in git history or a published artifact.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `gitleaks` or `trufflehog` scan flags a file in the repo or history.
- A user or automated scan reports a token visible in a commit, diff, or release artifact.
- CI secret-scanning workflow in `.github/workflows/gitleaks.yml` fails on a PR or push.

## First response (≤5 min)

1. **Rotate the secret immediately** — before any other action. Contact the provider (GitHub, PyPI, API vendor) to revoke the old credential and issue a new one. Assume the secret is compromised from the moment it entered history.
2. Do not push any new code until rotation is confirmed.

## Investigation

Run a full scan to determine scope:

```bash
gitleaks detect --source . --no-banner
```

This uses the configuration in `.github/workflows/gitleaks.yml` (check for any allow-list entries that might have masked findings).

Confirm which commits contain the secret:

```bash
git log --all --oneline --follow -- <suspect file>
git log -S "<secret-pattern>" --all --oneline
```

Determine whether the secret is in:
- A working-tree file (easy to fix forward).
- Git history on an unpublished branch (clean with care).
- Git history on a published branch or tag (scope is wider; treat as confirmed exposure).
- A published PyPI wheel or GitHub Release artifact.

## Mitigation

**Always rotate first; never rely on history rewrite alone.**

For a working-tree-only secret:
1. Remove the file or redact the value.
2. Add the file to `.gitignore`.
3. Commit the removal.

For a secret in published history (treat as confirmed exposure):
1. Rotation is already done (Step 1 above).
2. Decide on forward-only fix vs history rewrite. Rewriting published history breaks forks and clone caches; for a pre-release with few forks, a rewrite is acceptable. For a secret in a published stable release, consult `requires-human`.
3. If rewriting: use `git filter-repo` (not `filter-branch`) and force-push only after coordinating with any collaborators.
4. If keeping history: accept the exposure, document it in `docs/release/decision-log-v0.2.0rc1.md`, and ensure rotation was complete.

For a secret in a PyPI artifact: yank per `docs/ops/runbooks/pypi-release-failure.md` and issue a replacement build without the secret.

## Communication

Treat this as a security report. Follow `docs/ops/runbooks/security-vulnerability-report.md` for GHSA opening and disclosure timeline.

## Escalation

Any confirmed signing-key or PyPI upload-token exposure is a P0 launch blocker. `requires-human` for legal review if the secret belongs to a third-party service with contractual obligations.

## Postmortem trigger

Any confirmed secret exposure, regardless of scope or whether it was exploited.
