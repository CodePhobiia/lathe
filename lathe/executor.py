"""Build executor: orchestrates every stage in ``STAGE_ORDER``.

Stage 2.IV (Wave 2) decomposed this module from a 2,315-LOC god-class into
a thin dispatcher that delegates per-stage step bodies to ``lathe.core.stages.*``.
The public surface — ``BuildError``, ``build_asset``, ``build_surface_stage``,
``validate_surface_stage``, ``repair_surface_stage``, ``BuildExecutor``,
``RuntimeMesh``, ``STAGE_ORDER`` — is preserved unchanged. Implementation
helpers (``_run_reference_topology_cleanup``) are also re-exported from the
extracted ``lathe.core.geometry`` module to keep existing imports working.

Do NOT change the stable contract ``lathe.shape.intent_mesh_handoff_v1``
emitted by the shape stage. See ``lathe/shape/`` for the contract bytes.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .capabilities import probe_topology_backend  # noqa: F401 — re-export for test mocking
from .checker import check_program
from .core.common import dump_json, hash_obj, relpath
from .core.errors import BuildError
from .core.geometry import (
    run_reference_topology_cleanup as _run_reference_topology_cleanup,
)
from .core.mesh import RuntimeMesh
from .core.stages import (
    execution as stage_execution,
    interfaces as stage_interfaces,
    optimize as stage_optimize,
    package as stage_package,
    physics as stage_physics,
    rig as stage_rig,
    shape as stage_shape,
    surface as stage_surface,
    topology as stage_topology,
    uv as stage_uv,
    validate as stage_validate,
)
from .core.stages.topology import run_blender_topology as _run_blender_topology  # noqa: F401
from .normalizer import normalize_program
from .planner import build_plan
from .resolver import Resolver
from .runtime_config import merge_runtime_config
from .validators.surface_quality import evaluate_surface_quality


STAGE_ORDER = [
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
]


BUILD_CACHE_ROOT = Path(tempfile.gettempdir()) / "lathe_build_cache"
BUILD_CACHE_VERSION = "v10_rc2"


__all__ = [
    "BuildError",
    "BuildExecutor",
    "RuntimeMesh",
    "STAGE_ORDER",
    "build_asset",
    "build_surface_stage",
    "repair_surface_stage",
    "validate_surface_stage",
    "_run_reference_topology_cleanup",
]


class BuildExecutor:
    def __init__(
        self,
        program: dict[str, Any],
        asset_name: str,
        out_dir: str | Path,
        runtime_config: dict[str, Any] | None = None,
        execution_profile_override: str | None = None,
    ) -> None:
        self.program = program
        self.asset_name = asset_name
        self.out_dir = Path(out_dir)
        source_path = program.get("_source_path")
        self.source_root = Path(source_path).resolve().parent if source_path else Path.cwd()
        self.resolver = Resolver(program)
        self.asset = self.resolver.materialize_asset(asset_name, execution_profile_override=execution_profile_override)
        self.plan = build_plan(program, asset_name, execution_profile_override=execution_profile_override)
        self.backend_stack = self.plan["backend_stack"]
        self.selected_backends = self.plan["selected_backends"]
        self.normalized_program = normalize_program(program)
        self.normalized_asset_path = self.out_dir / "normalized_program.json"
        self.runtime_config = merge_runtime_config(runtime_config, None)
        self.runtime: dict[str, Any] = {
            "shape": {},
            "topology": {},
            "uv": {},
            "surface": {},
            "execution": {},
            "rig": {},
            "interfaces": {},
            "physics": {},
            "optimize": {},
            "validate": {},
            "package": {},
        }
        self.critics = {critic["name"]: critic for critic in program.get("critics", [])}
        self.stage_dirs = {stage: self.out_dir / "stages" / stage for stage in STAGE_ORDER}
        self.cache_key = hash_obj(
            {
                "cache_version": BUILD_CACHE_VERSION,
                "program": self.normalized_program,
                "asset": self.asset_name,
                "runtime_config": self.runtime_config,
            }
        )
        self.cache_dir = BUILD_CACHE_ROOT / self.cache_key

    def build(self) -> dict[str, Any]:
        diagnostics = check_program(self.program)
        errors = [item for item in diagnostics if item["severity"] == "error"]
        if errors:
            raise BuildError("Build blocked by semantic errors", diagnostics=diagnostics)

        cached = self._restore_cached_build()
        if cached is not None:
            return cached

        self._prepare_dirs()
        dump_json(self.normalized_asset_path, self.normalized_program)
        dump_json(self.out_dir / "plan.json", self.plan)
        dump_json(self.out_dir / "materialized_asset.json", self.asset)

        shape_bundle = stage_shape.run(self)
        topology_bundle = stage_topology.run(self, shape_bundle)
        uv_bundle = stage_uv.run(self, topology_bundle)
        surface_bundle = stage_surface.run(self, uv_bundle)
        rig_bundle = stage_rig.run(self, surface_bundle)
        interfaces_bundle = stage_interfaces.run(self, rig_bundle)
        physics_bundle = stage_physics.run(self, interfaces_bundle)
        optimize_bundle = stage_optimize.run(self, physics_bundle)
        execution_bundle = stage_execution.run(self, optimize_bundle)
        validate_bundle = stage_validate.run(self, optimize_bundle)
        if not validate_bundle["certified"]:
            repaired = self._attempt_surface_repair(validate_bundle, topology_bundle, uv_bundle)
            if repaired is not None:
                surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = repaired
                execution_bundle = stage_execution.run(self, optimize_bundle)
        if not validate_bundle["certified"]:
            reselection = self._attempt_reselect_candidates()
            if reselection is not None:
                topology_bundle, uv_bundle, surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = reselection
                execution_bundle = stage_execution.run(self, optimize_bundle)
                if not validate_bundle["certified"]:
                    repaired = self._attempt_surface_repair(validate_bundle, topology_bundle, uv_bundle)
                    if repaired is not None:
                        surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = repaired
                        execution_bundle = stage_execution.run(self, optimize_bundle)
        if not validate_bundle["certified"]:
            raise BuildError("Validation failed", diagnostics=validate_bundle["diagnostics"])
        package_bundle = stage_package.run(self, optimize_bundle, validate_bundle)

        report = {
            "asset": self.asset_name,
            "kind": self.asset["kind"],
            "out_dir": str(self.out_dir),
            "certified": True,
            "backend_stack": self.backend_stack,
            "selected_backends": self.selected_backends,
            "runtime_config": self.runtime_config,
            "stage_bundles": {
                "shape": relpath(self.out_dir, self.stage_dirs["shape"] / "bundle.json"),
                "topology": relpath(self.out_dir, self.stage_dirs["topology"] / "bundle.json"),
                "uv": relpath(self.out_dir, self.stage_dirs["uv"] / "bundle.json"),
                "surface": relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
                "execution": relpath(self.out_dir, self.stage_dirs["execution"] / "bundle.json"),
                "rig": relpath(self.out_dir, self.stage_dirs["rig"] / "bundle.json"),
                "interfaces": relpath(self.out_dir, self.stage_dirs["interfaces"] / "bundle.json"),
                "physics": relpath(self.out_dir, self.stage_dirs["physics"] / "bundle.json"),
                "optimize": relpath(self.out_dir, self.stage_dirs["optimize"] / "bundle.json"),
                "validate": relpath(self.out_dir, self.stage_dirs["validate"] / "report.json"),
                "package": relpath(self.out_dir, self.stage_dirs["package"] / "bundle.json"),
            },
            "outputs": package_bundle["outputs"],
            "manifest_path": package_bundle["manifest_path"],
            "trace_path": package_bundle.get("trace_path"),
            "score": validate_bundle["score"],
            "threshold": validate_bundle["threshold"],
        }
        dump_json(self.out_dir / "build_report.json", report)
        self._persist_build_cache()
        return report

    def _prepare_dirs(self) -> None:
        for stage_dir in self.stage_dirs.values():
            stage_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_uncached_build(self) -> None:
        diagnostics = check_program(self.program)
        errors = [item for item in diagnostics if item["severity"] == "error"]
        if errors:
            raise BuildError("Build blocked by semantic errors", diagnostics=diagnostics)
        self._prepare_dirs()
        dump_json(self.normalized_asset_path, self.normalized_program)
        dump_json(self.out_dir / "plan.json", self.plan)
        dump_json(self.out_dir / "materialized_asset.json", self.asset)

    def build_surface_stage(self, *, repair_mode: str | None = None) -> dict[str, Any]:
        self._prepare_uncached_build()
        shape_bundle = stage_shape.run(self)
        topology_bundle = stage_topology.run(self, shape_bundle)
        uv_bundle = stage_uv.run(self, topology_bundle)
        surface_bundle = stage_surface.run(self, uv_bundle, repair_mode=repair_mode)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "surface_bundle_path": relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            "surface_bundle": surface_bundle,
            "stage_bundles": {
                "shape": relpath(self.out_dir, self.stage_dirs["shape"] / "bundle.json"),
                "topology": relpath(self.out_dir, self.stage_dirs["topology"] / "bundle.json"),
                "uv": relpath(self.out_dir, self.stage_dirs["uv"] / "bundle.json"),
                "surface": relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            },
        }

    def validate_surface_stage(self) -> dict[str, Any]:
        surface_result = self.build_surface_stage()
        report = evaluate_surface_quality(self.asset, self.runtime)
        dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": report["ok"],
            "surface_bundle_path": surface_result["surface_bundle_path"],
            "surface_quality_report_path": relpath(self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"),
            "surface_validation_ir": self.runtime["surface"]["bundle"].get("surface_validation_ir", {}),
            "metrics": report["metrics"],
            "diagnostics": report["diagnostics"],
        }

    def repair_surface_stage(self) -> dict[str, Any]:
        initial = self.validate_surface_stage()
        if initial["ok"]:
            return {**initial, "repaired": False, "repair_reason": "surface_already_valid"}
        repaired_bundle = stage_surface.run(self, self.runtime["uv"]["bundle"], repair_mode="surface_enhance_v1")
        repaired_report = evaluate_surface_quality(self.asset, self.runtime)
        dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", repaired_report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": repaired_report["ok"],
            "repaired": True,
            "repair_reason": "surface_enhance_v1",
            "surface_bundle_path": relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            "surface_quality_report_path": relpath(self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"),
            "surface_repair_ir": repaired_bundle.get("surface_repair_ir", {}),
            "before": {"ok": initial["ok"], "metrics": initial["metrics"], "diagnostics": initial["diagnostics"]},
            "after": {"ok": repaired_report["ok"], "metrics": repaired_report["metrics"], "diagnostics": repaired_report["diagnostics"]},
        }

    def _restore_cached_build(self) -> dict[str, Any] | None:
        if not self.cache_dir.exists():
            return None
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        self.out_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.cache_dir, self.out_dir)
        report_path = self.out_dir / "build_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["out_dir"] = str(self.out_dir)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report
        return None

    def _persist_build_cache(self) -> None:
        try:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
            self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.out_dir, self.cache_dir)
        except Exception:  # noqa: BLE001
            pass

    def _select_shape_candidate(self, candidate_id: str, reason: str) -> None:
        stage_shape.select_candidate(self, candidate_id, reason)

    def _attempt_reselect_candidates(self) -> tuple[dict[str, Any], ...] | None:
        repair_cfg = self.asset.get("validate", {}).get("repair", {})
        allowed = set(repair_cfg.get("allow", []))
        if "reselect_candidate" not in allowed:
            return None
        bundle = self.runtime["shape"]["bundle"]
        current_id = bundle.get("selected_candidate_id")
        ordered_candidates = sorted(
            bundle.get("candidates", []),
            key=lambda item: (-float(item.get("score", 0.0)), item.get("candidate_id", "")),
        )
        last_result: tuple[dict[str, Any], ...] | None = None
        for candidate in ordered_candidates:
            candidate_id = candidate.get("candidate_id")
            if candidate_id == current_id:
                continue
            self._select_shape_candidate(candidate_id, "reselected_after_validation_failure")
            topology_bundle = stage_topology.run(self, self.runtime["shape"]["bundle"])
            uv_bundle = stage_uv.run(self, topology_bundle)
            surface_bundle = stage_surface.run(self, uv_bundle)
            rig_bundle = stage_rig.run(self, surface_bundle)
            interfaces_bundle = stage_interfaces.run(self, rig_bundle)
            physics_bundle = stage_physics.run(self, interfaces_bundle)
            optimize_bundle = stage_optimize.run(self, physics_bundle)
            validate_bundle = stage_validate.run(self, optimize_bundle)
            last_result = (
                topology_bundle,
                uv_bundle,
                surface_bundle,
                rig_bundle,
                interfaces_bundle,
                physics_bundle,
                optimize_bundle,
                validate_bundle,
            )
            if validate_bundle["certified"]:
                return last_result
        return last_result

    def _attempt_surface_repair(
        self,
        validate_bundle: dict[str, Any],
        topology_bundle: dict[str, Any],
        uv_bundle: dict[str, Any],
    ) -> tuple[dict[str, Any], ...] | None:
        allowed = set(self.asset.get("validate", {}).get("repair", {}).get("allow", []))
        if "reauthor_surface_layer" not in allowed:
            return None
        diagnostic_names = {item.get("name") for item in validate_bundle.get("diagnostics", [])}
        if "visual_surface_authoring_quality_failed" not in diagnostic_names:
            return None
        surface_bundle = stage_surface.run(self, uv_bundle, repair_mode="surface_enhance_v1")
        rig_bundle = stage_rig.run(self, surface_bundle)
        interfaces_bundle = stage_interfaces.run(self, rig_bundle)
        physics_bundle = stage_physics.run(self, interfaces_bundle)
        optimize_bundle = stage_optimize.run(self, physics_bundle)
        repaired_validate = stage_validate.run(self, optimize_bundle)
        attempts = self.runtime["shape"].setdefault("reselection_attempts", [])
        attempts.append({
            "candidate_id": self.runtime["shape"]["bundle"].get("selected_candidate_id"),
            "reason": "surface_reauthor_repair",
            "score": repaired_validate.get("score"),
        })
        return surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, repaired_validate

    def _resolved_profile_names(self) -> list[str]:
        names = []
        for decl in self.resolver.resolve_use_chain(self.asset.get("uses", [])):
            if decl.get("node_type") == "profile":
                names.append(decl["name"])
        return names


def build_asset(
    program: dict[str, Any],
    asset_name: str,
    out_dir: str | Path,
    runtime_config: dict[str, Any] | None = None,
    execution_profile_override: str | None = None,
) -> dict[str, Any]:
    return BuildExecutor(
        program,
        asset_name,
        out_dir,
        runtime_config=runtime_config,
        execution_profile_override=execution_profile_override,
    ).build()


def build_surface_stage(program: dict[str, Any], asset_name: str, out_dir: str | Path, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).build_surface_stage()


def validate_surface_stage(program: dict[str, Any], asset_name: str, out_dir: str | Path, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).validate_surface_stage()


def repair_surface_stage(program: dict[str, Any], asset_name: str, out_dir: str | Path, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).repair_surface_stage()
