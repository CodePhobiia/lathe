from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from collections import Counter

import numpy as np
import trimesh
from PIL import Image, ImageDraw

from .assembly_ir import AssemblyIR
from .capabilities import probe_blender, probe_topology_backend, probe_uv_backend
from .backends import resolve_selected_backends
from .checker import check_program
from .feature_ir import FeatureIR
from .fit_ir import FitIR
from .kit_ir import KitIR
from .normalizer import normalize_program
from .planner import build_plan
from .repair_policy import RepairPolicyIR
from .reference_ir import ReferenceIR
from .resolver import Resolver
from .shape_backend import collect_shape_conditioning as _shape_collect_conditioning, run_shape_backend as _shape_run_backend
from .surface_ir import SurfaceIR
from .surface_runtime import build_surface_bundle
from .topology_runtime import derive_topology_semantics, should_preserve_integrated_shape
from .transfer_ir import TransferIR
from .runtime_config import merge_runtime_config
from .blender_execution import build_execution_bundle
from .uv_runtime import derive_uv_semantics
from .validators.semantic_quality import evaluate_semantic_quality
from .validators.flow_quality import evaluate_flow_quality
from .validators.surface_quality import evaluate_surface_quality
from .validators.visual_quality import evaluate_visual_quality


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

IMAGE_SIZE = 1024
PREVIEW_BG = (248, 248, 250, 255)
LINE_COLOR = (24, 28, 33, 255)
IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BUILD_CACHE_ROOT = Path(tempfile.gettempdir()) / "lathe_build_cache"
BUILD_CACHE_VERSION = "v10_rc2"


