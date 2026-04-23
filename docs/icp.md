# Ideal Customer Profile (Wedge)

The ICP below is specifically for **Persona A** — the wedge. ICPs for Personas B and C follow after the wedge is validated (Month 4+).

## Firmographic

- Engine: **Godot 4.x** (4.2+). Not Unity, not Unreal. Godot's MIT license + native `.glb` import + open editor make it the lowest-friction target for V0.3 → V0.5.
- Team size: **1–10 developers**. Solo indies count; anything over ~10 trends toward Persona B territory.
- Genre fit: **hard-surface-heavy**. Factory / sci-fi / dungeon / stylized-industrial / cyberpunk-lite. Anything where crates, panels, doors, consoles, pedestals, and cabinets are first-class set dressing.
- Funding stage: bootstrapped, solo-funded, or small publisher deal. No AAA budgets; time is the scarce resource.

## Workflow signals

- Already has a **Blender** pipeline. DCC switching cost is zero for Lathe because Blender is the execution substrate we adopt, not replace.
- Ships on a **milestone cadence** (every 2–6 weeks), not a continuous-deployment one. Asset debt accumulates between milestones.
- Has felt **manual QA pain**: at least one shipped bug traced to a broken pivot, wrong collision, or bad UV density.
- Uses **git** for source and `.glb`/`.tres`/`.tscn` for asset delivery. No Perforce dependency.

## Anti-ICP (explicit non-targets)

- **AAA studios.** Too entrenched; their pipelines, naming, and validation already encode a contract they would not swap out for a V0.x tool. Revisit at V1.0+.
- **Organic-asset shops.** Characters, creatures, foliage, cloth. Out of scope for V0.x; Lathe's validators and backends are tuned for hard-surface geometry. Revisit with `soft_surface_prop_v1` stack (Plan 08 Phase 4).
- **Web / mobile / AR shops.** `.usdz` export and AR-kit pivots are not a V0.x priority; `.glb` + Godot is. Revisit post-V1.0.
- **Unity/Unreal-only shops.** Possible future fit, but not wedge. Each engine adapter is a real cost and dilutes the Godot-first demo.

## Why this ICP is tight (and stays tight)

A narrow wedge is how a 3-day-old repo earns its first believable users. A Godot hard-surface indie who ships a certified crate on her first `lathe build` is worth ten curious AAA TDs who "might evaluate next quarter." When the Godot slice works and the 5-asset benchmark (`docs/benchmarks/v0_5_five_asset_study.md`, Month 3) is published, we widen — not before.
