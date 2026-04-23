"""Shared pytest fixtures for the Lathe test suite.

Mocks for external services (Hunyuan, VGGT, Blender, xatlas, Codex ImageGen)
and sample-program factories live here. Individual fixture modules register
plugins via the `tests/conftest.py` plugin list when needed.
"""
