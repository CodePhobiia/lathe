# Implementation Plan: Product Value & Vision 8/10 → 10/10

## Overview

Lathe's thesis ("the build passed") is strong; the gap to 10/10 is *external validation*: one named wedge persona, one engine integration that turns the thesis into a 90-second demo, a defensible benchmark, a monetization path, and 3 design partners under LOI. This plan sequences that work across 6 months.

---

## Phase 1 — Persona & ICP Sharpening (Month 1)

`docs/personas.md` with 3 personas; **Persona A** is the wedge:

- **Persona A — "Indie/small-studio Godot tech artist" (WEDGE).** Ships 5–30 hard-surface props per milestone; Blender + Godot; pain = repeatable game-ready assets with correct pivots/collision/LODs without babysitting. JTBD: *"When I need a new crate/panel/door variant, hire Lathe to produce a certified `.tscn`-ready asset in under 10 minutes so I can keep level-building."*
- **Persona B — Pipeline TD at 10–50-person studio.** JTBD: encode studio asset contract as source; gate CI on certification.
- **Persona C — AI coding agent operating a game repo.** JTBD: emit `.lth`, run `lathe build`, trust the certification signal.

ICP for wedge: Godot 4.x indie/small studios (1–10 devs) shipping hard-surface-heavy games (factory/sci-fi/dungeon). `docs/icp.md` with firmographic + workflow signals.

**Deliverables:** `docs/personas.md`, `docs/icp.md`, `docs/jtbd.md`. **Target:** 8 persona interviews logged in `docs/research/interviews/`.

## Phase 2 — Wedge Integration: `lathe-godot` (Month 1–2)

**Why Godot:** (1) open-source aligns with Lathe's OSS-core stance; (2) MIT lets us ship a first-party addon without gatekeepers; (3) `.glb`/`.gltf` import is native and lossless for collision/LOD metadata; (4) Unreal/Unity have established asset-store economics that crowd a new entrant; Roblox locks us into `.rbxm` + Studio pipeline. Godot is the shortest path to "run one command, drag into editor, it works."

Scope for `lathe-godot` (new repo `lathe-godot/`, referenced from `docs/integrations/godot.md`):

1. GDScript addon watches `lathe_out/` dir and auto-imports `.glb` + `manifest.json`.
2. Maps Lathe sockets/anchors → Godot `Marker3D`; collision → `CollisionShape3D`; LODs → `MeshInstance3D.lod_bias`.
3. Surfaces certification status (pass/fail + repair log) in Godot Import dock.
4. One-click "open build trace" → `lathe.cli inspect`.

**Flagship demo:** `examples/godot_industrial_crate/` — 90-second screen-capture from `.lth` edit to crate in-game.

## Phase 2b — Persona-C GTM: Distribution to AI Coding Agents (Month 2–4)

Persona C (AI coding agent operating a game repo) is named in Phase 1 but has no distribution channel. Coding agents don't join Discords; their reachable surfaces are tool/skill registries and spec listings. Channels for Persona C:

- (a) **Claude Code skills marketplace** (`~/.claude/skills/` + plugin directory) — ship a `lathe` skill that wraps `lathe check/plan/build` with intent-preserving prompts and emits the certification signal back to the agent.
- (b) **Continue.dev rules hub** — submit Lathe tool-use rules so agents running in Continue can author `.lth` and trust the pass/fail verdict.
- (c) **Cursor rules hub** — equivalent rules package for Cursor's tool-use layer.
- (d) **OpenHands / Devin tool directories** — register `lathe` as a first-class tool with schema and cookbook entry.
- (e) **NeurIPS / ICLR Workshop demos (tool track)** — submit a tool-track paper/demo positioning Lathe as a verification harness for generative-3D coding agents.
- (f) **`agents.md` spec listings** — add Lathe to any open agent-tool spec that aggregates build/verify tools.

No Discord outreach for Persona C — it's programmatic. Success metric: ≥3 registries accept the package by Month 5; ≥1 agent-framework cookbook references `lathe build` as the certification step.

Deliverables: `docs/integrations/agents/claude_code_skill.md`, `continue_rules.md`, `cursor_rules.md`, `openhands_tool.md`, `devin_tool.md`, `agents_md_listing.md`; `docs/talks/neurips_workshop_demo.md`.

## Phase 2c — Side-Bet: Roblox Studio Spike (Month 5)

Not committed. 2-week Roblox Studio spike evaluating `.lth → .rbxm` exporter feasibility via the Roblox Studio MCP (mesh generation, Luau execution, scene inspection, multi-edit). Evaluated in **Month 5**, after Godot ships — not before. Deliverables: `docs/integrations/roblox_spike.md` with (a) can a Lathe-built mesh + collision + pivots round-trip into `.rbxm` losslessly, (b) does the Roblox UGC/Marketplace economy justify a second wedge, (c) cost-to-maintain a Roblox exporter alongside Godot.

