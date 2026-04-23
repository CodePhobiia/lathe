# Public Roadmap

Lathe has **two axes**. Mixing them causes planning confusion, so they are tracked separately here and cross-referenced via the mapping table.

- **Engineering milestones (PRD M1–M5).** Technical capability gates. Defined in `docs/lathe_prd.md`.
- **GTM versions (V0.1 → V0.3 → V0.5 → V0.8 → V1.0).** Adoption and distribution gates. Defined here.

A GTM version cannot ship before its underlying engineering milestone lands, but the reverse is not true: an engineering milestone can land quietly and wait for GTM to catch up (e.g. M2 may be complete before the Godot addon is polished enough for V0.3).

All dates below are **relative** (Month N after V0.1 internal freeze). Absolute dates land when Wave 0 is committed and the V0.1 tag is cut.

## Mapping table

| GTM (public) | Engineering (PRD) | GTM-specific exit criteria | Target (relative) |
|---|---|---|---|
| **V0.1 (now)** | M1 (fallback compiler lane stable) | Repo private; personas / ICP / JTBD drafted; manifesto + PRD published to team | Month 0 |
| **V0.3** | M2 (local deterministic stages: topology, UV, bake adapters) | Godot addon alpha; `industrial_crate` 90-sec demo recorded; 5-asset benchmark **draft** (private); 3 design-partner LOIs in flight | Month 2 |
| **V0.5** | M3 (first true learned lanes certified) | Public OSS launch (GitHub public, PyPI package, Godot AssetLib listing); 5-asset benchmark published with raw data; Discord open with seed channels; ≥3 design partners **signed** | Month 4 |
| **V0.8** | M4 (autonomous repair loop) | V1.2 surface lane public (governed surface authoring, Codex ImageGen backend); **paid hosted registry beta** launched; `std/` kits reach critical mass | Month 6 |
| **V1.0** | M5 (standalone compiler; first-party generation parity) | Standalone compiler GA; **CI certification SaaS** GA; studio references public (≥1 Persona-B studio case study); second backend stack (`soft_surface_prop_v1`) shipped | Month 9 |

## Engineering milestones (PRD, one-line each)

- **M1** — Reliable fallback compiler lane. Stable language, deterministic fallback generation, robust validation, packaging + trace.
- **M2** — Real local deterministic stages. Topology cleanup, real UV adapter, reliable local doctor/bootstrap.
- **M3** — First true learned lanes. Explicit reconstruction + generate providers; attempted-vs-actual tracing.
- **M4** — Autonomous repair loop. Repair planning, bounded iterative repair, certification-driven convergence.
- **M5** — Standalone compiler. First-party generation stack, fallback/learned parity, CI-friendly production readiness.

## GTM versions (detailed exit criteria)

### V0.1 (now) — Month 0

- [ ] Wave 0 Foundation: git init, LICENSE, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY stub, `v0.1.0` tag.
- [ ] Wave 1 additive scaffolding complete (CI, docs, DX, tests, vision).
- [x] Manifesto + PRD published internally.
- [x] Personas / ICP / JTBD drafted (this commit).
- Repo remains **private**. No remote push.

### V0.3 — Month 2 (alpha)

- [ ] `lathe-godot/` repo: GDScript addon auto-imports `.glb` + `manifest.json`, maps sockets → `Marker3D`, collision → `CollisionShape3D`, LODs → `MeshInstance3D.lod_bias`.
- [ ] 90-second `industrial_crate` demo screen-capture.
- [ ] 5-asset benchmark **draft** (fallback lane vs Meshy vs Hunyuan standalone vs Blender-by-hand), private.
- [ ] 3 design-partner LOIs **in flight** (outreach sent, ≥1 first-call booked).
- [ ] Wave 2 code surgery complete; contract hash `lathe.shape.intent_mesh_handoff_v1` unchanged.

### V0.5 — Month 4 (public OSS launch)

- [ ] Public repo on GitHub; `pip install lathe` works from PyPI.
- [ ] Godot AssetLib listing live.
- [ ] Benchmark study published (`docs/benchmarks/v0_5_five_asset_study.md`) with raw data.
- [ ] ≥3 design-partner LOIs **signed**.
- [ ] Discord open: `#announce`, `#show-your-asset`, `#builds-that-passed`, `#help`, `#rfc`.
- [ ] Persona-C channels: **Claude Code skill shipped** (Month 4 deliverable); Continue.dev + Cursor rules submitted.
- [ ] 10,000 unique visits to manifesto launch post; 2,000 GitHub stars (Month-6 target, tracked from V0.5).

*Solo-maintainer feasibility cut:* Month 4 scope is locked at {Godot addon ready, 3 LOIs signed, public OSS launch}. **CI-SaaS beta drops to Month 6+** to respect capacity. Do not re-add CI-SaaS to the V0.5 scope.

### V0.6 — Month 5 (side-bets + NeurIPS demo)

- [ ] **Roblox Studio spike** (2 weeks, evaluate `.lth → .rbxm` via Roblox Studio MCP). Output: go / no-go recommendation in `docs/integrations/roblox_spike.md`. Godot remains primary.
- [ ] **NeurIPS workshop tool-track demo** (tentative): submit or present the "Lathe as verification harness for generative-3D coding agents" demo. Contingent on workshop acceptance; track as aspirational until accepted.

### V0.8 — Month 6 (surface lane + monetization beta)

- [ ] V1.2 surface lane public: `surface_backend`, `surface_policy`, `decal_library`, `mask_program`, `trim_sheet` all documented and exercised by ≥1 hero.
- [ ] Codex ImageGen backend governed, with explicit fallback.
- [ ] **Paid hosted registry beta** opens — shared kits / libraries / materials from `std/`. This is the *primary* monetization path (Plan 09 Phase 8 inversion); lower activation energy than CI-SaaS, compounds with community seeding.
- [ ] CI-SaaS *not yet* sold. Validator thresholds (`semantic_preservation_quality`, `join_legality`, silhouette checks) must be stable before CI-SaaS is defensible.

### V1.0 — Month 9 (GA)

- [ ] Standalone Lathe compiler (M5): first-party generation parity with fallback lane on representative heroes.
- [ ] **CI certification SaaS GA** — now safe to sell; validator thresholds have soaked for 3+ months under registry usage.
- [ ] Second backend stack: `soft_surface_prop_v1`.
- [ ] ≥1 studio reference publicly citing Lathe in their pipeline.
- [ ] Benchmark re-run with V1.0 numbers; external review commissioned.

## Monetization order (explicit)

Per Plan 09 Phase 8 (inverted): **hosted registry FIRST (Month 6), CI-SaaS SECOND (V0.8+ post-validation-soak, targeting V1.0 GA at Month 9).** Rejected: paid Blender addon (fragments compiler story); studio support contracts (doesn't scale). See `docs/business/monetization.md` when authored.

## Persona-C GTM milestones (cross-reference)

Persona C is programmatic, not Discord-reachable. Milestones land on the same calendar as the GTM versions above:

- **Month 4 (V0.5):** Claude Code skill shipped to `~/.claude/skills/` + plugin directory.
- **Month 4–5 (V0.5–V0.6):** Continue.dev rules hub + Cursor rules hub submissions.
- **Month 5 (V0.6):** OpenHands / Devin tool directory listings; `agents.md` spec listing.
- **Month 6 (V0.8):** NeurIPS / ICLR workshop tool-track demo (tentative, contingent on acceptance).

Success metric for Persona-C GTM: ≥3 registries accept the package by Month 5; ≥1 agent-framework cookbook references `lathe build` as the certification step.
