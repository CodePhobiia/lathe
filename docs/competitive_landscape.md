# Competitive Landscape

Single comparison against the tools a Persona-A artist realistically considers when producing a hard-surface game asset. Lathe is shown in **two lanes**: *fallback* (deterministic, no learned providers) and *learned* (runtime config enables Hunyuan / VGGT / Codex ImageGen under the stable `intent_mesh_handoff_v1` contract).

**Stated honestly up front.** Lathe **loses on visual novelty at the pixel level** against any text-to-3D tool whose whole product surface is "make this pretty." That is expected and not the wedge. Lathe **wins on contract, certification, and provenance** — the things a pretty mesh cannot deliver on its own.

| Axis | Lathe (fallback) | Lathe (learned) | Meshy | Hunyuan standalone | Luma | Houdini HDA + SideFX Labs | Quixel / Sketchfab | Blender + manual QA |
|---|---|---|---|---|---|---|---|---|
| Declarative source (text `.lth` / HDA) | yes | yes | no (prompt) | no (prompt + params) | no (prompt) | yes (HDA params) | no (asset library) | no (scene file) |
| Reproducibility hash-stable | yes | yes on fallback; attempted-vs-actual tracing on learned | no | no | no | yes within same Houdini version | N/A (fixed asset) | only by discipline |
| Certification gates (validators run, pass/fail verdict) | yes | yes | no | no | no | no (manual) | no | no (human review) |
| Topology guarantee (manifold, tri-budget respected) | yes | yes | no | no | no | depends on HDA author | varies per asset | yes, by hand |
| UV validity (atlas-packable, texel density respected) | yes | yes | no | no | no | depends on HDA author | varies per asset | yes, by hand |
| Collision / pivot / LOD metadata | yes | yes | no | no | no | if the HDA was built for it | rarely; engine-dependent | yes, by hand |
| Engine import lossless (Godot `.glb` + manifest) | yes | yes | partial (`.glb` only; no pivots/collision) | partial | partial | via Houdini Engine plugin | varies | yes, by hand |
| Provenance (who / when / why / which providers ran) | yes (full trace) | yes (attempted-vs-actual recorded) | no | no | no | partial (Houdini log) | license metadata only | git history only |
| Licensing clarity for output | clear (your source, your output) | clear (your source, provider terms recorded) | per-plan terms | provider-bound | per-plan terms | clear | varies per asset | clear |
| Cost per asset | $0 | $0–few cents per learned call | per-credit | per-token | per-credit | one-time HDA license | per-asset fee or sub | artist hours |
| Iteration speed (re-run after intent tweak) | seconds | seconds–minutes | re-prompt (minutes) | re-prompt (minutes) | re-prompt (minutes) | fast within Houdini | N/A (swap asset) | hours |
| Visual novelty at pixel level | low | medium | high | high | high | medium | medium (curated) | artist-dependent |

## Read

Lathe is the only row that ships a *certification verdict* the artist or an agent can parse. Meshy / Hunyuan / Luma are the strongest at raw visual generation and the weakest at "will this survive import to Godot." Houdini HDAs are the closest philosophical neighbor — declarative, parametric, reproducible — but require a Houdini seat, an HDA author upstream of the artist, and per-HDA discipline to even approach Lathe's validator coverage. Quixel/Sketchfab solve a different problem (find an asset someone already made) and are complementary, not competitive. Blender + manual QA is the honest baseline — it works, it just costs the artist a day per variant.

## Where Lathe does not compete (and should not pretend to)

- **Concept-art-to-hero-mesh pixel quality.** Text-to-3D will out-pretty us for a solo statue or a stylized creature. That is fine; the wedge is crates and panels, not statues.
- **Asset-store breadth.** Quixel has tens of thousands of scanned assets. We have `std/` kits and a compiler. Different product.
- **Full DCC replacement.** Blender remains the execution substrate. Lathe is a language on top, not a replacement below.
