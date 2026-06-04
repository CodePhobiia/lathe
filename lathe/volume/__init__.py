"""Volume primitives for effects-class assets (smoke, fire, magic, fluids).

Roadmap §7.8. Sparse 3D grid abstraction with optional OpenVDB backend
and pure-numpy fallback. Scaffolding-grade simulators for advection,
buoyancy, and diffusion plus a marching-cubes isosurface extractor.

Public API:

    Volume                  -- sparse 3D grid container
    compile_volume          -- build Volume from a normalized volume_program decl
    simulate_volume         -- dispatch advection/buoyancy/diffusion stages
    extract_isosurface      -- marching cubes mesh from a density threshold
    simulate_advection      -- semi-Lagrangian density advection
    simulate_buoyancy       -- temperature-driven Boussinesq buoyancy
    simulate_diffusion      -- gaussian-blur-style density diffusion
    fractal_volume          -- volumetric Perlin sum noise
    worley_clusters         -- Worley sphere-cluster noise
    VDB_AVAILABLE           -- True if pyopenvdb is importable
    SKIMAGE_AVAILABLE       -- True if scikit-image marching_cubes is importable

Effects volumes are NOT a substitute for full GPU fluid solvers. They are
deterministic-with-seed numpy reference implementations designed to give
a coherent volumetric form (smoke cloud, magic wisp, ember plume) that
extract_isosurface can hand back as a mesh suitable for the rest of the
shape pipeline.
"""

from __future__ import annotations

from .advection import simulate_advection
from .buoyancy import simulate_buoyancy
from .diffusion import simulate_diffusion
from .extract import SKIMAGE_AVAILABLE, extract_isosurface
from .noise_field import fractal_volume, worley_clusters
from .vdb_backend import VDB_AVAILABLE
from .volume import Volume, compile_volume, simulate_volume

__all__ = [
    "SKIMAGE_AVAILABLE",
    "VDB_AVAILABLE",
    "Volume",
    "compile_volume",
    "extract_isosurface",
    "fractal_volume",
    "simulate_advection",
    "simulate_buoyancy",
    "simulate_diffusion",
    "simulate_volume",
    "worley_clusters",
]
