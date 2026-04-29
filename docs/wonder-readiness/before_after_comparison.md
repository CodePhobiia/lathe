# Wonder Before/After Comparison

Wave 3 makes visual iteration provable without requiring Blender, Roblox Studio, or an external viewer in core mode.

## Core Path

The core comparison path is deterministic and local:

1. Lock a camera from the Scene Graph.
2. Render before/after proxy PNGs with the existing scene proxy renderer.
3. Compare the PNGs pixel-for-pixel.
4. Write a Render Comparison report and link it into Scene History.

```powershell
python -m lathe.cli wonder lock-camera scene_graph.json --camera-id camera_reveal --out camera_lock.json
python -m lathe.cli wonder compare-renders --before before/render_reveal.png --after after/render_reveal.png --camera-lock camera_lock.json --out comparison.json
python -m lathe.cli wonder demo-before-after examples/wonder/alchemist_observatory --out .tmp_tests/wonder_before_after
```

The proxy path is non-blocking and suitable for CI because it only depends on committed JSON and local PNG generation.

## Camera Lock

Camera locks prevent false comparisons by pinning the camera used for before/after renders. A lock captures:

- `scene_id`
- `camera_id`
- projection/type
- target, framing, purpose
- transform, position, rotation, scale, and FOV when present
- `camera_hash`, a stable hash of the locked camera payload

If the requested camera does not exist, `wonder lock-camera` fails with a structured diagnostic instead of choosing another camera.

## Render Comparison

`wonder compare-renders` reads two PNGs and writes `lathe.render_comparison.v1`:

- `before_hash`
- `after_hash`
- dimensions
- changed pixel count
- changed pixel ratio
- camera lock status and hash when a lock is provided
- status

Dimension mismatches fail clearly. Pixel comparisons are deterministic and real, but target-level semantic visual evaluation is not implemented in Wave 3. Reports therefore emit:

```json
"semantic_delta": {
  "status": "not_evaluated",
  "reason": "Wave 3 proxy comparison measures deterministic pixel deltas only; target-level semantic visual evaluation is not implemented."
}
```

## Optional Lanes

Blender-backed visual comparison is optional/strict future work, not part of the core Wave 3 path. Missing Blender or Roblox runtimes must be reported as skipped optional lanes in core mode, not as failures.

The `demo-before-after` report records those skipped lanes explicitly so alpha evidence can distinguish local proof from deferred external runtime proof.
