# The Build Passed

**Working title:** *The Build Passed: A Manifesto for Production 3D Asset Generation*

**One-sentence hook:** In every other serious engineering discipline, the
defining signal of success is "the build passed" — and 3D asset generation
deserves the same.

**Target audience:** Technical artists, game engine developers, and studio
tooling leads who are frustrated with demo-grade AI asset tools and are
looking for something they can put in front of a CI job.

**Distribution channel (primary):** Hacker News front page submission,
timed to a tagged PyPI release.

**Distribution channel (secondary):** Tech artist Twitter/Bluesky, the
Godot subreddit, the r/gamedev weekly thread, the Game Dev League Discord
#tools channel. Crosspost with a 48-hour gap so each channel has its own
arrival moment rather than arriving as a broadcast.

**Length target:** 1600-2000 words.

**Tone:** First-person plural ("we built this because"). Manifesto energy
without being sanctimonious. Concrete example in every abstract paragraph.

**Status:** Outline for the Plan 09 Phase 11 launch post. Not yet written.

---

## Outline

### Section 1 — The gap: novelty-first generation vs production reality

- Open with a scene: a studio tech artist watches a demo of a state-of-the-art
  text-to-3D model, is genuinely impressed, and then closes the tab because
  nothing in the output is usable in their engine on Monday morning.
- Name the gap explicitly. Generation models optimize for novelty on a
  rendered thumbnail. Production pipelines optimize for reliability across
  a weeks-long integration.
- Enumerate the concrete failures that sit in the gap: non-manifold geometry,
  UV islands overlapping, no pivots or sockets, materials that look nothing
  like the studio's PBR pipeline, no collision, no LODs, no export target,
  no idea which model produced what or whether the output satisfies any
  concrete constraint.
- Frame Lathe's thesis, which is the core of the manifesto: asset generation
  is a compiler problem. A model proposes; a compiler guarantees. See
  `docs/lathe_manifesto.md`.
- Companion asset: a side-by-side screenshot. Left: a pretty render from a
  generative model. Right: the same intent, compiled through Lathe,
  showing the pivot marker, the UV atlas, the collision proxy, and the
  `validate` pass/fail banner.

### Section 2 — What "the build passed" actually means in Lathe

- Borrow the phrase deliberately from software engineering. In software,
  nobody ships a feature because the code "looked good" — they ship when
  the build passes, because the build asserts concrete, named guarantees.
- Walk through what a Lathe build asserts at `validate`:
  - geometry is manifold, oriented, and within the declared triangle
    budget
  - UVs are non-overlapping and hit the declared texel density
  - the `silhouette` validator matches the intent within tolerance
  - the `semantic_quality` validator confirms the named parts are present
  - the `flow_quality` validator confirms semantic preservation and
    reconstruct honesty where relevant
  - the packaged `.glb` opens cleanly in Godot and Blender
- Show the CLI output. Not a marketing render — the actual terminal output
  of `python -m lathe.cli build examples/courier_drone.lth courier_drone
  --out dist` with a green `build: passed` line at the bottom.
- Companion asset: a terminal recording (asciinema) of a full build,
  under 90 seconds, ending on the pass line. No voiceover, no music.

### Section 3 — Showcase: a hero asset, end to end

- Pick the `brassbound_chest` example or the new `sci_fi_wall_panel`, both
  of which compile end-to-end on the native-only path without any learned
  provider config.
- Show the `.lth` source. Annotate it in three short passes: intent,
  contract, build constraints.
- Show the command. Show the output directory listing. Call out the
  `manifest.json`, the `trace.json`, the `certification.json`, and the
  packaged `.glb` and `.usd`.
- Drop the `.glb` into a Godot scene live (or in a pre-recorded clip).
  Confirm the pivot is correct, the socket markers line up, the LODs
  switch at their declared distances.
- Note explicitly what did *not* happen: the user did not hand-retopologize,
  did not bake AO in Substance, did not write a Godot importer shim, did
  not inspect a mesh in Blender to decide if it was "good enough."
- Companion asset: a 45-second screen capture of the Godot drop-in. Saved
  at `assets/blog/01_chest_godot_dropin.mp4` once recorded.

### Section 4 — Why a compiler contract is the whole idea

