# Monetization

**Status.** Plan 09 Phase 8 (inverted). This document records the monetization order of operations decided during Plan 09: hosted registry FIRST, CI-SaaS SECOND, everything else rejected. The inversion from an earlier "CI-SaaS first" sketch is load-bearing — ordering, not just menu.

## Ordering, in one line

1. **V0.8 (Month 6)** — paid hosted registry beta for shared kits / libraries / materials / trim-sheets / decal-libraries.
2. **V1.0 (Month 9)** — CI certification SaaS GA, after validator thresholds have soaked under registry usage for 3+ months.
3. **Everything else** — not a priority and not going to be.

See `docs/roadmap_public.md` § Monetization order for the cross-reference.

## Why registry first (and not CI-SaaS first)

**Activation energy.** A user pays for a registry seat by wanting one kit, once. A user pays for CI-SaaS by deciding to gate every PR on our validator thresholds — that requires a *trust-in-the-validators* bar we have not cleared as of V0.5. Selling CI gates when the gate itself is 3 months old is how you end up with a refund queue.

**Compounding with stdlib.** `std/` is growing (V0.8 adds surface-lane kits, trim sheets, decal libraries). Every new stdlib entry doubles as a registry listing for a paid "verified / hosted / versioned" variant. The registry is the monetized layer on top of content we were already going to ship.

**Community alignment.** The V0.5 community (`docs/community/early_access.md`) is seeded around *sharing builds that passed*. The registry monetizes the natural next step — sharing the *source* of a build that passed — without inventing a new motion. CI-SaaS would require introducing a compliance-flavored motion the community would resent at this stage.

## Rejected options (explicit, Plan 09 Phase 8)

- **(b) Paid Blender addon.** Rejected. A paid Blender addon *fragments the compiler story*: Lathe's contract is "`.lth` → certified asset via a CLI compiler." Selling a DCC plugin as the paid surface makes Blender feel like the product and makes Godot / future DCCs feel like second-class citizens. The Blender integration stays free and OSS; the Blender plugin is distribution, not product.
- **(d) Studio support contracts.** Rejected. Studio support doesn't scale with one maintainer in V0.5–V0.8. It also creates a "the maintainer is the bottleneck" dynamic that kills the OSS flywheel. Revisit post-V1.0 if a specific studio relationship compels it — but do not market it.

## The registry, sketched

### What sits in the registry

- Verified kits (e.g. `kit.industrial_crate_v1`, `kit.sci_fi_wall_panel_v1`).
- Verified libraries — reference sets, decal libraries, trim sheets.
- Verified materials / surface programs (V1.2+).
- Versioned. Immutable per version. Mutable "latest" tag.

### What does "verified" mean

- Registered-maintainer attestation (identity verified at signup).
- Passes Lathe's full validator suite on a matrix of representative host `.lth` files.
- Semver-tagged; breaking changes bump major.

### Pricing bracket ideas (indicative — not committed)

Numbers below are scratch-pad sketches for conversation with design partners, **not prices we have committed to**. They are marked indicative because we have not run real price discovery yet.

- **Free tier (indicative).** Pull from the registry at unlimited rate. Publish public, unverified listings.
- **Author tier (indicative, ≈ $10–$25 / month).** Publish *verified* listings. Usage analytics for your own listings. Semver-tag enforcement.
- **Studio tier (indicative, ≈ $100–$300 / month).** Private registry namespace for a studio's internal kits. Access-controlled. Import-from-public mirrors allowed.

Rationale for not committing: we have not yet done the 8 persona interviews (`docs/personas.md`), and indie willingness-to-pay numbers in the Godot ecosystem are genuinely unknown to us. We will set real prices after the V0.8 beta with ≥10 paying users on each tier.

## Launch path

- **V0.5 (Month 4).** Registry is NOT live. Community and benchmark only. This is deliberate — monetizing at launch kills the "is this OSS or not?" question. We want that question answered *OSS* before a dollar changes hands.
- **V0.8 (Month 6).** Paid hosted registry beta opens. Free tier is unlimited; Author + Studio tiers are invite-only at first (from the signed design partners, see `docs/business/design_partners.md`).
- **V0.8 → V1.0 (Months 6–9).** Registry soak. Validator thresholds stabilize under real usage. At the end of this window, we know which thresholds are producer-stable enough to sell as CI gates.
- **V1.0 (Month 9).** CI-SaaS GA. Priced against PR-volume tiers (likely) — but we will not pretend to know the pricing until Month 8 at the earliest.

## CI-SaaS, V1.0 shape

Not committing to detail yet. The sketch: run `lathe build` against every PR that touches `.lth` or referenced art sources; block merge on certification fail; report stage/rule in the PR. The same CLI the OSS release uses — we sell the *hosted execution + the verified threshold set*, not a different compiler.

Open questions for Month-8 revisit:

- Is the threshold set one-size-fits-all, or do studios get to override it? (Most likely: override with signed receipts.)
- Do we charge per build-minute, per PR, per merged PR, or per seat? (Most likely: per merged PR, because that aligns incentive with outcome.)
- Self-hosted tier? (Probably yes — studios with Perforce will want it.)

## Runway / TAM note (honest, no guesses)

**We do not have a TAM.** We have an estimate that "Godot indies who ship hard-surface assets" is in the thousands not millions, and that "pipeline TDs at 10–50-person studios using Godot or Unreal" is similarly thousands-order. Those numbers are order-of-magnitude guesses and not to be quoted externally.

What we *do* have:
- A qualitative theory that an under-served wedge (Persona A) with measurable output will seed an over-served wedge (Persona B) via case study.
- A roadmap that front-loads OSS adoption (Months 0–4) before revenue (Months 6+), so runway is spent on the adoption motion regardless.

What we will do instead of fabricating a TAM:
- Publish the benchmark (V0.5) with real numbers.
- Publish design-partner retros after V0.5 (see `docs/community/early_access.md`).
- Post monthly registry-beta numbers once the beta is live.

Numbers we will NOT put in a fundraising deck: monthly active developers, signed contracts, or pipeline revenue that does not yet exist.

## Cross-references

- `docs/roadmap_public.md` § Monetization order.
- `docs/business/design_partners.md` — who the V0.8 registry beta invites first.
- `docs/business/outreach_template.md` — how design partners are recruited.
- `docs/community/early_access.md` — the community that seeds registry listings.
- `docs/personas.md` — who we price for, tier by tier.
