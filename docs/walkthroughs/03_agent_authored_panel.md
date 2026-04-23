# 03 — Agent-Authored Panel: Bug Report to Certified PR

> **Synthetic scenario — not a real user story.** This is a narrative walkthrough; replace with a real case study when a design partner signs.

## Persona and stakes

A coding agent (Claude Code, invoked via the `lathe` skill in `~/.claude/skills/lathe/`) is assigned a bug on a Godot factory-survival repo. The repo uses Lathe to author 34 sci-fi wall panel variants. Issue #412:

> **panel collision off.** the `sci_fi_wall_panel_vents_a` variant's collision box is inside-out — player falls through. reproduces 100% on Godot 4.3 Forward+ renderer. plz fix before friday demo.

The human who filed the issue is not available. The agent has `lathe build`, repo read/write, and nothing else. Chen (the TD from scenario 2) trusts the agent because the agent is gated by certification, not by human review — a failing build blocks the merge.

## The agent's tool-use trace (mocked)

```
[agent]  tool:       read_file  path="assets/panels/sci_fi_wall_panel.lth"
         result:     (… 220 lines …)
[agent]  tool:       grep       pattern="vents_a"
         result:     assets/panels/sci_fi_wall_panel.lth:164: variant vents_a {
                     assets/panels/sci_fi_wall_panel.lth:170:   fit.collision = convex_hull
[agent]  reasoning:  variant uses convex_hull. Vented panel has interior voids;
                     convex hull would simplify to a solid box around the panel,
                     which is fine for collision but would not invert. Inverted
                     collision usually comes from a mesh whose face-winding flipped
                     during fallback generation and the collision derives from
                     the same source. Check the trace.
[agent]  tool:       shell      cmd="python -m lathe.cli build \
                                  assets/panels/sci_fi_wall_panel.lth vents_a \
                                  --out /tmp/lathe-triage --trace-verbose"
         result:     certified: PASS (!!!)
                     collision.pivot.at=panel.center
                     collision.winding=inverted        <-- flagged by validator but below threshold
[agent]  reasoning:  validator flags inverted winding but doesn't fail — the rule is
                     `warn`, not `ensure`. For this studio's Godot 4.3 Forward+
                     pipeline, inverted winding on collision is actually fatal.
                     Fix: tighten the rule locally for this variant, or force
                     `collision.auto_fix_winding = true` in the fit block.
                     Prefer the second — it is a source fix, reviewable.
[agent]  tool:       edit_file  path="assets/panels/sci_fi_wall_panel.lth"
                                patch: see "Source diff" below
[agent]  tool:       shell      cmd="python -m lathe.cli build \
                                  assets/panels/sci_fi_wall_panel.lth vents_a \
                                  --out /tmp/lathe-triage"
         result:     certified: PASS
                     collision.pivot.at=panel.center
                     collision.winding=ccw (fixed)
[agent]  reasoning:  build passes; collision winding now ccw as Godot expects.
                     Open PR.
[agent]  tool:       git_create_pr  title="fix(panels): force ccw collision winding on vents_a"
                                    body="(see below)"
                                    base=main
         result:     PR #418 opened
```

The agent is blind to the mesh. It is not blind to the certification signal. The `certified: PASS` with `collision.winding=ccw (fixed)` is the yes/no verdict it needs, and it is machine-parseable.

## Source diff (agent-authored)

```diff
  variant vents_a {
    intent {
      role = "sci-fi wall panel, vented intake, A-series"
      style = ["clean_industrial", "brushed_aluminum"]
    }
-   fit.collision = convex_hull
+   fit.collision             = convex_hull
+   fit.collision_auto_fix_winding = true
  }
```

One line added. No geometry edited. No Blender opened. The source is the contract.

## Agent-authored PR body (mocked)

```
### Fixes #412 — panel collision off (vents_a)

**Root cause.** `sci_fi_wall_panel_vents_a` fallback generation produced a mesh
with inverted face winding. The collision stage derives from the same mesh, so
the collider inherited the inverted winding. Godot 4.3 Forward+ treats inverted
collision meshes as "inside-out," causing the player fall-through reproduction.

**Fix.** One-line addition in the `vents_a` variant: force
`fit.collision_auto_fix_winding = true`. This turns a validator `warn` into
an `ensure + auto-repair` for this variant. All other panel variants unchanged.

**Certification.**
- Before: build passes with `collision.winding=inverted` (warned, not blocked).
- After:  build passes with `collision.winding=ccw (fixed)`.
- Trace:  `/tmp/lathe-triage/trace.json` (attached).

**Test plan.**
- [x] `lathe build` passes on `vents_a` with the fix.
- [ ] Load `dist/panels/vents_a.glb` in Godot 4.3 Forward+ and verify collision.
      (Requires a human — I cannot eyeball the scene.)
- [ ] Regression: re-build all 34 panel variants; confirm none regressed.
```

Note the agent **explicitly flags what it cannot verify** (the in-engine visual check). It does not claim the fix is complete without a human doing the last-mile eye-check. That honesty is a feature of the trust contract.

## What this walkthrough validates (and what it doesn't)

**Validates.** The Persona-C JTBD: "turn an `.lth` diff into a trusted machine-readable pass/fail signal." The agent operated end-to-end without a human, landed a reviewable one-line source fix, and stopped where it should stop (visual verification in-engine). Lathe's value to Persona C is not "the agent can generate 3D" — it is "the agent can know whether its diff is shippable."

**Does not validate.** That every agent is this disciplined (a worse agent would have claimed success without the build signal). That Lathe validators already cover every kind of breakage (this scenario assumes `collision.winding` is a warn-level rule; in V0.1 scaffold, validator coverage is still growing). That agents are ready to own art PRs today — they are ready to *scaffold* them under human review, and that is where the trust is earned.
