# RACI — Lathe v0.2.0rc1 Release Readiness

### 1. Header

| Field | Value |
|---|---|
| Version | v0.2.0rc1 (pre-release; not production-ready) |
| Last reviewed | 2026-04-28 |
| Owner | Tal Merri |
| Reviewer | `requires-human:` second reviewer needed before v0.2.0 final |

---

### 2. RACI Matrix per Readiness Dimension

| Dimension | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Strategic readiness | Tal Merri | Tal Merri | `requires-human:` named strategic advisor or co-founder before v0.2.0 final | `requires-human:` named release watcher for v0.2.0 final |
| Product experience | Tal Merri | Tal Merri | `requires-human:` named beta partner(s) to validate asset-pipeline UX end-to-end | `requires-human:` named release watcher for v0.2.0 final |
| Technical architecture | Tal Merri | Tal Merri | `requires-human:` named technical reviewer (architecture sign-off) before v0.2.0 final | `requires-human:` named release watcher for v0.2.0 final |
| Security | Tal Merri | Tal Merri | `requires-human:` named security reviewer to sign off CVE / dependency scan results | `requires-human:` named release watcher for v0.2.0 final |
| Reliability + observability | Tal Merri | Tal Merri | `requires-human:` named SRE or reliability reviewer before any public-launch milestone | `requires-human:` named release watcher for v0.2.0 final |
| Operations (runbooks, on-call) | Tal Merri | Tal Merri | `requires-human:` named on-call backup who has read and accepted the runbooks | `requires-human:` named release watcher for v0.2.0 final |
| Data + telemetry | Tal Merri | Tal Merri | `requires-human:` named data reviewer to validate telemetry schema and privacy controls | `requires-human:` named release watcher for v0.2.0 final |
| Compliance + legal | Tal Merri | Tal Merri | `requires-human:` named legal counsel to review license obligations and export restrictions | `requires-human:` named release watcher for v0.2.0 final |
| Financials | Tal Merri | Tal Merri | `requires-human:` named financial reviewer (infra cost approval, billing exposure) | `requires-human:` named release watcher for v0.2.0 final |
| Launch + GTM | Tal Merri | Tal Merri | `requires-human:` named GTM partner or marketing reviewer before v0.2.0 final | `requires-human:` named release watcher for v0.2.0 final |
| Team / org readiness | Tal Merri | Tal Merri | `requires-human:` named Godot smoke tester(s) to validate integration before v0.2.0 final | `requires-human:` named release watcher for v0.2.0 final |
| Risk register | Tal Merri | Tal Merri | `requires-human:` named risk co-reviewer to validate P0/P1 classification and mitigations | `requires-human:` named release watcher for v0.2.0 final |

---

### 3. Final Launch Decision DACI

| Role | Who |
|---|---|
| Driver | Tal Merri |
| Approver | Tal Merri (solo maintainer); `requires-human:` named approving authority duplicate before v0.2.0 final to avoid single-point approval failure |
| Contributors | Product: `requires-human:` named once available. Security: `requires-human:` named once available. Legal: `requires-human:` named once available. |
| Informed | Community moderation: `requires-human:` when Discord channel launches |

---

### 4. Veto Authority

| Veto type | Authority |
|---|---|
| Security veto | Tal Merri + `requires-human:` named security backup before v0.2.0 final |
| Legal / privacy veto | `requires-human:` named legal counsel |
| Release-quality veto | Tal Merri |

---

### 5. Risk-Acceptance Authority

| Risk level | Authority |
|---|---|
| P0 | NOT permitted. P0 must be fixed or formally exception'd with signed counsel approval. No P0 may be accepted unilaterally. |
| P1 | Tal Merri. `requires-human:` named backup authority must be identified before any v0.2.0 final milestone. |
| P2 | Tal Merri solo. |

---

### 6. Post-Launch Operating Cadence

Cross-reference: `docs/ops/on-call.md` § "Post-launch operating cadence (first 14 days)". Cadence is prospective for v0.2.0rc1 (pre-release internal artifact); it activates at the first public-launch milestone. Do not duplicate here.

---

### 7. Hotfix Capacity Reservation

Cross-reference: `docs/ops/on-call.md` § "Hotfix capacity reservation". Reservation is 40% during the launch window. For v0.2.0rc1 itself the reservation is 0% (pre-release artifact; no public launch window is active). Do not duplicate here.

---

### 8. Post-Launch Sprint Plan

Cross-reference: `docs/ops/on-call.md` § "Post-launch sprint plan (skeleton)". First-real-launch sprint plan is drafted from that skeleton at the end of Phase 18 in the readiness pass. Do not duplicate here.

---

### 9. Open `requires-human:` Inventory

Every named-individual gap from the matrix above. Assign a person to each entry before v0.2.0 final.

| Dimension | Role | What is needed |
|---|---|---|
| Strategic readiness | Strategic advisor / co-founder | Named individual to consult on strategic go/no-go before v0.2.0 final |
| Strategic readiness | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Product experience | Beta partner(s) | Named beta partner(s) to validate asset-pipeline UX end-to-end |
| Product experience | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Technical architecture | Technical reviewer | Named technical reviewer to sign off architecture for v0.2.0 final |
| Technical architecture | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Security | Security reviewer | Named reviewer to sign off CVE and dependency scan results |
| Security | Security veto backup | Named backup authority for security veto decisions |
| Security | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Reliability + observability | SRE / reliability reviewer | Named reviewer to approve reliability and observability posture before public launch |
| Reliability + observability | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Operations | On-call backup | Named on-call backup who has read and accepted the runbooks |
| Operations | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Data + telemetry | Data reviewer | Named reviewer to validate telemetry schema and privacy controls |
| Data + telemetry | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Compliance + legal | Legal counsel | Named counsel to review license obligations and export restrictions |
| Compliance + legal | Legal / privacy veto | Named counsel with legal/privacy veto authority |
| Compliance + legal | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Financials | Financial reviewer | Named reviewer to approve infra cost and billing exposure |
| Financials | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Launch + GTM | GTM partner / marketing reviewer | Named GTM partner or marketing reviewer before v0.2.0 final |
| Launch + GTM | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Team / org readiness | Godot smoke tester(s) | Named Godot integration smoke tester(s) before v0.2.0 final |
| Team / org readiness | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Risk register | Risk co-reviewer | Named reviewer to validate P0/P1 classification and mitigations |
| Risk register | P1 risk-acceptance backup | Named backup authority for P1 risk-acceptance before v0.2.0 final |
| Risk register | Release watcher | Named individual to receive release notifications for v0.2.0 final |
| Launch decision (DACI) | Approving authority duplicate | Named second approver to prevent single-point approval failure at v0.2.0 final |
| Launch decision (DACI) | Product contributor | Named product contributor for DACI once available |
| Launch decision (DACI) | Security contributor | Named security contributor for DACI once available |
| Launch decision (DACI) | Legal contributor | Named legal contributor for DACI once available |
| Launch decision (DACI) | Community moderation | Named community moderator once Discord channel launches |
