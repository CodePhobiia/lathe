# Godot Integration Walkthrough

**Working title:** *From `.lth` File to Playable Crate in 90 Seconds: A
Godot Walkthrough*

**One-sentence hook:** Write a Lathe file, run one build, and drop the
result into your Godot scene with pivot, collision, and LODs already
correct.

**Target audience:** Godot developers, solo and small-team game devs,
gameplay engineers who do not want to hand-craft every prop, and tech
artists evaluating Lathe as a pipeline component for a Godot-based
project.

**Distribution channel (primary):** Godot Discord (#tools and
#showcase), r/godot, the Godot forum "Tutorials & Resources" section,
Godot AssetLib page description, Mastodon #godot hashtag.

**Distribution channel (secondary):** Tech artist Twitter/Bluesky with
the 90-second screen capture embedded, cross-posted to r/gamedev once
community reception is positive, linked from the Lathe landing page as
the primary "try it" entry for anyone who prefers a worked example to a
manifesto.

**Length target:** 1400-1800 words plus inline code snippets.

**Tone:** Concrete, example-first. No abstractions until the final
section. Every step is a command or a click.

**Status:** Outline for Plan 09 Phase 11, depends on a working
`lathe-godot` addon release.

---

## Outline

### Section 1 — What we are going to build, and what "done" looks like

- The demo target: a supply crate that spawns in a Godot scene, is
  physics-interactable, casts shadows correctly, and switches LODs
  when the player walks away. Total wall-clock: 90 seconds, install
  time excluded.
- What the reader needs: Godot 4.3 or later, Python 3.12 or later,
  `pip install lathe`, and the `lathe-godot` addon installed from
  AssetLib. The `docs/quickstart.md` path covers everything except
  the addon install.
- The one screenshot at the end: the crate in a Godot scene with the
  debug overlay showing collision shape, pivot marker, and active
  LOD. That screenshot is the "done" state.
- Companion asset: the 90-second screen capture itself, captured
  from a fresh Godot project.

### Section 2 — The `.lth` source

- Author a minimal `.lth` file for the supply crate. Use the
  existing `industrial_crate` hero example as the starting point —
  it is in `examples/` and compiles on the native-only path.
- Show the intent block in full, annotated inline:
  - `role = "modular supply crate"`
  - `style = ["industrial", "weathered"]`
  - `parts = [body, lid, handle_l, handle_r]`
  - `materials = ["painted_steel", "rubber_trim"]`
  - `scale = 0.8m`
  - `interactions = [pick_up, throw, stack]`
- Show the contract references that wire in pivots, sockets, and
  collision. Call out that these are already provided by
  `std/patterns/` and `std/components/` — the user is composing,
  not re-implementing.
- Save as `supply_crate.lth` in the Godot project root (Godot is
  fine with non-Godot files sitting alongside `.tscn` scenes).
- Companion asset: the annotated source as a syntax-highlighted
  code block, with a side note indicating which `std/` module each
  imported symbol comes from.

### Section 3 — The build

- Three commands, run from the Godot project root:
  ```bash
  python -m lathe.cli check supply_crate.lth
  python -m lathe.cli plan supply_crate.lth supply_crate
  python -m lathe.cli build supply_crate.lth supply_crate --out dist
  ```
- Walk through what each command did:
  - `check` validated the source against the grammar and schema;
    any typos in a style token or a missing part declaration got
    caught here.
  - `plan` emitted the effective build plan, so the reader can see
    which stages will run and which backends will handle each.
  - `build` ran the pipeline end-to-end, producing
    `dist/supply_crate/` with `.glb`, `.usd`, `manifest.json`,
    `trace.json`, and `certification.json`.
- Show the final terminal line: `build: passed`. Note that if any
  validator had failed, this line would say so and the rest of the
  walkthrough would be a debugging walkthrough instead. That is
  the point — the build tells you.
- Touch on runtime-config: the walkthrough runs on the conservative
  native-only path. A reader with Hunyuan or VGGT wired up can pass
  `--runtime-config` and the same commands produce a higher-quality
  shape; every downstream step is identical.
- Companion asset: a short terminal recording (< 30 seconds) of the
  three commands running back to back.

### Section 4 — The Godot side

- Switch to the Godot editor. The `lathe-godot` addon is expected to
  be already installed and enabled — cover this in a prerequisites
  box at the top of the post, not in the walkthrough body, because
  it is a one-time setup.
- Show the new inspector dock added by the addon. It scans for
  `dist/*/manifest.json` files relative to the project root and
  lists built assets with their certification status.
- Click "Import" on `supply_crate`. The addon:
  - imports the `.glb` into `res://assets/lathe/supply_crate/`
  - creates a `.tres` material resource per material
  - wires the pivot to the scene's root transform
  - adds a `StaticBody3D` with the collision shape named in the
    manifest
  - configures the LOD distances declared in the `.lth` source
- Drag the imported scene into a Godot scene tree. Save and run.
  The crate renders, has correct collision, and switches LODs.
- Companion asset: the inspector dock screenshot, annotated with
  arrows to the certification badge and the import button.

### Section 5 — What happens when you edit and rebuild

- Change a value in `supply_crate.lth` — say, bump the tri budget
  or rename a material. Re-run the `build` command.
- The addon's watcher picks up the new manifest and offers to
  re-import. Accept. The Godot scene updates in place; any nodes
  the reader hand-added (lights, gameplay scripts) are preserved
  because they are parented to the imported scene, not embedded in
  it.
- Frame this as the real win: the Lathe source and the Godot scene
  stay in sync, and the round trip is seconds rather than the
  minutes of a manual DCC-to-engine loop.
- Call out the limitation honestly: if the reader modifies the
  imported mesh inside Godot directly, those edits are destroyed on
  re-import. The intended flow is: edits live in `.lth`, Godot
  consumes the build output.
- Companion asset: a short before/after comparing two builds after
  an intent edit.

### Calls to action

1. Run the three commands from Section 3 on the `industrial_crate`
   example in the Lathe repo. Total time: five minutes.
2. Install the `lathe-godot` addon and import the resulting build.
   Another two minutes.
3. Author a `.lth` file for one prop in your current Godot project.
   Measure whether the build output is good enough to replace a
   hand-made asset. An hour or two per prop.
4. If the addon does not cover an import case you need, open an
   issue against the `lathe-godot` repo with the manifest and the
   expected Godot node structure.

### Companion assets checklist

- 90-second screen capture of the full walkthrough. MP4, ≤ 20 MB.
- Annotated `.lth` source code block.
- Terminal recording of the three commands. asciinema cast.
- Godot inspector dock screenshot, annotated.
- Before/after build comparison.
- Final "done" screenshot with debug overlay. PNG, 1600x900.

### Cross-links

- `docs/quickstart.md` — the install path.
- `docs/distribution.md` — how the addon gets distributed via Godot
  AssetLib.
- `docs/blog/01_the_build_passed.md` — why we care about the
  "passed" state instead of the mesh itself.
- `docs/blog/02_3d_asset_generation_is_a_compiler_problem.md` — the
  architectural context.
- `docs/walkthroughs/` — other per-engine walkthroughs as they land.
- `examples/industrial_crate.lth` — the starting point for the
  walkthrough.

### Publishing checklist

- [ ] The 90-second capture is recorded against a tagged
      `lathe-godot` addon release, not a local dev build.
- [ ] Every command in the walkthrough has been run on a fresh
      Godot project and a fresh Lathe venv within the last week.
- [ ] The AssetLib page for `lathe-godot` links back to this post.
- [ ] The "prerequisites" box at the top is prominent enough that
      readers don't get stuck on install issues.
- [ ] Limitation about in-editor edits being destroyed on re-import
      is in the body, not hidden in a footnote.
- [ ] File paths and command examples match the real
      `lathe-godot` addon behavior; no guessed API calls.
