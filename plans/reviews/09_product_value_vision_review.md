# Review — Plan 09: Product Value & Vision (8/10 → 10/10)

## Summary

The plan is among the more coherent in this set. It names the right gap (external validation, not thesis), picks a defensible wedge (Godot), and sequences work through a realistic 6-month horizon. It is mostly faithful to `docs/lathe_manifesto.md` and `docs/lathe_prd.md`, though it overweights Persona A (Godot indie) relative to where the PRD actually leans, underinvests in the AI-agent persona (Persona C) that the manifesto treats as a peer user class, and specifies a CI-SaaS monetization motion without explaining how a 3-day-old codebase earns the right to sell CI before owning the free tier. KPIs are aggressive but not crazy. A 10/10 plan would tighten alignment with the PRD's non-goals, instrument "return build rate" concretely, and hedge the Godot bet with a cheap Persona-C GTM spike.

## Coverage of original findings

| Gap | Addressed? | Where |
|---|---|---|
| No public adoption | Partial | Phase 7 (community seeding) + Phase 10 (distribution). Acknowledges repo-private → V0.5 public. |
| No case studies / user stories | Yes | Phase 5: 3 day-in-the-life docs. Synthetic, not real — flagged below. |
| No published benchmark | Yes | Phase 4: 5-asset study with raw data; reviewer reproduction. |
| No wedge product / flagship integration | Yes | Phase 2: `lathe-godot` + 90-sec demo. |
| Ambiguous persona | Yes | Phase 1: 3 personas, Persona A named as wedge. |
| No retention story | Weak | Only KPI `return build rate ≥ 40%`. No product mechanic that *causes* return. |
| No monetization | Yes | Phase 8: CI-cert SaaS primary, hosted registry secondary. |
| No partnerships / distribution | Yes | Phase 9 (3 LOIs) + Phase 10 (PyPI/AssetLib/Extensions). |

Coverage is close to complete at the bullet level; depth varies.

## Alignment with existing PRD / manifesto

**Accurate:**
- "The build passed" framing (manifesto L69–71) is correctly treated as the thesis North Star.
- Scope discipline (hard-surface props, env modules, mechanical assemblies) matches `docs/lathe_prd.md` non-goals (L104–111: no DCC replacement, scene generator, gameplay lang, shader graph, prompt toy).
- Contract/certification emphasis lines up with PRD §5 validation-and-repair and manifesto's "A production asset is a verified artifact that satisfies a contract."
- Persona C (AI coding agent) derives directly from PRD Target Users L70 ("AI coding agents operating on game/content repositories") and JTBD L83–90.

**Misaligned / missed:**
- PRD L70–79 lists *primary users* as "technical artists, gameplay/content engineers, AI coding agents, small teams needing asset throughput" — the PRD does **not** privilege Godot indies. The plan's Persona-A wedge is a narrowing choice the plan makes, not one the PRD implies. That is fine, but the plan should say so explicitly instead of implying PRD support.
- PRD Milestones 1–5 (L370–400) are engineering milestones (fallback lane, local deterministic stages, learned lanes, repair loop, standalone). The plan's "V0.3/V0.5/V0.8/V1.0" roadmap co-opts similar version numbers but binds them to GTM events (addon alpha, OSS launch, hosted registry). This risks semantic drift between engineering and GTM versions and should be reconciled — either rename GTM milestones or explicitly cross-map to PRD M1–M5.
- Manifesto's "backend independence" / "AI as a stage, not the whole system" (L131, L144) is the strongest anti-competitor wedge against Meshy/Hunyuan/Luma. Phase 3's competitive table mentions it, but the marketing posts in Phase 11 do not lead with it. Post (2) "compiler problem" is closest; worth making the backend-independence point its own post.
- PRD §7 provenance requirements (L217–232) are a marketing asset the plan barely uses. "Reproducibility hash stability" appears in the benchmark but not in the content plan.

## Questionable picks

**Godot over Roblox/Unreal/Unity.** The Godot rationale (MIT, native glTF, OSS alignment) is defensible and matches the manifesto's OSS-core ethos. But the environment exposes a `roblox-studio` MCP server with mesh generation, Luau execution, and scene inspection — that is a much shorter path to a closed-loop demo than shipping a GDScript addon from scratch, and Roblox UGC has a paying economy Godot lacks. Switching to Roblox would change: (a) wedge persona (UGC creator, not indie tech artist), (b) export target (`.rbxm` via Studio, not `.glb` + `.tscn`), (c) monetization (attach to Marketplace fees rather than CI SaaS), (d) OSS-core story (Roblox is closed, dilutes the manifesto). Net: Godot is still correct as the *primary* wedge given the manifesto, but a 2-week Roblox spike using the MCP is cheap insurance and should be listed as a Phase-2 side-bet, not ignored.