Godot remains primary per manifesto OSS stance (Roblox is closed, dilutes backend-independence story). Spike outcome is a go/no-go recommendation, not a commitment.

## Phase 3 — Competitive Positioning (Month 2)

`docs/competitive_landscape.md` — single table, Lathe vs. Meshy / Hunyuan standalone / Luma (text-to-3D); Houdini HDA + SideFX Labs (procedural); Quixel / Sketchfab / Unity Asset Store (stores); Blender + manual QA. Axes: declarative source, reproducibility, certification gates, topology/UV guarantees, collision/pivots/LOD, engine handoff, provenance, licensing clarity, cost/asset, iteration speed. Lathe wins on *contract + certification + provenance*; loses on *visual novelty at pixel level*. Stated honestly.

## Phase 4 — Benchmark Study (Month 2–3)

5 reference assets stressing the thesis: `industrial_crate`, `sci_fi_wall_panel`, `mechanical_door`, `control_pedestal`, `service_cabinet` (in-repo heroes). Produce via: Lathe (fallback lane), Lathe (learned lane), Meshy, Hunyuan standalone, Quixel closest match, Blender-by-hand (contracted artist, 1 pass). Measure: wall-clock, $ cost, tri count adherence, UV validity, collision presence, pivot correctness, Godot-import success first try, reproducibility hash stability across 3 runs, iteration speed (time to re-run after intent tweak).

**Deliverables:** `docs/benchmarks/v0_5_five_asset_study.md` + raw data in `docs/benchmarks/data/`. Published alongside Phase 7 launch post.

## Phase 5 — Scenario Walkthroughs (Month 3)

3 synthetic day-in-the-life scenarios in `docs/walkthroughs/`. Explicitly **not** case studies — they are synthetic; calling them case studies is misleading against real-user-story expectations. Re-label to "scenario walkthroughs" until a design partner signs and contributes a real case study.

1. `01_godot_indie_crate_family.md` — solo dev ships 12 crate variants in an afternoon.
2. `02_studio_door_contract.md` — TD encodes studio door contract; junior artist submits PR that fails certification on UV density; fix is one-line.
3. `03_agent_authored_panel.md` — coding agent takes a bug report ("panel collision off") and lands a certified `.lth` diff.

Each with before/after timing, source diff, build trace excerpt. Each explicitly marked "synthetic scenario" at the top of the doc.

## Phase 6 — Public Roadmap (Month 1, ongoing)

`docs/roadmap_public.md` tied to PRD milestones:

- **V0.1 (now):** fallback compiler lane; repo private.
- **V0.3 (Month 2):** Godot addon alpha; 5-asset benchmark draft; 3 design-partner LOIs.
- **V0.5 (Month 4):** public OSS launch; benchmark published; 1 learned lane certified; Discord open.
- **V0.8 (Month 6):** V1.2 surface lane public; paid hosted registry beta.
- **V1.0 (Month 9):** standalone compiler; CI cert service GA.

Each milestone has explicit exit criteria tied to PRD Milestones 1–5.

**Clarification: two axes, not one.** PRD Milestones M1–M5 are **engineering** milestones (technical capabilities: fallback lane, local deterministic stages, learned lanes, repair loop, standalone). Public roadmap V0.x versions are **GTM** milestones (adoption + distribution: addon alpha, OSS launch, hosted registry beta, standalone GA). They map to each other but are not the same axis: e.g., V0.5 public launch = M3 engineering milestone + benchmark publication + Discord open. Maintain the two axes separately in `docs/roadmap_public.md`; cross-reference each so a reader can trace a GTM version back to its underlying engineering milestone.

Mapping table (maintained in `docs/roadmap_public.md`):

| GTM (public) | Engineering (PRD) | GTM deliverables beyond engineering |
|---|---|---|
| V0.1 | M1 (fallback compiler lane) | repo private; personas drafted |
| V0.3 | M2 (local deterministic stages) | Godot addon alpha; 5-asset benchmark draft; 3 LOIs |
| V0.5 | M3 (learned lanes certified) | public OSS launch; benchmark published; Discord open |
| V0.8 | M4 (repair loop) | V1.2 surface lane public; paid hosted registry beta |
| V1.0 | M5 (standalone compiler) | CI-cert SaaS GA; studio references |

## Phase 7 — Community Seeding (Month 3–4)

- Discord: `#announce`, `#show-your-asset`, `#builds-that-passed`, `#help`, `#rfc`.
- Weekly "show your asset" thread; monthly "build-passed gallery" blog post.
- Early access: 20 Godot tech artists from Phase 1 interviews; 5 pipeline TDs; 3 agent-builder teams. Tracked in `docs/community/early_access.md`.

