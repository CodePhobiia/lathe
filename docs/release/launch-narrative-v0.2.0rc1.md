# Launch narrative — Lathe v0.2.0rc1

**Date:** 2026-04-28  
**Status:** Pre-release. All messaging below is for internal review only until the owner authorizes publication.

---

## Audience

- Pre-existing readers of the Lathe roadmap who have been tracking V0.2 progress
- Indie game developers evaluating asset pipelines for Godot 4.x or similar engines
- AI agent authors looking for structured, text-diffable 3D-asset tooling with machine-readable pass/fail signals

---

## Three launch messages

### Honest framing message

Lathe v0.2.0rc1 is a pre-release reference compiler scaffold for declaring and certifying 3D assets — not a production-ready service. It exists so early users can evaluate the language, the certification model, and the Godot path before the V1.0 roadmap lands.

### Capability message

v0.2.0rc1 ships hero-asset families compiling end-to-end through native assembly and deterministic topology/UV/package, with optional learned-provider proposal sources behind explicit runtime configs.

### What this is not message

This release is not GA, not benchmarked at scale, not security-audited by a third party, not on Godot AssetLib, and does not yet have signed design partners. Those gates are tracked openly in the Phase 18 re-review.

---

## Press / community / influencer contact list

`requires-human: solo maintainer has no published outreach list yet; build before any soft-launch attempt.`

| Name | Outlet | Beat | Contact | Status |
|---|---|---|---|---|
| (placeholder) | (placeholder) | (placeholder) | (placeholder) | not started |

Recommended beats to populate: Godot devlog YouTube/Bluesky, r/godot prominent contributors, game-pipeline / tech-art Bluesky/Twitter-X accounts, AI coding-agent newsletters (e.g. agent-builders who have covered Claude Code or Continue).

---

## First-30-day content calendar

Blog post host: `docs/blog/` directory exists with five posts (`01` through `05`). `requires-human: choose public blog-post host and URL before week 1 (options: GitHub Pages off `docs/blog/`, dev.to, Substack, personal site).`

| Week | Content | Owner | Status |
|---|---|---|---|
| Week 1 | Release announcement + link to `docs/blog/04_godot_integration_walkthrough.md` as the walkthrough artifact | Tal Merri | draft — `requires-human: review and publish` |
| Week 2 | Reconstruct flow walkthrough (no existing blog post; needs authoring from scratch) | Tal Merri | draft — `requires-human: write and review` |
| Week 3 | Surface-authoring intro (no existing blog post; V1.2 surface lane; label as experimental) | Tal Merri | draft — `requires-human: write and review` |
| Week 4 | 30-day retrospective + roadmap status update | Tal Merri | draft — `requires-human: write after beta feedback lands` |

Existing `docs/blog/01_the_build_passed.md` and `docs/blog/05_certification_as_the_product.md` are candidates for cross-promotion in weeks 1–2. Confirm they are current before linking publicly.

---

## Community moderation plan

`requires-human: no Discord launched yet. If launched before public soft-open, define:`

- Moderation policy (what gets removed, what gets a warning, what results in a ban)
- Escalation path (who the second reviewer is when the solo maintainer is unavailable)
- Code of conduct — CONTRIBUTING.md does not yet exist in this repo; create and link before any community space opens
- Response SLA for GitHub Issues: `requires-human: owner must commit to a realistic SLA before the first GitHub-linked announcement goes out`

Until a Discord or forum is live, GitHub Issues is the only moderated space. Issue templates should be in place (see Phase 6 / Phase 8 of readiness-tasks.md).

---

## Crisis communications playbook

All drafts below are marked `requires-human: counsel review if any legal, privacy, or security issue is referenced before publication.`

### Install failure draft

> We're aware of an installation issue affecting [platform / Python version]. The symptom is [description]. Workaround: [step]. A fix is tracked at [issue link]. We'll update this thread when the fix ships. Sorry for the friction — please report any variants at [issue tracker].

### Security advisory draft

> We've identified a security issue in Lathe v[X.Y.Z]: [brief, non-exploitable description]. A fix is available in v[X.Y.Z+1]. To update: `pip install --upgrade lathe`. Full advisory at SECURITY.md. `requires-human: SECURITY.md does not yet exist — create before any advisory is needed.` If you believe you've discovered a vulnerability, please follow the disclosure process in SECURITY.md rather than posting publicly.

### Telemetry/privacy complaint draft

> Lathe telemetry is disabled by default. No usage data is sent unless you explicitly opt in via [config key / env var]. If you opted in and wish to opt out, [step]. If you believe data was collected without your consent, please open an issue at [issue tracker] with details and we will investigate within [SLA — `requires-human: set SLA`].

### Bad generated output draft

> The output you received does not match the declared intent. This can happen when a learned provider falls back to the reference path or when the conformance fit produces a lower-quality result than expected. To re-run: [step]. To force the deterministic reference path: [step]. If the issue persists on the reference path, please open an issue with your `.lth` source and `build_report.json`. We'll investigate and, where appropriate, document it as a known limitation.

### Yanked-package draft

> Lathe v[X.Y.Z] has been yanked from PyPI due to [brief reason — e.g. a broken install script / a critical certification regression]. The previous stable version is v[X.Y.Z-1]. To install it: `pip install lathe==[X.Y.Z-1]`. We expect to publish a fix as v[X.Y.Z+1] within [timeframe]. Details at [issue / release notes link].

---

## Competitive / positioning currency check

**Currency check date: 2026-04-28**

Source documents reviewed: `docs/competitive_landscape.md`, `docs/product_value.md`.

The competitive landscape table compares Lathe against Meshy, Hunyuan standalone, Luma, Houdini HDA + SideFX Labs, Quixel/Sketchfab, and Blender + manual QA. The positioning is honest: Lathe loses on visual novelty and wins on contract, certification, and provenance.

**Currency flags:**

- The landscape table has no version dates or pricing figures for Meshy, Luma, or Quixel — those tools update pricing and tiers frequently. `requires-human: re-check competitor pricing before any public launch comparison. The table was written without a version date; treat all competitor-row claims as potentially stale as of 2026-04-28.`
- Hunyuan and VGGT are listed as runtime-config opt-in providers. Their API availability and pricing are not tracked in the competitive doc. `requires-human: verify Hunyuan and VGGT API status before any capability message that references them.`
- The "Cost per asset" row shows "$0–few cents per learned call" for Lathe (learned). This is accurate only if the user controls the model server. If Lathe ever intermediates a provider call, this row must be updated before publication.
- `docs/product_value.md` references `docs/personas.md`, `docs/jtbd.md`, `docs/gallery.md`, `docs/benchmarks/methodology.md`, and `docs/benchmarks/v0_5_five_asset_study.md` — verify these files exist and are current before linking them in any launch post.

No dollar figures in the competitive or product-value docs contradict PyPI or GitHub Pages reality (both remain $0 for the OSS distribution path). No conflict found on that axis.

---

## Cross-references

- `docs/business/monetization.md` — monetization order and launch path
- `docs/business/design_partners.md` — design-partner program (no signed LOIs yet)
- `docs/business/unit_economics.md` — cost estimates and sustainability thresholds
- `docs/competitive_landscape.md` — full competitive table
- `docs/product_value.md` — product positioning and success metrics
- `docs/blog/` — five existing blog posts available for content calendar
- readiness-tasks.md Phase 13 (Launch and GTM) and Phase 18 (Re-review gate)
