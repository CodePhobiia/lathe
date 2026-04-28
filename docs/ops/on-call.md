# On-Call — v0.2.0rc1

## Roster (v0.2.0rc1)

| Role | Primary | Backup | Escalation timeout | How to contact |
|---|---|---|---|---|
| Launch-day primary | Tal Merri / @talmerri | **requires-human: name a backup before public launch — solo-maintainer single-point-of-failure is logged in risk register** | 24 h | talmerri@gmail.com / GitHub @talmerri |
| Launch-day backup | **requires-human: name a backup before public launch — solo-maintainer single-point-of-failure is logged in risk register** | — | — | — |
| Security primary | Tal Merri / @talmerri | **requires-human: name a security backup before public launch** | 3 business days (per SECURITY.md) | talmerri@gmail.com subject: `[SECURITY]` |
| Security backup | **requires-human: name a security backup before public launch** | — | — | — |
| Legal/compliance | **requires-human: no counsel engaged yet — engage before public GA** | — | — | — |
| PyPI release authority | Tal Merri / @talmerri | **requires-human: add a second PyPI maintainer before public launch** | — | PyPI account: talmerri |
| GitHub release authority | Tal Merri / @talmerri | **requires-human: add a GitHub release backup before public launch** | — | GitHub @talmerri |
| Community moderation | **requires-human: no Discord launched yet — name a moderator when community channel is opened** | — | — | — |

## First-response SLAs for launch week

These targets apply from the moment an issue or report is received.

| Priority | Acknowledgement | Triage | Resolution target | Comms-update cadence |
|---|---|---|---|---|
| P0 (broken install, security, legal) | 24 h | 24 h | Best-effort; rollback within 4 h if unresolvable | Every 24 h while open |
| P1 (degraded feature, provider failure, docs error) | 24 h | 3 business days | Next hotfix window | On triage and on close |
| P2 (cosmetic, non-blocking) | Best-effort | Best-effort | Scheduled sprint | On close |

Security-specific SLAs mirror SECURITY.md:
acknowledgement 3 business days, triage 10 business days, fix + advisory 90 days from report.

## Escalation paths

### Security report

1. Reporter submits via GitHub Security Advisory "Report a vulnerability" button, or emails talmerri@gmail.com with subject `[SECURITY]`.
2. Primary security contact (Tal Merri) acknowledges within 3 business days.
3. Assess severity. P0 = potential RCE, data exfil, or supply-chain compromise.
4. If P0: immediately evaluate PyPI yank — see `docs/release/rollback-plan-v0.2.0rc1.md`.
5. **Who decides yank:** Tal Merri (primary). Backup: **requires-human**.
6. **What gets pulled:** PyPI wheel yanked; GitHub Release set to draft; docs banner added.
7. **Where to update users:** pinned GitHub issue, GitHub Security Advisory (GHSA), SECURITY.md acknowledgements page once resolved.

### Broken install

1. Reported via GitHub Issue or community channel.
2. Reproduce with `pip install lathe=={version}` on a clean environment.
3. If reproducible across two or more Python/OS combinations: P0 — evaluate yank.
4. **Who decides yank:** Tal Merri. Backup: **requires-human**.
5. **What gets pulled:** PyPI wheel yanked; `Known issues` section added to GitHub Release notes.
6. **Where to update users:** pinned GitHub issue; release notes edit.

### Package yank decision

Criteria for immediate yank (do not wait for fix):
- Broken import or CLI crash on install for any supported Python version.
- Security vulnerability with known exploit path.
- Legal/IP issue identified post-publication.
- Corrupted artifact (hash mismatch, missing files).

Criteria for deprecation instead of yank:
- Known-bad behavior discovered after broader adoption with no install-time breakage (yank causes unnecessary disruption; deprecation warns new installers).

See `docs/release/rollback-plan-v0.2.0rc1.md` for the exact commands.

### Legal/privacy complaint

1. Received via email or GitHub issue.
2. **Who decides:** **requires-human: no counsel engaged yet — escalate immediately to legal contact once engaged.**
3. If complaint involves a published artifact (wheel, docs page, example): preserve evidence before any removal.
4. Interim action: set GitHub Release to draft, add docs banner. Do not delete artifacts until legal guidance received.
5. Update risk register entry `RISK-001` (missing privacy/legal sign-off).

### Godot addon breakage

1. Reported via GitHub issue, tagged `godot-addon`.
2. Reproduce on the affected Godot version and OS (smoke tests require macOS/Linux human).
3. P1 by default unless the addon prevents project import on a stable Godot release — then P0.
4. **Who decides:** Tal Merri. Backup: **requires-human**.
5. **What gets pulled:** if Godot AssetLib submission is active, request removal from AssetLib while fix is prepared.
6. **Where to update users:** pinned GitHub issue; `docs/godot_integration.md` known-issues section; AssetLib listing description update.
