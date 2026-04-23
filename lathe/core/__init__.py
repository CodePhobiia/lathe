"""Executor core: helpers and per-stage step bodies for the build pipeline.

This subpackage was created in Stage 2.IV (Wave 2) to decompose
``lathe/executor.py`` from a 2,315-LOC god-module into per-stage step modules
plus a small set of shared helper modules. The public entry points
(``BuildError``, ``build_asset``, ``build_surface_stage``,
``validate_surface_stage``, ``repair_surface_stage``, ``BuildExecutor``,
``RuntimeMesh``, ``STAGE_ORDER``) still live in ``lathe.executor`` and are
re-exported unchanged. Everything in this package is implementation detail.
"""
