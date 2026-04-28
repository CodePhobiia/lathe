# Runbook: GitHub Actions Outage

A required CI check is failing because GitHub Actions itself is unavailable.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- Required checks are stuck in "Queued" or failing with `"We had a problem reaching GitHub"` on multiple unrelated PRs.
- `githubstatus.com` shows an incident affecting Actions.
- Workflows that were passing 30 minutes ago are now timing out.

## First response (≤5 min)

1. Check `https://www.githubstatus.com` for an active Actions incident.
2. If Actions is confirmed degraded or down: declare CI-blocked, hold all merges until restored.

## Investigation

```bash
# Check your own recent workflow run status
gh run list --limit 5

# Check if it's a repo-specific issue vs global GitHub outage
gh run view <recent-run-id> --log-failed
```

Distinguish between:
- **GitHub-wide outage** (githubstatus.com shows incident) — nothing to fix locally; wait.
- **Repository-scoped issue** (other repos' Actions work fine) — could be a billing limit, runner quota, or a broken workflow file.
- **Single-workflow failure** (other workflows pass) — likely a code or config issue, not an outage.

For a repo-scoped issue, check:
```bash
gh api /repos/talmerri/lathe/actions/runs --jq '.workflow_runs[:3] | .[] | {id, status, conclusion, name}'
```

## Mitigation

**If GitHub Actions is down:**
- Declare CI-blocked in the current PR/issue thread.
- Hold all merges that require a green required check.
- If a change **must** merge during the outage: run the full test suite locally as a manual gate:
  ```bash
  python -m pytest -q
  scripts/lathe_smoke.sh
  ```
  Document the manual gate result in the PR comment before merging.

**If it's a runner-quota issue:** check Actions billing in repo settings; free-tier quotas reset monthly.

**If a specific workflow file is broken:** fix it in a new PR; use `act` (https://github.com/nektos/act) to test locally before pushing.

## Communication

Post a brief comment on any blocked PRs noting the outage and that merges are held. Monitor `githubstatus.com` and unblock when restored.

## Escalation

If the outage persists >4 h and a time-sensitive release is blocked, escalate to `requires-human` to evaluate whether a manual-gate merge is appropriate.

## Postmortem trigger

No postmortem required for external GitHub outages. A postmortem is warranted if a broken workflow file went undetected for >24 h.