## Phase 8 — Monetization (Month 3 decision, Month 6 beta)

Options matrix in `docs/business/monetization.md`: (a) OSS core + paid hosted registry for shared kits/libraries; (b) paid Blender addon; (c) paid CI certification SaaS; (d) studio support contracts.

**Primary: (a) hosted registry** for shared kits/libraries — lower activation energy, aligns with community seeding (Phase 7), compounds with stdlib growth (`std/` families/components/materials/kits/libraries). A 3-day-old repo can monetize *reuse* before it can monetize *gating*; a registry also doesn't require customers to have CI at all, and it ships the moment `std/` reaches critical mass.

**Secondary: (c) CI certification SaaS** — wait until V0.8+ when validator thresholds (`semantic_preservation_quality`, `join_legality`, silhouette checks) are stable enough that a SaaS contract is defensible. Selling certification-as-a-service on unstable thresholds forfeits trust; hold until the product earns the right.

**Reject (b) paid Blender addon** — fragments the compiler story; Blender is an adapter, not a product surface per manifesto L30–38. **Reject (d) studio support contracts** — doesn't scale, couples maintainer throughput to customer count, and diverts energy from product.

## Phase 9 — Design Partners (Month 2–3)

3 prospects in `docs/business/design_partners.md`:
1. Godot-first indie studio shipping factory/sci-fi title (Godot Discord + Mastodon).
2. Mid-size studio with Houdini pipeline seeking AI augmentation (SideFX community + GDC).
3. AI-agent tooling company building coding agents for games (direct outreach).

Outreach in `docs/business/outreach_template.md`: one-paragraph thesis, 90-sec Godot demo link, LOI ask for 3-month co-development + logo rights + quarterly feedback; no cash either direction.

**Target: 3 signed LOIs by Month 4.**

## Phase 10 — Distribution (Month 4, launch)

Day 1: PyPI (`pip install lathe`), GitHub releases (signed tarballs), Godot AssetLib submission for `lathe-godot`, Blender Extensions Platform for inspector addon. Month 5: Homebrew tap + scoop manifest. `docs/distribution.md`.

## Phase 10b — Telemetry Design for `return build rate` KPI (Month 4)

The 40% return-build-rate KPI (Measurable 10/10) requires opt-in telemetry. Design:

- **Opt-in mechanism.** User must run `lathe telemetry enable` once; nothing pings before that. `lathe telemetry disable` + `lathe telemetry status` also ship. Default state is disabled. Settings persist in `~/.config/lathe/telemetry.json`.
- **Ping payload.** On `lathe build` completion (success or failure), emit `{build_id_hash, lathe_version, stack_id, exit_code, wall_ms, user_salt}` where `user_salt` is a per-install random 16-byte value generated at enable time. **No asset content, no file paths, no environment variables, no command-line args, no hostnames.**
- **Endpoint.** `https://telemetry.lathe.dev/ingest` — HTTPS only, POST JSON, 2-second timeout, best-effort. Build must **not** depend on network reachability; failure to send is silent and never blocks the build. Reject any design where telemetry becomes a build dependency.
- **Retention.** 90 days raw; aggregated counts kept indefinitely.
- **Counted metric.** Unique `user_salt` that runs `lathe build` ≥2 times in a rolling 7-day window. Reported weekly in `docs/community/telemetry_report.md`.
- **Privacy posture.** Public privacy statement in `docs/privacy.md`. Source of the telemetry client in `lathe/telemetry.py` is the only code path that ever contacts the network in the free CLI — easy to audit.

Reject telemetry that depends on network for build (must be opt-in, failure-silent). Botched telemetry kills OSS trust faster than missing features.

## Phase 11 — Content Marketing (Month 3–4)

5 launch posts in `docs/blog/`: (1) "The build passed" manifesto-as-post; (2) "Why 3D asset generation is a compiler problem"; (3) 5-asset benchmark; (4) Godot integration walkthrough; (5) "Certification as the product." Keynote version of (1) pitched to GDC Experimental, Roguelike Celebration, FOSDEM graphics devroom — `docs/talks/manifesto_keynote.md`.

---

## Measurable 10/10 Criteria (Month 6 checkpoint)

- [ ] 2,000 GitHub stars
- [ ] 500 Discord members; 50 weekly active
- [ ] 100 assets certified by external users (opt-in telemetry via `lathe build --share-cert`)
- [ ] 3 signed design-partner LOIs
- [ ] Return build rate: 40% of users who run `lathe build` once run it again within 7 days
- [ ] Benchmark study cited by 1 external outlet (80.lv, Game Developer, Godot newsletter)
- [ ] 10,000 unique visits to manifesto post in launch month
- [ ] 1 paying CI-cert beta customer

## Risks & Mitigations