- A model is a function from latent noise to geometry. Useful, but not a
  product.
- A compiler contract is what a studio actually needs: stable inputs,
  stable outputs, explicit failure modes, reproducible builds, swap-able
  backends.
- Reference the stable contract ID `lathe.shape.intent_mesh_handoff_v1`.
  Explain why a public contract ID matters: a provider can be swapped, a
  model can be upgraded, a fallback can kick in, and the downstream
  topology, UV, and packaging stages are unaffected because the bundle
  they consume is contractually stable.
- Reference the `attempted` vs `actual` provider fields in the trace.
  Explain that this is how Lathe is honest about fallback: if Hunyuan was
  configured but unreachable and `reference_conditioned_v1` was used
  instead, the trace says so in plain JSON.
- Touch on what this unlocks for CI: a studio can set a policy that
  rejects builds where `actual` does not match the declared
  `required_provider`, and that policy lives in the `.lth` source where
  it belongs.
- Companion asset: a diagram of the stages, marking which are
  deterministic (topology, UV, surface bakes, validate, package) and which
  are probabilistic (shape). Draw the contract ID as the boundary between
  the two.

### Section 5 — Try it

- One `pip install lathe` line. Link to `docs/quickstart.md`.
- One `python -m lathe.cli build examples/courier_drone.lth courier_drone`
  line.
- Link to the Godot walkthrough post
  (`docs/blog/04_godot_integration_walkthrough.md`) for anyone who wants
  to see the in-engine wedge.
- Link to the compiler deep-dive
  (`docs/blog/02_3d_asset_generation_is_a_compiler_problem.md`) for anyone
  who wants the technical argument at greater depth.
- Link to the benchmark post
  (`docs/blog/03_five_asset_benchmark.md`) for anyone who wants numbers
  before they install.
- Link to the certification-as-product post
  (`docs/blog/05_certification_as_the_product.md`) for anyone evaluating
  this as a CI dependency.
- Close on the defining line from the manifesto: "the defining user
  experience is not 'look what the model made.' It is: 'the build
  passed.'"

### Calls to action (in order of commitment)

1. Read the quickstart and run one build. Five minutes.
2. Drop the produced `.glb` into your engine of choice and confirm it
   loads cleanly. Ten minutes.
3. Open an issue if the build fails on your asset, with the `.lth` source
   and the `trace.json` attached. One hour if it reveals a real bug.
4. Author a `.lth` file for one asset in your current project backlog.
   Measure whether the certified build is good enough to ship. An
   afternoon.

### Companion assets checklist

- Side-by-side screenshot (gap illustration). PNG, 2400px wide.
- Terminal recording of a passing build. asciinema cast file, < 90s.
- Screen capture of Godot drop-in. MP4, 45s, no audio.
- Stage pipeline diagram with contract boundary. SVG.
- Hero image: the compiled `brassbound_chest` rendered in Godot with the
  `build: passed` line overlaid. PNG, 1600x900.

### Cross-links

- `docs/lathe_manifesto.md` — the long form of this argument.
- `docs/blog/02_3d_asset_generation_is_a_compiler_problem.md` — the
  technical follow-up for readers who want the pipeline deep-dive.
- `docs/blog/03_five_asset_benchmark.md` — the evidence for anyone who
  wants numbers.
- `docs/blog/04_godot_integration_walkthrough.md` — the in-engine story.
- `docs/blog/05_certification_as_the_product.md` — the CI argument.
- `docs/quickstart.md` — five-minute install-to-build path.

### Publishing checklist

- [ ] Hero image produced and optimized (< 200 KB).
- [ ] Terminal recording captured against a tagged release.
- [ ] Godot capture recorded against a current `lathe-godot` addon
      build.
- [ ] Pipeline diagram reviewed for accuracy against
      `STAGE_ORDER` in `lathe/executor.py`.
- [ ] Quotes from the manifesto verified verbatim against
      `docs/lathe_manifesto.md`.
- [ ] All cross-links resolve to published posts (not draft outlines).
- [ ] HN submission title chosen (current working candidate:
      "Show HN: Lathe — a compiler for 3D assets where 'the build
      passed' is the signal").
- [ ] Submission time chosen: Tuesday or Wednesday, 08:00 PT.
