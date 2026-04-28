# Design partners

**Status.** Plan 09 Phase 9. Target: **3 signed LOIs by Month 4** (coinciding with V0.5 public launch; see `docs/roadmap_public.md` § V0.5). LOIs in flight by Month 2; LOIs signed by Month 4.

## What "design partner" means here

A design partner is **not a customer**. They are:

- Willing to adopt a pre-V1.0 tool on a real project (not a tech demo).
- Willing to give structured feedback monthly for 3 months.
- Willing to let us use their studio's logo on a one-page "who is using this" section of the website.
- Not paying us. Not being paid. This is a mutual co-development relationship; we sharpen the compiler against their pipeline, they get early access and a say in V0.8+ priorities.

The LOI that lands this shape is in `docs/business/outreach_template.md`. Three months, logo rights, quarterly feedback, no cash either direction. If a prospect wants cash either direction, they are not a design partner — they are a customer or a contractor, and neither of those conversations should happen before V1.0.

## The three target prospects

### 1. Godot-first indie studio shipping factory / sci-fi

**Why.** This is the wedge. If Persona A cannot adopt Lathe on a real shipping Godot project, nothing else matters. Ideal prospect profile:

- 1–10 people.
- Publicly shipping or visibly-in-development factory, sci-fi, dungeon, or stylized-industrial Godot game.
- Blender pipeline. Not Perforce.
- Has publicly complained (blog, Discord, Twitter-X, Bluesky) about asset re-export pain at least once in the last 6 months.

**Where to find them.** Godot Discord `#general-dev`, godotengine.org/asset-library publisher list (filter for hard-surface kits), r/godot. Also itch.io game pages tagged `godot + factory` or `godot + sci-fi`.

**What they get.** Free Author-tier registry seat at V0.8 beta. Direct Slack/Discord with the maintainer. First dibs on influencing V0.6 (addon polish) and V0.8 (surface lane) scope.

**What we get.** Case study #1 (named, logo-rights). The V0.5 benchmark post becomes credible the moment one of these studios shows up at the end of it saying *"we shipped Factory X with Lathe."*

### 2. Mid-size studio with Houdini pipeline

**Why.** Persona B cover. A studio with a real TD and a real Houdini-based procedural pipeline is the test for whether Lathe's "asset contract in a versioned file" story survives contact with a studio that already has a contract — just one that lives in TD heads and Houdini HDAs. Ideal prospect profile:

- 10–50 people.
- Houdini for procedural generation; Blender or Maya for DCC; Unreal or Godot as engine.
- Has a dedicated tools/pipeline TD (not a rotating duty).
- Has had ≥1 public incident / postmortem about an asset QA gap.

**Where to find them.** GDC tools roundtable attendee lists (public), r/gamedev tech-art threads, LinkedIn searches for "pipeline TD" + mid-size game company. Twitter-X still has a pipeline-TD community under `#techart`.

**What they get.** Private-namespace Studio-tier registry seat at V0.8 beta. A voice in the CI-SaaS threshold-stability soak (V0.8–V1.0). Honest "Lathe is pre-V1.0" framing — they know what they're signing up for.

**What we get.** The Persona-B case study we need for V1.0 GA (≥1 studio reference publicly citing Lathe, per `docs/roadmap_public.md` § V1.0). Also: the Houdini interop story gets pressure-tested before we pretend to ship it.

### 3. AI-agent tooling company building coding agents for games

**Why.** Persona C cover. An agent-tooling company that ships agents which touch game repos will be the first to discover whether our `agents.md` + framework integrations (`docs/integrations/agents/*`) are sufficient for their agents to use Lathe without human prompting. Ideal prospect profile:

- Company building or selling an agent framework or agent-backed game-dev service.
- Has real deployed agents, not research demos.
- Has hit the "my agent writes a Blender script instead of using the tool I meant for it to use" problem at least once.

**Where to find them.** Continue.dev / OpenHands / Claude Code community — the people writing the agent frameworks know who is deploying agents in game pipelines. Also: NeurIPS / ICLR workshop tool-track submissions overlap with this population (`docs/roadmap_public.md` § V0.6).

**What they get.** Direct input on the `agents.md` listing + the five framework adapters. Early access to `stages/package/trace_manifest.json` schema evolutions. Co-authorship on any agent-track workshop demo.

**What we get.** The Persona-C validation loop in one relationship: they deploy agents that try to use Lathe, we fix the integration sharp edges. Without a partner in this seat, we are guessing at what agents need.

## Why only three

Bandwidth. One maintainer can run three monthly 60-minute syncs plus async Slack/Discord for three partners. Four stretches quality; five breaks it. If we have five qualified prospects at sign time, we take the three most honest about pre-V1.0 risk.

Three is also enough to triangulate. One partner's feedback is a data point; two is a coincidence; three is a pattern. Patterns are what drive V0.8 scope.

## Timeline

- **Month 0–1**: identify ~10 candidate prospects across the three buckets.
- **Month 2 (V0.3)**: 3 LOIs **in flight** (outreach sent, ≥1 first-call booked).
- **Month 3**: continue nurturing; avoid early closures — wait for the benchmark draft as credibility boost.
- **Month 4 (V0.5)**: 3 LOIs **signed** before the public OSS launch post goes live.
- **Month 5 (post-launch)**: design-partner retro (see `docs/community/early_access.md`).
- **Month 6 (V0.8)**: registry beta invites go to the three partners first.

## Evaluation criteria at Month 5 retro

The question the retro answers is *does the wedge hold?* Specifically:

- Did the partner ship (or credibly start shipping) something with Lathe on a real project?
- Did they hit a blocker that Lathe could not work around? If yes, is it structural (re-architect) or a leaf bug (fix and move on)?
- Would they adopt on the next project?

If 0 or 1 partner answers yes to adoption, **V0.8 scope pauses for wedge revalidation** rather than layering on features (per Plan 09 Phase 7 amendment).

## Cross-references

- `docs/business/outreach_template.md` — the cold-outreach template used to recruit these three.
- `docs/business/monetization.md` — how design partners feed the V0.8 registry beta.
- `docs/community/early_access.md` — the 28-seat community that design partners are a subset of.
- `docs/personas.md` — Personas A/B/C, which map 1:1 to the three prospects above.
- `docs/roadmap_public.md` § V0.3, V0.5 — the two LOI deadlines.