**CI-cert SaaS as primary monetization.** Reasonable long-term, premature short-term. A 3-day-old private repo has no CI integrations, no studio customers with pipelines to gate, and no track record to sell trust. Hosted registry (option a) is a better *first* paid product — it monetizes kit/library reuse the moment `std/` hits critical mass, doesn't require customers to have CI at all, and aligns with the kit/library work already in V1.1. Plan rejects paid Blender addon correctly (fragments the compiler story, per manifesto L30–38). Keep (c) as the long-term bet but swap the order with (a).

**Synthetic case studies.** Phase 5 calls the 3 case studies "synthetic day-in-the-life." That is fine as placeholder content but must not be labeled as case studies externally — the original finding is specifically "no *real* user stories." Re-label as "worked examples" until a design partner signs and contributes a real one.

## Gaps

1. **Persona-C GTM is empty.** Persona C (AI coding agent) is named in Phase 1 and gets one case study, but no distribution channel. Coding agents don't join Discords. The channels are: (a) agent-framework docs (Claude Code, Cursor, Aider, Devin) via skill/plugin registration; (b) `pip install lathe` discoverability in agent tool catalogs; (c) a "Lathe for coding agents" cookbook post. None of these appear in Phases 7, 10, or 11.
2. **"Return build rate" measurement is unspecified.** The 40% KPI requires opt-in telemetry. Plan mentions `--share-cert` once but no telemetry design, privacy posture, or opt-in mechanism. For an OSS project this is load-bearing — botched telemetry kills OSS trust faster than missing features.
3. **No GDC/FOSDEM deliverable timeline.** Phase 11 names the talks but not submission deadlines. FOSDEM CFP closes ~October for Feb; GDC Experimental closes ~August. If Month 4 is launch, talk submissions need to be on the calendar in Phase 6 milestones.
4. **Manifesto post distribution.** 10,000-unique-visits KPI has no corresponding seed plan: HN/Lobsters/Reddit r/gamedev/Godot forums timing, co-posting with design partners, embargoed preview to press (80.lv, Game Developer). Phase 11 lists the posts but not the launch choreography.
5. **Dependencies on other plans.** Plan does not cross-reference: Maintenance plan (needs PyPI pipeline before Phase 10), Product Quality plan (hero demos must ship without fallback-lane caveats before Phase 2's demo-capture), Governance plan (LOI template needs legal review before Phase 9 outreach). Add a "Depends on" block.
6. **Failure modes for benchmark.** Phase 4 measures Lathe winning on contract/cert/provenance. It does not specify what Lathe is *allowed to lose on* — visual novelty at the pixel level is admitted in Phase 3, but the benchmark doc needs to pre-commit to that or it will read as cherry-picked.

## Feasibility

Six months for one maintainer is tight but not unrealistic *if* the plan trades scope. Realistic: personas/ICP (week), competitive doc (week), 5-asset benchmark (3–4 weeks with infra), roadmap/distribution docs (days each), content posts (2–3 weeks), Discord setup (days). Not realistic solo in this window: production-grade Godot addon (Phase 2) **and** CI-cert SaaS beta (Phase 8) **and** 3 signed LOIs (Phase 9) **and** V0.5 public launch (Phase 6). One of {Godot addon polish, CI-SaaS beta, LOI pursuit} must slip or get contractor help.

Hard dependencies on work outside this plan:
- PyPI publishing pipeline (Maintenance plan).
- Hero examples (`industrial_crate`, `mechanical_door`, `console_terminal`, `service_cabinet`, `control_pedestal`) must produce demo-worthy output on the fallback lane — current CLAUDE.md warns validators are strict and "don't weaken these without intent." Phase 2's 90-sec demo requires at least one hero to pass cleanly end-to-end *today*.
- Legal review of LOI template (not in any plan I have visibility into).

## 10/10 verdict

Not yet. Path to 10/10:

1. Reconcile roadmap versions with PRD Milestones 1–5 or rename GTM milestones (resolves semantic drift).
2. Add explicit Persona-C GTM (agent-framework registration, cookbook, tool-catalog discoverability).
3. Design telemetry/opt-in mechanism for `return build rate` and the certified-asset KPI — document privacy posture.
4. Add 2-week Roblox-MCP spike as a Phase-2 side-bet; commit to Godot as primary but don't ignore the available channel.
5. Swap monetization order: hosted registry first, CI-SaaS second; or justify current order against 3-day-old repo reality.
6. Relabel synthetic case studies as "worked examples" until real partner content exists.
7. Add "Depends on" block referencing Maintenance (PyPI), Product Quality (demo-ready heroes), Governance (LOI legal review).
8. Put GDC/FOSDEM CFP deadlines on Phase-6 calendar.
9. Add launch-choreography subsection to Phase 11 (HN/Lobsters/forum timing, press embargo).
10. Cut or resource one of {addon polish, CI-SaaS beta, LOI pursuit} — solo maintainer cannot land all three at quality.

With those, this is a 10/10. As written: **8.5/10** — an improvement over the starting 8, limited mostly by unexamined sequencing and missing Persona-C go-to-market.
