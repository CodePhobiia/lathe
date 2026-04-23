"""Mock xatlas parametrization fixture.

Monkeypatches ``xatlas.parametrize`` (when the package is importable) with
a deterministic UV generator. Return shape matches xatlas' real output:

- ``vmapping``: ``uint32`` array, shape ``[N_verts_out]``
- ``indices``:  ``uint32`` array, shape ``[N_tris, 3]``
- ``uvs``:      ``float32`` array, shape ``[N_verts_out, 2]``

Seeded (via numpy) for reproducibility. If ``xatlas`` is not installed
the fixture is a no-op and still usable — tests that hit the fallback
path will exercise ``lathe.uv.*`` deterministic paths instead.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest


@dataclass
class MockXatlasAtlas:
    """Handle returned by the fixture; ``calls`` captures every invocation."""

    seed: int = 7
    calls: list[dict[str, Any]] = field(default_factory=list)

    def parametrize(
        self,
        positions: np.ndarray,
        indices: np.ndarray,
        normals: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self.calls.append(
            {
                "positions_shape": tuple(positions.shape),
                "indices_shape": tuple(indices.shape),
                "normals_shape": None if normals is None else tuple(normals.shape),
            }
        )
        rng = np.random.default_rng(self.seed + len(self.calls))
        n_verts = int(positions.shape[0])
        n_tris = int(indices.shape[0])
        vmapping = np.arange(n_verts, dtype=np.uint32)
        out_indices = indices.astype(np.uint32, copy=True).reshape(n_tris, 3)
        uvs = rng.random(size=(n_verts, 2), dtype=np.float32)
        return vmapping, out_indices, uvs


@pytest.fixture()
def mock_xatlas_atlas(monkeypatch: pytest.MonkeyPatch) -> MockXatlasAtlas:
    """Patch ``xatlas.parametrize`` when the module is importable.

    Returns the ``MockXatlasAtlas`` handle either way so tests may access
    ``.calls`` and ``.seed`` uniformly across environments.
    """
    atlas = MockXatlasAtlas()
    try:
        xatlas = importlib.import_module("xatlas")
    except ImportError:
        return atlas
    monkeypatch.setattr(xatlas, "parametrize", atlas.parametrize, raising=True)
    return atlas
