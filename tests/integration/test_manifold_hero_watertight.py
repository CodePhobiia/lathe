"""Integration tests: Manifold kernel drives heroes to watertight_rate 1.0 (GEO-3)."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from lathe.asset_graph import build_asset_graph
from lathe.geometry.manifold_kernel import manifold_available
from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.scaffold_compiler import compile_scaffold_candidates


MANIFOLD_AVAILABLE = manifold_available()
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFOLD_RUNTIME = {"runtime": {"geometry": {"backend": "lathe.geometry.manifold_v1"}}}
REFERENCE_RUNTIME = {"runtime": {"geometry": {"backend": "lathe.geometry.reference_v1"}}}


def _load_asset_graph(hero: str):
    path = REPO_ROOT / "examples" / f"{hero}.lth"
    assert path.exists(), f"Hero source missing: {path}"
    program = parse_file(str(path))
    asset = materialize_asset(program, hero)
    return build_asset_graph(asset)


def _all_candidates_watertight(result: dict) -> tuple[bool, list[bool]]:
    flags = [bool(c["mesh"].is_watertight) for c in result["runtime_candidates"]]
    return (all(flags) and bool(flags), flags)


def _body_counts(result: dict) -> list[int]:
    counts = []
    for c in result["runtime_candidates"]:
        mesh = c["mesh"]
        try:
            counts.append(len(mesh.split(only_watertight=False)))
        except Exception:
            counts.append(-1)
    return counts


@pytest.mark.skipif(not MANIFOLD_AVAILABLE, reason="manifold3d is not installed")
def test_courier_drone_manifold_watertight_rate_is_one() -> None:
    asset_graph = _load_asset_graph("courier_drone")
    result = compile_scaffold_candidates(
        asset_graph,
        seed=42,
        candidates_count=1,
        conditioning={},
        mode="generate",
        runtime_config=MANIFOLD_RUNTIME,
    )
    ok, flags = _all_candidates_watertight(result)
    assert flags, "no candidates produced"
    assert ok, f"expected all candidates watertight under manifold, got flags={flags}"
    # Record the kernel used into the report so downstream consumers can trace it.
    assert result["report"]["geometry_kernel"] == "lathe.geometry.manifold_v1"


@pytest.mark.skipif(not MANIFOLD_AVAILABLE, reason="manifold3d is not installed")
def test_courier_drone_manifold_body_count_is_deterministic() -> None:
    asset_graph = _load_asset_graph("courier_drone")
    counts_across_rebuilds: list[list[int]] = []
    for _ in range(3):
        result = compile_scaffold_candidates(
            asset_graph,
            seed=42,
            candidates_count=1,
            conditioning={},
            mode="generate",
            runtime_config=MANIFOLD_RUNTIME,
        )
        counts_across_rebuilds.append(_body_counts(result))
    assert counts_across_rebuilds[0] == counts_across_rebuilds[1] == counts_across_rebuilds[2], (
        f"body counts drifted across rebuilds: {counts_across_rebuilds}"
    )


@pytest.mark.skipif(not MANIFOLD_AVAILABLE, reason="manifold3d is not installed")
def test_mechanical_door_manifold_watertight_and_not_slower_than_reference() -> None:
    asset_graph = _load_asset_graph("mechanical_door")

    t0 = time.perf_counter()
    ref_result = compile_scaffold_candidates(
        asset_graph,
        seed=42,
        candidates_count=1,
        conditioning={},
        mode="generate",
        runtime_config=REFERENCE_RUNTIME,
    )
    ref_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    mf_result = compile_scaffold_candidates(
        asset_graph,
        seed=42,
        candidates_count=1,
        conditioning={},
        mode="generate",
        runtime_config=MANIFOLD_RUNTIME,
    )
    mf_elapsed = time.perf_counter() - t0

    ok, flags = _all_candidates_watertight(mf_result)
    assert flags, "no candidates produced"
    assert ok, f"mechanical_door not watertight under manifold, flags={flags}"

    # Manifold must be no slower than 2x the reference path on a hero that
    # already succeeds under both. The GEO-1 bench measured ~100x faster;
    # we leave a wide margin so CPU noise on CI doesn't flake.
    assert mf_elapsed <= ref_elapsed * 2.0 + 0.25, (
        f"manifold {mf_elapsed:.3f}s slower than reference {ref_elapsed:.3f}s"
    )
