# Quickstart

Three commands take a fresh checkout to a verified local build loop.

## 1. Bootstrap

From the repository root, create `.venv` and install Lathe editable with the
normal contributor extras:

=== "PowerShell"

    ```powershell
    scripts/bootstrap_local.ps1 -Dev -Export
    ```

=== "bash"

    ```bash
    scripts/bootstrap_local.sh --dev --export
    ```

The bootstrap command upgrades pip tooling, installs the base package plus the
selected extras, then runs `lathe doctor`. The expected interpreter after
bootstrap is `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` on
macOS/Linux. See [Local golden path](local_golden_path.md) for the longer
first-run story.

## 2. Run the smoke command

=== "PowerShell"

    ```powershell
    scripts/lathe_smoke.ps1
    ```

=== "bash"

    ```bash
    bash scripts/lathe_smoke.sh
    ```

The smoke command uses the repo `.venv` when present. It runs `doctor`, checks
and plans `examples/courier_drone.lth`, runs a small explicit pytest smoke
partition, and builds `courier_drone` into `tmp_lathe_smoke/`.

For a narrated demo script suitable for walkthroughs:

=== "PowerShell"

    ```powershell
    scripts/demo_core_workflow.ps1
    ```

=== "bash"

    ```bash
    bash scripts/demo_core_workflow.sh
    ```

Add `-DryRun` or `--dry-run` to preview the commands without creating build
artifacts. By default, the demo writes detailed command output under
`tmp_lathe_demo/_demo_workflow/` and keeps the terminal walkthrough concise; add
`-VerboseOutput` or `--verbose-output` when you want the full command output on
screen.

Useful overrides:

```powershell
scripts/lathe_smoke.ps1 -Python .\.venv\Scripts\python.exe -OutDir tmp_my_smoke
```

```bash
PYTHON_BIN=./.venv/bin/python bash scripts/lathe_smoke.sh
LATHE_SMOKE_OUT=tmp_my_smoke bash scripts/lathe_smoke.sh
```

## 3. Build your first asset

Build the reference `courier_drone` asset into `dist/`:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
```

The compiler runs the full stage pipeline (`refs -> intent -> shape -> topology
-> uv -> surface -> rig -> interfaces -> physics -> optimize -> validate ->
package`) and writes a certified package:

```text
dist/
|-- courier_drone/
    |-- build_report.json
    |-- courier_drone.lathe_for_godot.json
    |-- courier_drone.lathe_for_unity.yaml
    |-- courier_drone.lathe_for_unreal.json
    |-- materialized_asset.json
    |-- normalized_program.json
    |-- plan.json
    |-- selector_manifest.json
    |-- stages/
        |-- shape/bundle.json
        |-- topology/bundle.json
        |-- uv/bundle.json
        |-- surface/bundle.json
        |-- rig/bundle.json
        |-- interfaces/bundle.json
        |-- physics/bundle.json
        |-- optimize/
            |-- bundle.json
            |-- budget_report.json
            |-- lod_manifest.json
            |-- collision_manifest.json
        |-- validate/report.json
        |-- package/
            |-- bundle.json
            |-- courier_drone.usda
            |-- courier_drone.glb
            |-- package_manifest.json
            |-- trace_manifest.json
            |-- previews/
                |-- turntable.png
                |-- wireframe.png
                |-- uv_layout.png
                |-- lod_sheet.png
