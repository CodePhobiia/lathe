# Houdini HDA + SideFX Labs — manual run instructions

_Status: stub. No Houdini runs have been executed in this study yet._

This is the non-AI procedural baseline: a senior TA authors an HDA (Houdini
Digital Asset) parameterized to match the `.lth` intent, and SideFX Labs tools
assemble panels / UV / collision. It represents "parametric authoring done
well" and is the hardest-to-beat row for architecture-family assets.

## Install

1. Houdini Indie / Core / FX (2020 or later). Indie license is the cheapest
   legal option for a commercial comparison — record license class in the
   `note` field.
2. Install SideFX Labs via the Houdini menu (free with any license).
3. Optionally: `Labs: Game Dev Tools` shelf for auto-UV and collision
   generation.

## Author the HDA per asset

The HDA is authored once per asset family and parameterized. For these 5:

| Asset | HDA approach |
|---|---|
| `industrial_crate` | Box base + panel seam boolean + bevel. Expose side count, panel depth, corner reinforcement as parameters. |
| `sci_fi_wall_panel` | Plane base + greeble SOP over procedural noise + trim sheet UVs via Labs. |
| `mechanical_door` | Frame (Box) + door (Box) + hinge pivot locator. Expose width / height / hinge side. |
| `control_pedestal` | Cone/frustum base + angled top plane + bevels. |
| `service_cabinet` | Box body + boolean door recess + vent slots via copy-to-points. |

Keep each HDA under 30 minutes of authoring for a fair comparison — this is
"procedural done competently," not "artist hand-polishes for hours."

## Export

1. Configure the HDA node with the 5-asset parameter values matching the
   `.lth` intent.
2. `ROP_FBX` or `ROP_GLTF` export → `.glb`.
3. Save the `.hipnc` scene to `docs/benchmarks/data/houdini_runs/<asset>.hip`
   for reproducibility.

## Ingest

Manual, as with other competitors. In the `note` field record:

- Houdini version + Labs version.
- Total authoring time (one-shot) **and** per-asset re-export time (the
  iteration-speed metric — this is where Houdini should shine).
- License class and annual cost.

## Known caveats

- Iteration speed is the reason Houdini is in this list. Record both the
  first-run authoring time and a follow-up iteration (e.g. "make the door 10%
  wider") in the study doc's iteration-speed column.
- `Labs Auto UV` produces valid UVs but not necessarily trim-sheet-aware;
  score `uv_valid: true` if charts pack, but note trim-sheet discipline in the
  study doc's commentary, not in the JSON.

## Licensing

Commercial. Indie license (~USD $269/year as of 2026 — re-check) is the entry
point. FX license is $4–5k/yr. Record the tier used.
