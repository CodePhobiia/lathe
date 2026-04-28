# Rollback Plan — Lathe v0.2.0rc1

**Pre-release only.** This plan covers PyPI yank, GitHub Release withdrawal, docs banner,
and community communication for v0.2.0rc1 and future v0.2.x patch releases.

---

## Kill-switch authority

| Action | Primary authority | Backup | Decision-to-visible-reversal target |
|---|---|---|---|
| PyPI yank | Tal Merri | requires-human: add a second PyPI maintainer before public launch | 4 hours |
| GitHub Release set to draft | Tal Merri | requires-human | 1 hour |
| Docs banner add/update | Tal Merri | requires-human | 1 hour |
| GitHub Release delete | Tal Merri | requires-human | 30 minutes |
| Pinned GitHub issue | Tal Merri | requires-human | 30 minutes |

**Reversal targets are clock time from decision, not from report receipt.** Triage and
decision time is additional. See on-call SLAs in `docs/ops/on-call.md`.

---

## PyPI yank / deprecation procedure

### Difference between yank and deprecation

- **Yank** (`pip download` stops resolving the version unless pinned exactly): use for a broken
  artifact — corrupted wheel, broken import, security issue, legal problem. Users already
  running the yanked version are unaffected; new `pip install lathe` will skip it.
  Reference: https://pypi.org/help/#yanked
- **Deprecation** (project-level warning visible on PyPI project page and via `pip`): use for
  known-bad behavior discovered after wider adoption where the install itself is not broken.
  A deprecated project still installs; pip displays a warning.

### Yank procedure

```bash
# Using twine (requires PyPI credentials or Trusted Publishing session):
# Option A — PyPI web UI
# 1. Log in to pypi.org as talmerri.
# 2. Go to: https://pypi.org/manage/project/lathe/releases/
# 3. Click the release version to yank.
# 4. Click "Yank release" and enter a reason (shown to users pinning that version).

# Option B — gh + PyPI API (if API token is available)
# PyPI does not expose a public yank API directly via pip/twine.
# Use the web UI (Option A) as the canonical path.

# Verify yank is effective (new resolver should skip the version):
pip index versions lathe
# The yanked version should appear with [yanked] suffix.
```

### Post-yank deprecation notice (if needed in addition to yank)

```bash
# Post a GitHub Release edit with a prominent warning in the body:
gh release edit v0.2.0rc1 --notes "$(cat <<'EOF'
> **This release has been yanked from PyPI.**
> Reason: <describe issue>.
> Install v0.2.0rc1.post1 or later once available.
EOF
)"
```

**User-visible effect of yank:** `pip install lathe` will not resolve this version in a
fresh install. `pip install lathe==0.2.0rc1` will succeed with a warning. Users with the
version already installed are not affected and must upgrade manually.

---

## GitHub Release edit / withdrawal procedure

### Set release to draft (preferred for temporary withdrawal)

Setting a release back to draft removes it from the public releases page and the "latest"
tag, but preserves the tag SHA and all uploaded artifacts. This is reversible.

```bash
gh release edit v0.2.0rc1 --draft
# Verify:
gh release view v0.2.0rc1 --json isDraft
```

### Delete a release (use only if draft is insufficient)

Deletes the GitHub Release object (release notes, attached artifacts) but does NOT delete
the git tag. The tag and its SHA remain public and immutable in the repository history.

```bash
# List release assets first for your records:
gh release view v0.2.0rc1 --json assets

# Delete the release (not the tag):
gh release delete v0.2.0rc1 --yes
```

**Trade-off:** deletion removes the changelog and artifacts from the UI but the tag SHA
is permanent. Anyone who pinned the SHA retains access. Prefer draft over deletion for
transparency; use deletion only if the release notes themselves contain harmful or legally
problematic content.

### Leave a public note explaining the withdrawal

After deletion, create a new GitHub Release or Discussion post explaining the withdrawal:

```bash
gh release create v0.2.0rc1-withdrawn --draft \
  --title "v0.2.0rc1 — withdrawn" \
  --notes "This release was withdrawn on $(date +%Y-%m-%d). Reason: <describe>. See issue #<N> for details."
# Then immediately publish the draft:
gh release edit v0.2.0rc1-withdrawn --draft=false
```

---

## Docs banner update procedure

The docs site uses mkdocs-material. To add an announcement bar:

1. Open `mkdocs.yml` and locate or add the `theme.announcement` config, or use a
   `docs/_overrides/` template. If neither exists, create `docs/_status_banner.md` and
   reference it via the mkdocs-material announcement bar plugin.

