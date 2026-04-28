# Persona Interviews — v0.2.0rc1

## Status

No persona interviews completed for v0.2.0rc1 as of 2026-04-28. This file is
the **template + tracking index** for the 5 + 2 + 1 interview commitment in
Phase 15 of `readiness-tasks.md`. Each completed interview lands as its own
file under `docs/research/interviews/` and rolls up into
`docs/research/beta-feedback-v0.2.0rc1.md`.

## Interview targets

| Persona | Description | Target count | Completed | Status |
|---|---|---:|---:|---|
| Persona A | Godot indie / small-team technical artist | 5 | 0 | `requires-human: schedule + run interviews` |
| Persona B | Pipeline TD (mid-to-large studio, owns asset pipeline) | 2 | 0 | `requires-human: schedule + run interviews` |
| Persona C | AI coding agent author (LLM/agent harness builder) | 1 | 0 | `requires-human: schedule + run interviews` |

Total target: 8 interviews. None completed. Phase 15 of `readiness-tasks.md`
treats this as a launch-blocker for any GA framing; pre-release usage may
proceed without it but findings remain unsupported.

## Per-interview file convention

Filename: `docs/research/interviews/<YYYYMMDD>-personaA-<initials>.md`

Examples:
- `20260512-personaA-jd.md` — Persona A (Godot indie), interviewee initials JD
- `20260520-personaB-mr.md` — Persona B (pipeline TD), interviewee initials MR
- `20260528-personaC-st.md` — Persona C (agent author), interviewee initials ST

Each file uses the question template below filled in. Keep the interviewee's
real name, employer, and contact details out of the file; record those in
the team's private CRM/notes. The repo file may include consented-attribution
quotes only.

## Question template

Copy this into each new interview file. Open-ended questions; let the
interviewee talk; do not steer toward Lathe specifically until Q4.

1. **Current 3D-asset workflow.** Walk me through your current end-to-end
   workflow for getting a 3D asset from intent to engine-ready file.
   What tools, what hand-offs, what's manual?
2. **Biggest pain in current workflow.** Where does your current workflow
   waste the most time or break trust? What's the single change that
   would matter most?
3. **Where do you stop trusting AI-generated meshes?** When you've used
   Hunyuan / VGGT / Meshy / Tripo / Rodin output, at what step do you
   reach for the model in Blender to fix it yourself? What signal made
   you decide it wasn't usable?
4. **What would make you commit a Lathe artifact to your project?**
   Show them a Lathe-built `.glb` + cert report. What would have to be
   true for you to put it in `git` for your own project?
5. **What would make you stop using it?** What single bug, friction, or
   missing capability would cause you to uninstall and not come back?
6. **What about the language surface is confusing?** Walk through one
   `.lth` file with them. Where do they get lost? Which keywords feel
   wrong? What did they expect that wasn't there?
7. **What would you pay for, and at what price?** Free tier — what's
   the most they'd accept being missing? Paid tier — what feature(s)
   would justify a monthly price, and what price feels reasonable for
   their team size?
8. **Would you adopt on the next project?** Yes / no / why. If yes,
   what's the first thing you'd build with it? If no, what's the
   blocker?

Optional follow-ups when there's time:

9. **Closest competitor / alternative.** What do you use today that
   solves part of this problem? What did you try that failed?
10. **Decision-maker map.** Who else on your team would need to sign off
    before Lathe lands in your pipeline?

## How findings roll up

Once interviews land, the per-persona summary lives in
`docs/research/beta-feedback-v0.2.0rc1.md` with the top-3 pains /
objections / blockers per persona. Raw transcripts stay in the dated
files under this directory; the rollup is the artifact a launch reviewer
reads.

Aggregation rule: a "blocker" is a yes-answer to "would this stop you
from adopting?" from ≥2 interviewees in the same persona. A "pain" is a
recurring complaint that did not block adoption but degraded the
experience. An "objection" is a stated reason for skepticism even if
the interviewee continued past it.

## Persona validity refresh

The three persona definitions used to scope v0.2.0rc1 are not yet
validated against real interviewees. After the first cohort lands,
re-test each persona against the actual interview pool and re-record
here.

| Persona | Wedge | Valid? | Evidence |
|---|---|---|---|
| Persona A | Godot indie wedge — solo or 1-3 person team using Godot 4.x for hobby/early-revenue projects | unknown | `requires-human: confirm after first cohort` — no interviews yet |
| Persona B | Pipeline TD — mid-to-large studio TD owning the 3D-asset pipeline as a job function | unknown | `requires-human: confirm after first cohort` — no interviews yet |
| Persona C | Agent-builder — author of an LLM/agent harness that wants to call into a deterministic 3D-asset compiler | unknown | `requires-human: confirm after first cohort` — no interviews yet |

If any persona fails validation, drop it from the launch story rather
than papering over the gap with hopeful language.
