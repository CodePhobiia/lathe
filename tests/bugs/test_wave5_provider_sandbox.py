"""Wave 5 regression tests: provider/sandbox correctness.

Covers:

- M6  ``parser.imports._MAX_IMPORT_DEPTH`` boundary now matches the
      documented limit (no off-by-one).
- M8  ``scaffold_compiler._compile_scaffold_candidate`` preserves the
      original fuse_shape_ir failure under ``integration_report.attempted``
      when the manifold-CSG fallback succeeds.
- M9  ``sandbox.blender._close_windows_job_handles`` exists and is wired
      to atexit (smoke-tested without Windows).
- M10 ``asset_quality.vision_critique._safe_config_keys`` keeps legitimate
      keys that contain ``url``/``endpoint``/``token`` as substrings, and
      still drops actual credential names.
"""

from __future__ import annotations

import atexit
from pathlib import Path
from unittest.mock import patch

import pytest

from lathe.asset_quality.vision_critique import _safe_config_keys
from lathe.parser import LatheParseError, parse_file
from lathe.parser.imports import _MAX_IMPORT_DEPTH
from lathe.sandbox import blender as sandbox_blender


# --- M6 -------------------------------------------------------------


def test_parser_allows_import_chain_at_max_depth(tmp_path: Path) -> None:
    # Chain of length _MAX_IMPORT_DEPTH should parse cleanly.
    for index in range(_MAX_IMPORT_DEPTH):
        next_import = f"import m{index + 1}\n" if index < _MAX_IMPORT_DEPTH - 1 else ""
        (tmp_path / f"m{index}.lth").write_text(next_import, encoding="utf-8")
    parse_file(tmp_path / "m0.lth")  # must not raise


def test_parser_rejects_import_chain_above_max_depth(tmp_path: Path) -> None:
    # Chain of length _MAX_IMPORT_DEPTH + 1 must fail.
    for index in range(_MAX_IMPORT_DEPTH + 1):
        next_import = f"import m{index + 1}\n" if index < _MAX_IMPORT_DEPTH else ""
        (tmp_path / f"m{index}.lth").write_text(next_import, encoding="utf-8")
    with pytest.raises(LatheParseError, match="Import depth exceeded"):
        parse_file(tmp_path / "m0.lth")


# --- M8 -------------------------------------------------------------


def test_manifold_fallback_records_attempted_report() -> None:
    """When fuse_shape_ir fails and the manifold CSG path succeeds, the
    integration_report must preserve the original failure under ``attempted``.
    """
    import trimesh

    from lathe import scaffold_compiler
    from lathe.asset_graph import AssetGraph
    from lathe.fidelity import FidelityProfile
    from lathe.shape_ir import ShapeIR

    asset_graph = AssetGraph(
        name="demo",
        kind="prop",
        family="hard_surface",
        blueprint_id="demo_v1",
        role="prop",
        scale_cm=10.0,
        symmetry_axis=None,
        validation_threshold=0.8,
        critic_name=None,
        parts=[],
        joints=[],
        sockets=[],
        anchors=[],
        connections=[],
        connection_layout={},
        materials=[],
        styles=[],
        interactions=[],
        part_graph=[],
        semantic_requirements={},
        authoring={},
    )
    shape_ir = ShapeIR(
        asset_name="demo",
        family="hard_surface",
        blueprint_id="demo_v1",
        symmetry_axis=None,
        units="cm",
        primitives=[],
        regions=[],
        primitives_used=[],
        part_graph=[],
        signature={},
    )
    profile = FidelityProfile(
        tier="standard",
        detail_density=1.0,
        edge_weight=1.0,
        panel_depth=0.5,
        trim_complexity=2,
        support_complexity=0.6,
        silhouette_refinement=0.6,
        repair_budget=2,
    )
    failure_report = {
        "mode": "fuse_shape_ir",
        "ok": False,
        "reason": "no primitives provided",
    }
    fake_combined = trimesh.creation.box(extents=(1.0, 1.0, 1.0))

    with patch.object(
        scaffold_compiler,
        "fuse_shape_ir",
        return_value=(None, failure_report),
    ), patch.object(
        scaffold_compiler,
        "_fuse_via_manifold_kernel",
        return_value=(fake_combined, ["body"] * len(fake_combined.faces)),
    ):
        candidate = scaffold_compiler._runtime_from_shape_ir(
            asset_graph=asset_graph,
            shape_ir=shape_ir,
            candidate_index=0,
            conditioning={},
            mode="native",
            repairs_applied=[],
            fidelity_tier="standard",
            feature_report={},
            candidate_params={},
            fidelity_profile=profile,
            geometry_kernel_id="lathe.geometry.manifold_v1",
        )

    integration_report = candidate["meta"]["integration_report"]
    assert integration_report["mode"] == "manifold_csg"
    assert integration_report["attempted"] == {
        **failure_report,
        # geometry_kernel was set by setdefault before the manifold fallback.
        "geometry_kernel": "lathe.geometry.manifold_v1",
    }


# --- M9 -------------------------------------------------------------


def test_close_windows_job_handles_is_idempotent_on_posix() -> None:
    # On POSIX the cleanup function is a no-op, but it must not raise.
    sandbox_blender._WINDOWS_JOB_HANDLES.append(0)  # poison entry
    sandbox_blender._close_windows_job_handles()
    sandbox_blender._WINDOWS_JOB_HANDLES.clear()


def test_close_windows_job_handles_registered_with_atexit() -> None:
    callbacks = getattr(atexit, "_run_exitfuncs", None)
    assert callable(callbacks)
    assert callable(sandbox_blender._close_windows_job_handles)


# --- M10 ------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "endpoint_url",
        "endpoint",
        "url",
        "keypoints",
        "tokens_per_second",
        "service_url",
    ],
)
def test_safe_config_keys_keeps_legitimate_substring_collisions(key: str) -> None:
    config = {key: "value"}
    assert _safe_config_keys(config) == [key]


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "auth_token",
        "db_password",
        "aws_secret",
        "credential",
        "service.api_key",
    ],
)
def test_safe_config_keys_drops_credential_segments(key: str) -> None:
    config = {key: "value"}
    assert _safe_config_keys(config) == []
