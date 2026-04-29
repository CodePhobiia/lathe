from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import lathe.scene

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENE_PACKAGE = Path(lathe.scene.__file__).parent

SCENE_MODULE_TEST_OWNERS = {
    "__init__": {"test_scene_module_coverage.py"},
    "artifacts": {"test_scene_executor.py", "test_wonder_examples_catalog.py"},
    "assembly": {"test_scene_assembly.py"},
    "bench": {"test_scene_bench.py"},
    "blender_export": {"test_scene_blender_export.py"},
    "camera_lighting": {"test_scene_style_layout.py", "test_scene_cli.py"},
    "camera_lock": {"test_scene_camera_lock.py", "test_wonder_before_after_cli.py"},
    "compare": {"test_scene_compare.py", "test_wonder_before_after_cli.py"},
    "curiosity": {"test_scene_curiosity.py"},
    "diagnostics": {"test_scene_validators.py", "test_wonder_scene_validation.py"},
    "environment": {"test_scene_environment_modules.py"},
    "executor": {"test_scene_executor.py"},
    "game_readiness": {"test_scene_game_readiness_provenance.py"},
    "graph": {"test_wonder_contracts.py", "test_wonder_scene_validation.py"},
    "history": {"test_scene_history.py"},
    "ids": {"test_scene_ids.py"},
    "io": {"test_scene_io.py"},
    "layout": {"test_scene_style_layout.py"},
    "materialize": {"test_scene_materialize.py", "test_scene_executor.py"},
    "memory": {"test_wonder_memory.py", "test_scene_cli.py"},
    "package": {"test_scene_package_manifest.py", "test_scene_cli.py"},
    "patch": {"test_scene_patch.py"},
    "planner": {"test_scene_planner.py"},
    "provenance": {"test_scene_game_readiness_provenance.py"},
    "repair": {"test_scene_repair.py"},
    "roblox": {"test_scene_roblox.py"},
    "rollback": {"test_scene_rollback.py"},
    "source": {"test_scene_source_roundtrip.py"},
    "source_diagnostics": {"test_scene_source_diagnostics.py", "test_wonder_llm.py"},
    "stdlib": {"test_scene_stdlib.py"},
    "style": {"test_scene_style_layout.py"},
    "versioning": {"test_scene_versioning.py"},
}


def _scene_modules() -> set[str]:
    module_names = {"__init__"}
    module_names.update(module.name for module in pkgutil.iter_modules([str(SCENE_PACKAGE)]) if not module.ispkg)
    return module_names


def test_every_scene_module_has_test_owner() -> None:
    modules = _scene_modules()

    assert set(SCENE_MODULE_TEST_OWNERS) == modules
    for module_name, owners in SCENE_MODULE_TEST_OWNERS.items():
        for owner in owners:
            assert (REPO_ROOT / "tests" / "unit" / owner).is_file(), f"{module_name}: missing {owner}"


def test_every_scene_module_imports_cleanly() -> None:
    for module_name in sorted(_scene_modules() - {"__init__"}):
        module = importlib.import_module(f"lathe.scene.{module_name}")

        assert module.__name__ == f"lathe.scene.{module_name}"
