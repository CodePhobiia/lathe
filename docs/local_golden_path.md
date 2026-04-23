# Local golden path

This is the shortest reliable path from a fresh checkout to a working local Lathe loop.

## 1. Fresh setup

PowerShell:

```powershell
scripts/bootstrap_local.ps1 -Dev -Export
```

Bash:

```bash
scripts/bootstrap_local.sh --dev --export
```

That creates `.venv`, installs the base editable repo, adds `pytest`, and installs the optional `export` toolchain.

## 2. Verify the machine

```powershell
.\.venv\Scripts\python.exe -m lathe.cli doctor
.\.venv\Scripts\python.exe -m lathe.cli doctor --json
```

Look for:

- `Lathe editable install: True`
- Blender availability
- whether xatlas is available or the UV backend is in explicit fallback mode
- whether Hunyuan or VGGT are actually reachable/importable

## 3. Build in fallback mode

Generate example:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli check examples/courier_drone.lth
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out dist_local
```

Reconstruct example:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli check examples/reconstruct_courier_from_views.lth
.\.venv\Scripts\python.exe -m lathe.cli build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out dist_local_reconstruct
```

These builds remain runnable even without Hunyuan, VGGT, or xatlas:

- shape falls back to `lathe.provider.shape.reference_conditioned_v1`
- topology may fall back from Blender to the reference cleanup path if Blender output fails the watertightness quality gate
- UV falls back to the reference box-atlas path when xatlas is unavailable

Inspect the stage and trace bundles to see the actual adapters/providers that ran.

Even if VGGT or Hunyuan dependencies are installed locally, the default no-runtime-config path remains conservative and uses the reference-conditioned provider unless you explicitly opt into learned routing with a runtime config.

## 4. Build with a real Hunyuan endpoint

First, make sure your Hunyuan HTTP server responds on the configured base URL:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli doctor --runtime-config examples/runtime_configs/hunyuan_http.json
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/courier_drone.lth courier_drone --out dist_hunyuan --runtime-config examples/runtime_configs/hunyuan_http.json
```

If the server is unreachable, Lathe will say so clearly. In non-strict mode it falls back explicitly; in strict mode it fails instead of pretending the real provider ran.

## 5. Build with VGGT if available

Install `torch` plus `torchvision`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[vggt]"
```

Install the official VGGT package from source:

```powershell
git clone https://github.com/facebookresearch/vggt.git external\vggt
.\.venv\Scripts\python.exe -m pip install -e .\external\vggt
```

Check the environment:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli doctor --runtime-config examples/runtime_configs/vggt_local.json
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m lathe.cli build examples/reconstruct_courier_from_views.lth reconstruct_courier_from_views --out dist_vggt --runtime-config examples/runtime_configs/vggt_local.json
```

If VGGT is unavailable, the trace will record that the attempted provider fell back to the reference-conditioned provider.

Convenience scripts:

```powershell
scripts/first_vggt_test.ps1
```

```bash
scripts/first_vggt_test.sh
```
