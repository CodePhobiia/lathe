# syntax=docker/dockerfile:1.7
# Lathe slim image — deterministic compile/runtime, no Blender, no GPU.
# Target size: < 400 MB. For Blender-backed execution, see
# docker/Dockerfile.blender.

# ------------------------------------------------------------------
# Stage 1: builder — resolves pinned deps into a prebuilt venv
# ------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1

# uv is pinned via its official image; copying the binary keeps the
# builder image free of network installs at image-build time.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Install deps first so source edits don't bust the dep layer cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------
# Stage 2: final — runtime-only image
# ------------------------------------------------------------------
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

# OCI image metadata.
LABEL org.opencontainers.image.source="https://github.com/lathe-lang/lathe" \
      org.opencontainers.image.title="lathe" \
      org.opencontainers.image.description="Declarative language + compiler for 3D asset intent" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="0.1.0"

# Non-root user. Matches the Dockerfile.blender extension expectation.
RUN groupadd --system --gid 1000 lathe \
 && useradd  --system --uid 1000 --gid lathe --create-home --shell /bin/bash lathe

WORKDIR /app

# Resolved venv from the builder.
COPY --from=builder --chown=lathe:lathe /app/.venv /app/.venv

# Only the source trees required to run the compiler. Tests, docs,
# scripts that manipulate the repo, and dev tooling stay out of the
# slim image.
COPY --chown=lathe:lathe lathe/    ./lathe/
COPY --chown=lathe:lathe grammar/  ./grammar/
COPY --chown=lathe:lathe schema/   ./schema/
COPY --chown=lathe:lathe std/      ./std/
COPY --chown=lathe:lathe examples/ ./examples/
COPY --chown=lathe:lathe scripts/  ./scripts/

USER lathe

ENTRYPOINT ["python", "-m", "lathe.cli"]
CMD ["--help"]
