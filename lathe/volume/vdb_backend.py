"""Optional OpenVDB backend (pyopenvdb) for sparse volume IO.

If ``pyopenvdb`` is importable, ``VDB_AVAILABLE`` is True and the
helper functions in this module can write/read ``.vdb`` files for
interchange with Houdini, Blender (volume nodes), and DCC tools that
already speak OpenVDB. Otherwise these functions fall back to a numpy
``.npz`` archive that round-trips a Volume but is not interoperable
with non-Lathe tools.

Asset-level smoke / fire / magic volumes are typically dense at the
resolutions Lathe targets (<= 256^3); the OpenVDB integration here
exists primarily to plug into existing studio pipelines that key on
``.vdb`` as the canonical volume interchange format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

try:  # pragma: no cover - import-availability guard
    import pyopenvdb as _vdb  # type: ignore[import-not-found,import-untyped]

    VDB_AVAILABLE = True
except Exception:  # pragma: no cover - import-availability guard
    _vdb = None
    VDB_AVAILABLE = False


def write_volume(volume: Any, path: str | Path) -> dict[str, Any]:
    """Write a Volume to disk.

    Uses OpenVDB if available, else numpy ``.npz``. Returns a report
    mapping including the actual path written and the backend used.
    """
    p = Path(path)
    if VDB_AVAILABLE and _vdb is not None:
        return _write_vdb(volume, p.with_suffix(".vdb"))
    return _write_npz(volume, p.with_suffix(".npz"))


def read_volume(path: str | Path) -> dict[str, Any]:
    """Read a Volume back from disk; returns the kwargs needed to construct one."""
    p = Path(path)
    if p.suffix == ".vdb":
        if not VDB_AVAILABLE or _vdb is None:
            raise RuntimeError("pyopenvdb is not installed; cannot read .vdb files")
        return _read_vdb(p)
    return _read_npz(p)


def _write_vdb(volume: Any, path: Path) -> dict[str, Any]:  # pragma: no cover - optional dep
    grids = []
    density_grid = _vdb.FloatGrid()
    density_grid.copyFromArray(volume.density)
    density_grid.name = "density"
    grids.append(density_grid)
    if volume.temperature is not None:
        temp_grid = _vdb.FloatGrid()
        temp_grid.copyFromArray(volume.temperature)
        temp_grid.name = "temperature"
        grids.append(temp_grid)
    if volume.velocity is not None:
        vel_grid = _vdb.Vec3SGrid()
        vel_grid.copyFromArray(volume.velocity)
        vel_grid.name = "velocity"
        grids.append(vel_grid)
    _vdb.write(str(path), grids=grids)
    return {
        "backend": "pyopenvdb",
        "path": str(path),
        "grid_count": len(grids),
    }


def _write_npz(volume: Any, path: Path) -> dict[str, Any]:
    payload: dict[str, np.ndarray] = {
        "density": volume.density,
        "resolution": np.asarray(volume.resolution, dtype=np.int32),
        "bounds": np.asarray(volume.bounds, dtype=np.float32),
    }
    if volume.temperature is not None:
        payload["temperature"] = volume.temperature
    if volume.velocity is not None:
        payload["velocity"] = volume.velocity
    np.savez_compressed(path, **payload)
    return {
        "backend": "numpy_npz_fallback",
        "path": str(path),
        "grid_count": len(payload) - 2,
    }


def _read_vdb(path: Path) -> dict[str, Any]:  # pragma: no cover - optional dep
    grids = _vdb.readAllGridMetadata(str(path))
    payload: dict[str, Any] = {}
    for grid in grids:
        if grid.name == "density":
            arr = np.zeros(grid.evalActiveVoxelDim(), dtype=np.float32)
            grid.copyToArray(arr)
            payload["density"] = arr
        elif grid.name == "temperature":
            arr = np.zeros(grid.evalActiveVoxelDim(), dtype=np.float32)
            grid.copyToArray(arr)
            payload["temperature"] = arr
        elif grid.name == "velocity":
            arr = np.zeros((*grid.evalActiveVoxelDim(), 3), dtype=np.float32)
            grid.copyToArray(arr)
            payload["velocity"] = arr
    payload["backend"] = "pyopenvdb"
    return payload


def _read_npz(path: Path) -> dict[str, Any]:
    data = np.load(path, allow_pickle=False)
    payload: dict[str, Any] = {
        "density": data["density"],
        "resolution": tuple(int(v) for v in data["resolution"]),
        "bounds": tuple(float(v) for v in data["bounds"]),
    }
    if "temperature" in data.files:
        payload["temperature"] = data["temperature"]
    if "velocity" in data.files:
        payload["velocity"] = data["velocity"]
    payload["backend"] = "numpy_npz_fallback"
    return payload
