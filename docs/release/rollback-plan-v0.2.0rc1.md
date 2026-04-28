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
