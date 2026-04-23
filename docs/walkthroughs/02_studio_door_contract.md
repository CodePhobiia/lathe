# 02 — Studio Door Contract: Certification Blocks a Bad PR

> **Synthetic scenario — not a real user story.** This is a narrative walkthrough; replace with a real case study when a design partner signs.

## Persona and stakes

Chen is the pipeline TD at a 24-person studio shipping a cyberpunk action-RPG on Godot 4.3. The game has **47 door variants** across 6 biomes. Every door must: be 2m tall ± 5cm, have a single handle socket at door-left at 1.0m height, carry lightmap UVs at texel density ≥ 320 px/m, and import to Godot with correct hinge pivot.

Historically this was enforced in a Notion page and by Chen's own code review. Junior artist Priya just joined; she models door #48 and opens a PR. Chen is out sick.

## The contract (`std/components/door_contract_v2.lth`)

```lathe
contract studio_door_v2 {
  ensure scale.height_m        between 1.95 and 2.05
  ensure sockets.contains("handle") where handle.x_offset_m = -0.45 and handle.y_offset_m = 1.0
  ensure uv.texel_density      >= 320
  ensure uv.lightmap           = true
  ensure topology.manifold     = true
  ensure collision.pivot.at    = "door.hinge_l"
  ensure package.format        in ["glb"]
}

profile door_v2: hard_surface_prop uses studio_door_v2 {
  intent.parts    = [frame, leaf, handle, hinge_l, hinge_r]
  fit.texel_density = 320
  fit.lightmap_uv   = true
  fit.collision     = convex_hull
}
```

This file lives in the studio's shared `std/` repo, versioned. A change to the contract is a PR, not a Slack message.

## Priya's asset PR (`assets/doors/biome_6_bulkhead.lth`)

```lathe
asset biome_6_bulkhead: door_v2 {
  intent {
    role = "reinforced bulkhead door, biome 6 (reactor deck)"
    style = ["industrial", "reinforced", "hazard_yellow"]
    scale = 2.00m
    materials = ["steel_reinforced", "hazard_stripe"]
  }

  fit.texel_density = 256   # <-- Priya overrode the contract default; she thought it was optional
}
```

Priya pushes. GitHub Actions runs `lathe check` and `lathe build` against the PR.

## Failing validator report (mocked)

```
$ python -m lathe.cli build assets/doors/biome_6_bulkhead.lth biome_6_bulkhead --out dist/
[lathe]  source:       assets/doors/biome_6_bulkhead.lth  (sha256:2b1d…a78c)
[lathe]  stack:        lathe.stack.hard_surface_game_asset_v1
...
  stage intent      OK    role=reinforced bulkhead door, style=industrial/reinforced
  stage shape       OK    fallback; 1 candidate
  stage topology    OK    manifold=true, tris=3840
  stage uv          OK    atlas packed; texel_density measured = 261 px/m
  stage surface     OK
  stage optimize    OK    LOD0=3840  LOD1=1920
  stage validate    FAIL
                    contract: studio_door_v2
                    rule:     uv.texel_density >= 320
                    actual:   261
                    source:   biome_6_bulkhead.lth:10   (fit.texel_density = 256)
                    suggestion: raise `fit.texel_density` to >= 320 (contract minimum),
                                or split surface into 2 atlases so measured density >= 320.

[lathe]  certified:    FAIL
[lathe]  exit:         2
```

CI marks the PR red. The failure names the **rule**, the **measured value**, the **offending line**, and a **concrete suggestion**. Priya does not need Chen to decode a stack trace.

## The one-line fix

```diff
  fit {
-   fit.texel_density = 256
+   fit.texel_density = 320
  }
```

Priya pushes the fix. CI re-runs:

```
  stage uv          OK    atlas packed; texel_density measured = 326 px/m
  stage validate    PASS  studio_door_v2 (7/7 ensures)
[lathe]  certified:    PASS
```

Merge unblocks. Priya learned the contract in the way the contract was designed to teach it — by a red CI run on her own PR, not by Chen's third Slack message that week.

## What this walkthrough validates (and what it doesn't)

**Validates.** The Persona-B JTBD: "encode studio asset contract as source, gate CI on certification." The contract is versioned, the enforcement is machine-readable, and a junior artist is taught by the tool rather than by the TD's bandwidth. Onboarding cost shifts from "weeks of tribal knowledge" to "one failed PR."

**Does not validate.** That every studio has an asset contract worth formalizing (some do not). That Godot is always the target (it is for the wedge, V0.3–V0.5). That `lathe check` catches every kind of asset bug (it catches what validators and contracts are written for — which is why `docs/benchmarks/v0_5_five_asset_study.md` matters).
