# Certification Is the Product

**Working title:** *Certification Is the Product: Why the Validator
Report Is the Shippable Artifact*

**One-sentence hook:** The mesh is not the product — the certified
proof that the mesh satisfies a named contract is the product, and
that is what a studio's CI actually wants to buy.

**Target audience:** Studio tech directors, tools leads, and platform
engineers who make buy-vs-build decisions on CI tooling. Secondary:
investors, advisors, and ecosystem partners evaluating the Lathe
monetization thesis.

**Distribution channel (primary):** LinkedIn long-form, a targeted
share to studio-eng Slack communities (IGDA tools, GameDev.TV), and a
commentary post on Hacker News framed as "why we think the product is
the report, not the mesh." This post is written for decision-makers,
so it goes where decision-makers read.

**Distribution channel (secondary):** A light rewrite pushed to the
Lathe blog front page, cross-linked from the benchmark post for
readers who walked in through the evidence door and are now asking
"okay, but what's the business?" Defer an industry-publication angle
until after the V1.0 monetization pivot is announced.

**Length target:** 1800-2200 words.

**Tone:** Strategic, but grounded in the compiler architecture the
previous posts established. Avoid VC-memo register; stay close to the
engineering argument because that is what the audience trusts.

**Status:** Outline for Plan 09 Phase 11. The V1.0 monetization pivot
this post advocates is itself a strategic decision — this post is the
public articulation of that pivot, so its publication is gated on
strategic alignment, not just the content being ready.

---

## Outline

### Section 1 — The mesh is not the product

- Restate the observation from the manifesto: a production asset is
  not a mesh. A production asset is a verified artifact that
  satisfies a contract.
- Name why this is counterintuitive to the market. Every
  generative-3D product currently positions the mesh as the
  deliverable. The pitch is always "look at this output." The
  purchase decision is supposed to follow from the visual.
- But studios do not consume assets visually. They consume them
  through a pipeline: the mesh enters the import step, goes through
  material assignment, gets checked against budget, is fit into an
  LOD chain, and finally reaches the game. At every step, the
  question is not "does this look good" but "does this satisfy the
  constraint." That is a report question, not a picture question.
- Argue the inversion: the shippable artifact is the certification
  report. The mesh is the thing the report certifies. The report is
  what you check into the studio's asset database alongside the
  mesh, and the report is what the CI job reads to make a merge
  decision.
- Companion asset: a side-by-side showing a raw mesh render on the
  left and a `certification.json` document on the right, both at
  equal visual weight, with the caption "only one of these is
  actually what the pipeline consumes."

### Section 2 — What Lathe's certification artifact already is

- Walk through a real `certification.json` from a passing build.
  Not a synthetic example; pull one from the hero family, with the
  exact validator outputs.
- The document structure:
  - contract: the declared asset contract and the intent it claims
    to satisfy
  - validators: the five-validator output from `lathe/validators/`
    with pass/fail and specific sub-metrics
  - provenance: the `attempted` vs `actual` provider trail, the
    seeds, the runtime config hash, the input reference hashes, the
    Lathe version
  - budgets: tri count, texel density, memory footprint — measured
    against declared budgets, with pass/fail per budget
  - repair history: any repair rounds that ran, what validator
    triggered them, and whether they succeeded
- Emphasize: this document is already produced today, on the
  reference path, for every build. This is not speculative; it is
  the thing the validator stage already emits. What the V1.0
  monetization pivot proposes is to make the document the
  first-class, user-facing artifact — not just a build byproduct.
- Companion asset: an annotated screenshot of a real
  `certification.json`, with callouts to each section.

### Section 3 — The CI argument

- The natural home for the certification artifact is CI. A `.lth`
  file in a PR triggers a Lathe build on a runner; the runner
  emits the certification; the CI status check parses the
  certification and reports pass or fail back to the PR.
- Draw the analogy to code CI: nobody ships a feature because the
  code "looks good" — they ship when the test suite passes. Asset
  shipping should work the same way.
- Show a concrete pattern: a Lathe CI action that runs on every
  `.lth` change, caches builds by source hash + runtime-config
  hash + Lathe version, and posts the certification summary as a
  PR comment. The mesh is an artifact; the summary is the signal.
