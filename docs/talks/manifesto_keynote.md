# Manifesto Keynote

**Working title:** *The Build Passed: A Compiler for 3D Assets*

**Format:** 30-minute keynote with a live demo in the final third.

**Target venues (in priority order):**

1. **GDC Experimental** — the tools / experimental gameplay track. The
   right audience for the "compiler contract" framing. Submission
   typically opens in the September preceding the following March
   conference. Expect a ten-minute shorter slot if accepted into a
   track; pre-cut a 20-minute version.
2. **Roguelike Celebration** — smaller, community-run, and receptive
   to tooling talks that help solo and small-team devs. Submissions
   open late summer for the early-fall event. Our natural home while
   GDC is being prepared.
3. **FOSDEM graphics devroom** — deeply technical audience, open
   source culture, free to attend. Submissions open early autumn for
   the February event. Good fit for the compiler-architecture
   framing; the live demo should emphasize the MIT-licensed stack
   and the reproducible build story.

**Speaker prep time:** Target four complete dry runs before the
event, with the final one being at full length with the live demo
executed end to end on the presentation laptop.

**Status:** Outline for Plan 09 Phase 11. Not yet submitted to any
venue.

---

## Audience takeaways

These are what a listener should remember a week later. Every slide
serves one of these.

1. **3D asset generation is a compiler problem.** The mental model is
   not "model-plus-orchestration" but "source language, stages, stable
   contracts, and a validator-gated target artifact." This one
   reframe is the talk's single most valuable export.
2. **"The build passed" is the product.** Not the mesh, not the
   render, not the demo. The certification that the mesh satisfies a
   named contract is the deliverable.
3. **Lathe exists today, is MIT-licensed, and compiles five hero
   assets on a laptop with no API keys.** The path from watching the
   talk to running a build is a `pip install` and three commands.
4. **Learned generation is one stage in a larger pipeline, not the
   whole system.** The `lathe.shape.intent_mesh_handoff_v1` contract
   is the boundary that keeps downstream stages deterministic and
   keeps provider choice a configuration concern rather than a
   source-code concern.

## Slide outline

Target 13 slides for a 30-minute slot. Aim for ~2 minutes per slide
with a longer live demo in slides 10-12. Every slide has speaker
notes below.

### Slide 1 — Title

**Visual:** Project name, talk title, speaker name and handle.
Black background, large type. No logo clutter.

**Speaker notes:** Keep the open short. Name the talk, name
yourself, tell the audience when we will do the live demo so they
stay present for the architectural framing that precedes it.

### Slide 2 — A moment from every tech artist's last year

**Visual:** A screenshot split three ways: left, a genuinely
impressive generative-3D demo render; middle, the same output
opened in Blender showing non-manifold edges, overlapping UVs, and
no pivot; right, a closed browser tab.

**Speaker notes:** Tell the story without naming specific vendors.
"We have all seen the first frame. Most of us have closed the
browser on the third frame." Ground the talk in a shared
frustration the audience has actually experienced.

### Slide 3 — The gap

**Visual:** Two columns. Left column header: "what the model
optimizes for" with a list — novelty, visual plausibility,
diversity, single-shot impressiveness. Right column header: "what
the pipeline needs" with a list — manifold topology, valid UVs,
declared pivots and sockets, collision proxies, LODs, packaged
formats, provenance, reproducibility, a pass/fail signal.

**Speaker notes:** This is the central claim of the talk. The gap
between those two columns is where every "AI 3D" product currently
fails. We are not going to close that gap by building a better
model. We are going to close it with a different system shape.

### Slide 4 — The reframe: this is a compiler problem

**Visual:** The word "compiler" in large type. Below: the
definition reduced to four clauses — source language, stages with
explicit IRs, contracts between stages, a validator-gated target
artifact.

**Speaker notes:** Name the inversion. Most generative-3D systems
are models with orchestration bolted on. Lathe is a compiler with
a learned stage embedded inside it. That inversion changes
everything downstream.

### Slide 5 — The Lathe pipeline