class BuildError(Exception):
    def __init__(self, message: str, diagnostics: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or []


@dataclass
class RuntimeMesh:
    mesh: trimesh.Trimesh
    face_parts: list[str]
    part_colors: dict[str, tuple[int, int, int]]
    units: str = "cm"


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
        self.cache_key = _hash_obj(
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
        _dump_json(self.normalized_asset_path, self.normalized_program)
        _dump_json(self.out_dir / "plan.json", self.plan)
        _dump_json(self.out_dir / "materialized_asset.json", self.asset)

        shape_bundle = self._run_shape()
        topology_bundle = self._run_topology(shape_bundle)
        uv_bundle = self._run_uv(topology_bundle)
        surface_bundle = self._run_surface(uv_bundle)
        rig_bundle = self._run_rig(surface_bundle)
        interfaces_bundle = self._run_interfaces(rig_bundle)
        physics_bundle = self._run_physics(interfaces_bundle)
        optimize_bundle = self._run_optimize(physics_bundle)
        execution_bundle = self._run_execution(optimize_bundle)
        validate_bundle = self._run_validate(optimize_bundle)
        if not validate_bundle["certified"]:
            repaired = self._attempt_surface_repair(validate_bundle, topology_bundle, uv_bundle)
            if repaired is not None:
                surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = repaired
                execution_bundle = self._run_execution(optimize_bundle)
        if not validate_bundle["certified"]:
            reselection = self._attempt_reselect_candidates()
            if reselection is not None:
                topology_bundle, uv_bundle, surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = reselection
                execution_bundle = self._run_execution(optimize_bundle)
                if not validate_bundle["certified"]:
                    repaired = self._attempt_surface_repair(validate_bundle, topology_bundle, uv_bundle)
                    if repaired is not None:
                        surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, validate_bundle = repaired
                        execution_bundle = self._run_execution(optimize_bundle)
        if not validate_bundle["certified"]:
            raise BuildError("Validation failed", diagnostics=validate_bundle["diagnostics"])
        package_bundle = self._run_package(optimize_bundle, validate_bundle)

        report = {
            "asset": self.asset_name,
            "kind": self.asset["kind"],
            "out_dir": str(self.out_dir),
            "certified": True,
            "backend_stack": self.backend_stack,
            "selected_backends": self.selected_backends,
            "runtime_config": self.runtime_config,
            "stage_bundles": {
                "shape": _relpath(self.out_dir, self.stage_dirs["shape"] / "bundle.json"),
                "topology": _relpath(self.out_dir, self.stage_dirs["topology"] / "bundle.json"),
                "uv": _relpath(self.out_dir, self.stage_dirs["uv"] / "bundle.json"),
                "surface": _relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
                "execution": _relpath(self.out_dir, self.stage_dirs["execution"] / "bundle.json"),
                "rig": _relpath(self.out_dir, self.stage_dirs["rig"] / "bundle.json"),
                "interfaces": _relpath(self.out_dir, self.stage_dirs["interfaces"] / "bundle.json"),
                "physics": _relpath(self.out_dir, self.stage_dirs["physics"] / "bundle.json"),
                "optimize": _relpath(self.out_dir, self.stage_dirs["optimize"] / "bundle.json"),
                "validate": _relpath(self.out_dir, self.stage_dirs["validate"] / "report.json"),
                "package": _relpath(self.out_dir, self.stage_dirs["package"] / "bundle.json"),
            },
            "outputs": package_bundle["outputs"],
            "manifest_path": package_bundle["manifest_path"],
            "trace_path": package_bundle.get("trace_path"),
            "score": validate_bundle["score"],
            "threshold": validate_bundle["threshold"],
        }
        _dump_json(self.out_dir / "build_report.json", report)
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
        _dump_json(self.normalized_asset_path, self.normalized_program)
        _dump_json(self.out_dir / "plan.json", self.plan)
        _dump_json(self.out_dir / "materialized_asset.json", self.asset)

    def build_surface_stage(self, *, repair_mode: str | None = None) -> dict[str, Any]:
        self._prepare_uncached_build()
        shape_bundle = self._run_shape()
        topology_bundle = self._run_topology(shape_bundle)
        uv_bundle = self._run_uv(topology_bundle)
        surface_bundle = self._run_surface(uv_bundle, repair_mode=repair_mode)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "surface_bundle_path": _relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            "surface_bundle": surface_bundle,
            "stage_bundles": {
                "shape": _relpath(self.out_dir, self.stage_dirs["shape"] / "bundle.json"),
                "topology": _relpath(self.out_dir, self.stage_dirs["topology"] / "bundle.json"),
                "uv": _relpath(self.out_dir, self.stage_dirs["uv"] / "bundle.json"),
                "surface": _relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            },
        }

    def validate_surface_stage(self) -> dict[str, Any]:
        surface_result = self.build_surface_stage()
        report = evaluate_surface_quality(self.asset, self.runtime)
        _dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": report["ok"],
            "surface_bundle_path": surface_result["surface_bundle_path"],
            "surface_quality_report_path": _relpath(self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"),
            "surface_validation_ir": self.runtime["surface"]["bundle"].get("surface_validation_ir", {}),
            "metrics": report["metrics"],
            "diagnostics": report["diagnostics"],
        }

    def repair_surface_stage(self) -> dict[str, Any]:
        initial = self.validate_surface_stage()
        if initial["ok"]:
            return {**initial, "repaired": False, "repair_reason": "surface_already_valid"}
        repaired_bundle = self._run_surface(self.runtime["uv"]["bundle"], repair_mode="surface_enhance_v1")
        repaired_report = evaluate_surface_quality(self.asset, self.runtime)
        _dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", repaired_report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": repaired_report["ok"],
            "repaired": True,
            "repair_reason": "surface_enhance_v1",
            "surface_bundle_path": _relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            "surface_quality_report_path": _relpath(self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"),
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

    def _run_shape(self) -> dict[str, Any]:
        shape_cfg = self.asset["build"]["shape"]
        backend = self.selected_backends["shape"]
        seed = _resolve_seed(shape_cfg.get("seed", "auto"), self.asset_name)
        candidates_count = int(shape_cfg.get("candidates", 1) or 1)
        assembly_ir = AssemblyIR.from_asset(self.asset)
        feature_ir = FeatureIR.from_asset(self.asset)
        surface_ir = SurfaceIR.from_asset(self.asset)
        repair_policy_ir = RepairPolicyIR.from_asset(self.asset)
        reference_ir = ReferenceIR.from_asset(self.asset)
        fit_ir = FitIR.from_asset(self.asset)
        transfer_ir = TransferIR.from_asset(self.asset)
        kit_ir = KitIR.from_asset(self.asset)
        conditioning = _shape_collect_conditioning(self.asset, self.source_root)
        provider_result = _shape_run_backend(
            backend["id"],
            self.asset,
            source_root=self.source_root,
            seed=seed,
            candidates_count=candidates_count,
            conditioning=conditioning,
            work_dir=self.stage_dirs["shape"],
            runtime_config=self.runtime_config,
        )
        runtime_candidates = provider_result["runtime_candidates"]
        provider_report = provider_result["provider_report"]
        asset_graph = provider_result.get("asset_graph")
        shape_ir = provider_result.get("shape_ir")
        scaffold_report = provider_result.get("scaffold_report", {})
        conformance_report = provider_result.get("conformance_report", {})
        candidates: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        selected_runtime: RuntimeMesh | None = None
        runtime_candidates_by_id: dict[str, RuntimeMesh] = {}
        consumed_refs = conditioning.get("consumed_refs", [])
        for index, candidate_runtime in enumerate(runtime_candidates):
            runtime_mesh = RuntimeMesh(
                mesh=candidate_runtime["mesh"],
                face_parts=list(candidate_runtime["face_parts"]),
                part_colors=dict(candidate_runtime["part_colors"]),
                units=candidate_runtime.get("units", "cm"),
            )
            meta = candidate_runtime["meta"]
            candidate_id = f"candidate_{index:02d}"
            runtime_candidates_by_id[candidate_id] = runtime_mesh
            mesh_path = self.stage_dirs["shape"] / f"{candidate_id}.glb"
            _export_glb(runtime_mesh.mesh, mesh_path)
            preview_path = self.stage_dirs["shape"] / f"{candidate_id}.png"
            _render_mesh_preview(runtime_mesh, preview_path, mode="material_ids")
            candidate = {
                "candidate_id": candidate_id,
                "mesh_uri": _relpath(self.out_dir, mesh_path),
                "preview_uri": _relpath(self.out_dir, preview_path),
                "units": runtime_mesh.units,
                "frame": {"handedness": "right", "up": "+Y", "forward": "+Z"},
                "part_labels": sorted(meta["parts"]),
                "coarse_material_slots": int(meta.get("coarse_material_slots", 1)),
                "mesh_stats": _mesh_stats(runtime_mesh.mesh),
                "score": meta["score"],
                "selection_notes": meta["selection_notes"],
                "conditioning": meta.get("conditioning", {}),
                "provider": meta.get("conditioning", {}).get("provider"),
                "blueprint_id": meta.get("blueprint_id"),
                "primitives_used": meta.get("primitives_used", []),
                "shape_assessment": meta.get("shape_assessment", {}),
                "repairs_applied": meta.get("repairs_applied", []),
                "feature_report": meta.get("feature_report", {}),
                "candidate_params": meta.get("candidate_params", {}),
                "integration_report": meta.get("integration_report", {}),
            }
            candidates.append(candidate)
            if selected is None or candidate["score"] > selected["score"] or (
                math.isclose(candidate["score"], selected["score"]) and candidate_id < selected["candidate_id"]
            ):
                selected = candidate
                selected_runtime = runtime_mesh

        assert selected is not None and selected_runtime is not None
        bundle = {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "determinism_class": backend["determinism_class"],
            "seed": seed,
            "selected_candidate_id": selected["candidate_id"],
            "blueprint_id": scaffold_report.get("blueprint_id"),
            "primitives_used": scaffold_report.get("primitives_used", []),
            "conditioning_report": conditioning,
            "provider_report": provider_report,
            "assembly_ir": assembly_ir.to_dict(),
            "feature_ir": feature_ir.to_dict(),
            "surface_ir": surface_ir.to_dict(),
            "repair_policy_ir": repair_policy_ir.to_dict(),
            "reference_ir": reference_ir.to_dict(),
            "fit_ir": fit_ir.to_dict(),
            "transfer_ir": transfer_ir.to_dict(),
            "kit_ir": kit_ir.to_dict(),
            "asset_graph": asset_graph,
            "shape_ir": shape_ir,
            "scaffold_report": scaffold_report,
            "conformance_report": conformance_report,
            "proposal_sources_attempted": conformance_report.get("proposal_sources_attempted", []),
            "proposal_sources_used": conformance_report.get("proposal_sources_used", []),
            "accepted_deltas": conformance_report.get("accepted_deltas", []),
            "rejected_deltas": conformance_report.get("rejected_deltas", []),
            "conformance_failures": conformance_report.get("conformance_failures", []),
            "authoritative_candidate_reason": conformance_report.get("authoritative_candidate_reason", scaffold_report.get("authoritative_candidate_reason")),
            "shape_assessment": scaffold_report.get("shape_assessment", {}),
            "candidates": candidates,
            "provenance": {
                "backend_id": backend["id"],
                "backend_version": backend["version"],
                "seed": seed,
                "consumed_refs": consumed_refs,
                "shape_provider_id": provider_report.get("actual_provider_id"),
                "shape_provider_version": provider_report.get("actual_provider_version"),
                "attempted_shape_provider_id": provider_report.get("selected_provider_id"),
                "attempted_shape_provider_version": provider_report.get("selected_provider_version"),
            },
        }
        self.runtime["shape"] = {
            "bundle": bundle,
            "selected": selected,
            "runtime_mesh": selected_runtime,
            "runtime_candidates": runtime_candidates_by_id,
            "conditioning": conditioning,
        }
        _dump_json(self.stage_dirs["shape"] / "bundle.json", bundle)
        return bundle

    def _select_shape_candidate(self, candidate_id: str, reason: str) -> None:
        bundle = self.runtime["shape"]["bundle"]
        selected = next((item for item in bundle.get("candidates", []) if item.get("candidate_id") == candidate_id), None)
        runtime_mesh = self.runtime["shape"].get("runtime_candidates", {}).get(candidate_id)
        if selected is None or runtime_mesh is None:
            raise BuildError(f"Unknown shape candidate '{candidate_id}' for reselection")
        bundle["selected_candidate_id"] = candidate_id
        bundle["authoritative_candidate_reason"] = reason
        self.runtime["shape"]["selected"] = selected
        self.runtime["shape"]["runtime_mesh"] = runtime_mesh
        attempts = self.runtime["shape"].setdefault("reselection_attempts", [])
        attempts.append({"candidate_id": candidate_id, "reason": reason, "score": selected.get("score")})
        _dump_json(self.stage_dirs["shape"] / "bundle.json", bundle)

    def _attempt_reselect_candidates(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        repair_cfg = self.asset.get("validate", {}).get("repair", {})
        allowed = set(repair_cfg.get("allow", []))
        if "reselect_candidate" not in allowed:
            return None
        bundle = self.runtime["shape"]["bundle"]
        current_id = bundle.get("selected_candidate_id")
        ordered_candidates = sorted(bundle.get("candidates", []), key=lambda item: (-float(item.get("score", 0.0)), item.get("candidate_id", "")))
        last_result = None
        for candidate in ordered_candidates:
            candidate_id = candidate.get("candidate_id")
            if candidate_id == current_id:
                continue
            self._select_shape_candidate(candidate_id, "reselected_after_validation_failure")
            topology_bundle = self._run_topology(self.runtime["shape"]["bundle"])
            uv_bundle = self._run_uv(topology_bundle)
            surface_bundle = self._run_surface(uv_bundle)
            rig_bundle = self._run_rig(surface_bundle)
            interfaces_bundle = self._run_interfaces(rig_bundle)
            physics_bundle = self._run_physics(interfaces_bundle)
            optimize_bundle = self._run_optimize(physics_bundle)
            validate_bundle = self._run_validate(optimize_bundle)
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

    def _run_topology(self, shape_bundle: dict[str, Any]) -> dict[str, Any]:
        backend = self.selected_backends["topology"]
        runtime_mesh: RuntimeMesh = self.runtime["shape"]["runtime_mesh"]
        adapter_report = probe_topology_backend(self.runtime_config)
        strict = bool(adapter_report.get("strict", False))
        preserve_integrated = should_preserve_integrated_shape(self.runtime["shape"]["bundle"], self.runtime_config)
        if adapter_report["requested_adapter"] == "blender" and not adapter_report["real_adapter_available"] and strict:
            raise _runtime_stage_error(
                self.asset_name,
                "topology",
                backend["id"],
                "Requested Blender topology adapter is unavailable and strict mode is enabled",
                details=adapter_report,
            )
        try:
            if preserve_integrated:
                topology_runtime, execution = _run_reference_topology_cleanup(runtime_mesh, self.asset)
                execution["mode"] = "integrated_preserve_cleanup"
                adapter_report["status"] = "preserved"
                adapter_report["selected_adapter"] = "integrated_preserve_cleanup"
                adapter_report["fallback_reason"] = None
            elif adapter_report["selected_adapter"] == "blender_subprocess":
                topology_runtime, execution = _run_blender_topology(runtime_mesh, self.stage_dirs["topology"], self.runtime_config)
                blender_stats = _mesh_stats(topology_runtime.mesh)
                if not blender_stats["watertight"]:
                    message = "Blender topology adapter produced a non-watertight mesh"
                    if strict:
                        raise RuntimeError(message)
                    topology_runtime, fallback_execution = _run_reference_topology_cleanup(runtime_mesh, self.asset)
                    execution = {
                        "mode": "reference_cleanup",
                        "fallback_from": "blender_subprocess",
                        "reason": message,
                        "blender_execution": execution,
                        "blender_mesh_stats": blender_stats,
                        "fallback_execution": fallback_execution,
                    }
                    adapter_report["status"] = "fallback"
                    adapter_report["fallback_reason"] = message
                    adapter_report["error"] = {"type": "quality_gate", "message": message}
                else:
                    adapter_report["status"] = "success"
            else:
                topology_runtime, execution = _run_reference_topology_cleanup(runtime_mesh, self.asset)
                adapter_report["status"] = "forced" if adapter_report["requested_adapter"] in {"cleanup", "reference_cleanup"} else "fallback"
                if not adapter_report["real_adapter_available"]:
                    adapter_report["fallback_reason"] = adapter_report["probe"].get("message", "Blender unavailable")
        except Exception as exc:  # noqa: BLE001
            if strict:
                raise _runtime_stage_error(
                    self.asset_name,
                    "topology",
                    backend["id"],
                    f"Topology adapter failed in strict mode: {exc}",
                    details={"adapter_report": adapter_report, "error_type": type(exc).__name__},
                ) from exc
            topology_runtime, execution = _run_reference_topology_cleanup(runtime_mesh, self.asset)
            adapter_report["status"] = "fallback"
            adapter_report["fallback_reason"] = str(exc)
            adapter_report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        actual_adapter = execution.get("mode", adapter_report["selected_adapter"])
        topology_path = self.stage_dirs["topology"] / "topology.glb"
        _export_glb(topology_runtime.mesh, topology_path)
        part_groups = _part_groups_from_face_parts(topology_runtime.mesh, topology_runtime.face_parts)
        topology_semantics = derive_topology_semantics(self.runtime["shape"]["bundle"])
        bundle = {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "mesh_uri": _relpath(self.out_dir, topology_path),
            "mesh_stats": _mesh_stats(topology_runtime.mesh),
            "normals": {"mode": "face", "count": int(len(topology_runtime.mesh.face_normals))},
            "part_groups": part_groups,
            **topology_semantics,
            "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
            "provenance": {
                "backend_id": backend["id"],
                "backend_version": backend["version"],
                "runtime_adapter": actual_adapter,
            },
        }
        self.runtime["topology"] = {"bundle": bundle, "runtime_mesh": topology_runtime}
        _dump_json(self.stage_dirs["topology"] / "bundle.json", bundle)
        return bundle

    def _run_uv(self, topology_bundle: dict[str, Any]) -> dict[str, Any]:
        backend = self.selected_backends["uv"]
        topology_runtime: RuntimeMesh = self.runtime["topology"]["runtime_mesh"]
        adapter_report = probe_uv_backend(self.runtime_config)
        strict = bool(adapter_report.get("strict", False))
        if adapter_report["requested_adapter"] == "xatlas" and not adapter_report["real_adapter_available"] and strict:
            raise _runtime_stage_error(
                self.asset_name,
                "uv",
                backend["id"],
                "Requested xatlas UV adapter is unavailable and strict mode is enabled",
                details=adapter_report,
            )
        try:
            if adapter_report["selected_adapter"] == "xatlas":
                uv_mesh, uv_meta, execution = _apply_xatlas_uv(topology_runtime, self.asset, self.runtime_config)
                adapter_report["status"] = "success"
            else:
                uv_mesh, uv_meta = _apply_box_uv(topology_runtime, self.asset)
                execution = {"mode": "reference_box"}
                adapter_report["status"] = "forced" if adapter_report["requested_adapter"] in {"box", "reference_box"} else "fallback"
                if not adapter_report["real_adapter_available"]:
                    adapter_report["fallback_reason"] = adapter_report["probe"].get("message", "xatlas unavailable")
        except Exception as exc:  # noqa: BLE001
            if strict:
                raise _runtime_stage_error(
                    self.asset_name,
                    "uv",
                    backend["id"],
                    f"UV adapter failed in strict mode: {exc}",
                    details={"adapter_report": adapter_report, "error_type": type(exc).__name__},
                ) from exc
            uv_mesh, uv_meta = _apply_box_uv(topology_runtime, self.asset)
            execution = {"mode": "reference_box"}
            adapter_report["status"] = "fallback"
            adapter_report["fallback_reason"] = str(exc)
            adapter_report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        actual_adapter = execution.get("mode", adapter_report["selected_adapter"])
        uv_path = self.stage_dirs["uv"] / "uv.glb"
        _export_glb(uv_mesh.mesh, uv_path)
        uv_semantics = derive_uv_semantics(self.runtime["topology"]["bundle"], self.runtime["shape"]["bundle"])
        bundle = {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "mesh_uri": _relpath(self.out_dir, uv_path),
            "uv_sets": uv_meta["uv_sets"],
            "packing_report": uv_meta["packing_report"],
            "texel_density": uv_meta["texel_density"],
            **uv_semantics,
            "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
            "provenance": {
                "backend_id": backend["id"],
                "backend_version": backend["version"],
                "runtime_adapter": actual_adapter,
            },
        }
        self.runtime["uv"] = {"bundle": bundle, "runtime_mesh": uv_mesh, "uv_meta": uv_meta}
        _dump_json(self.stage_dirs["uv"] / "bundle.json", bundle)
        return bundle

    def _run_surface(self, uv_bundle: dict[str, Any], *, repair_mode: str | None = None) -> dict[str, Any]:
        stage_dir = self.stage_dirs["surface"]
        bundle = build_surface_bundle(
            asset=self.asset,
            out_dir=stage_dir,
            shape_bundle=self.runtime["shape"]["bundle"],
            shape_runtime_mesh=self.runtime["shape"]["runtime_mesh"],
            topology_bundle=self.runtime["topology"]["bundle"],
            uv_runtime_mesh=self.runtime["uv"]["runtime_mesh"],
            repair_mode=repair_mode,
            runtime_config=self.runtime_config,
        )
        self.runtime["surface"] = {"bundle": bundle, "stage_dir": stage_dir}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _attempt_surface_repair(
        self,
        validate_bundle: dict[str, Any],
        topology_bundle: dict[str, Any],
        uv_bundle: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        allowed = set(self.asset.get("validate", {}).get("repair", {}).get("allow", []))
        if "reauthor_surface_layer" not in allowed:
            return None
        diagnostic_names = {item.get("name") for item in validate_bundle.get("diagnostics", [])}
        if "visual_surface_authoring_quality_failed" not in diagnostic_names:
            return None
        surface_bundle = self._run_surface(uv_bundle, repair_mode="surface_enhance_v1")
        rig_bundle = self._run_rig(surface_bundle)
        interfaces_bundle = self._run_interfaces(rig_bundle)
        physics_bundle = self._run_physics(interfaces_bundle)
        optimize_bundle = self._run_optimize(physics_bundle)
        repaired_validate = self._run_validate(optimize_bundle)
        attempts = self.runtime["shape"].setdefault("reselection_attempts", [])
        attempts.append({"candidate_id": self.runtime["shape"]["bundle"].get("selected_candidate_id"), "reason": "surface_reauthor_repair", "score": repaired_validate.get("score")})
        return surface_bundle, rig_bundle, interfaces_bundle, physics_bundle, optimize_bundle, repaired_validate

    def _run_rig(self, surface_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["rig"]
        rig_cfg = self.asset["build"]["rig"]
        topology_runtime: RuntimeMesh = self.runtime["topology"]["runtime_mesh"]
        part_centroids = _part_centroids(topology_runtime.mesh, topology_runtime.face_parts)
        joints = []
        for joint_name in rig_cfg.get("joints", []):
            centroid = part_centroids.get(joint_name, [0.0, 0.0, 0.0])
            joints.append({
                "name": joint_name,
                "pivot": [round(float(v), 6) for v in centroid],
            })
        bundle = {
            "backend_id": "lathe.rig.rigid_mechanical_stub_v1",
            "type": rig_cfg.get("type"),
            "pivot_policy": rig_cfg.get("pivot_policy", "auto"),
            "joints": joints,
        }
        self.runtime["rig"] = {"bundle": bundle}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _run_interfaces(self, rig_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["interfaces"]
        cfg = self.asset["build"]["interfaces"]
        mesh = self.runtime["topology"]["runtime_mesh"].mesh
        bounds = mesh.bounds
        center = mesh.bounding_box.centroid
        sockets = []
        for idx, name in enumerate(cfg.get("sockets", [])):
            z_offset = (-0.2 + 0.4 * idx / max(1, len(cfg.get("sockets", [])))) * (bounds[1, 2] - bounds[0, 2])
            sockets.append({
                "name": name,
                "position": [round(float(center[0]), 6), round(float(center[1]), 6), round(float(center[2] + z_offset), 6)],
            })
        anchors = []
        for idx, name in enumerate(cfg.get("anchors", [])):
            anchors.append({
                "name": name,
                "position": [round(float(center[0]), 6), round(float(bounds[0, 1]), 6), round(float(center[2]), 6)],
            })
        bundle = {
            "backend_id": "lathe.interfaces.socket_stub_v1",
            "sockets": sockets,
            "anchors": anchors,
            "clearance": cfg.get("clearance"),
            "snap_grid": cfg.get("snap_grid"),
        }
        self.runtime["interfaces"] = {"bundle": bundle}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _run_physics(self, interfaces_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["physics"]
        topology_runtime: RuntimeMesh = self.runtime["topology"]["runtime_mesh"]
        cfg = self.asset["build"]["physics"]
        collision_mesh = topology_runtime.mesh.bounding_box.copy()
        collision_path = stage_dir / "collision.glb"
        _export_glb(collision_mesh, collision_path)
        mass_value = _estimate_mass_kg(topology_runtime.mesh)
        bundle = {
            "backend_id": "lathe.physics.proxy_v1",
            "collision": cfg.get("collision"),
            "collision_proxy_uri": _relpath(self.out_dir, collision_path),
            "collision_proxy": True,
            "mass_kg": round(mass_value, 4),
            "center_of_mass": [round(float(v), 6) for v in topology_runtime.mesh.center_mass],
        }
        self.runtime["physics"] = {"bundle": bundle, "collision_mesh": collision_mesh}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _run_optimize(self, physics_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["optimize"]
        cfg = self.asset["build"]["optimize"]
        uv_runtime: RuntimeMesh = self.runtime["uv"]["runtime_mesh"]
        lod_count = max(1, int(cfg.get("lods", 1)))
        lods = []
        for lod_index in range(lod_count):
            lod_path = stage_dir / f"lod{lod_index}.glb"
            _export_glb(uv_runtime.mesh, lod_path)
            lods.append({
                "name": f"lod{lod_index}",
                "mesh_uri": _relpath(self.out_dir, lod_path),
                "triangle_count": int(len(uv_runtime.mesh.faces)),
                "vertex_count": int(len(uv_runtime.mesh.vertices)),
                "decimation": "cloned",
            })
        draw_calls = max(1, int(cfg.get("draw_calls") or 1)) if cfg.get("draw_calls") is not None else 1
        texture_memory_bytes = 0
        bundle = {
            "backend_id": "lathe.optimize.deterministic_clone_v1",
            "lods": lods,
            "draw_calls": draw_calls,
            "texture_memory_bytes": texture_memory_bytes,
            "mesh_compression": bool(cfg.get("mesh_compression", False)),
            "atlas": bool(cfg.get("atlas", False)),
        }
        self.runtime["optimize"] = {"bundle": bundle, "runtime_mesh": uv_runtime}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _run_execution(self, optimize_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["execution"]
        bundle = build_execution_bundle(
            asset=self.asset,
            stage_dir=stage_dir,
            runtime=self.runtime,
            runtime_config=self.runtime_config,
            out_dir=self.out_dir,
        )
        self.runtime["execution"] = {"bundle": bundle, "stage_dir": stage_dir}
        render_metrics = bundle.get("render_eval_ir", {}).get("metrics", {})
        if render_metrics:
            self.runtime["render_eval"] = {
                "report": {
                    "views": bundle.get("render_eval_ir", {}).get("view_metrics", {}),
                    "metrics": render_metrics,
                }
            }
        else:
            self.runtime.pop("render_eval", None)
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _run_validate(self, optimize_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["validate"]
        diagnostics: list[dict[str, Any]] = []
        semantic_report = evaluate_semantic_quality(self.asset, self.runtime)
        self.runtime["semantic_quality"] = semantic_report
        diagnostics.extend(semantic_report["diagnostics"])
        visual_report = evaluate_visual_quality(self.asset, self.runtime)
        self.runtime["visual_quality"] = visual_report
        diagnostics.extend(visual_report["diagnostics"])
        flow_report = evaluate_flow_quality(self.asset, self.runtime)
        self.runtime["flow_quality"] = flow_report
        diagnostics.extend(flow_report["diagnostics"])
        diagnostics.extend(self.runtime.get("execution", {}).get("bundle", {}).get("diagnostics", []))
        rule_results = []
        for rule in self.asset["validate"].get("rules", []):
            if rule.get("kind") == "ensure":
                passed, detail = _evaluate_rule(rule["expr"], self.asset, self.runtime)
                rule_results.append({"kind": "ensure", "expr": rule["expr"], "passed": passed, "detail": detail})
                if not passed:
                    diagnostics.append({
                        "code": "L6100",
                        "name": "ensure_failed",
                        "severity": "error",
                        "phase": "validate",
                        "asset": self.asset_name,
                        "stage": detail.get("stage"),
                        "path": detail.get("path"),
                        "message": detail.get("message", f"Validation rule failed: {rule['expr']}"),
                        "details": detail,
                        "suggested_repairs": detail.get("suggested_repairs", []),
                    })
            else:
                score = _evaluate_metric(rule["expr"], self.asset, self.runtime)
                rule_results.append({"kind": "prefer", "expr": rule["expr"], "score": score, "weight": rule.get("weight", 1.0)})

        threshold = float(self.asset["validate"].get("threshold", 0.80))
        score = _evaluate_critic(self.asset["validate"].get("score"), self.asset, self.runtime, self.critics, self.asset["validate"].get("rules", []))
        certified = not any(item.get("severity") == "error" for item in diagnostics) and score >= threshold
        report = {
            "certified": certified,
            "threshold": threshold,
            "score": round(score, 6),
            "semantic_quality": semantic_report,
            "visual_quality": visual_report,
            "flow_quality": flow_report,
            "rule_results": rule_results,
            "diagnostics": diagnostics,
            "repair_policy": self.asset["validate"].get("repair", {}),
            "repair_suggestions": sorted({repair for diag in diagnostics for repair in diag.get("suggested_repairs", [])}),
            "semantic_repairs_applied": next(
                (
                    candidate.get("repairs_applied", [])
                    for candidate in self.runtime["shape"]["bundle"].get("candidates", [])
                    if candidate.get("candidate_id") == self.runtime["shape"]["bundle"].get("selected_candidate_id")
                ),
                [],
            ),
            "reselection_attempts": list(self.runtime.get("shape", {}).get("reselection_attempts", [])),
        }
        self.runtime["validate"] = {"bundle": report}
        _dump_json(stage_dir / "report.json", report)
        return report

    def _run_package(self, optimize_bundle: dict[str, Any], validate_bundle: dict[str, Any]) -> dict[str, Any]:
        stage_dir = self.stage_dirs["package"]
        package_cfg = self.asset["package"]
        optimize_runtime: RuntimeMesh = self.runtime["optimize"]["runtime_mesh"]
        mesh = optimize_runtime.mesh.copy()
        outputs: list[dict[str, Any]] = []
        if "usd" in package_cfg.get("formats", []):
            usd_path = stage_dir / f"{self.asset_name}.usda"
            _write_usda(mesh, usd_path, asset_name=self.asset_name)
            outputs.append(_output_entry(self.out_dir, usd_path, "usd"))
        if "glb" in package_cfg.get("formats", []):
            glb_path = stage_dir / f"{self.asset_name}.glb"
            _export_glb(mesh, glb_path)
            outputs.append(_output_entry(self.out_dir, glb_path, "glb"))
        if "gltf" in package_cfg.get("formats", []):
            gltf_paths = _export_gltf(mesh, stage_dir, self.asset_name)
            for path in gltf_paths:
                outputs.append(_output_entry(self.out_dir, path, "gltf" if path.suffix == ".gltf" else "gltf_resource"))
        if "obj" in package_cfg.get("formats", []):
            obj_path = stage_dir / f"{self.asset_name}.obj"
            _export_obj(mesh, obj_path)
            outputs.append(_output_entry(self.out_dir, obj_path, "obj"))

        previews = []
        preview_dir = stage_dir / "previews"
        preview_dir.mkdir(exist_ok=True)
        requested_previews = package_cfg.get("previews", [])
        if "turntable" in requested_previews:
            path = preview_dir / "turntable.png"
            _render_mesh_preview(optimize_runtime, path, mode="shaded")
            previews.append(_relpath(self.out_dir, path))
        if "wireframe" in requested_previews:
            path = preview_dir / "wireframe.png"
            _render_mesh_preview(optimize_runtime, path, mode="wireframe")
            previews.append(_relpath(self.out_dir, path))
        if "material_ids" in requested_previews:
            path = preview_dir / "material_ids.png"
            _render_mesh_preview(optimize_runtime, path, mode="material_ids")
            previews.append(_relpath(self.out_dir, path))
        if "uv_layout" in requested_previews:
            path = preview_dir / "uv_layout.png"
            _render_uv_layout(self.runtime["uv"]["runtime_mesh"], path)
            previews.append(_relpath(self.out_dir, path))
        if "collision" in requested_previews:
            path = preview_dir / "collision.png"
            collision_mesh = RuntimeMesh(
                mesh=self.runtime["physics"]["collision_mesh"],
                face_parts=["collision"] * int(len(self.runtime["physics"]["collision_mesh"].faces)),
                part_colors={"collision": (220, 92, 60)},
                units="cm",
            )
            _render_mesh_preview(collision_mesh, path, mode="wireframe")
            previews.append(_relpath(self.out_dir, path))
        if "lod_sheet" in requested_previews:
            path = preview_dir / "lod_sheet.png"
            _render_lod_sheet(optimize_runtime, int(len(optimize_bundle["lods"])), path)
            previews.append(_relpath(self.out_dir, path))

        manifest = {
            "asset_id": self.asset_name,
            "kind": self.asset["kind"],
            "contracts": list(self.asset.get("uses", [])),
            "profiles": self._resolved_profile_names(),
            "version": self.asset["publish"].get("version"),
            "formats": list(package_cfg.get("formats", [])),
            "outputs": outputs,
            "output_hashes": {entry["uri"]: entry["sha256"] for entry in outputs},
            "previews": previews,
            "trace_path": None,
            "normalized_source_path": _relpath(self.out_dir, self.normalized_asset_path),
            "build_timestamp": None,
        }
        trace_path = None
        if package_cfg.get("include_trace", True):
            trace_path = stage_dir / "trace_manifest.json"
            trace = self._build_trace(outputs, previews, validate_bundle)
            _dump_json(trace_path, trace)
            manifest["trace_path"] = _relpath(self.out_dir, trace_path)
        manifest_path = stage_dir / "package_manifest.json"
        _dump_json(manifest_path, manifest)
        bundle = {
            "backend_id": self.selected_backends["package"]["id"],
            "outputs": outputs,
            "manifest_path": _relpath(self.out_dir, manifest_path),
            "trace_path": _relpath(self.out_dir, trace_path) if trace_path else None,
            "normalized_source_path": _relpath(self.out_dir, self.normalized_asset_path),
            "previews": previews,
        }
        self.runtime["package"] = {"bundle": bundle}
        _dump_json(stage_dir / "bundle.json", bundle)
        return bundle

    def _resolved_profile_names(self) -> list[str]:
        names = []
        for decl in self.resolver.resolve_use_chain(self.asset.get("uses", [])):
            if decl.get("node_type") == "profile":
                names.append(decl["name"])
        return names

    def _build_trace(self, outputs: list[dict[str, Any]], previews: list[str], validate_bundle: dict[str, Any]) -> dict[str, Any]:
        refs = []
        for group_name, group_values in self.asset.get("refs", {}).items():
            if not isinstance(group_values, list):
                continue
            for value in group_values:
                refs.append({
                    "group": group_name,
                    "value": value,
                    "sha256": _hash_ref(value),
                })
        return {
            "asset_id": self.asset_name,
            "source_hash": _hash_obj(self.program),
            "normalized_hash": _hash_obj(self.normalized_program),
            "compiler_version": "0.1.0",
            "backend_versions": {stage: data["id"] + "@" + data["version"] for stage, data in self.selected_backends.items()},
            "determinism_by_stage": {stage: data["determinism_class"] for stage, data in self.selected_backends.items()},
            "refs_with_hashes": refs,
            "uses": list(self.asset.get("uses", [])),
            "stage_configs": {
                "shape": self.asset["build"]["shape"],
                "topology": self.asset["build"]["topology"],
                "uv": self.asset["build"]["uv"],
                "surface": self.asset["build"]["surface"],
                "execution": self.asset.get("execution", {}),
                "rig": self.asset["build"]["rig"],
                "interfaces": self.asset["build"]["interfaces"],
                "physics": self.asset["build"]["physics"],
                "optimize": self.asset["build"]["optimize"],
                "package": self.asset["package"],
                "publish": self.asset["publish"],
            },
            "stage_outputs": {
                stage: _relpath(self.out_dir, self.stage_dirs[stage] / ("report.json" if stage == "validate" else "bundle.json"))
                for stage in STAGE_ORDER
            },
            "stage_execution": {
                "shape": {
                    "provider_report": self.runtime["shape"]["bundle"].get("provider_report"),
                    "blueprint_id": self.runtime["shape"]["bundle"].get("blueprint_id"),
                    "primitives_used": self.runtime["shape"]["bundle"].get("primitives_used", []),
                    "proposal_sources_attempted": self.runtime["shape"]["bundle"].get("proposal_sources_attempted", []),
                    "proposal_sources_used": self.runtime["shape"]["bundle"].get("proposal_sources_used", []),
                    "accepted_deltas": self.runtime["shape"]["bundle"].get("accepted_deltas", []),
                    "rejected_deltas": self.runtime["shape"]["bundle"].get("rejected_deltas", []),
                    "conformance_failures": self.runtime["shape"]["bundle"].get("conformance_failures", []),
                    "authoritative_candidate_reason": self.runtime["shape"]["bundle"].get("authoritative_candidate_reason"),
                "shape_assessment": self.runtime["shape"]["bundle"].get("shape_assessment", {}),
                "reference_ir": self.runtime["shape"]["bundle"].get("reference_ir", {}),
                "fit_ir": self.runtime["shape"]["bundle"].get("fit_ir", {}),
                "transfer_ir": self.runtime["shape"]["bundle"].get("transfer_ir", {}),
                "kit_ir": self.runtime["shape"]["bundle"].get("kit_ir", {}),
            },
                "topology": self.runtime["topology"]["bundle"].get("adapter_report"),
                "uv": self.runtime["uv"]["bundle"].get("adapter_report"),
                "surface": {
                    "surface_backend_report": self.runtime["surface"]["bundle"].get("surface_backend_report", {}),
                    "surface_control_pack": self.runtime["surface"]["bundle"].get("surface_control_pack", {}),
                    "codex_imagegen_requests": self.runtime["surface"]["bundle"].get("codex_imagegen_requests", {}),
                    "codex_imagegen_outputs": self.runtime["surface"]["bundle"].get("codex_imagegen_outputs", {}),
                    "atlas_assembly_ir": self.runtime["surface"]["bundle"].get("atlas_assembly_ir", {}),
                    "surface_validation_ir": self.runtime["surface"]["bundle"].get("surface_validation_ir", {}),
                    "surface_repair_ir": self.runtime["surface"]["bundle"].get("surface_repair_ir", {}),
                },
                "execution": self.runtime.get("execution", {}).get("bundle", {}),
                "flow_quality": self.runtime.get("flow_quality", {}),
                "package": {"adapter": "reference_package"},
            },
            "candidate_selection": self.runtime["shape"]["bundle"],
            "repairs_applied": self.runtime["validate"]["bundle"].get("semantic_repairs_applied", []),
            "diagnostics": validate_bundle["diagnostics"],
            "package_outputs": outputs,
            "previews": previews,
            "approval_state": "pending_required_approval" if self.asset["publish"].get("approval") == "required" else "not_required",
        }


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


def _relpath(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(root))


def _dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def _resolve_seed(seed: Any, asset_name: str) -> int:
    if isinstance(seed, int):
        return seed
    if isinstance(seed, str) and seed != "auto":
        try:
            return int(seed)
        except ValueError:
            pass
    digest = hashlib.sha256(asset_name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _hash_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_ref(value: Any) -> str:
    try:
        path = Path(str(value))
        if path.exists() and path.is_file():
            return _hash_file(path)
    except OSError:
        pass
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _output_entry(root: Path, path: Path, fmt: str) -> dict[str, Any]:
    return {
        "format": fmt,
        "uri": _relpath(root, path),
        "sha256": _hash_file(path),
        "size_bytes": path.stat().st_size,
    }


def _unit_to_cm(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "mm":
        return amount / 10.0
    if unit == "cm":
        return amount
    if unit == "m":
        return amount * 100.0
    if unit == "px":
        return amount
    if unit == "px_per_m":
        return amount
    if unit == "px_per_cm":
        return amount * 100.0
    if unit == "kb":
        return amount * 1024.0
    if unit == "mb":
        return amount * 1024.0 * 1024.0
    if unit == "gb":
        return amount * 1024.0 * 1024.0 * 1024.0
    return amount


def _unit_to_bytes(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "kb":
        return int(amount * 1024)
    if unit == "mb":
        return int(amount * 1024 * 1024)
    if unit == "gb":
        return int(amount * 1024 * 1024 * 1024)
    raise ValueError(f"Cannot convert unit '{unit}' to bytes")


def _unit_to_px_per_m(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict) or value.get("type") != "unit":
        raise TypeError(f"Expected unit literal, got {value!r}")
    amount = float(value["value"])
    unit = value["unit"]
    if unit == "px_per_m":
        return amount
    if unit == "px_per_cm":
        return amount * 100.0
    raise ValueError(f"Cannot convert unit '{unit}' to px_per_m")


def _characteristic_scale_cm(asset: dict[str, Any]) -> float:
    intent = asset.get("intent", {})
    if "dimensions" in intent and isinstance(intent["dimensions"], dict) and intent["dimensions"].get("type") == "call":
        args = intent["dimensions"].get("args", [])
        values = [_unit_to_cm(item["value"]) for item in args if isinstance(item, dict) and item.get("value") is not None]
        if values:
            return max(values)
    if "scale" in intent:
        return max(1.0, _unit_to_cm(intent["scale"]))
    return 200.0 if asset.get("kind") == "env_module" else 100.0


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _candidate_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * 7919)


def _translated_box(extents: Iterable[float], center: Iterable[float]) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def _translated_cylinder(radius: float, height: float, center: Iterable[float], axis: str = "y") -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=24)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


def _generate_candidate_mesh(asset: dict[str, Any], *, index: int, seed: int) -> tuple[RuntimeMesh, dict[str, Any]]:
    rng = _candidate_rng(seed, index)
    scale_cm = _characteristic_scale_cm(asset)
    role = asset.get("intent", {}).get("role", "")
    parts = list(asset.get("intent", {}).get("parts", []))
    if not parts:
        parts = ["body"]
    kind = asset.get("kind")
    part_meshes: list[trimesh.Trimesh] = []
    face_parts: list[str] = []
    part_colors = {part: _make_color(part) for part in parts}

    def add_part(name: str, mesh: trimesh.Trimesh) -> None:
        part_meshes.append(mesh)
        face_parts.extend([name] * int(len(mesh.faces)))

    body_names = [name for name in parts if any(token in name for token in ("body", "hull", "core", "base"))]
    root_name = body_names[0] if body_names else parts[0]

    if kind == "env_module":
        width = scale_cm * float(1.6 + 0.1 * rng.uniform(-1, 1))
        height = scale_cm * float(1.2 + 0.05 * rng.uniform(-1, 1))
        depth = scale_cm * float(1.0 + 0.1 * rng.uniform(-1, 1))
        for idx, name in enumerate(parts):
            lname = name.lower()
            if "floor" in lname:
                add_part(name, _translated_box([width, 8.0, depth], [0.0, -height / 2.0 + 4.0, 0.0]))
            elif "ceiling" in lname or "roof" in lname:
                add_part(name, _translated_box([width, 8.0, depth], [0.0, height / 2.0 - 4.0, 0.0]))
            elif "wall" in lname:
                side = idx % 4
                thickness = 6.0
                if side == 0:
                    center = [0.0, 0.0, depth / 2.0 - thickness / 2.0]
                    extents = [width, height, thickness]
                elif side == 1:
                    center = [0.0, 0.0, -depth / 2.0 + thickness / 2.0]
                    extents = [width, height, thickness]
                elif side == 2:
                    center = [width / 2.0 - thickness / 2.0, 0.0, 0.0]
                    extents = [thickness, height, depth]
                else:
                    center = [-width / 2.0 + thickness / 2.0, 0.0, 0.0]
                    extents = [thickness, height, depth]
                add_part(name, _translated_box(extents, center))
            elif "column" in lname or "pillar" in lname:
                angle = 2.0 * math.pi * idx / max(1, len(parts))
                add_part(name, _translated_box([10.0, height, 10.0], [math.cos(angle) * width * 0.35, 0.0, math.sin(angle) * depth * 0.35]))
            else:
                add_part(name, _translated_box([width * 0.2, height * 0.4, depth * 0.2], [0.0, 0.0, 0.0]))
    else:
        body_extents = np.array([
            scale_cm * float(0.38 + 0.04 * rng.uniform(-1, 1)),
            scale_cm * float(0.14 + 0.02 * rng.uniform(-1, 1)),
            scale_cm * float(0.48 + 0.04 * rng.uniform(-1, 1)),
        ])
        root_mesh = _translated_box(body_extents, [0.0, 0.0, 0.0])
        add_part(root_name, root_mesh)
        rotor_positions = [
            [body_extents[0] * 0.9, body_extents[1] * 0.55, body_extents[2] * 0.85],
            [-body_extents[0] * 0.9, body_extents[1] * 0.55, body_extents[2] * 0.85],
            [body_extents[0] * 0.9, body_extents[1] * 0.55, -body_extents[2] * 0.85],
            [-body_extents[0] * 0.9, body_extents[1] * 0.55, -body_extents[2] * 0.85],
        ]
        leg_positions = [
            [body_extents[0] * 0.55, -body_extents[1] * 0.75, body_extents[2] * 0.25],
            [-body_extents[0] * 0.55, -body_extents[1] * 0.75, -body_extents[2] * 0.25],
        ]
        generic_idx = 0
        rotor_idx = 0
        leg_idx = 0
        for name in parts:
            if name == root_name:
                continue
            lname = name.lower()
            if "rotor" in lname or "fan" in lname or "prop" in lname:
                pos = rotor_positions[rotor_idx % len(rotor_positions)]
                rotor_idx += 1
                radius = scale_cm * float(0.09 + 0.01 * rng.uniform(-1, 1))
                height = scale_cm * 0.015
                add_part(name, _translated_cylinder(radius, height, pos, axis="y"))
            elif "leg" in lname or "foot" in lname:
                pos = leg_positions[leg_idx % len(leg_positions)]
                leg_idx += 1
                add_part(name, _translated_box([scale_cm * 0.04, scale_cm * 0.18, scale_cm * 0.04], pos))
            elif "door" in lname or "hatch" in lname or "cargo" in lname:
                center = [0.0, -body_extents[1] * 0.55, body_extents[2] * 0.15]
                add_part(name, _translated_box([body_extents[0] * 0.7, scale_cm * 0.03, body_extents[2] * 0.35], center))
            elif "camera" in lname or "gimbal" in lname or "sensor" in lname:
                center = [0.0, -body_extents[1] * 0.7, body_extents[2] * 0.45]
                add_part(name, _translated_cylinder(scale_cm * 0.05, scale_cm * 0.08, center, axis="y"))
            else:
                angle = 2.0 * math.pi * generic_idx / max(1, len(parts) - 1)
                generic_idx += 1
                center = [math.cos(angle) * body_extents[0] * 0.8, 0.0, math.sin(angle) * body_extents[2] * 0.8]
                add_part(name, _translated_box([scale_cm * 0.12, scale_cm * 0.08, scale_cm * 0.18], center))

    combined = trimesh.util.concatenate(part_meshes)
    score = 0.72
    if "drone" in role.lower() and sum(1 for part in parts if "rotor" in part.lower()) >= 4:
        score += 0.18
    if asset.get("build", {}).get("shape", {}).get("symmetry") in {"x", "z"}:
        score += 0.04
    score += min(0.06, 0.01 * max(0, len(parts) - 1))
    score = min(0.99, score)
    return RuntimeMesh(mesh=combined, face_parts=face_parts, part_colors=part_colors, units="cm"), {
        "parts": parts,
        "score": round(float(score), 6),
        "selection_notes": [
            f"generated procedurally from role='{role}'",
            f"parts={len(parts)}",
            f"candidate_index={index}",
        ],
    }


def _runtime_stage_error(
    asset_name: str,
    stage: str,
    backend_id: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> BuildError:
    return BuildError(
        message,
        diagnostics=[
            {
                "code": "L5101",
                "name": "runtime_stage_error",
                "severity": "error",
                "phase": "build",
                "asset": asset_name,
                "stage": stage,
                "path": f"build.{stage}.backend",
                "message": message,
                "details": {**(details or {}), "backend_id": backend_id},
                "suggested_repairs": [],
            }
        ],
    )


def _seal_non_watertight_mesh(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, str | None]:
    if mesh.is_watertight:
        return mesh, None
    repaired = mesh.copy()
    try:
        repaired.fill_holes()
    except Exception:  # noqa: BLE001
        pass
    if repaired.is_watertight:
        return repaired, "fill_holes"
    try:
        hull = repaired.convex_hull
        if hull is not None and len(hull.faces) > 0 and hull.is_watertight:
            return hull, "convex_hull"
    except Exception:  # noqa: BLE001
        pass
    return repaired, None


def _quadrant_tokens(part_name: str) -> tuple[int | None, int | None]:
    name = part_name.lower()
    if "_fl" in name or name.endswith("fl"):
        return 1, 1
    if "_fr" in name or name.endswith("fr"):
        return -1, 1
    if "_rl" in name or name.endswith("rl"):
        return 1, -1
    if "_rr" in name or name.endswith("rr"):
        return -1, -1
    return None, None


def _assign_faces_by_score(assignments: np.ndarray, score: np.ndarray, part_name: str, face_count: int) -> None:
    if face_count <= 0:
        return
    order = np.argsort(score)[::-1]
    chosen = 0
    for face_index in order:
        if score[face_index] <= 0:
            continue
        assignments[face_index] = part_name
        chosen += 1
        if chosen >= face_count:
            break


def _infer_face_parts_from_mesh(mesh: trimesh.Trimesh, expected_parts: list[str], default_name: str) -> list[str]:
    face_count = int(len(mesh.faces))
    if face_count == 0:
        return []
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    center = (bounds[0] + bounds[1]) / 2.0
    half_extents = np.maximum((bounds[1] - bounds[0]) / 2.0, 1e-6)
    normalized = (centroids - center) / half_extents
    x = normalized[:, 0]
    y = normalized[:, 1]
    z = normalized[:, 2]
    radial = np.sqrt(np.maximum(0.0, x * x + z * z))
    assignments = np.array([default_name] * face_count, dtype=object)

    rotor_parts = [part for part in expected_parts if any(token in part.lower() for token in ("rotor", "fan", "prop"))]
    rotor_target = max(4, face_count // max(12, len(rotor_parts) * 8)) if rotor_parts else 0
    for part_name in rotor_parts:
        x_sign, z_sign = _quadrant_tokens(part_name)
        score = np.maximum(0.0, y) * 0.35 + np.maximum(0.0, radial - 0.2) * 0.65
        if x_sign is not None:
            score += 0.4 * np.maximum(0.0, x * x_sign)
        if z_sign is not None:
            score += 0.4 * np.maximum(0.0, z * z_sign)
        _assign_faces_by_score(assignments, score, part_name, rotor_target)

    leg_parts = [part for part in expected_parts if any(token in part.lower() for token in ("leg", "foot"))]
    leg_target = max(3, face_count // max(18, len(leg_parts) * 10)) if leg_parts else 0
    for part_name in leg_parts:
        x_sign = 1 if any(token in part_name.lower() for token in ("_l", " left")) else -1 if any(token in part_name.lower() for token in ("_r", " right")) else 0
        score = np.maximum(0.0, -y) * 0.6 + np.maximum(0.0, np.abs(x) - 0.1) * 0.4
        if x_sign != 0:
            score += 0.35 * np.maximum(0.0, x * x_sign)
        _assign_faces_by_score(assignments, score, part_name, leg_target)

    for part_name in expected_parts:
        lname = part_name.lower()
        if any(token in lname for token in ("door", "hatch", "cargo")):
            score = np.maximum(0.0, z) * 0.7 + np.maximum(0.0, -np.abs(y - (-0.1)) + 0.8) * 0.3
            _assign_faces_by_score(assignments, score, part_name, max(4, face_count // 16))
        elif any(token in lname for token in ("camera", "gimbal", "sensor")):
            score = np.maximum(0.0, z) * 0.55 + np.maximum(0.0, -y) * 0.45
            _assign_faces_by_score(assignments, score, part_name, max(4, face_count // 18))
        elif any(token in lname for token in ("wing", "arm")):
            score = np.maximum(0.0, np.abs(x) - 0.15) * 0.6 + np.maximum(0.0, np.abs(z) - 0.15) * 0.4
            _assign_faces_by_score(assignments, score, part_name, max(4, face_count // 16))

    missing_parts = [part for part in expected_parts if part != default_name and part not in set(assignments.tolist())]
    if missing_parts:
        order = np.argsort(np.linalg.norm(normalized, axis=1))[::-1]
        cursor = 0
        for part_name in missing_parts:
            while cursor < len(order) and assignments[order[cursor]] != default_name:
                cursor += 1
            if cursor >= len(order):
                break
            assignments[order[cursor]] = part_name
            cursor += 1

    return [str(value) for value in assignments.tolist()]


def _run_reference_topology_cleanup(runtime_mesh: RuntimeMesh, asset: dict[str, Any] | None = None) -> tuple[RuntimeMesh, dict[str, Any]]:
    mesh = runtime_mesh.mesh.copy()
    mesh.remove_infinite_values()
    mesh.remove_unreferenced_vertices()
    initial_watertight = bool(mesh.is_watertight)
    if not initial_watertight:
        mesh.merge_vertices()
        mesh.fix_normals(multibody=False)
        mesh, seal_strategy = _seal_non_watertight_mesh(mesh)
    else:
        seal_strategy = None
    face_parts = list(runtime_mesh.face_parts)
    inferred_parts = False
    if asset is not None:
        expected_parts = list(asset.get("intent", {}).get("parts", []))
        default_name = next((name for name in expected_parts if any(token in name.lower() for token in ("body", "hull", "core", "base"))), expected_parts[0] if expected_parts else "mesh")
        counts = Counter(face_parts) if face_parts else Counter()
        sparse_nondefault = sum(1 for name, count in counts.items() if name != default_name and count <= 2)
        part_distribution_unreliable = (
            len(face_parts) != len(mesh.faces)
            or len(set(face_parts)) <= 1
            or (expected_parts and len(set(face_parts)) < max(2, len(expected_parts) // 2))
            or sparse_nondefault >= max(2, min(len(expected_parts), 4))
        )
        if expected_parts and part_distribution_unreliable:
            face_parts = _infer_face_parts_from_mesh(mesh, expected_parts, default_name)
            inferred_parts = True
    return (
        RuntimeMesh(
            mesh=mesh,
            face_parts=face_parts if len(face_parts) == len(mesh.faces) else [next(iter(runtime_mesh.part_colors), "mesh")] * int(len(mesh.faces)),
            part_colors=dict(runtime_mesh.part_colors),
            units=runtime_mesh.units,
        ),
        {
            "mode": "reference_cleanup",
            "seal_strategy": seal_strategy,
            "heuristic_part_groups": inferred_parts,
        },
    )


def _runtime_scene_parts(runtime_mesh: RuntimeMesh) -> list[tuple[str, trimesh.Trimesh]]:
    if not runtime_mesh.face_parts or len(runtime_mesh.face_parts) != len(runtime_mesh.mesh.faces):
        return [("mesh", runtime_mesh.mesh.copy())]
    parts: list[tuple[str, trimesh.Trimesh]] = []
    for part in sorted(set(runtime_mesh.face_parts)):
        face_indices = [idx for idx, name in enumerate(runtime_mesh.face_parts) if name == part]
        submesh = runtime_mesh.mesh.submesh([face_indices], append=True, repair=False)
        parts.append((part, submesh))
    return parts


def _export_runtime_scene_glb(runtime_mesh: RuntimeMesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    for part_name, submesh in _runtime_scene_parts(runtime_mesh):
        scene.add_geometry(submesh, geom_name=part_name, node_name=part_name)
    path.write_bytes(scene.export(file_type="glb"))


def _load_runtime_mesh_from_scene(path: Path, source_runtime: RuntimeMesh) -> RuntimeMesh | None:
    try:
        loaded = trimesh.load(path, force="scene")
    except Exception:  # noqa: BLE001
        return None
    if isinstance(loaded, trimesh.Scene):
        meshes: list[trimesh.Trimesh] = []
        face_parts: list[str] = []
        known_parts = set(source_runtime.part_colors)
        for name, geom in loaded.geometry.items():
            if not isinstance(geom, trimesh.Trimesh):
                continue
            meshes.append(geom.copy())
            part_name = name if name in known_parts else (next(iter(known_parts)) if known_parts else "mesh")
            face_parts.extend([part_name] * int(len(geom.faces)))
        if not meshes:
            return None
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        return RuntimeMesh(mesh=mesh, face_parts=face_parts, part_colors=dict(source_runtime.part_colors), units=source_runtime.units)
    if isinstance(loaded, trimesh.Trimesh):
        part_name = next(iter(source_runtime.part_colors), "mesh")
        return RuntimeMesh(
            mesh=loaded.copy(),
            face_parts=[part_name] * int(len(loaded.faces)),
            part_colors=dict(source_runtime.part_colors),
            units=source_runtime.units,
        )
    return None


def _run_blender_topology(runtime_mesh: RuntimeMesh, stage_dir: Path, runtime_config: dict[str, Any] | None) -> tuple[RuntimeMesh, dict[str, Any]]:
    blender = probe_blender(runtime_config)
    if not blender["available"]:
        raise RuntimeError(blender.get("message", "Blender is unavailable"))
    input_path = stage_dir / "blender_input.glb"
    output_path = stage_dir / "blender_output.glb"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "blender_topology_adapter.py"
    _export_runtime_scene_glb(runtime_mesh, input_path)
    timeout_s = int(((runtime_config or {}).get("topology", {}).get("blender", {}) or {}).get("timeout_s", 300))
    proc = subprocess.run(
        [
            blender["path"],
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
            "--",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(stderr[-500:] if stderr else "Blender topology subprocess failed")
    topology_runtime = _load_runtime_mesh_from_scene(output_path, runtime_mesh)
    if topology_runtime is None or len(topology_runtime.mesh.faces) == 0:
        raise RuntimeError("Blender topology subprocess did not produce a valid mesh")
    return (
        topology_runtime,
        {
            "mode": "blender_subprocess",
            "blender_path": blender["path"],
            "blender_version": blender.get("version"),
            "input_artifact": input_path.name,
            "output_artifact": output_path.name,
            "stdout_tail": (proc.stdout or "").strip()[-500:] or None,
            "stderr_tail": (proc.stderr or "").strip()[-500:] or None,
        },
    )


def _derived_lightmap_uv(uv: np.ndarray) -> np.ndarray:
    return np.clip(uv * 0.9 + 0.05, 0.0, 1.0)


def _apply_xatlas_uv(runtime_mesh: RuntimeMesh, asset: dict[str, Any], runtime_config: dict[str, Any] | None) -> tuple[RuntimeMesh, dict[str, Any], dict[str, Any]]:
    try:
        import xatlas
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"xatlas is unavailable: {exc}") from exc

    mesh = runtime_mesh.mesh
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32)
    vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
    mapped_vertices = vertices[np.asarray(vmapping, dtype=np.int64)]
    mapped_faces = np.asarray(indices, dtype=np.int64)
    base_uv = np.asarray(uvs, dtype=np.float64)

    lightmap_uv = _derived_lightmap_uv(base_uv)
    uv_mesh = trimesh.Trimesh(vertices=mapped_vertices, faces=mapped_faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=base_uv)
    face_parts = list(runtime_mesh.face_parts) if len(runtime_mesh.face_parts) == len(mesh.faces) else ["mesh"] * int(len(mapped_faces))
    runtime = RuntimeMesh(mesh=uv_mesh, face_parts=face_parts, part_colors=runtime_mesh.part_colors, units=runtime_mesh.units)

    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    uv_sets = []
    for name, coords in [("base", base_uv), ("lightmap", lightmap_uv)]:
        if name not in requested_sets:
            continue
        uv_sets.append(
            {
                "name": name,
                "coverage": {
                    "u_min": round(float(coords[:, 0].min()), 6),
                    "u_max": round(float(coords[:, 0].max()), 6),
                    "v_min": round(float(coords[:, 1].min()), 6),
                    "v_max": round(float(coords[:, 1].max()), 6),
                },
                "vertex_count": int(len(coords)),
            }
        )
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(_unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    resolution = int(((runtime_config or {}).get("uv", {}).get("xatlas", {}) or {}).get("resolution", 2048))
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(_unit_to_cm(padding_px)) / max(1.0, float(resolution)))
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": max(1, len(set(face_parts))),
            "resolution": resolution,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
        },
        "texel_density": {"requested_px_per_m": px_per_m, "actual_px_per_m": px_per_m},
    }
    execution = {
        "mode": "xatlas",
        "resolution": resolution,
        "lightmap_strategy": "derived_inset",
        "vertex_count": int(len(mapped_vertices)),
        "triangle_count": int(len(mapped_faces)),
    }
    return runtime, meta, execution


def _body_count(mesh: trimesh.Trimesh) -> int:
    try:
        return int(mesh.body_count)
    except Exception:  # noqa: BLE001
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if len(faces) == 0:
            return 0
        vertex_to_faces: dict[int, list[int]] = {}
        for face_index, face in enumerate(faces):
            for vertex in face:
                vertex_to_faces.setdefault(int(vertex), []).append(face_index)
        visited = np.zeros(len(faces), dtype=bool)
        body_count = 0
        for start in range(len(faces)):
            if visited[start]:
                continue
            body_count += 1
            stack = [start]
            visited[start] = True
            while stack:
                face_index = stack.pop()
                for vertex in faces[face_index]:
                    for neighbor in vertex_to_faces[int(vertex)]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            stack.append(neighbor)
        return int(body_count)


def _mesh_stats(mesh: trimesh.Trimesh) -> dict[str, Any]:
    bounds = mesh.bounds
    extents = bounds[1] - bounds[0]
    return {
        "vertex_count": int(len(mesh.vertices)),
        "triangle_count": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume": float(mesh.volume) if mesh.is_volume else 0.0,
        "bounds_min": [round(float(v), 6) for v in bounds[0]],
        "bounds_max": [round(float(v), 6) for v in bounds[1]],
        "extents": [round(float(v), 6) for v in extents],
        "body_count": _body_count(mesh),
    }


def _part_groups_from_face_parts(mesh: trimesh.Trimesh, face_parts: list[str]) -> list[dict[str, Any]]:
    if len(face_parts) != len(mesh.faces):
        face_parts = ["mesh"] * int(len(mesh.faces))
    groups: list[dict[str, Any]] = []
    for part in sorted(set(face_parts)):
        face_indices = [idx for idx, name in enumerate(face_parts) if name == part]
        part_mesh = mesh.submesh([face_indices], append=True, repair=False)
        groups.append({
            "name": part,
            "face_count": len(face_indices),
            "vertex_count": int(len(part_mesh.vertices)),
            "bounds_min": [round(float(v), 6) for v in part_mesh.bounds[0]],
            "bounds_max": [round(float(v), 6) for v in part_mesh.bounds[1]],
        })
    return groups


def _part_centroids(mesh: trimesh.Trimesh, face_parts: list[str]) -> dict[str, list[float]]:
    if len(face_parts) != len(mesh.faces):
        face_parts = ["mesh"] * int(len(mesh.faces))
    out: dict[str, list[float]] = {}
    for part in sorted(set(face_parts)):
        face_indices = [idx for idx, name in enumerate(face_parts) if name == part]
        part_mesh = mesh.submesh([face_indices], append=True, repair=False)
        centroid = part_mesh.bounding_box.centroid
        out[part] = [float(v) for v in centroid]
    return out


def _apply_box_uv(runtime_mesh: RuntimeMesh, asset: dict[str, Any]) -> tuple[RuntimeMesh, dict[str, Any]]:
    mesh = runtime_mesh.mesh
    face_parts = runtime_mesh.face_parts
    unique_parts = sorted(set(face_parts))
    cells = math.ceil(math.sqrt(max(1, len(unique_parts))))
    cell_size = 1.0 / cells
    padding_px = asset["build"]["uv"].get("padding", {"type": "unit", "value": 8, "unit": "px"})
    padding_norm = min(0.1, float(_unit_to_cm(padding_px)) / 1024.0)
    part_to_cell = {part: (idx % cells, idx // cells) for idx, part in enumerate(unique_parts)}

    vertices = mesh.vertices[mesh.faces].reshape(-1, 3)
    faces = np.arange(len(vertices), dtype=np.int64).reshape(-1, 3)
    uv = np.zeros((len(vertices), 2), dtype=np.float64)
    uv_lightmap = np.zeros((len(vertices), 2), dtype=np.float64)
    new_face_parts: list[str] = []

    for face_index, face in enumerate(mesh.faces):
        face_vertices = mesh.vertices[face]
        normal = mesh.face_normals[face_index]
        abs_normal = np.abs(normal)
        if abs_normal[1] >= abs_normal[0] and abs_normal[1] >= abs_normal[2]:
            projected = face_vertices[:, [0, 2]]
        elif abs_normal[0] >= abs_normal[2]:
            projected = face_vertices[:, [2, 1]]
        else:
            projected = face_vertices[:, [0, 1]]
        mins = projected.min(axis=0)
        maxs = projected.max(axis=0)
        span = np.maximum(maxs - mins, 1e-6)
        local = (projected - mins) / span
        part = face_parts[face_index]
        cell_x, cell_y = part_to_cell[part]
        u0 = cell_x * cell_size + padding_norm * cell_size
        v0 = cell_y * cell_size + padding_norm * cell_size
        usable = cell_size * (1.0 - 2.0 * padding_norm)
        tri_uv = np.column_stack((u0 + local[:, 0] * usable, v0 + local[:, 1] * usable))
        tri_uv_lightmap = np.column_stack((u0 + 0.05 * usable + local[:, 0] * usable * 0.9, v0 + 0.05 * usable + local[:, 1] * usable * 0.9))
        base = face_index * 3
        uv[base : base + 3] = tri_uv
        uv_lightmap[base : base + 3] = tri_uv_lightmap
        new_face_parts.append(part)

    uv_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    uv_mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv)
    runtime = RuntimeMesh(mesh=uv_mesh, face_parts=new_face_parts, part_colors=runtime_mesh.part_colors, units=runtime_mesh.units)

    uv_sets = []
    requested_sets = list(asset["build"]["uv"].get("sets", ["base"]))
    for name, coords in [("base", uv), ("lightmap", uv_lightmap)]:
        if name not in requested_sets:
            continue
        uv_sets.append({
            "name": name,
            "coverage": {
                "u_min": round(float(coords[:, 0].min()), 6),
                "u_max": round(float(coords[:, 0].max()), 6),
                "v_min": round(float(coords[:, 1].min()), 6),
                "v_max": round(float(coords[:, 1].max()), 6),
            },
            "vertex_count": int(len(coords)),
        })
    texel_density = asset["build"]["uv"].get("texel_density")
    px_per_m = round(_unit_to_px_per_m(texel_density), 6) if texel_density is not None else None
    meta = {
        "uv_sets": uv_sets,
        "packing_report": {
            "chart_count": len(unique_parts),
            "cells": cells,
            "padding_normalized": round(padding_norm, 6),
            "pack_rotate": bool(asset["build"]["uv"].get("pack_rotate", True)),
        },
        "texel_density": {"requested_px_per_m": px_per_m, "actual_px_per_m": px_per_m},
    }
    return runtime, meta


def _export_glb(mesh: trimesh.Trimesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = mesh.export(file_type="glb")
    path.write_bytes(blob)


def _export_gltf(mesh: trimesh.Trimesh, directory: Path, asset_name: str) -> list[Path]:
    payload = mesh.export(file_type="gltf")
    written: list[Path] = []
    for name, data in payload.items():
        out_path = directory / name.replace("model", asset_name)
        if isinstance(data, str):
            out_path.write_text(data, encoding="utf-8")
        else:
            out_path.write_bytes(data)
        written.append(out_path)
    return written


def _export_obj(mesh: trimesh.Trimesh, path: Path) -> None:
    text = mesh.export(file_type="obj")
    path.write_text(text, encoding="utf-8")
    mtl_path = path.with_name("material.mtl")
    if not mtl_path.exists():
        mtl_path.write_text("newmtl material_0\nKd 0.8 0.8 0.8\n", encoding="utf-8")


def _write_usda(mesh: trimesh.Trimesh, path: Path, *, asset_name: str) -> None:
    points = ", ".join(f"({v[0]:.6f}, {v[1]:.6f}, {v[2]:.6f})" for v in mesh.vertices)
    counts = ", ".join("3" for _ in mesh.faces)
    indices = ", ".join(str(int(i)) for i in mesh.faces.reshape(-1))
    uv = None
    if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None:
        uv = mesh.visual.uv
    else:
        uv = np.zeros((len(mesh.vertices), 2), dtype=np.float64)
    st = ", ".join(f"({u:.6f}, {v:.6f})" for u, v in uv)
    st_indices = ", ".join(str(int(i)) for i in mesh.faces.reshape(-1))
    bounds = mesh.bounds
    extent = f"[{_vec3(bounds[0])}, {_vec3(bounds[1])}]"
    text = f'''#usda 1.0
(
    defaultPrim = "{asset_name}"
    upAxis = "Y"
    metersPerUnit = 0.01
)

def Xform "{asset_name}" {{
    def Mesh "mesh" {{
        uniform token subdivisionScheme = "none"
        point3f[] points = [{points}]
        int[] faceVertexCounts = [{counts}]
        int[] faceVertexIndices = [{indices}]
        texCoord2f[] primvars:st = [{st}] (
            interpolation = "vertex"
        )
        int[] primvars:st:indices = [{st_indices}]
        float3[] extent = {extent}
    }}
}}
'''
    path.write_text(text, encoding="utf-8")


def _vec3(values: Iterable[float]) -> str:
    coords = list(values)
    return f"({coords[0]:.6f}, {coords[1]:.6f}, {coords[2]:.6f})"


def _render_mesh_preview(runtime_mesh: RuntimeMesh, path: Path, *, mode: str = "shaded") -> None:
    mesh = runtime_mesh.mesh
    vertices = mesh.vertices
    rotation = _rotation_matrix(math.radians(35.264), math.radians(45.0))
    projected = vertices @ rotation.T
    xy = projected[:, :2]
    z = projected[:, 2]
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    span = np.maximum(bounds_max - bounds_min, 1e-6)
    scale = min((IMAGE_SIZE - 120) / span[0], (IMAGE_SIZE - 120) / span[1])
    screen = (xy - bounds_min) * scale + np.array([60.0, 60.0])
    screen[:, 1] = IMAGE_SIZE - screen[:, 1]
    image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
    draw = ImageDraw.Draw(image, "RGBA")

    triangles = []
    for face_index, face in enumerate(mesh.faces):
        pts = [tuple(screen[idx]) for idx in face]
        depth = float(np.mean(z[face]))
        part = runtime_mesh.face_parts[min(face_index, len(runtime_mesh.face_parts) - 1)] if runtime_mesh.face_parts else "mesh"
        color = runtime_mesh.part_colors.get(part, (140, 160, 190))
        brightness = 0.78 + 0.22 * (0.5 + 0.5 * np.clip(np.dot(mesh.face_normals[face_index], np.array([0.5, 0.7, 0.5])), -1, 1))
        shaded = tuple(min(255, max(0, int(channel * brightness))) for channel in color) + (255,)
        triangles.append((depth, pts, shaded))
    triangles.sort(key=lambda item: item[0])

    if mode in {"shaded", "material_ids"}:
        for _, pts, color in triangles:
            fill = color if mode == "shaded" else color[:3] + (255,)
            draw.polygon(pts, fill=fill, outline=(30, 36, 45, 255))
    if mode == "wireframe":
        for _, pts, _ in triangles:
            draw.line([pts[0], pts[1], pts[2], pts[0]], fill=LINE_COLOR, width=2)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _render_uv_layout(runtime_mesh: RuntimeMesh, path: Path) -> None:
    mesh = runtime_mesh.mesh
    uv = getattr(mesh.visual, "uv", None)
    if uv is None:
        image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
        image.save(path)
        return
    image = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), PREVIEW_BG)
    draw = ImageDraw.Draw(image, "RGBA")
    scale = IMAGE_SIZE - 80
    for face_index, face in enumerate(mesh.faces):
        pts = []
        for vertex_idx in face:
            u, v = uv[vertex_idx]
            pts.append((40 + u * scale, IMAGE_SIZE - (40 + v * scale)))
        part = runtime_mesh.face_parts[min(face_index, len(runtime_mesh.face_parts) - 1)] if runtime_mesh.face_parts else "mesh"
        color = runtime_mesh.part_colors.get(part, (140, 160, 190))
        draw.polygon(pts, outline=(30, 36, 45, 255), fill=color + (140,))
    image.save(path)


def _render_lod_sheet(runtime_mesh: RuntimeMesh, lod_count: int, path: Path) -> None:
    grid = min(4, max(1, lod_count))
    cell = 512
    sheet = Image.new("RGBA", (cell * 2, cell * 2), PREVIEW_BG)
    for idx in range(grid):
        tmp_path = path.parent / f"._lod_{idx}.png"
        _render_mesh_preview(runtime_mesh, tmp_path, mode="shaded")
        img = Image.open(tmp_path).resize((cell, cell))
        x = (idx % 2) * cell
        y = (idx // 2) * cell
        sheet.paste(img, (x, y))
        tmp_path.unlink(missing_ok=True)
    sheet.save(path)


def _rotation_matrix(x_angle: float, y_angle: float) -> np.ndarray:
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(x_angle), -math.sin(x_angle)],
            [0.0, math.sin(x_angle), math.cos(x_angle)],
        ]
    )
    ry = np.array(
        [
            [math.cos(y_angle), 0.0, math.sin(y_angle)],
            [0.0, 1.0, 0.0],
            [-math.sin(y_angle), 0.0, math.cos(y_angle)],
        ]
    )
    return rx @ ry


def _estimate_mass_kg(mesh: trimesh.Trimesh) -> float:
    volume_cm3 = abs(float(mesh.volume)) if mesh.is_volume else float(np.prod(mesh.extents)) * 0.2
    density_g_cm3 = 0.8
    return (volume_cm3 * density_g_cm3) / 1000.0


def _evaluate_rule(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    value = _evaluate_expression(expr, asset, runtime)
    if isinstance(value, bool):
        return value, {"message": f"Rule {'passed' if value else 'failed'}", "value": value}
    if isinstance(value, (int, float)):
        passed = float(value) >= 0.5
        return passed, {"message": f"Numeric rule {'passed' if passed else 'failed'}", "value": value}
    return False, {"message": f"Unsupported rule result: {value!r}"}


def _evaluate_expression(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> Any:
    if isinstance(expr, (bool, int, float, str)):
        if isinstance(expr, str):
            if expr in _predicate_dispatch():
                return _predicate_dispatch()[expr](asset, runtime, {})
            if expr in _metric_dispatch():
                return _metric_dispatch()[expr](asset, runtime)
        return expr
    if isinstance(expr, dict):
        etype = expr.get("type")
        if etype == "call":
            name = expr["name"]
            kwargs = {item["name"] if item.get("name") is not None else f"_{idx}": item["value"] for idx, item in enumerate(expr.get("args", []))}
            if name in _predicate_dispatch():
                return _predicate_dispatch()[name](asset, runtime, kwargs)
            if name in _metric_dispatch():
                return _metric_dispatch()[name](asset, runtime)
            raise BuildError(f"Unsupported builtin '{name}' in runtime evaluator")
        if etype == "range":
            return expr
        if etype == "unary":
            value = _evaluate_expression(expr["value"], asset, runtime)
            if expr["op"] == "not":
                return not bool(value)
            if expr["op"] == "-":
                return -float(value)
        if etype == "binary":
            left = _evaluate_expression(expr["left"], asset, runtime)
            right = _evaluate_expression(expr["right"], asset, runtime)
            op = expr["op"]
            if op == "and":
                return bool(left) and bool(right)
            if op == "or":
                return bool(left) or bool(right)
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "in":
                return left in right
    raise BuildError(f"Unsupported expression: {expr!r}")


def _predicate_dispatch() -> dict[str, Any]:
    return {
        "manifold": lambda asset, runtime, kwargs: bool(runtime["topology"]["bundle"]["mesh_stats"]["watertight"]),
        "watertight": lambda asset, runtime, kwargs: bool(runtime["topology"]["bundle"]["mesh_stats"]["watertight"]),
        "lightmap_uvs": lambda asset, runtime, kwargs: any(item["name"] == "lightmap" for item in runtime["uv"]["bundle"]["uv_sets"]),
        "collision_proxy": lambda asset, runtime, kwargs: bool(runtime["physics"]["bundle"]["collision_proxy"]),
        "material_slots": lambda asset, runtime, kwargs: int(runtime["surface"]["bundle"]["material_slots"]) <= int(kwargs.get("max", 999999)),
        "uv_range": _predicate_uv_range,
        "texel_density": _predicate_texel_density,
        "runtime_budget": _predicate_runtime_budget,
        "pivots": _predicate_pivots,
        "names": _predicate_names,
        "units": lambda asset, runtime, kwargs: kwargs.get("_0") == "cm" or kwargs.get("unit") == "cm",
        "lods": lambda asset, runtime, kwargs: len(runtime["optimize"]["bundle"]["lods"]) >= int(kwargs.get("min", 1)),
        "triangles": lambda asset, runtime, kwargs: int(runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"]) <= int(kwargs.get("max", 99999999)),
        "texture_budget": lambda asset, runtime, kwargs: int(runtime["optimize"]["bundle"]["texture_memory_bytes"]) <= _unit_to_bytes(kwargs.get("max")),
        "socket_count": lambda asset, runtime, kwargs: len(runtime["interfaces"]["bundle"].get("sockets", [])) >= int(kwargs.get("min", 0)),
        "riggable": _predicate_riggable,
    }


def _predicate_uv_range(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    set_name = kwargs.get("set") or kwargs.get("_0")
    target_range = kwargs.get("range")
    if not isinstance(target_range, dict):
        return False
    for uv_set in runtime["uv"]["bundle"]["uv_sets"]:
        if uv_set["name"] != set_name:
            continue
        coverage = uv_set["coverage"]
        return (
            coverage["u_min"] >= float(target_range["from"]) - 1e-6
            and coverage["u_max"] <= float(target_range["to"]) + 1e-6
            and coverage["v_min"] >= float(target_range["from"]) - 1e-6
            and coverage["v_max"] <= float(target_range["to"]) + 1e-6
        )
    return False


def _predicate_texel_density(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    requested = kwargs.get("target")
    tolerance = float(kwargs.get("tolerance", 0.10))
    actual = runtime["uv"]["bundle"]["texel_density"].get("actual_px_per_m")
    if requested is None or actual is None:
        return False
    target_value = _unit_to_px_per_m(requested)
    if target_value == 0:
        return False
    return abs(actual - target_value) / target_value <= tolerance + 1e-9


def _predicate_runtime_budget(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    draw_calls_ok = runtime["optimize"]["bundle"]["draw_calls"] <= int(kwargs.get("draw_calls", 99999999))
    texture_memory_ok = runtime["optimize"]["bundle"]["texture_memory_bytes"] <= _unit_to_bytes(kwargs.get("texture_memory"))
    return draw_calls_ok and texture_memory_ok


def _predicate_names(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    names = [asset["name"]]
    names.extend(asset.get("intent", {}).get("parts", []))
    names.extend(item.get("name") for item in runtime["rig"]["bundle"].get("joints", []))
    names.extend(item.get("name") for item in runtime["interfaces"]["bundle"].get("sockets", []))
    names.extend(item.get("name") for item in runtime["interfaces"]["bundle"].get("anchors", []))
    return all(name is not None and IDENT_RE.match(str(name)) for name in names)


def _predicate_pivots(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    desired_policy = kwargs.get("policy") or kwargs.get("_0") or "auto"
    rig_bundle = runtime["rig"]["bundle"]
    actual_policy = rig_bundle.get("pivot_policy", "auto")
    joints = rig_bundle.get("joints", [])
    if joints:
        return actual_policy == desired_policy and all("pivot" in joint for joint in joints)
    # Static assets still have an object/world pivot even when they have no joint list.
    return actual_policy in {desired_policy, "auto"}


def _predicate_riggable(asset: dict[str, Any], runtime: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    required_parts = kwargs.get("parts", [])
    if not isinstance(required_parts, list):
        return False
    joint_names = {item["name"] for item in runtime["rig"]["bundle"].get("joints", [])}
    return all(part in joint_names for part in required_parts)


def _metric_dispatch() -> dict[str, Any]:
    return {
        "prompt_match": _metric_prompt_match,
        "silhouette_readability": _metric_silhouette_readability,
        "topology_quality": _metric_topology_quality,
        "material_quality": _metric_material_quality,
        "runtime_efficiency": _metric_runtime_efficiency,
        "part_coherence": _metric_part_coherence,
        "uv_quality": _metric_uv_quality,
        "assembly_compatibility": _metric_assembly_compatibility,
        "surface_consistency": _metric_surface_consistency,
    }


def _metric_prompt_match(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    expected_parts = set(asset.get("intent", {}).get("parts", []))
    actual_parts = {group["name"] for group in runtime["topology"]["bundle"].get("part_groups", [])}
    part_ratio = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    return round(
        min(
            1.0,
            0.26
            + 0.22 * part_ratio
            + 0.16 * visual.get("silhouette_complexity", 0.0)
            + 0.12 * (1.0 - visual.get("primitive_likeness_penalty", 0.0))
            + 0.08 * visual.get("attachment_integration_quality", 0.0),
        ),
        6,
    )


def _metric_silhouette_readability(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        return round(
            min(
                1.0,
                0.60 * float(runtime["semantic_quality"]["metrics"]["silhouette_fidelity"])
                + 0.25 * visual.get("silhouette_complexity", 0.0)
                + 0.15 * visual.get("edge_readability", 0.0),
            ),
            6,
        )
    extents = runtime["topology"]["bundle"]["mesh_stats"]["extents"]
    largest = max(extents)
    smallest = max(1e-6, min(extents))
    ratio = smallest / largest
    return round(max(0.7, min(0.98, 0.7 + 0.4 * ratio)), 6)


def _metric_topology_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        metrics = runtime["semantic_quality"]["metrics"]
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        score = (
            0.22 * metrics["structural_richness"]
            + 0.16 * metrics["component_score"]
            + 0.18 * metrics["symmetry_score"]
            + 0.14 * metrics["adjacency_score"]
            + 0.12 * (1.0 - metrics["fragmentation_penalty"])
            + 0.10 * visual.get("detail_density", 0.0)
            + 0.04 * visual.get("edge_readability", 0.0)
            + 0.14 * visual.get("geometry_integration_quality", 0.0)
        )
        if metrics["toy_detected"]:
            score -= 0.18
        score -= 0.10 * visual.get("primitive_likeness_penalty", 0.0)
        score -= 0.08 * visual.get("assembled_primitives_penalty", 0.0)
        return round(min(1.0, max(0.0, score)), 6)
    stats = runtime["topology"]["bundle"]["mesh_stats"]
    score = 0.6
    if stats["watertight"]:
        score += 0.25
    if stats["body_count"] >= 1:
        score += 0.1
    if stats["triangle_count"] > 0:
        score += 0.05
    return round(min(score, 1.0), 6)


def _metric_material_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    maps = runtime["surface"]["bundle"].get("maps", [])
    workflow = runtime["surface"]["bundle"]["surface_manifest"].get("workflow")
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    score = 0.30
    if workflow in {"pbr_metal_rough", "pbr_spec_gloss"}:
        score += 0.08
    score += 0.012 * min(5, len(maps))
    score += 0.06 * visual.get("feature_coherence", 0.0)
    score += 0.22 * visual.get("surface_authoring_quality", 0.0)
    score += 0.10 * visual.get("surface_material_zone_coherence", 0.0)
    return round(min(score, 0.74), 6)


def _metric_runtime_efficiency(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    tris = runtime["topology"]["bundle"]["mesh_stats"]["triangle_count"]
    draw_calls = runtime["optimize"]["bundle"]["draw_calls"]
    score = 1.0
    score -= min(0.15, tris / 500000.0)
    score -= min(0.1, draw_calls * 0.03)
    return round(max(0.7, score), 6)


def _metric_part_coherence(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if runtime.get("semantic_quality"):
        metrics = runtime["semantic_quality"]["metrics"]
        visual = runtime.get("visual_quality", {}).get("metrics", {})
        return round(
            min(
                1.0,
                0.28 * metrics["part_coverage"]
                + 0.16 * metrics["symmetry_score"]
                + 0.14 * metrics["interface_score"]
                + 0.14 * metrics["adjacency_score"]
                + 0.08 * (1.0 - metrics["fragmentation_penalty"])
                + 0.10 * visual.get("attachment_integration_quality", 0.0)
                + 0.10 * visual.get("support_plausibility", 0.0),
            ),
            6,
        )
    expected_parts = set(asset.get("intent", {}).get("parts", []))
    actual_parts = {group["name"] for group in runtime["topology"]["bundle"].get("part_groups", [])}
    ratio = len(expected_parts & actual_parts) / max(1, len(expected_parts))
    return round(min(1.0, 0.8 + 0.2 * ratio), 6)


def _metric_uv_quality(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    if not runtime["uv"]["bundle"]["uv_sets"]:
        return 0.0
    base = runtime["uv"]["bundle"]["uv_sets"][0]["coverage"]
    in_range = all(0.0 <= base[key] <= 1.0 for key in base)
    return 0.95 if in_range else 0.4


def _metric_assembly_compatibility(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    sockets = len(runtime["interfaces"]["bundle"].get("sockets", []))
    anchors = len(runtime["interfaces"]["bundle"].get("anchors", []))
    return round(min(1.0, 0.75 + 0.05 * (sockets + anchors)), 6)


def _metric_surface_consistency(asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    semantic = len(runtime["surface"]["bundle"]["surface_manifest"].get("semantic_materials", []))
    visual = runtime.get("visual_quality", {}).get("metrics", {})
    return round(
        min(
            0.95,
            0.54
            + 0.03 * semantic
            + 0.18 * visual.get("surface_authoring_quality", 0.0)
            + 0.10 * visual.get("surface_material_zone_coherence", 0.0),
        ),
        6,
    )


def _evaluate_metric(expr: Any, asset: dict[str, Any], runtime: dict[str, Any]) -> float:
    value = _evaluate_expression(expr, asset, runtime)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    raise BuildError(f"Metric expression did not resolve to score: {expr!r}")


def _evaluate_critic(name: Any, asset: dict[str, Any], runtime: dict[str, Any], critics: dict[str, Any], rules: list[dict[str, Any]]) -> float:
    if not name:
        prefer_rules = [rule for rule in rules if rule.get("kind") == "prefer"]
        if not prefer_rules:
            return 1.0
        total_weight = sum(float(rule.get("weight", 1.0)) for rule in prefer_rules)
        if total_weight <= 0:
            return 0.0
        total = 0.0
        for rule in prefer_rules:
            weight = float(rule.get("weight", 1.0)) / total_weight
            total += _evaluate_metric(rule["expr"], asset, runtime) * weight
        return round(total, 6)
    if name not in critics:
        raise BuildError(f"Unknown critic '{name}'")
    critic = critics[name]
    body = critic.get("body")
    if isinstance(body, dict) and body.get("type") == "weighted":
        total_weight = sum(float(item.get("weight", 0.0)) for item in body.get("items", []))
        if total_weight <= 0:
            return 0.0
        total = 0.0
        for item in body.get("items", []):
            metric = item["metric"]
            score = _metric_dispatch()[metric](asset, runtime)
            total += score * (float(item.get("weight", 0.0)) / total_weight)
        return round(total, 6)
    return _evaluate_metric(body, asset, runtime)
