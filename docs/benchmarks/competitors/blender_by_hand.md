# Blender (by hand) — manual run instructions

_Status: stub. No Blender-by-hand runs have been executed in this study yet._

This row measures a skilled-human ceiling: a senior 3D artist models each
asset from scratch in Blender, aiming for a game-ready hard-surface result
that matches the `.lth` intent. It is the reference all generators secretly
aspire to.

## Who runs this

A named operator — record the operator's name and approximate hard-surface
experience in the `note` field. Two operators running the same asset will
produce wildly different tri counts, so the identity matters.

## Time budget

Give each asset a **30-minute** wall-clock budget per the fair-comparison
rule. An artist who spends 2 hours polishing `service_cabinet` is not
comparable to a Meshy 3-minute generation. 30 minutes is enough for a
competent hard-surface block-in with UVs and a single PBR material assignment.

Record the actual time spent in `wall_clock_s`. If the operator exceeded
budget, flag it in `note` and do not re-grade to match the generators.

## Method per asset

| Asset | Suggested approach |
|---|---|
| `industrial_crate` | Cube → extrude corners → bevel edges → inset panel faces → material assign. |
| `sci_fi_wall_panel` | Plane → subdivide → inset panels → boolean greeble → trim-sheet UVs. |
| `mechanical_door` | Cube door + cube frame + empty as hinge pivot → parent. |
| `control_pedestal` | Frustum → top bevel → angled control face boolean. |
| `service_cabinet` | Cube body → boolean door recess → extrude vents → door as child. |

Use Blender 4.x (LTS preferred). Record the version.

## Export

`.glb` via Blender's built-in glTF 2.0 exporter, with:

- Selected objects or full scene, operator's choice — document it.
- Apply modifiers on export: yes.
- UV, normals, materials: yes.
- Compress: off (so the `.glb` byte count is comparable to Lathe's uncompressed
  output).

## Ingest

Same manual flow as other competitors. Add to `note`:

- Blender version.
- Operator name + experience level.
- Actual authoring time.
- Whether a collision proxy was hand-authored (usually no — record honestly).
- Whether a pivot was placed explicitly (usually yes for `mechanical_door`,
  rarely for others).

## Licensing

Blender is free (GPL). The operator's labor is not — cost is
`operator_hourly_rate × wall_clock_s / 3600`. Record assumed hourly rate in
`note` for parity with paid SaaS rows.

## Why this row matters

If Lathe-fallback or Lathe-learned beats the Blender-by-hand column on tri
count, Godot-import cleanliness, or iteration speed, that's a meaningful
claim. If it loses across the board, the study says so honestly and points at
which metrics the gap lives in.
