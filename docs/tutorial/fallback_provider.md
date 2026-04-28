# Fallback Provider Workflow

**Time:** about 10 minutes. **Prerequisite:** [Quickstart](../quickstart.md).

This tutorial proves the default local path: build a certified asset without
Hunyuan, VGGT, Blender, or xatlas being required on the critical path.

## 1. Check the source

```bash
python -m lathe.cli check examples/courier_drone.lth
```

The checker validates the public language surface before any stage writes
artifacts.

## 2. Build with default providers

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist_fallback
```

This build uses the deterministic reference-conditioned shape provider unless a
runtime config explicitly opts into learned routing. Topology and UV adapters
also record whether a real adapter or fallback path ran.

## 3. Read the evidence

Open these files:

- `dist_fallback/courier_drone/build_report.json`
- `dist_fallback/courier_drone/stages/package/package_manifest.json`
- `dist_fallback/courier_drone/stages/package/trace_manifest.json`
- `dist_fallback/courier_drone/stages/validate/report.json`

Look for provider fields that name the attempted provider, the actual provider,
and any degraded state. The fallback path is acceptable only when it says what
really happened.

## 4. Confirm package output

The package stage should include `.glb`, `.usda`, engine manifests, and preview
media under `stages/package/previews/`. If certification fails, start with
`stages/validate/report.json`; the report should name the rule, expected value,
actual value, and artifact to inspect.