**Visual:** Horizontal diagram of the stage order: `refs → intent
→ shape → topology → uv → surface → (execution) → rig →
interfaces → physics → optimize → validate → package → publish`.
Shade the `shape` stage differently to mark it as probabilistic.
Mark `validate` with a gate icon.

**Speaker notes:** Walk the pipeline left to right in 90 seconds,
one short clause per stage. Do not over-explain; the diagram does
most of the work. Emphasize that `shape` is the only
probabilistic stage — everything downstream of it is
deterministic.

### Slide 6 — Stable contracts

**Visual:** Zoom into the boundary between `shape` and
`topology`. Label the boundary: `lathe.shape.intent_mesh_handoff_v1`.
Show the contract as a named bundle with typed fields.

**Speaker notes:** The contract ID is the thing this talk most
wants to hand to the audience. Explain that a provider can be
swapped under this contract and no downstream stage notices. Show
that the trace records `attempted` vs `actual` so fallback is
visible, not hidden.

### Slide 7 — Validators

**Visual:** Five labeled bars: `semantic_quality`,
`visual_quality`, `flow_quality`, `surface_quality`,
`silhouette`. Each bar shows pass at the top and specific
sub-metrics below.

**Speaker notes:** Name each validator in one sentence. Emphasize
that these are deliberately strict. A lenient validator that
passes toy outputs destroys the value of the "build passed"
signal. This matters more than any single quality metric.

### Slide 8 — The user experience

**Visual:** A terminal frame showing three commands:
`python -m lathe.cli check ...`, `python -m lathe.cli plan ...`,
`python -m lathe.cli build ...`. Below the terminal: the final
line `build: passed`.

**Speaker notes:** This is the experience we are selling. Not a
web UI, not a Discord bot, not a hand-curated dashboard. Three
commands in a terminal, one of which says `passed` at the end.
Familiar to every engineer in the room.

### Slide 9 — What we are not

**Visual:** A short list with strike-throughs:
- not a prompt front-end
- not a provider router
- not an exporter wrapper
- not a mesh generator without downstream guarantees

**Speaker notes:** Anticipate the objection. Lathe looks superficially
like several tools the audience has seen and been disappointed by.
Name those tools' shapes and name why Lathe's shape is different.

### Slide 10 — Live demo, part 1: source

**Visual:** A `.lth` file open in an editor, full-screen. Syntax
highlighting on. The asset is the supply crate from the Godot
walkthrough.

**Speaker notes:** Read the intent block aloud. Name the contract
reference. Emphasize that this is the whole source — no
accompanying prompt, no side-channel configuration, no hidden
state.

### Slide 11 — Live demo, part 2: build

**Visual:** A terminal, large font, high-contrast. Run the three
commands from slide 8 live. Leave the terminal on screen for the
full duration of the build (~60 seconds on the presentation
laptop).

**Speaker notes:** Narrate sparingly. Let the output speak.
Call out the `validate` stage when it prints, and call out the
final `build: passed` line. If the build fails (it shouldn't on
the native-only path), debug live — that is also a demonstration
of the product.

### Slide 12 — Live demo, part 3: drop into Godot

**Visual:** Switch to Godot. Use the `lathe-godot` addon's
inspector to import the just-built crate. Drag into the scene.
Hit play.

**Speaker notes:** The crate renders, collides, switches LODs.
This is the payoff moment. Say one line: "From intent in Lathe,
to packaged artifact, to in-engine asset. No hand-cleanup."

### Slide 13 — Close and call to action

**Visual:** Four lines of large type:
- `pip install lathe`
- `python -m lathe.cli build <file> <asset>`
- MIT-licensed. OSS compiler.
- github.com/... and talk URL.

**Speaker notes:** Land the thesis one more time: "the defining
user experience is not 'look what the model made.' It is: 'the
build passed.'" Invite questions. Hold the final slide for the
Q&A.

## Live-demo script

Scope: the 5 minutes that span slides 10-12. Rehearsed end to end
until it is boring.

