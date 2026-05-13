"""Wave 6 regression test: build wall-clock budget (C4).

The marquee courier_drone build was hanging silently past 15 minutes.
This test verifies that the executor now turns "silent hang" into a
structured ``BuildError`` with a ``stage_timeout`` diagnostic when a
single stage's wall-clock pushes the cumulative budget past the
configured cap.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from lathe import executor
from lathe.errors import BuildError


def test_build_emits_stage_timeout_when_budget_exceeded(tmp_path) -> None:
    """A stage that takes longer than the budget triggers BuildError with
    a ``stage_timeout`` diagnostic naming the offending stage.
    """
    # Build a stub BuildExecutor that skips _restore_cached_build / _prepare_dirs
    # / per-stage work and instead exercises the timeout path directly.
    inst = executor.BuildExecutor.__new__(executor.BuildExecutor)
    inst.program = {}
    inst.asset_name = "demo"
    inst.out_dir = tmp_path
    inst.cache_dir = tmp_path / "_cache"
    inst.cache_key = "demo"
    inst.normalized_asset_path = tmp_path / "normalized_program.json"
    inst.normalized_program = {}
    inst.plan = {}
    inst.asset = {"kind": "prop"}
    inst.runtime_config = {"execution": {"timeout_s": 0.05}}
    inst.runtime = {}
    inst.stage_dirs = {}
    inst.selected_backends = {}
    inst.backend_stack = "stack"
    inst.critics = {}

    def slow_stage_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(0.1)
        return {}

    with patch.object(executor, "check_program", return_value=[]), patch.object(
        executor.BuildExecutor, "_restore_cached_build", return_value=None
    ), patch.object(executor.BuildExecutor, "_prepare_dirs"), patch.object(
        executor.BuildExecutor, "_publish_pre_shape_quality_context"
    ), patch.object(executor, "dump_json"), patch.object(
        executor.stage_shape, "run", side_effect=slow_stage_run
    ):
        with pytest.raises(BuildError) as exc_info:
            inst.build()

    assert "wall-clock budget exceeded" in str(exc_info.value)
    diagnostics = exc_info.value.diagnostics
    assert any(diag.get("code") == "stage_timeout" for diag in diagnostics)
    assert any(diag.get("phase") == "shape" for diag in diagnostics)
