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

## Post-launch operating cadence (first 14 days)

The first 14 days after any public-launch milestone (closed beta, soft launch, GA — `out of scope` for v0.2.0rc1 but defined here so the cadence is ready when v0.2.0 final lands) follow this rhythm. Pre-release v0.2.0rc1 itself is not a "public launch" — it is an artifact build for internal review — so the cadence is applied prospectively.

| Day | Activity | Owner | Output |
|-----|----------|-------|--------|
| Day 0 (launch) | Pinned launch announcement; on-call active; status check every 2 h for first 8 h | Tal Merri / **requires-human:** backup | Announcement issue + 4 status comments |
| Day 1 | Triage all open issues; classify P0/P1/P2/P3; respond to all P0 within 24 h ack SLA | Tal Merri | Triage comment on every open issue |
| Day 2 | Status post on GitHub Discussions / pinned issue summarizing first-day blockers | Tal Merri | Day-2 status post |
| Day 3 | First-week retro starts; collect every blocker into beta-feedback-v0.2.0rc1.md | Tal Merri | Updated beta-feedback |
| Day 7 | Public week-1 retrospective post: install funnel, top 3 blockers, P0/P1 closure rate, hotfix delivery | Tal Merri / **requires-human:** content review | Week-1 retrospective post |
| Day 10 | Mid-window risk-register review: re-score every risk against actual launch data | Tal Merri | Updated risk_register.md |
| Day 14 | End-of-window go/no-go for next phase (closed beta → soft launch, soft launch → GA): hold meeting, record verdict | Tal Merri + **requires-human:** named decision panel | Decision-log entry |

If any P0 is open at Day 14, the next-phase go decision is automatically NO until the P0 closes or the rollback procedure fires.

### Hotfix capacity reservation

The launch-window team reserves **40% of one maintainer-week of capacity (≈16 h / week of one solo maintainer's 40 h equivalent, or ≈3 h / week of the actual hobby budget)** for hotfix work during days 0–14. This is enforced by:

1. Pre-blocking the hotfix slots on the maintainer's calendar before launch day.
2. Refusing to merge non-hotfix PRs during the reserved slots.
3. Falling back to **`requires-human:`** named backup if reserved slots are exhausted; if no backup exists, the launch is paused per RISK-015 / RISK-007.

For v0.2.0rc1 specifically (which is NOT a public launch), the reservation is **0%** — it activates at the first public-launch milestone.

### Post-launch sprint plan (skeleton)

The two-week post-launch sprint focuses exclusively on what the launch surfaces. Backlog rules:

- **Hotfix lane (40% capacity, days 0–14):** any P0 from the launch funnel; CVE response; install-broken or cert-broken on a supported matrix cell; documented telemetry/privacy regression.
- **Stabilization lane (40% capacity, days 0–14):** every P1 from the launch funnel; doc fixes for confused-user issues; FAQ / runbook gaps surfaced by support.
- **Forward-progress lane (20% capacity, days 0–14):** highest-priority post-launch roadmap item *only if* both hotfix and stabilization lanes are clear for the day. NOT default.

The sprint plan is reviewed at Day 7 retro and adjusted at Day 14. **`requires-human:`** name a sprint owner and a content reviewer for the Day-7 retro post before any public-launch milestone fires.

This is a skeleton. The first-real-launch sprint plan is drafted from this skeleton at the end of Phase 18 in the readiness pass.
