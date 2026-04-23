# Jobs To Be Done

The JTBD frame pulls the product back from features ("we ship LOD generation") to outcomes ("the artist trusts the asset in-engine"). Functional, emotional, and social jobs are listed for Persona A (wedge). Secondary JTBDs for Personas B and C follow.

---

## Persona A — Indie Godot tech artist (WEDGE)

### Functional job

> Produce a certified hard-surface game asset in under 10 minutes.

"Certified" means the asset passes Lathe's validator gates: manifold topology within tri-budget, UV atlas valid with declared texel density, collision present and matching the declared pivot, LODs derived to spec, Godot-importable `.glb` with manifest. "Under 10 minutes" is wall-clock from `.lth` edit to `.tscn` drop.

### Emotional job

> Trust that the asset won't break downstream.

The artist has been burned by silent breakage: a pivot that looks right in Blender but lands at the origin in Godot; a UV that previews fine but fails lightmap bake; a collision that imports but is inside-out. She wants to hit build, see a green certification, and move on. "The build passed" is not branding — it is a felt thing: tension released.

### Social job

> Be known as the artist who ships reproducibly.

In a small studio, reputation compounds. The artist who can deterministically reproduce any asset she shipped 6 months ago — same bytes, same manifest, same provenance — is trusted with the next hard problem. Lathe's reproducibility story makes "I shipped this and I can prove it" a personal brand asset, not just a CI feature.

---

## Persona B — Pipeline TD at 10–50-person studio (secondary)

### Functional job

> Encode studio asset contract as source, gate CI on certification.

Contract lives in versioned `.lth` files; CI runs `lathe build` on every art PR; failures block merge with named-rule errors the artist can act on. Contract changes are PRs, not Slack decrees.

---

## Persona C — AI coding agent operating a game repo (secondary)

### Functional job

> Turn an `.lth` diff into a trusted machine-readable pass/fail signal.

Agent edits `.lth`, runs `lathe build`, parses the exit code and structured trace, decides whether to open a PR. No human in the loop for the verdict itself. The agent does not need to interpret a mesh — it needs to interpret a contract result.
