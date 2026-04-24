"""Unit tests for the ``lathe.shape_backend`` shim and the
``lathe.shape.backend`` module it re-exports.

The shim is the four-line back-compat module created in ADR-0005 (the
shape backend was relocated to the ``lathe.shape`` subpackage).  These
tests pin two contracts: that the shim's exported names are the same
objects as the canonical ones, and that ``run_shape_backend``'s contract
ID gate plus provider-normalization branch behave as advertised — these
are the entry-point invariants other stages rely on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import lathe.shape as shape_pkg
import lathe.shape_backend as shim
from lathe import shape_backend as shim_mod
from lathe.shape import backend as canonical


def _minimal_asset() -> dict[str, Any]:
    return {
        "name": "tiny_widget",
        "kind": "hard_surface_prop",
        "intent": {
            "role": "widget",
            "parts": ["body"],
            "scale": {"type": "unit", "value": 10, "unit": "cm"},
            "materials": ["aluminum"],
        },
        "build": {"shape": {"mode": "generate"}},
        "assembly": {"resolved_components": []},
    }


class TestShimReexports:
    def test_shim_exports_run_shape_backend(self) -> None:
        from lathe.shape_backend import collect_shape_conditioning, run_shape_backend  # noqa: F401

    def test_shim_run_is_canonical_run(self) -> None:
        assert shim.run_shape_backend is canonical.run_shape_backend

    def test_shim_collect_is_canonical_collect(self) -> None:
        assert shim.collect_shape_conditioning is canonical.collect_shape_conditioning

    def test_shape_package_reexports_match_shim(self) -> None:
        # The shape package should also expose the canonical name.
        assert shape_pkg.run_shape_backend is canonical.run_shape_backend

    def test_shim_module_all_is_minimal(self) -> None:
        assert set(shim_mod.__all__) == {"run_shape_backend", "collect_shape_conditioning"}


class TestRunShapeBackend:
    def test_unknown_backend_id_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported runnable shape backend"):
            shim.run_shape_backend(
                "lathe.shape.does_not_exist",
                _minimal_asset(),
                source_root=tmp_path,
                seed=0,
                candidates_count=1,
                conditioning={},
                work_dir=tmp_path,
                runtime_config=None,
            )

    def test_literal_string_provider_none_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid shape_cfg.provider"):
            shim.run_shape_backend(
                "lathe.shape.intent_mesh_handoff_v1",
                _minimal_asset(),
                source_root=tmp_path,
                seed=0,
                candidates_count=1,
                conditioning={},
                work_dir=tmp_path,
                runtime_config={"shape": {"provider": "None"}},
            )

    def test_literal_string_provider_null_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid shape_cfg.provider"):
            shim.run_shape_backend(
                "lathe.shape.intent_mesh_handoff_v1",
                _minimal_asset(),
                source_root=tmp_path,
                seed=0,
                candidates_count=1,
                conditioning={},
                work_dir=tmp_path,
                runtime_config={"shape": {"provider": "null"}},
            )

    def test_provider_normalization_accepts_none_empty_auto(self, tmp_path: Path) -> None:
        # Patch downstream collaborators so we can isolate the
        # provider-string normalization branch without running compilers.
        with (
            patch("lathe.shape.backend.build_asset_graph", return_value=object()),
            patch(
                "lathe.shape.backend.compile_scaffold_candidates",
                return_value={
                    "asset_graph": type("AG", (), {"to_dict": lambda self: {}})(),
                    "report": {"shape_irs": [], "blueprint_id": "bp", "primitives_used": [], "shape_assessment": {}},
                    "shape_irs": [],
                },
            ),
            patch(
                "lathe.shape.backend.maybe_run_shape_provider",
                return_value={"provider_report": {"selected_provider_id": "x"}, "runtime_candidates": []},
            ),
            patch(
                "lathe.shape.backend.fit_provider_proposals",
                return_value={"runtime_candidates": [], "report": {}},
            ),
        ):
            for value in (None, "", "auto"):
                # asset_graph stub has no .authoring attribute — patch it in
                with patch(
                    "lathe.shape.backend.build_asset_graph",
                    return_value=type("AG", (), {"authoring": {}})(),
                ):
                    out = shim.run_shape_backend(
                        "lathe.shape.intent_mesh_handoff_v1",
                        _minimal_asset(),
                        source_root=tmp_path,
                        seed=0,
                        candidates_count=1,
                        conditioning={},
                        work_dir=tmp_path,
                        runtime_config={"shape": {"provider": value}},
                    )
                assert "provider_report" in out
