# Personas

Three personas define Lathe's audience. **Persona A is the wedge** — every Wave-1-through-Wave-4 GTM decision should be testable against her needs first. Personas B and C come online after the wedge is validated.

---

## Persona A — Indie / small-studio Godot tech artist (WEDGE)

**Profile.** Solo developer or tech artist embedded in a 1–10-person Godot studio. Ships 5–30 hard-surface props per milestone (crates, panels, doors, consoles, pedestals, cabinets). Lives in Blender + Godot 4.x. Knows Python well enough to read stack traces, not well enough to write a DCC plugin from scratch. Reads release notes; does not file issues unless something is broken twice.

**Daily reality.** Level-building is blocked on props. Every new variant means: Blender model → manual UV unwrap → collision shape by hand → LOD pass → export to `.glb` → drag into Godot → discover the pivot is wrong → re-export → discover collision is broken → re-export. A "simple crate variant" is a 45-minute chore, not a 3-minute one.

**Pain.** Repeatable game-ready assets with correct pivots, collision, LODs, and UV density — without babysitting. Weekly, she loses half a day to re-exports caused by silent breakage no tool caught.

**JTBD (exact, from Plan 09).**

> When I need a new crate/panel/door variant, hire Lathe to produce a certified `.tscn`-ready asset in under 10 minutes so I can keep level-building.

**What "good" looks like to her.**
- One source file per asset family; variants are a few lines of diff.
- `lathe build` emits a `.glb` + manifest; the Godot addon drops it in and it works first try.
- When a build fails, the failure names the stage and the rule (e.g. `uv.texel_density below 256 px/m`) — not a stack trace.
- She can re-run the exact build months later and get the same bytes.

**Anti-signals (she will bounce).**
- "Write a prompt and hope." She has been burned before.
- Tools that ship without collision/pivot/LOD. That is 60% of her work.
- Tools that require a cloud account to evaluate.

**Why she is the wedge.** She is under-served (existing text-to-3D targets hobbyists or concept artists), she has a budget of *time* rather than *money* (so OSS is a feature), and her output is measurable (the `.tscn` either works or it doesn't). If Lathe ships her a certified crate in 10 minutes, she tells two friends. If we ship her a broken one, she writes a post and we are done.

---

## Persona B — Pipeline TD at a 10–50-person studio

**Profile.** Senior tools/pipeline engineer at a mid-size studio (indie-plus or AA). Owns the asset contract: tri-budgets, UV conventions, naming, collision rules, engine-import guarantees. Reviews art PRs. Runs internal Jenkins/GitHub Actions. Writes Python/C#; has shipped a DCC plugin or two.

**Daily reality.** Enforces studio standards by hand and by code review. Every new hire re-learns "how we do doors here" over 2–3 failed PRs. When a junior artist ships a door with wrong texel density, it lands in the build; three weeks later it ships in a demo; the Art Director notices; a Slack fire starts.

**Pain.** No machine-readable source of truth for "what counts as a shippable asset here." Standards live in a wiki that is 70% stale and in one TD's head.

**JTBD.**

> When a junior artist submits an asset PR, hire Lathe to certify it against our studio contract in CI so I don't have to review every texel-density violation by eye.

**What "good" looks like to him.**
- Studio asset contract lives in a versioned `.lth` file — reviewable, diffable, auditable.
- CI runs `lathe build` and blocks merge on certification failure.
- Failure output tells the junior artist exactly what to fix.
- New hires onboard against a contract, not tribal knowledge.

**Distribution.** Reachable via Godot/Unreal tech-art forums, TD-focused Discords, and GDC tools roundtables. Typically waits until V0.5 (public launch + benchmark published) before piloting.

---

## Persona C — AI coding agent operating a game repo

**Profile.** An autonomous coding agent (Claude Code, Cursor, Continue, OpenHands, Devin, etc.) assigned a task like "the panel collision is off" or "add 3 crate variants." Reads the repo, edits code, runs commands, opens PRs. Has no intuition about art — only about signals. Needs a *yes/no verdict* it can trust.

**Daily reality.** A bug report lands. The agent can read `.lth` sources, diff them, run a build, and interpret a structured certification result. It cannot eyeball a mesh. If the tool ships "it looks roughly right" as its output, the agent is blind.

**Pain.** Current generative-3D tools emit meshes with no pass/fail signal. The agent has no way to know whether its diff helped or broke things downstream — no UV validity, no collision sanity, no tri-budget check that it can parse.

**JTBD.**

> When I'm assigned a 3D asset bug or request, hire Lathe to turn my `.lth` diff into a certified build and emit a machine-readable pass/fail signal I can trust without human review.

**What "good" looks like to it.**
- `.lth` is text. Diffing is native.
- `lathe build` exits non-zero on certification failure; emits a structured trace on success.
- Failure messages name the stage, rule, and offending value — all parseable.
- The tool is reachable via a Claude Code skill / Continue rule / Cursor rule / OpenHands tool entry — NOT a human-facing Discord.

**Distribution (reminder: NOT Discord).** Persona C is programmatic. Channels are: Claude Code skills marketplace, Continue.dev rules hub, Cursor rules hub, OpenHands/Devin tool directories, NeurIPS/ICLR tool-track demos, and `agents.md` spec listings. See `docs/roadmap_public.md` Phase 2b.

---

## Interview target: 8 persona interviews

Interviews validate (or invalidate) the persona sketches above. Target distribution: **5 Persona A, 2 Persona B, 1 Persona C (agent-builder team, not the agent itself).** Logged in `docs/research/interviews/` once that directory exists. Goal is not to confirm the personas as written — it is to find where they are wrong.

### Persona A — template questions (ask 5 of these)

1. Walk me through the last hard-surface prop you shipped. Where did time actually go?
2. How many variants of a single prop family do you typically ship per milestone?
3. What part of the Blender → Godot handoff breaks most often? Pivot, collision, UV, or LODs?
4. When a re-export breaks something silently, how do you usually find out?
5. If a tool produced a `.glb` + manifest and the Godot addon auto-imported it correctly, would you trust it after one try, or does it need to earn trust?
6. Do you care more about visual fidelity or about not having to redo collision? Be honest.
7. Have you tried Meshy / Luma / Hunyuan? What stopped you from using them in your actual pipeline?

### Persona B — template questions (ask 5 of these)

1. Where does your studio's asset contract live today? Wiki, Notion, a TD's head, a script, all of the above?
2. What's the most common reason an art PR gets kicked back in review?
3. Do you gate CI on asset QA today? If yes, what does it check? If no, why not?
4. How much of a junior artist's first three weeks is spent re-learning studio standards the hard way?
5. If you could encode "what counts as a shippable door here" in a versioned file, what would break first — your art team or your tooling?
6. What would it take for you to let a CI job block a merge on art QA, not just flag it?
7. Which engines, and which families (hard-surface vs organic vs environment), matter most for the next 6 months?

### Persona C — template questions (ask the agent-builder team that deploys Persona C)

1. What 3D-asset tasks do your agents get assigned today, and how do they currently handle them?
2. When your agent edits something it can't visually verify, what signal does it trust?
3. Do your agents have a reliable way to tell "this mesh is shippable" vs "this mesh is garbage"?
4. If a tool emitted a structured pass/fail with named rule violations, would your agent use it? What would make it not use it?
5. What's the biggest class of silent-failure you see when agents touch binary/asset files?
