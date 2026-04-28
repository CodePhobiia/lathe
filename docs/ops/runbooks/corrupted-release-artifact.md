# Runbook: Corrupted Release Artifact

A user reports a SHA256 hash mismatch when installing or downloading the Lathe wheel.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `pip install lathe==0.2.0rc1` fails with `HASH MISMATCH`.
- A user compares the wheel SHA256 against the GitHub Release SHA256SUMS file and they do not match.
- The PyPI "Files" page shows a different hash than what was uploaded.

## First response (≤5 min)

1. Ask the user to paste the exact pip error and the hash they computed locally.
2. Independently compare the wheel SHA against the GitHub Release SHA256SUMS file.

## Investigation

```bash
# Download the wheel independently and check its hash
pip download lathe==0.2.0rc1 --no-deps -d /tmp/lathe_check
sha256sum /tmp/lathe_check/lathe-0.2.0rc1*.whl
```

Compare against:
- The SHA256SUMS file attached to the GitHub Release.
- The hash shown on the PyPI "Files" tab for `lathe 0.2.0rc1`.

If **PyPI hash ≠ GitHub Release hash**: the upload was corrupt or replaced post-upload. This is a supply-chain incident — follow `docs/ops/runbooks/security-vulnerability-report.md` in parallel.

If **PyPI hash = GitHub Release hash but user's local hash differs**: the user's download is corrupt. This is likely a transient network issue. Ask the user to clear pip cache and retry:

```bash
pip cache purge
pip install lathe==0.2.0rc1 --no-cache-dir
```

If **user reports many instances of the same mismatch**: the artifact on PyPI may have been replaced or tampered with. Treat as supply-chain incident immediately.

## Mitigation

**For a genuine upload corruption:**
1. Yank the corrupt release via the PyPI web UI (`Manage → Release history → Yank`).
2. Rebuild the package locally from the tagged commit:
   ```bash
   git checkout v0.2.0rc1
   python -m build
   twine check dist/*
   sha256sum dist/lathe-0.2.0rc1*.whl
   ```
3. Compare against the original SHA in the GitHub Release. If they match, re-upload the clean wheel.
4. Update the SHA256SUMS file on the GitHub Release page.
5. Post a release note: "Wheel was briefly yanked due to upload corruption; the re-published wheel has the same source hash."

**For a supply-chain incident (hashes differ between sources):** immediately yank, open a GHSA, and follow `docs/ops/runbooks/security-vulnerability-report.md`.

## Communication

If the yank affected more than a handful of users, open a pinned GitHub issue with the timeline and ETA for the clean re-release. Notify affected users in the issue thread if identifiable.

## Escalation

Any confirmed hash mismatch between PyPI and the GitHub Release is a P0 supply-chain incident and a launch blocker. Escalate to `requires-human` immediately.

## Postmortem trigger

Any confirmed corrupted artifact that was downloaded by end users, or any supply-chain incident regardless of user impact.
