# Unit Economics

## Status

Lathe v0.2.0rc1 has **no monetized surface**. The numbers below are forward-looking estimates intended to size when free support and hosted infrastructure become unsustainable, not to model live revenue.

---

## Cost per active user (current OSS / pre-release support mode)

| Line item | Estimate | Note |
|---|---|---|
| Maintainer support hours / active user / week | ~0.25 h | `requires-human: validate after 30 days of beta` |
| Maintainer hourly rate (fully-loaded) | $100/h | `requires-human: confirm hourly rate with owner` |
| Support cost / active user / week | ~$25 | estimate only; product of the two rows above |
| CI minutes / release | not tracked | `requires-human: pull from GitHub Actions billing after first rc release` |
| Docs hosting (GitHub Pages) | $0 | current; no CDN or custom domain cost |
| Artifact hosting (PyPI) | $0 | current; PyPI storage is free for open-source packages |

These per-user numbers use a solo-maintainer model. If volunteer contributors absorb support load, the effective rate drops; if a contracted maintainer replaces the solo owner, the rate rises. Neither scenario applies today.

---

## Cost per build

| Mode | Marginal cost to Lathe | Notes |
|---|---|---|
| Local-only (fallback path) | ~$0 | User pays compute + electricity; Lathe incurs no per-build cost |
| Learned provider — Hunyuan | $0 to Lathe (currently) | Real $ to whoever runs the model server; `requires-human: estimate with confirmed model-server pricing once selected` |
| Learned provider — VGGT | $0 to Lathe (currently) | Same as Hunyuan row above |
| Codex ImageGen (surface lane) | $0 to Lathe (currently) | Governed fallback to deterministic path when unavailable |

In all current modes the user controls and pays for the model-server cost directly via their own runtime config. Lathe is not a reseller or aggregator of provider calls in v0.2.0rc1.

---

## Cost per registry transaction (FUTURE)

`requires-human: not applicable in v0.2.0rc1; document trigger to fill in when registry ships (target: V0.8, Month 6, per docs/business/monetization.md).`

---

## Cost per CI-SaaS run (FUTURE)

`requires-human: not applicable in v0.2.0rc1; document trigger to fill in when CI-SaaS ships (target: V1.0, Month 9, per docs/business/monetization.md).`

---

## Infra cost projections

Baseline: 50 active users at launch week (estimate — `requires-human: revise after first beta cohort`).

| Scale | Active users | Maintainer h/week | CI min/week | Support tickets/week | Total $/week (estimate) |
|---|---|---|---|---|---|
| 1× (launch week) | 50 | ~12.5 h | `requires-human` | `requires-human` | ~$1,250 |
| 10× | 500 | ~125 h | `requires-human` | `requires-human` | ~$12,500 |
| 100× | 5,000 | ~1,250 h | `requires-human` | `requires-human` | ~$125,000 |

All $/week figures use an assumed $100/h rate and 0.25 h/active-user/week estimate. CI minutes and ticket volume are `requires-human` until first-beta data is available. The 10× and 100× rows are unsustainable on a solo-maintainer model without either community support absorption or revenue — that is the point of this table.

---

## Gross margin model

Not applicable. There is no revenue in v0.2.0rc1.

When monetization launches (V0.8 registry beta, per `docs/business/monetization.md`), the gross-margin model must subtract:

- Per-build provider cost (if Lathe ever resells provider compute — not planned for V0.8)
- Storage egress (if a hosted registry ships — applicable at V0.8)
- Support hours per transaction (estimated above)

Margin floors required before any paid surface ships: TBD. `requires-human: product-owner ratification before V0.8 pricing is set.`

---

## Sensitivity — provider costs

All cells are `requires-human: needs current model-server pricing`.

| Provider | Low estimate | Expected estimate | High estimate |
|---|---|---|---|
| Hunyuan | `requires-human` | `requires-human` | `requires-human` |
| VGGT | `requires-human` | `requires-human` | `requires-human` |

These cells must be filled before Lathe resells or aggregates any provider call. Current architecture routes provider calls directly from the user's runtime config; Lathe does not intermediate billing.

---

## Sensitivity — support load

All hours/ticket values are `requires-human: needs first-beta data`.

| Scenario | Tickets/week | Hours/ticket | Total h/week | Total $/week |
|---|---|---|---|---|
| Low | `requires-human` | `requires-human` | `requires-human` | `requires-human` |
| Expected | `requires-human` | `requires-human` | `requires-human` | `requires-human` |
| High | `requires-human` | `requires-human` | `requires-human` | `requires-human` |

Ticket volume is expected to spike at the V0.5 public launch post and at each new engine-target addition. Issue template triage (CONTRIBUTING.md — `requires-human: CONTRIBUTING.md does not yet exist`) will reduce raw inbound volume.

---

## Pricing experiment plan (FUTURE)

`requires-human: revisit when V0.5 monetization criteria land.`

When a paid surface launches, the experiment plan should include:

- Price points to test for Author tier (indicative $10–$25/month per `docs/business/monetization.md`)
- Price points to test for Studio tier (indicative $100–$300/month)
- Paywall lines (free pull vs. paid publish-verified)
- Cohort split methodology (invite-only beta means controlled exposure, not a public A/B)
- Signal to declare a winner: ≥10 paying users per tier after 60-day soak, per monetization doc

Do not instrument any of this before the registry ships.

---

## WTP (willingness to pay) evidence

MISSING — no WTP interviews completed yet. Phase 15 of readiness-tasks.md tracks the work; this row stays empty until interviews land.

---

## Billing / refund / proration / tax / multi-currency / dunning / fraud / chargeback

| Item | Status |
|---|---|
| Billing | Not applicable in v0.2.0rc1 — no billing surface. To be defined when paid surface ships. |
| Refund policy | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Proration | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Tax (VAT/GST) | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Multi-currency | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Dunning | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Fraud | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |
| Chargeback | Not applicable in v0.2.0rc1. To be defined when paid surface ships. |

---

## Sustainability thresholds

All thresholds below are `requires-human: owner ratification before public launch`.

| Threshold | Trigger condition | Action |
|---|---|---|
| Free support unsustainable | >5 h/week of support out of one maintainer's ~8-h/week hobby budget | Flag to community; evaluate whether community triage or async-only support reduces load; do not expand scope while over threshold |
| Hosted telemetry unsustainable | >$25/month self-hosted OR >$100/month managed | Evaluate self-hosted PostHog or similar; telemetry is opt-in and off-by-default, so load scales with opt-in rate only |
| Paid registry beta must pause | Revenue coverage <2× operating cost for >2 consecutive months | Pause new paid invites; publish reason transparently; do not hide |

These numbers are placeholders set by the solo maintainer to trigger a re-evaluation, not contractual commitments. `requires-human: owner ratification.`

---

## Cross-references

- `docs/business/monetization.md` — monetization order of operations (registry first, CI-SaaS second)
- `docs/business/design_partners.md` — who gets registry beta invites first
- `docs/personas.md` — Personas A/B/C, tier mapping
- readiness-tasks.md Phase 12 (Financial and unit economics) and Phase 15 (WTP evidence)