- **Feasibility cut for solo maintainer:** Month 4 cannot land all three of {Godot addon polish, CI-SaaS beta, 3 LOIs}. Drop **CI-SaaS beta to Month 6+**; keep **Godot + LOIs in Month 4**. If CI-SaaS beta moves earlier, drop LOI count to 1. This is a hard capacity constraint, not a preference — treat the Month-4 scope as locked at {Godot addon ready, 3 LOIs signed, V0.5 public launch} and resist additions.
- **Godot addon quality slips, kills first impressions** → treat `lathe-godot` as release blocker for V0.5; 2 weeks of polish before launch.
- **Benchmark read as rigged** → open raw data; invite competitors to reproduce; 1 external reviewer re-runs.
- **Monetization alienates OSS contributors** → hosted registry and CI SaaS both strictly additive; core CLI, certification logic, all stages remain OSS permissive.
- **Telemetry backfires on OSS trust** → opt-in only, failure-silent, minimal payload, auditable single file (`lathe/telemetry.py`); kill-switch documented in `docs/privacy.md`.

---

## Relevant paths

- `docs/lathe_manifesto.md`, `docs/lathe_prd.md`, `CLAUDE.md`
- **New docs:** `docs/personas.md`, `icp.md`, `jtbd.md`, `integrations/godot.md`, `integrations/roblox_spike.md`, `integrations/agents/{claude_code_skill,continue_rules,cursor_rules,openhands_tool,devin_tool,agents_md_listing}.md`, `competitive_landscape.md`, `benchmarks/v0_5_five_asset_study.md`, `walkthroughs/01_godot_indie_crate_family.md`, `02_studio_door_contract.md`, `03_agent_authored_panel.md`, `roadmap_public.md`, `community/early_access.md`, `community/telemetry_report.md`, `business/monetization.md`, `design_partners.md`, `outreach_template.md`, `distribution.md`, `privacy.md`, `talks/manifesto_keynote.md`, `talks/neurips_workshop_demo.md`

---

## Amendment log (2026-04-23)

Applied from `plans/reviews/09_product_value_vision_review.md` and meta-review cross-cutters:

1. **Added Phase 2b — Persona-C GTM.** Six programmatic channels (Claude Code skills, Continue.dev rules, Cursor rules, OpenHands/Devin tool dirs, NeurIPS/ICLR workshop, `agents.md` listings). No Discord for Persona C — it's programmatic. Closes review Gap #1.
2. **Added Phase 2c — Roblox Studio side-bet.** 2-week Month-5 spike evaluating `.lth → .rbxm` via Roblox Studio MCP; Godot remains primary per manifesto OSS stance. Not a commitment; go/no-go output. Closes review "Questionable pick: Godot over Roblox."
3. **Inverted Phase 8 monetization.** Primary is now **(a) hosted registry** (lower activation energy, compounds with `std/` growth, aligns with Phase 7). Secondary is **(c) CI certification SaaS**, held until V0.8+ when validator thresholds stabilize. Rejected (b) paid Blender addon and (d) studio support contracts with rationale. Closes review "Questionable pick: CI-SaaS primary."
4. **Resolved PRD M1–5 vs roadmap V0.x collision in Phase 6.** Added explicit two-axis clarification (engineering vs GTM) and a mapping table. Closes review "Misaligned: version-number drift."
5. **Added Phase 10b — Telemetry design.** Opt-in, failure-silent, minimal payload `{build_id_hash, lathe_version, stack_id, exit_code, wall_ms, user_salt}` to `https://telemetry.lathe.dev/ingest`; 90-day retention; counted metric defined for return-build-rate KPI. Closes review Gap #2.
6. **Relabeled Phase 5 "case studies" → "scenario walkthroughs."** Directory renamed `docs/case_studies/` → `docs/walkthroughs/`. Closes review "Synthetic case studies" note.
7. **Added solo-maintainer feasibility cut as top Risks bullet.** Month 4 drops CI-SaaS beta to Month 6+; keeps Godot + 3 LOIs. Closes review Feasibility finding.
8. **Updated Relevant paths** to reflect new docs (`walkthroughs/`, `privacy.md`, `roblox_spike.md`, agent-registry packages, NeurIPS workshop talk, telemetry report).

Not applied (deferred to other plans or unnecessary here):

- GDC/FOSDEM CFP deadlines on Phase 6 calendar (review Gap #3) — not in the 8 explicit amendment directives; flagged for a follow-up pass if desired.
- Launch-choreography subsection in Phase 11 (review Gap #4) — not in the 8 directives.
- `Depends on` block referencing Maintenance / Product Quality / Governance plans (review Gap #5) — cross-plan scaffolding belongs in a meta-plan, not plan-09.
- Benchmark "allowed to lose on" pre-commitment (review Gap #6) — belongs in `docs/benchmarks/v0_5_five_asset_study.md` itself, not this plan.