- Policy at the studio layer: a studio can configure the CI action
  with its own thresholds. Texel density floor. Tri budget ceiling.
  Required provider (reject builds that fell back to the
  conservative path, if the studio's policy forbids that). All of
  this lives in a config file the tools team owns, and it runs on
  every PR automatically.
- Companion asset: a screenshot of a GitHub PR with the Lathe
  certification action summary, showing three passing builds and
  one failing build with the specific validator called out.

### Section 4 — Why this is the monetization pivot

- The distinction between OSS compiler and paid CI service is the
  same distinction every healthy dev-tools company eventually
  draws. The language, the compiler, the validators, and the
  reference runtime stay permissive-licensed (MIT). The hosted CI
  certification service is the product you pay for.
- What the hosted service offers beyond the OSS runner:
  - scale: a fleet of runners with learned-backend access already
    provisioned, so a studio does not manage Hunyuan or VGGT
    endpoints themselves
  - continuity: long-lived build caches keyed across branches,
    so a feature branch that rebases onto main does not re-run
    every build from scratch
  - policy management: an organization-wide view of which
    thresholds are in force, which builds are passing, which
    `.lth` sources are drifting away from their budgets
  - audit: a signed, long-term-archived stream of certification
    artifacts, so a studio can prove to a publisher or a
    compliance auditor that every shipped asset passed the
    declared bar at the time of shipping
- Crucially, none of these features require locking down the
  language or the compiler. The OSS path stays complete. A studio
  can run every stage locally and self-host the CI; the hosted
  service is a convenience and scale bet, not a feature moat.
- State the thesis explicitly: the business is the report, not the
  mesh; the product is certified build-pass-at-scale, not
  novel-mesh-on-demand.

### Section 5 — What we are asking studios to do

- Start small. Take one prop in a current project, author a `.lth`
  file, run a local build, inspect the certification. Measure
  whether it clears your studio's acceptance bar.
- If it does: the per-asset path is established. Add a CI action
  that runs the build on every `.lth` change and surfaces the
  certification as a status check.
- If it doesn't: file an issue. The validator thresholds, the
  backend stack, the repair policy — these are knobs, and we
  want to tune them against real studio feedback.
- The longer-term ask: replace a category of hand-authored assets
  (modular props, trim sheets, interactive stand-ins) with
  Lathe-compiled equivalents. Measure the delta in tech-artist
  hours. Publish the number or keep it internal — either way,
  that delta is the real ROI conversation.
- Close on the frame: when the certification artifact is the
  thing you trust, the mesh stops being a thing you have to
  inspect. That is the real productivity shift.

### Calls to action

1. Read a real `certification.json` from a hero example. Five
   minutes.
2. Wire the Lathe build into a CI sandbox in your own repo. An
   afternoon.
3. Propose a studio-specific threshold profile in an issue or PR
   against `docs/lathe_prd.md`. A week of calendar time to get
   feedback.
4. If you are a platform lead evaluating Lathe's hosted offering,
   request a pilot: send the maintainers a sample asset family
   and a threshold profile. We will run the benchmark and publish
   (or keep private, per your preference) the certification
   summary.

### Companion assets checklist

- Annotated `certification.json` screenshot.
- GitHub PR screenshot showing the certification status check.
- A simple diagram showing: `.lth` source → CI runner → cert
  artifact → PR status check → merge decision.
- Pull-quote card for social sharing: "the mesh is not the
  product; the report is."

### Cross-links

- `docs/lathe_manifesto.md`
- `docs/lathe_prd.md` — the full product requirements frame.
- `docs/blog/01_the_build_passed.md` — the thesis this post
  extends.
- `docs/blog/02_3d_asset_generation_is_a_compiler_problem.md` —
  the technical grounding.
- `docs/blog/03_five_asset_benchmark.md` — the evidence that
  "certified" can be produced at scale.
- `docs/roadmap_public.md` — where the hosted CI offering sits on
  the public roadmap.
- `docs/versioning.md` — how certification artifacts survive
  Lathe version bumps.

### Publishing checklist

- [ ] Strategic alignment confirmed before publication (this post
      is the public articulation of the V1.0 monetization pivot).
- [ ] The annotated `certification.json` uses a real build, not a
      synthesized example.
- [ ] The CI action screenshot is against a real public repo or a
      faithfully mocked one with the repo name blurred.
- [ ] "The OSS path stays complete" language is load-bearing and
      reviewed carefully; if the monetization design drifts
      toward feature gating, this post must be revised before
      publishing.
- [ ] Pilot-invitation language is coordinated with whoever owns
      the maintainer inbox; unprepared inbound is worse than no
      inbound.
- [ ] Cross-links to sibling posts are valid and point to
      published URLs, not draft outlines.