**Demo prerequisites (verified on the presentation laptop before
the talk starts):**
- A fresh virtualenv with the tagged PyPI Lathe release installed.
- The `lathe-godot` addon installed in a prepared Godot project.
- A `supply_crate.lth` file already written and saved in the Godot
  project root (do not waste stage time typing it).
- A clipboard entry containing the three build commands, so one
  paste runs the whole build if typing falters under lights.
- A pre-built `dist/supply_crate/` directory as a disaster
  fallback, so if the live build fails the presenter can switch
  to the pre-built artifact and keep the narrative moving.
- `python -m lathe.cli doctor` run once and green, confirmed on
  the conference network (not relying on the network but confirmed
  anyway).

**Demo beats:**

1. Open `supply_crate.lth` in a text editor. Read the intent block
   aloud. Do not scroll; the whole file fits on screen. (~45 sec)
2. Switch to terminal. Run `check`, then `plan`, then `build`.
   Narrate the `validate` stage and the final `build: passed`
   line. (~90 sec)
3. Switch to Godot. Open the inspector dock. Click "Import" on
   `supply_crate`. Watch the asset appear in the scene tree.
   Drag into the scene. Hit play. (~90 sec)
4. Close with one sentence tying back to the thesis. (~15 sec)

**Failure contingencies:**
- If the build fails on stage: mention that the build produced a
  diagnostic, show the `certification.json` field that failed, and
  point out that this is the intended behavior when something is
  wrong. The talk's credibility survives a build failure better
  than a papered-over one.
- If Godot crashes on import: switch to a pre-recorded 45-second
  capture of the same workflow, note the crash briefly, and move
  on. Do not spend stage time debugging.
- If the presentation laptop loses network: the native-only path
  requires none. Confirm before starting that `--runtime-config` is
  not set.

## Conference-specific notes

- **GDC Experimental:** emphasize the category-definition angle and
  the studio-CI story. Audience is studio-heavy. Prepare a
  20-minute cut in case the slot is shorter than 30.
- **Roguelike Celebration:** emphasize the solo-and-small-team
  usefulness and the Godot wedge specifically. Audience is
  indie-heavy. Longer Q&A is common; prepare three or four deeper
  follow-ups.
- **FOSDEM graphics devroom:** emphasize the OSS stack, the MIT
  license, the stable contract ID, and the reproducibility angle.
  Audience is technical and licensing-aware. Expect sharp
  questions on the boundary between Lathe and the Blender /
  xatlas adapters.

## Companion materials

- Speaker repo with the exact source, build commands, and
  presentation slides, linked from the final slide.
- A short blog post version adapted from `docs/blog/01_the_build_passed.md`,
  published the day of the talk for attendees (and non-attendees)
  who want the written form.
- A 3-minute recut of the live demo, published on the same day as
  the talk, for social sharing.
- A one-page handout (PDF) with the three commands, the stable
  contract ID, and the key links. Printable. Distributed at the
  talk if the venue allows handouts.

## Cross-links

- `docs/lathe_manifesto.md` — the source material.
- `docs/blog/01_the_build_passed.md` — the companion written form.
- `docs/blog/02_3d_asset_generation_is_a_compiler_problem.md` —
  deeper technical version of the slide 4-7 argument.
- `docs/blog/04_godot_integration_walkthrough.md` — the prose
  version of the live demo.
- `docs/distribution.md` — install paths the talk assumes.

## Submission checklist

- [ ] Abstract drafted (250 words) matching the talk's claims.
- [ ] Bio drafted (80 words).
- [ ] Venue-specific lengths prepared (30-minute and 20-minute cuts).
- [ ] Presentation laptop has the tagged PyPI release installed and
      the demo project prepared.
- [ ] Four dry runs completed, the last one at full length with the
      live demo executed end to end.
- [ ] Disaster-fallback artifacts (pre-built `dist/`, recorded Godot
      capture) prepared and tested.
- [ ] Companion blog post and handout PDF ready to publish on the
      day of the talk.
