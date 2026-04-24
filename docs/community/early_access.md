# Early access program

**Status.** Plan 09 Phase 7 — community seeding for the V0.5 public launch (Month 4, see `docs/roadmap_public.md`). This document defines who gets early access, how they are selected, how Discord is structured, and what the weekly cadence looks like after launch.

## Invitee targets

Per Plan 09, early access is **not a numbers game**. Three groups, totaling 28 seats:

- **20 Godot tech artists (Persona A).** Solo / 1–10-person studio, hard-surface-heavy, shipping factory/sci-fi/dungeon/cyberpunk-lite. This is the wedge population — if they bounce, nothing else matters.
- **5 pipeline TDs (Persona B).** 10–50-person studios. Early for feedback on the asset-contract story; Persona B doesn't formally adopt until V0.8+.
- **3 agent-builder teams (Persona C).** Teams building coding agents that touch game repos. Not individual agents — the humans who decide which tools their agent picks up.

28 seats is a number we can serve with one maintainer. Bigger numbers dilute feedback quality.

## How invitees are selected

Invitees are sourced, in priority order:

1. **Persona interviewees.** The 8 persona interviews (`docs/personas.md` § interview target) — 5 Persona A, 2 Persona B, 1 Persona C agent-builder team. If they did the interview, they get a seat.
2. **Godot AssetLib publishers of hard-surface kits.** Publicly findable, pre-qualified by genre fit.
3. **Blender-pipeline authors on itch.io / Gumroad.** Already selling tools, already care about pipeline ergonomics.
4. **Agent-framework early contributors.** Continue.dev / OpenHands contributors who have shipped a 3D-adjacent tool.

Sourcing is manual, one-at-a-time, personal DM. No waitlist form; no generic interest sign-up. Friction is a feature — it filters for people who will actually try the thing.

## Discord channel plan

Five channels, deliberately small:

- **#announce** — release notes, benchmark updates, status. Read-only for everyone except maintainers. One post per week max on launch, dropping to one per month after V0.5.
- **#show-your-asset** — invitees post their `.lth` source + the resulting `.glb` screenshot. This is the Monday ritual (see cadence below). Public-by-default within the Discord; anything posted here is fair game to quote in the monthly blog.
- **#builds-that-passed** — auto-generated posts from the telemetry pipeline (see task #3) when someone opts in and their build passes certification. Zero-effort social proof; opt-in only; no personal data.
- **#help** — debug thread per question; maintainer responds within 48 hours (launch week: 24 hours). This is the main loss-leader channel and intentionally so.
- **#rfc** — proposals for language changes, stdlib kits, new backends. Drafts live in forum-style threads; decisions are summarized back into `docs/adr/`.

No general-chat channel. Deliberate — general chat is where Discords lose signal. Socializing happens implicitly in #show-your-asset.

## Weekly cadence

- **Monday**: "Show your asset" thread posted in #show-your-asset by a maintainer. Prompt format: *"What's the smallest `.lth` file you shipped this week?"* or *"What certification rule bit you this week?"*. Invitees reply with source + screenshot.
- **Wednesday**: maintainer "office hours" 1-hour window in #help. Announced in #announce. Not required; overflow routes back to async #help threads.
- **Friday**: digest post in #announce — "this week in Lathe": merged PRs, open RFCs, notable `#show-your-asset` entries.

## Monthly cadence

- **First Monday of each month**: "build-passed gallery" blog post at `blog.lathe.dev` (or equivalent; confirm hosting at V0.5). Curated from opt-in `#builds-that-passed` entries. Five to ten entries, one sentence each. Links back to the invitees' projects. This is the loudest distribution lever we have that is not paid.
- **Month end**: maintainer writes a one-page retro in `docs/research/retros/YYYY_MM.md`. What worked, what didn't, what to stop doing. Shared in #announce.

## Feedback loop: design-partner retro after V0.5 launch

Per Plan 09 Phase 7, a **design-partner retro runs 30 days after V0.5 ships** (so target date ≈ Month 5). The retro's job is to answer: *does the wedge hold?*

Format:
- 45-minute 1:1 with each signed design partner (see `docs/business/design_partners.md` for the three prospects and target-of-three signed).
- Structured question set: what did you ship with Lathe; what did you try to ship and fail; would you adopt Lathe on your next project; what is the single change that would move you from "trying" to "adopting."
- Output: a single `docs/research/retros/v0_5_design_partner_retro.md` document. Patterns across ≥2 partners are load-bearing; one-off requests are filed but not prioritized.
- Decision: if <2 partners say "would adopt on next project," V0.8 scope is **paused for wedge revalidation** rather than layered with more features. That is the Plan-09-Phase-7 amendment in one sentence.

## What we will NOT do at launch

- No newsletter sign-up form ("we will email you when it's ready"). Either someone can install it today or they're not early-access material.
- No premium / private channels for paying users. Registry (per `docs/business/monetization.md`) is a separate thing; Discord stays flat for V0.5.
- No bots that automate moderation. One maintainer, 28 seats, handled manually until ≥100 members.

## Cross-references

- `docs/personas.md` — Personas A/B/C definitions and interview targets.
- `docs/roadmap_public.md` § V0.5, § Persona-C GTM.
- `docs/business/design_partners.md` — three design-partner prospects.
- `docs/business/outreach_template.md` — cold-outreach template for invitees.
- `docs/business/monetization.md` — how the registry relates to the community (answer: not yet; V0.8).
