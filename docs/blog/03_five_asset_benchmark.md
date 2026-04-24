# The Five-Asset Benchmark

**Working title:** *The Five-Asset Benchmark: What It Takes to Ship
Generated 3D Assets*

**One-sentence hook:** We ran five hero assets through Lathe against
three baselines on the same hardware, with the same acceptance bar, and
published every artifact — here is what it looks like when the success
signal is "shippable," not "pretty."

**Target audience:** Studio tech leads, engine tools engineers, and
researchers who need concrete numbers before trusting a new system. This
is the evidence post.

**Distribution channel (primary):** Hacker News + lobste.rs on the day
of data release, paired with the full artifact bundle on GitHub
Releases. The artifacts are the teeth of the post; without them this is
just another set of unverifiable numbers.

**Distribution channel (secondary):** The graphics programming
subreddit, tech artist Twitter/Bluesky, a targeted share to industry
Slack/Discord groups (IGDA tools, Unreal-Devs, Godot) with the full
results table inline so skimmers get the summary without clicking.

**Length target:** 2000-2400 words plus an appendix of raw numbers.

**Tone:** Measured, evidence-first. No marketing language. Honest
losses are load-bearing for credibility.

**Status:** Outline for Plan 09 Phase 11, gated on BL-40+ (real-data
gatherer) producing real measurements. This post will not ship with
fabricated numbers.

---

## Outline

### Section 1 — What we benchmarked, and why five

- Frame the question the benchmark actually answers: can Lathe produce
  assets that pass a studio acceptance bar on the first build, without
  hand-cleanup, across a realistic range of asset families?
- The five hero assets, drawn from the V1.0 hero family list:
  - `brassbound_chest` — hero prop, symmetric, rich surface detail
  - `industrial_crate` — low-poly modular prop, tight tri budget
  - `mechanical_door` — interactive prop with socket and pivot
  - `console_terminal` — busy hard-surface with panel lines
  - `sci_fi_wall_panel` — modular tiling surface piece
- Why five: it is the smallest set that covers (a) symmetric vs
  asymmetric, (b) low-poly budget vs hero budget, (c) modular vs
  standalone, (d) interactive vs static. Three would be unfair;
  fifteen would delay publication past Plan 09.
- Why these five specifically: they are all native-compile examples
  already in the repo, which means every reader can reproduce the
  Lathe side of the results without an API key.
- What we explicitly did *not* benchmark: purely aesthetic
  preference, user-study ratings, or anything subjective. Those
  matter but are a separate post.

### Section 2 — Methodology

- Hardware: one reference workstation spec, named explicitly, wall-clock
  measured on that machine. No cloud GPUs in the hot loop for
  reproducibility. If a learned backend (Hunyuan, VGGT) was part of
  the config, the inference time is reported separately from the
  deterministic-stage wall-clock so readers can back out the portion
  that moves with their own hardware.
- Baselines, three of them, all named. One is Lathe in native-only
  mode (no learned providers). One is Lathe with a learned shape
  provider. One is a current open-source text-to-3D pipeline, run
  directly, without Lathe's downstream stages. We do not run closed
  providers against their stated terms of service.
- Acceptance bar: the validator suite in `lathe/validators/` with
  default thresholds. `semantic_quality`, `visual_quality`,
  `flow_quality`, `surface_quality`, and `silhouette` all green.
  `validate: passed` is the pass condition. Anything less is a fail,
  even if the mesh looks fine on first glance.
- Metrics reported per asset per baseline:
  - pass / fail at the acceptance bar
  - wall-clock to first passing build
  - tri count vs declared budget
  - texel density actual vs declared
  - manifold / non-manifold edge count
  - UV overlap percentage
  - `silhouette` IoU against intent reference
  - `semantic_preservation_quality` where the flow is
    reconstruction-shaped
- How we handle the probabilistic shape stage: five seeds per asset
  per probabilistic baseline. Report median and the full five-point
  spread, not just the best run. This is where "honesty" shows up in
  the methodology.
- Companion asset: the exact commands we ran, copy-pasted into the
  appendix so the methodology is auditable line-by-line.

### Section 3 — Results

- Full pass/fail matrix: 5 assets × 3 baselines = 15 cells. Each
  cell is green, yellow (passed after one repair round), or red
  (failed).
- Per-asset commentary. One paragraph per asset, calling out what
  specifically worked and what specifically failed.
- Headline numbers, stated plainly. No "up to 10x" framing; we report
  the actual per-asset delta.
- An honest-loss section. At least one asset where Lathe did not win
  outright — for example, a case where the raw text-to-3D baseline
  produced a mesh that was visually plausible but failed
  `semantic_quality` because a named part was missing, while a
  different asset's raw baseline actually beat Lathe's native-only
  path on wall-clock (but still failed the acceptance bar). Naming
  losses is the most persuasive part of the post.
