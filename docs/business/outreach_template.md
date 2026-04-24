# Design-partner outreach template

**Status.** Plan 09 Phase 9 — the copy-pastable template used to recruit the three design partners identified in `docs/business/design_partners.md`. One template; three variants by persona (A, B, C). All variants are short, specific, and ask for the same thing: a 30-minute call to evaluate a 3-month co-dev LOI with logo rights.

## The core template

The structure is always the same:

1. One-paragraph thesis — what Lathe is, in the prospect's language.
2. One-link proof — the 90-second Godot demo (Month 2 deliverable, `industrial_crate.lth` → `.tscn` in under 10 minutes) or the equivalent artifact for the prospect's persona.
3. One-paragraph ask — 3-month LOI, logo rights, quarterly feedback, no cash either direction.
4. One line on why *them specifically*.

No marketing language. No "disrupt / revolutionize / AI-powered." Prospects in this population smell that in one sentence and never reply.

## Variant A — Godot indie studio

Subject: `Lathe + <studio>: 3-month co-dev LOI?`

```
Hi <name>,

I'm <maintainer> — I'm building Lathe, a declarative compiler for
3D-asset intent. `.lth` source in, certified game-ready `.glb` + manifest
out, Godot addon auto-imports it correctly on the first try. The first
backend stack is hard-surface props (crates, panels, doors, consoles);
the engine target is Godot 4.x.

90-second demo of `industrial_crate.lth` → Godot: <link to demo>

<Studio>'s work on <specific factory/sci-fi Godot project> is exactly
the target; you've publicly mentioned <specific re-export pain / UV
density bug / collision thing>, which is the Monday-morning pain
Lathe's trying to delete.

Would you be open to a 3-month design-partner LOI? The shape:
- You adopt Lathe on one real variant family during development.
- Monthly 60-min sync with me for feedback.
- Logo rights on a one-page "who's using this" section.
- No cash either direction.

30 minutes to talk through it this week?

<maintainer>
<link to repo once V0.5 is public; pre-V0.5, personal demo link>
```

## Variant B — Mid-size studio pipeline TD

Subject: `Lathe + <studio>: versioned asset contract for co-dev?`

```
Hi <name>,

I'm <maintainer>. I'm working on Lathe, a declarative compiler that
puts a studio's asset contract — tri-budgets, UV conventions, pivot
rules, collision geometry — in a versioned file instead of a TD's head.
CI runs `lathe build` and blocks merge on contract violation with a
named stage/rule failure. Pre-V1.0.

90-second CI-style demo (fail → fix → pass, all on a real `.lth`):
<link>

I think <studio> fits because <specific public incident/postmortem OR
specific tool talk the TD gave OR specific hiring post mentioning
pipeline scale>. That's the shape of problem Lathe is trying to
compress.

The ask: 3-month design-partner LOI.
- Adopt Lathe on one internal asset family as an experiment.
- Monthly 60-min sync with me. You see the compiler grow toward your
  real pipeline, not a demo pipeline.
- Logo rights on a "who's using this" section.
- No cash either direction.

Open to 30 minutes?

<maintainer>
```

## Variant C — AI-agent tooling company

Subject: `Lathe + <company>: parseable pass/fail for 3D-asset agent tasks?`

```
Hi <name>,

I'm <maintainer> building Lathe — a declarative 3D-asset compiler that
emits a parseable pass/fail signal (exit code + `trace.json`) for
agents to consume. `.lth` source is text and diff-native; failures are
`[stage:rule] value (reason) at: file:line`. Built so your agent can
verify a 3D-asset change the same way it verifies a unit-test pass.

90-second demo of an agent driving `lathe check / build` via Claude
Code skill + OpenHands tool: <link>

<Company>'s work on <specific agent product> is the Persona-C slot in
our design-partner program: the agent-builder team, not the agent.
You've run into <specific public complaint about binary-asset
verification gap>, which is exactly the class of failure Lathe targets.

The ask: 3-month co-dev LOI.
- Your agents exercise Lathe on real tasks. You tell us where it
  breaks, where the trace is unreadable, what schema you wish
  `trace.json` exposed.
- Monthly 60-min sync. You get direct input on the `agents.md`
  listing + the five framework adapters (Claude Code, Continue,
  Cursor, OpenHands, Devin).
- Logo rights on a "who's using this" section. Co-authorship on any
  workshop demo (NeurIPS/ICLR tool track, tentative).
- No cash either direction.

30 minutes this week?

<maintainer>
```

## What NOT to say

- Do not promise delivery dates beyond `docs/roadmap_public.md`. If the roadmap says V0.8 Month 6 for surface lane, the template says V0.8 Month 6 — not "soon."
- Do not invent numbers. No "we see 10x faster iteration" unless the benchmark study (Month 3 draft, Month 4 published) backs it up with raw data.
- Do not promise exclusivity or white-labeling in V0.x. Both are reasonable V1.0+ conversations. Neither is on the table now.
- Do not write to a generic `hello@studio.com`. If you cannot find the specific person's name and public context to cite, the outreach is not ready.

## Sending cadence

- Month 0–1: draft candidate list (≈10 prospects across A/B/C buckets).
- Month 1–2: personalize and send, one at a time. Space sends 2–3 per week, not 10 per day; hand-crafted beats batch-sent by a margin that shows up in reply rates.
- Follow-up: **one** follow-up after 7 business days if no reply. Never a second. The prospects we want are busy; if they did not reply, they are not interested enough to be a design partner.

## Where replies go

- If yes: move to a 30-min call. Outcome of the call is either "sign LOI" or "not right now, ping at V0.8." No middle state.
- If no: thank them, ask if anyone on their team fits the profile better. Sometimes the TD's name arrives this way.
- If silent after 7 business days: close the loop internally. Do not retry.

## Cross-references

- `docs/business/design_partners.md` — the three-prospect slate these variants are for.
- `docs/business/monetization.md` — what design partners get at V0.8 registry beta.
- `docs/community/early_access.md` — the broader 28-seat community, which design partners are a subset of.
- `docs/personas.md` — Personas A/B/C, mapped 1:1 to variants A/B/C.
- `docs/roadmap_public.md` § V0.3, § V0.5 — the two LOI deadlines (in flight / signed).