```

The exact files depend on which adapters were available. `build_report.json`
points at the package manifest and trace paths, while
`stages/package/trace_manifest.json` is the authoritative record of what ran.
The documented preview media set is
`stages/package/previews/turntable.png`,
`stages/package/previews/wireframe.png`,
`stages/package/previews/uv_layout.png`, and
`stages/package/previews/lod_sheet.png`.
The `dist/` name is only a convention; ignored output roots include `dist/`,
`dist_*`, `tmp_*`, and `warm_*`.

By default `--out` is constrained to the repository safety root. Set
`LATHE_ALLOW_EXTERNAL_OUT=1` only for trusted local or CI runs that intentionally
write outside the repository.

## Optional extras

| Extra | Use it when | Notes |
| --- | --- | --- |
| `dev` | running tests, lint, type checks, or pre-commit | Included by `-Dev` / `--dev`. |
| `docs` | building docs locally | Install with `pip install -e ".[docs]"`. |
| `export` | using fuller mesh/export helpers | Included by `-Export` / `--export`. |
| `geometry` | testing optional geometry kernels | Installs heavier geometry packages. |
| `hunyuan_http` | routing to a real Hunyuan HTTP server | No Python package; configure the server in runtime config. |
| `vggt` | trying the VGGT reconstruction provider | Installs torch/torchvision; the official `vggt` package is a manual source install. |
| `xatlas` | using real xatlas UV unwrapping | Windows usually needs Visual Studio Build Tools with Desktop C++. |
| `publish` | exercising publish drivers | Adds cryptography and boto3. |

## Windows path behavior

- PowerShell: `.\.venv\Scripts\python.exe -m lathe.cli doctor`
- Git Bash on Windows: `./.venv/Scripts/python.exe -m lathe.cli doctor`
- macOS/Linux: `./.venv/bin/python -m lathe.cli doctor`
- Quote extras in PowerShell, for example `".[dev,export]"`.

## Shell completions

Lathe can emit static completion scripts for the installed `lathe` command:

```text
lathe completions bash > ~/.local/share/bash-completion/completions/lathe
lathe completions zsh > "${fpath[1]}/_lathe"
lathe completions powershell | Out-String | Invoke-Expression
```

## Troubleshooting

| Symptom | Likely cause | Next step |
| --- | --- | --- |
| `python` creates no `.venv` or points at the wrong version | Python 3.11+ is not first on PATH | Pass a Python 3.11+ executable path with `-Python C:\Path\To\python.exe`, or set `PYTHON_BIN` for the bash script. |
| `xatlas` install fails on Windows | Native C++ build tools are missing | Install Visual Studio Build Tools with the Desktop C++ workload, then rerun bootstrap with `-XAtlas`. |
| `doctor` says Blender is unavailable | Blender is not installed or not on PATH | Install Blender or continue in fallback mode; topology records the fallback in the trace. |
| Hunyuan or VGGT is unavailable | Runtime config points at a missing server/package | Run `doctor --runtime-config ...` and verify the server, package install, and allowlist. |
| Build writes outside the repo are rejected | Output path safety guard | Use an ignored in-repo output root, or set `LATHE_ALLOW_EXTERNAL_OUT=1` only for trusted runs. |
| Cache status looks stale | Old generated artifacts or cache metadata | Run `python -m lathe.cli cache migrate --dry-run`, then `cache migrate` or clean only the affected asset/cache root. |
| Permission denied while writing artifacts | Output root is read-only or held open | Choose a fresh ignored root such as `tmp_my_build` and close viewers holding generated files. |

## What just happened

- `examples/courier_drone.lth` declared what the asset is, how to build it,
  and what counts as passing.
- The compiler normalized, resolved, checked, planned, executed, validated,
  and packaged the result.
- Because you did not pass `--runtime-config`, the shape stage used the
  deterministic `lathe.provider.shape.reference_conditioned_v1` provider.
  Topology/UV fell back to reference paths if Blender or xatlas were
  unavailable.

## Next

- [Author your first `.lth` asset](tutorial/first_asset.md) - about 15 minutes,
  builds a bookshelf from scratch.
- [Reconstruct from reference views](tutorial/second_asset_reconstruct.md) -
  about 20 minutes, compares `generate` vs `reconstruct` flows.
- [Deep dive reading order](tutorial/deep_dive.md) - map of specs and manifests
  in the order that builds mental model fastest.
- [Local golden path](local_golden_path.md) - same loop with real Hunyuan / VGGT
  runtime configs.
