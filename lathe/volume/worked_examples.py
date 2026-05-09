"""Worked examples for the volume module (roadmap §7.8).

Currently exposes ``billowing_smoke_cloud`` which builds a 64^3 volume,
seeds it with fractal density + temperature, runs 20 buoyancy steps,
10 diffusion steps, 5 advection steps, and extracts an isosurface mesh
at density threshold 0.3. The returned mapping carries both the Volume
(post-simulation) and the extracted mesh, so callers can either inspect
voxels directly or hand the mesh to the rest of the shape pipeline.

This is the worked example called out in the §7.8 task description --
"should produce a recognizable cloud-like form with characteristic
up-rising buoyant shape".
"""

from __future__ import annotations

from typing import Any

from .extract import extract_isosurface
from .volume import compile_volume, simulate_volume


def billowing_smoke_cloud(seed: int = 42) -> dict[str, Any]:
    """Run the canonical §7.8 smoke-cloud worked example.

    Returns ``{"volume": Volume, "mesh": dict, "summary": dict}``.
    """
    program = {
        "seed": seed,
        "resolution": (64, 64, 64),
        "bounds": (-2.0, -2.0, 0.0, 2.0, 2.0, 4.0),
        "density_noise": {
            "kind": "fractal",
            "octaves": 4,
            "scale": 0.5,
            "persistence": 0.55,
            "seed": seed,
        },
        "temperature_noise": {
            "kind": "fractal",
            "octaves": 2,
            "scale": 1.0,
            "persistence": 0.6,
            "seed": seed + 1,
        },
        "initial_velocity": (0.0, 0.0, 0.05),
    }

    volume = compile_volume(program)
    simulate_volume(
        volume,
        stages=[
            {"kind": "buoyancy", "buoyancy_coef": 0.5, "dt": 0.05, "steps": 20},
            {"kind": "diffusion", "rate": 0.1, "dt": 0.05, "steps": 10},
            {"kind": "advection", "dt": 0.05, "steps": 5},
        ],
    )
    mesh = extract_isosurface(volume, threshold=0.3)
    return {
        "volume": volume,
        "mesh": mesh,
        "summary": volume.summary(),
    }
