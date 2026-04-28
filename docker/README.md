# Lathe container images

Two image variants plus a docker-compose harness.

## Variants

### `lathe:local` — slim runtime (`Dockerfile` at repo root)

- Base: `python:3.12-slim`
- Multi-stage: `uv sync --frozen --no-dev` in a builder stage, then the resolved
  `.venv` and the source trees (`lathe/`, `grammar/`, `schema/`, `std/`,
  `examples/`, `scripts/`) are copied into a clean final stage.
- Non-root user `lathe` (UID 1000).
- No Blender. No GPU. Entrypoint is `python -m lathe.cli`.
- Target image size: **< 400 MB**.

Build:

```bash
docker build -t lathe:local .
docker run --rm lathe:local doctor
docker run --rm -v "$PWD/dist:/app/dist" lathe:local build examples/courier_drone.lth courier_drone --out dist
```

### `lathe:blender` — Blender 4.5 LTS runtime (`docker/Dockerfile.blender`)

- `FROM lathe:local` — the slim image is a build prerequisite.
- Adds the pinned Blender 4.5 LTS tarball under `/opt/blender/`.
- Sets `LATHE_BLENDER_PATH=/opt/blender/blender` so topology + execution
  adapters find it automatically.
- `xatlas` is optional and currently commented out; uncomment the
  `pip install xatlas` line in the Dockerfile to enable.

Build (slim first, then Blender):

```bash
docker build -t lathe:local .
docker build -t lathe:blender -f docker/Dockerfile.blender .
docker run --rm lathe:blender doctor
```

Before publishing the Blender image, replace `BLENDER_SHA256` in
`docker/Dockerfile.blender` with the actual upstream hash from the
`SHA256SUMS` file alongside the tarball on
<https://download.blender.org/release/Blender4.5/>.

## GPU passthrough caveat

The Blender render/bake paths benefit from GPU acceleration, but passing
a GPU into the container requires either:

- Docker: `--gpus all` (requires `nvidia-container-toolkit`)
- Podman: `--device nvidia.com/gpu=all` (rootless, CDI-managed)

**This conflicts with `--network=none`.** Sandboxed runs that forbid
network access (the default for deterministic re-builds per Plan 07
Phase 4) cannot also use GPU. The CPU-only path is deterministic and
reproducible; the GPU path is faster but opts out of the network
sandbox. Pick one per run — we do not try to unify them.

## docker-compose profiles

`docker-compose.yml` at the repo root defines three services:

| Service | What it does |
|---|---|
| `lathe` | Slim image; mounts `examples/`, `std/` (read-only) and `dist/` (read-write). Use for `docker compose run --rm lathe build ...`. |
| `hunyuan-mock` | Local HTTP fixture matching the Hunyuan provider contract. Uses `tests/fixtures/mock_hunyuan.py` and exposes `/health` plus `/generate` on port 8080. |
| `blender-headless` | Blender image; runs `blender --background --version` as a smoke. |

Typical flows:

```bash
# Compile a hero asset inside the slim container.
docker compose run --rm lathe build examples/courier_drone.lth courier_drone --out dist

# Bring up the Hunyuan mock while developing provider-dependent code.
docker compose up -d hunyuan-mock

# Smoke-test the Blender image.
docker compose run --rm blender-headless
```