- A failure-mode inventory. For the red cells, what was the failing
  validator? That pattern is the actionable output for future Lathe
  work.
- Companion asset: a single results table, rendered as a PNG for
  sharing on social, and as inline markdown for the post body.

### Section 4 — What the numbers mean

- Claim 1, carefully stated: within these five assets on this
  hardware, Lathe produced assets that cleared the default
  acceptance bar on the first build in more cases than either
  baseline. State the exact cell count, do not generalize further.
- Claim 2: the failures Lathe did have were caught by the validator
  suite before they shipped. The alternative in production is
  catching them days later during integration, or not at all.
- Claim 3: the variance on the probabilistic stage matters and is
  visible in the spread. A mean alone is dishonest; we report the
  full five-point set.
- Claim 4 (the expensive one): the wall-clock numbers are not
  directly comparable across baselines because the scope of the
  work differs. Lathe bakes, UV-unwraps, packages, and validates;
  the raw baseline outputs a mesh. A 3x wall-clock for Lathe is
  not a loss if the output is ready to ship.
- Counter-arguments the reader might raise, answered:
  - "This is a cherry-picked asset family." — Named the hero families
    in public; we are not claiming results on assets we did not
    benchmark.
  - "Your validator thresholds are tuned to your pipeline." —
    Thresholds are in the repo, readable, and reviewers can argue
    for different ones. Re-running the benchmark with different
    thresholds is a 20-minute exercise.
  - "You did not run against [closed provider X]." — Correct, and
    we say why: terms of service do not permit unfunded benchmark
    publication for most closed providers.

### Section 5 — Reproducibility and next steps

- Everything in this post is reproducible. The raw numbers, the
  commands, the artifact bundles, and the CI runs are all
  published. Link to the GitHub Release with the artifact bundle
  and the benchmark notebook.
- A paragraph on what we want to benchmark next: modular assembly
  flows (BL-41+ territory), reconstruct flows from user-provided
  reference images, and a stress test on a 20-asset production
  set.
- Invitation: if a studio wants their own asset family benchmarked
  under the same methodology, we will run it and publish the
  numbers whether we win or lose. Point to the BL-40+ gatherer and
  its maintainer contact.
- Close on the methodology-preservation claim: "the build passed"
  only means something if we are honest when it did not.

### Calls to action

1. Download the artifact bundle and inspect the `certification.json`
   files for any of the five assets.
2. Re-run one asset on your own workstation using the exact command
   in the appendix. Compare wall-clock numbers.
3. If you work at a studio: pick an asset from your backlog, author
   the `.lth` file, and measure your own first-build acceptance rate.
4. If you disagree with a threshold or a methodology choice, open a
   PR against `docs/blog/03_five_asset_benchmark.md` and we will
   engage.

### Companion assets checklist

- Results matrix, PNG and inline markdown. PNG ≤ 200 KB.
- Artifact bundle on GitHub Releases (all five assets, three
  baselines, full traces). ≤ 500 MB zipped.
- Benchmark notebook reproducing the numbers. Runs to completion on
  the reference hardware in < 90 minutes.
- Appendix: exact commands per baseline per asset.
- Honest-loss screenshot: the failing mesh from the losing baseline
  with the specific validator failure called out.

### Cross-links

- `docs/blog/01_the_build_passed.md` — the thesis this post
  provides evidence for.
- `docs/blog/02_3d_asset_generation_is_a_compiler_problem.md` — the
  architectural argument.
- `docs/blog/05_certification_as_the_product.md` — where the
  validator report becomes the product.
- `docs/benchmarks/` — the benchmark specifications these runs
  conform to.
- `docs/walkthroughs/` — per-asset walkthroughs tied to the hero
  examples benchmarked here.

### Publishing checklist

- [ ] **No numbers are published until BL-40+ has produced real
      measurements.** Fabricated numbers are disqualifying.
- [ ] Every command in the appendix copy-pastes into a terminal
      and runs.
- [ ] The artifact bundle on GitHub Releases includes every
      `certification.json` cited in the post.
- [ ] Honest losses are called out in the body, not hidden in a
      footnote.
- [ ] Every claim in Section 4 is traceable to a specific cell in
      the matrix.
- [ ] Methodology section names the hardware, the commands, and
      the validator thresholds so a reader can reproduce any
      cell.
- [ ] The reproducibility notebook is linked and the run output is
      checked into the artifact bundle.
- [ ] The BL-40+ gatherer owner is tagged as a reviewer before
      publication.