2. In `mkdocs.yml`:

```yaml
theme:
  name: material
  custom_dir: docs/_overrides
```

3. Create `docs/_overrides/main.html` (or edit if it exists):

```html
{% extends "base.html" %}
{% block announce %}
  <strong>Notice:</strong> v0.2.0rc1 has been yanked. See
  <a href="https://github.com/talmerri/lathe/issues/<N>">issue #N</a> for details.
{% endblock %}
```

4. Rebuild and deploy the docs. The banner appears on every page until removed.

If the docs site is deployed via GitHub Actions on push to main, commit the override file
and push. The CI workflow will rebuild and publish automatically.

---

## Discord / community announcement procedure

**requires-human: no Discord launched yet — write the channel name and post template once
a community channel exists. Suggested channel: `#announcements` (read-only for members).**

Template for future use:

> **[NOTICE] v0.2.0rc1 yanked**
> We've yanked v0.2.0rc1 from PyPI due to: <reason>. Please upgrade to <next version> once
> available. Track progress at: <GitHub issue URL>. Apologies for the disruption.

---

## GitHub issue + Security Advisory procedure

### Pinned public issue

```bash
gh issue create \
  --title "[INCIDENT] v0.2.0rc1 — <brief description>" \
  --body "$(cat <<'EOF'
## Status
Investigating / Mitigating / Resolved

## Impact
<who is affected and how>

## Actions taken
- [ ] PyPI yank
- [ ] GitHub Release set to draft
- [ ] Docs banner added

## Next update
<time>
EOF
)" \
  --label "release-blocker" \
  --pin
```

### GitHub Security Advisory (GHSA)

For security issues: create a private GHSA first, then publish after fix is available.

```bash
# Via web UI: https://github.com/talmerri/lathe/security/advisories/new
# Or via API:
gh api repos/talmerri/lathe/security-advisories \
  --method POST \
  --field summary="Brief description" \
  --field description="Full description of the vulnerability" \
  --field severity="critical|high|medium|low" \
  --field cve_id=""
```

Reference SECURITY.md for disclosure timeline (90-day coordinated disclosure window).

---

## Rollback triggers — explicit objective conditions

A rollback decision is triggered when ANY of the following objective
conditions is met. The on-call must declare the trigger in the pinned
GitHub issue, then execute the kill-switch procedure for the affected
surface within the decision-to-visible-reversal target above.

| ID | Trigger | Threshold | Initial response | Owner |
|---|---|---|---|---|
| TR-01 | P0 security issue | Any reproducible CVSS ≥ 7.0 issue affecting the published wheel or runtime; OR active exploitation reported | Yank wheel + open GHSA + docs banner | Tal Merri / RISK-002 |
| TR-02 | P0 legal/privacy issue | Counsel or regulator notice; OR confirmed user-data leak even if accidental | Yank wheel + docs banner + privacy-complaint runbook | Tal Merri / RISK-001 |
| TR-03 | Package install failure | ≥3 independent install-failure reports for the same wheel on a supported Win/macOS/Linux × Python 3.11/3.12 cell within 24 h | Yank wheel + pinned issue + install-failure runbook | Tal Merri / RISK-006 |
| TR-04 | Critical build failure | `lathe build` of any canonical hero family (`brassbound_chest`, `industrial_crate`, `mechanical_door`, `console_terminal`, `courier_drone`, `sci_fi_wall_panel`, `service_cabinet`, `control_pedestal`, `supply_container`) crashes on a clean install on a supported matrix cell | Yank wheel + canonical-build-failure runbook | Tal Merri / RISK-006 |
| TR-05 | Canonical gallery certification failure | Gallery rebuild from clean checkout shows ≥1 hero family losing certification when the same example certified at release-tag time | Yank wheel + roll-back to last-good gallery + reproduce locally | Tal Merri / RISK-006 |
| TR-06 | Corrupted release artifact | SHA256 mismatch between `evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` and the wheel/sdist served by PyPI; OR user reports `pip install` integrity failure with the published hash | Yank wheel + corrupted-release-artifact runbook + republish | Tal Merri / RISK-011 |
| TR-07 | Misleading telemetry / privacy complaint | Any reproducible report that telemetry was emitted without explicit opt-in; OR payload-allowlist violation (a payload field outside the documented allowlist) found in code or in a captured request | Yank wheel + telemetry-privacy-complaint runbook + docs banner | Tal Merri / RISK-001 / RISK-008 |
| TR-08 | Support response breach | Acknowledgement SLA missed on a P0 (security/privacy/install-broken/cert-broken); OR launch-week response-time targets breached for ≥48 h | Pause new releases + post on-call status update + reassign to backup (`requires-human:` named backup) | Tal Merri / RISK-007 / RISK-015 |
| TR-09 | CI release-gate regression | A required check on the release branch flips red after the release tag is pushed but before launch; OR a previously-passing required check is silently dropped from required status | Hold launch + restore required check + replay gate | Tal Merri / RISK-012 / RISK-017 |
| TR-10 | Platform-policy rejection | Godot AssetLib submission rejected; OR PyPI policy notice on the published project; OR GitHub policy notice on the repository | Address feedback per platform-policy-rejection path; if rejected from a launch-critical surface, hold launch | Tal Merri / RISK-013 |

Triggers are OR'd: a single condition is enough to fire the rollback
decision. Triggers can be detected by automated check (CI / pip-audit /
gitleaks / external monitor) or by a human report; either source is
authoritative.

## README warning update procedure

For incidents that require a high-visibility user warning beyond the
docs banner (e.g., the docs site itself is down), update the README:

1. Add a top-of-README admonition block:

```markdown
> [!CAUTION]
> **v0.2.0rc1 has been yanked from PyPI.** Reason: <one line>.
> Track the incident at <github.com/talmerri/lathe/issues/N>.
> Recommended action: <upgrade to v0.2.0rc1.post1 once available
> / pin to v0.2.0rc0 / wait for next release>.
```

2. Commit on `main` (not on a feature branch — the README banner must
   be visible immediately).

3. After the incident is fully resolved, REMOVE the admonition block in
   a separate commit referencing the incident postmortem.

The README warning is the channel of last resort; prefer the docs banner
for incidents where the docs site is healthy.

## Comms dry-run (paper exercise, 2026-04-28)

To satisfy the "Dry-run rollback communications without executing
destructive release changes" requirement, the following exercise was
performed on paper (no PyPI / GitHub Release / docs / Discord changes
were made; the artifacts are recorded as drafts):

- **Scenario:** TR-07 (misleading telemetry) reported by a beta user at
  09:00 local time on a launch day.
- **Decision-to-visible-reversal:** PyPI yank (4h), docs banner (1h),
  GitHub pinned issue (30m), README admonition (30m).
- **Drafts produced (paper-only, not posted anywhere):**
  - PyPI yank reason text: "v0.2.0rc1 has been yanked while we
    investigate a reported telemetry-emission issue. The default config
    has telemetry disabled; we are reproducing the report and will
    follow up within 24 h."
  - Docs banner draft: see `docs/ops/runbooks/telemetry-privacy-complaint.md`
    (when Phase 5 lands the runbook, the banner draft lives in the
    runbook's "Communication" section).
  - GitHub pinned issue draft: see `docs/release/rollback-plan-v0.2.0rc1.md`
    "Pinned public issue" template above; filled with the TR-07 trigger.
  - README admonition draft: see template in this file.
  - Discord announcement: **`requires-human:`** no Discord launched yet
    — draft would point to the GitHub issue once channel exists.
- **Outcome of dry-run:** the procedures are coherent. Two follow-up
  items recorded as `requires-human` in `docs/release/evidence-v0.2.0rc1.md`:
  (1) name a backup PyPI release authority before public launch,
  (2) confirm the docs CI workflow rebuilds + publishes the announcement
  bar within 1 h of merge.

The dry-run does not replace a real incident-comms exercise once a
backup owner is named. A real exercise (still without destructive
changes) is scheduled into the Phase 18 re-review.

## What is irreversible after launch

The following actions cannot be fully undone once executed:

- **Signed and pushed git tag:** the tag SHA is public and permanently in the repository
  history. The tag can be deleted from the remote but the SHA itself is already known to
  anyone who cloned or mirrored the repo.
- **Wheel published to PyPI:** PyPI does not support true deletion of release files.
  A yank prevents new resolution but does not remove the file from PyPI's storage.
  Anyone who pinned the exact version can still download it.
- **Docs page indexed by search engines:** once a docs page is publicly accessible,
  archive services (Wayback Machine, Google Cache) may have captured it. Removing the
  page does not remove cached copies. Assume any published docs page persists indefinitely
  in archive form.
- **Discord post:** once sent, screenshots of the content persist regardless of deletion.
  Do not post anything to a community channel that you would not want permanently associated
  with the project.
- **GitHub Security Advisory published:** once a GHSA is made public, it is indexed by
  GitHub and third-party databases (NVD, OSV). It can be updated but not deleted.
