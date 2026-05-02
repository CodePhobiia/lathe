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
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .asset_quality.kit_library import KitLibrary, load_kit_library
from .asset_quality.quality_planner import build_generation_quality_context
from .asset_quality.reference_board import (
    load_reference_board,
    make_reference_board_error,
    reference_board_fingerprint,
)
from .cache_paths import CACHE_MANIFEST_FILENAME, lathe_cache_dir
from .capabilities import deterministic_backend_reports, probe_topology_backend  # noqa: F401
from .checker import check_program
from .core.common import dump_json, hash_obj, relpath
from .core.errors import BuildError
from .core.geometry import (
    run_reference_topology_cleanup as _run_reference_topology_cleanup,
)
from .core.mesh import RuntimeMesh
from .core.stages import (
    execution as stage_execution,
)
from .core.stages import (
    interfaces as stage_interfaces,
)
from .core.stages import (
    optimize as stage_optimize,
)
from .core.stages import (
    package as stage_package,
)
from .core.stages import (
    physics as stage_physics,
)
from .core.stages import (
    rig as stage_rig,
)
from .core.stages import (
    shape as stage_shape,
)
from .core.stages import (
    surface as stage_surface,
)
from .core.stages import (
    topology as stage_topology,
)
from .core.stages import (
    uv as stage_uv,
)
from .core.stages import (
    validate as stage_validate,
)
from .core.stages.topology import run_blender_topology as _run_blender_topology  # noqa: F401
from .logging_utils import debug as log_debug
from .normalizer import normalize_program
from .planner import build_plan
from .providers import list_shape_providers
from .resolver import Resolver
from .runtime_config import merge_runtime_config
from .security import redact_secrets
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


BUILD_CACHE_ROOT = lathe_cache_dir() / "builds"
BUILD_CACHE_VERSION = "v13_rc1"
log = logging.getLogger(__name__)


__all__ = [
    "STAGE_ORDER",
    "BuildError",
    "BuildExecutor",
    "RuntimeMesh",
    "_run_reference_topology_cleanup",
    "build_asset",
    "build_surface_stage",
    "repair_surface_stage",
    "validate_surface_stage",
]


def _stable_probe_fingerprint(probe: dict[str, Any]) -> dict[str, Any]:
    """Keep cache fingerprints capability-shaped, not host-path-shaped."""
    allowed = {
        "available",
        "code",
        "version",
        "python_module_available",
        "supported_modes",
        "gpu_cpu_render_capability",
        "cuda_available",
        "cuda_version",
        "torchvision_available",
    }
    return {key: probe.get(key) for key in sorted(allowed) if key in probe}


def _build_cache_root() -> Path:
    """Resolve the build-cache root at use time so env overrides stay live."""
    return lathe_cache_dir() / "builds"


def _deterministic_backend_fingerprint(runtime_config: dict[str, Any]) -> list[dict[str, Any]]:
    reports = deterministic_backend_reports(runtime_config)
    fingerprint: list[dict[str, Any]] = []
    for report in sorted(reports, key=lambda item: str(item.get("backend_id", ""))):
        probe = report.get("probe", {})
        if not isinstance(probe, dict):
            probe = {}
        fingerprint.append(
            {
                "backend_id": report.get("backend_id"),
                "requested_adapter": report.get("requested_adapter"),
                "selected_adapter": report.get("selected_adapter"),
                "strict": report.get("strict"),
                "available": report.get("available"),
                "real_adapter_available": report.get("real_adapter_available"),
                "fallback_available": report.get("fallback_available"),
                "probe": _stable_probe_fingerprint(probe),
            }
        )
    return fingerprint


def _selected_backend_fingerprint(selected_backends: dict[str, Any]) -> dict[str, Any]:
    return {
        stage: {
            "id": data.get("id"),
            "version": data.get("version"),
            "determinism_class": data.get("determinism_class"),
            "runtime_executor": data.get("runtime_executor"),
            "toolchain": list(data.get("toolchain", [])),
            "format_routes": data.get("format_routes", {}),
            "contract": data.get("contract", {}),
        }
        for stage, data in sorted(selected_backends.items())
    }


def _shape_provider_registry_fingerprint() -> list[dict[str, Any]]:
    providers = []
    for provider in list_shape_providers():
        providers.append(
            {
                "id": provider.get("id"),
                "version": provider.get("version"),
                "learned": provider.get("learned"),
                "modes": list(provider.get("modes", [])),
            }
        )
    return sorted(providers, key=lambda item: str(item.get("id", "")))


def _strict_highlow_cache_flag() -> bool:
    raw = os.environ.get("LATHE_STRICT_HIGHLOW")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes"}


def _safe_load_reference_board(
    asset_name: str, experimental_path: str | None = None
) -> dict[str, Any] | None:
    """Load the Phase 11 reference board without crashing the build.

    Wraps :func:`lathe.asset_quality.reference_board.load_reference_board`
    in a permissive try/except so a corrupt fixture or filesystem
    error never breaks the executor's lifecycle. Any unexpected
    exception is swallowed and ``None`` is published — the validator
    then emits a structured ``reference_board_not_loaded`` skipped
    reason in place of the missing board.

    Phase 13: when ``experimental_path`` is provided (resolved by the
    resolver from ``asset.experimental.references.use``) the loader
    uses it as the per-asset directory and the convention base path
    is bypassed.
    """
    try:
        if experimental_path:
            from pathlib import Path as _Path

            override = _Path(experimental_path)
            return load_reference_board(override.name, base_path=override.parent)
        return load_reference_board(asset_name)
    except Exception as exc:  # pragma: no cover - defensive guard
        return make_reference_board_error(
            asset_name,
            message=f"Reference board loader failed unexpectedly: {exc}",
            path=experimental_path,
        )


def _safe_load_kit_library() -> KitLibrary | None:
    """Load the Phase 12 kit library without crashing the build.

    Wraps :func:`lathe.asset_quality.kit_library.load_kit_library`
    in a permissive try/except. Any unexpected exception is swallowed
    and ``None`` is published — the validator then emits a structured
    ``kit_library_not_loaded`` skipped reason in place of the missing
    library.
    """
    try:
        return load_kit_library()
    except Exception:  # pragma: no cover - defensive guard
        return None


class BuildExecutor:
    """BuildExecutor."""

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
        self.asset = self.resolver.materialize_asset(
            asset_name, execution_profile_override=execution_profile_override
        )
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
            "_quality_generation": {},
        }
        self.critics = {critic["name"]: critic for critic in program.get("critics", [])}
        self.stage_dirs = {stage: self.out_dir / "stages" / stage for stage in STAGE_ORDER}
        self.cache_key = hash_obj(
            {
                "cache_version": BUILD_CACHE_VERSION,
                "program": self.normalized_program,
                "asset": self.asset_name,
                "runtime_config": self.runtime_config,
                "build_environment": self._build_cache_environment_fingerprint(),
            }
        )
        self.cache_dir = _build_cache_root() / self.cache_key

    def _build_cache_environment_fingerprint(self) -> dict[str, Any]:
        return {
            "selected_backends": _selected_backend_fingerprint(self.selected_backends),
            "deterministic_backends": _deterministic_backend_fingerprint(self.runtime_config),
            "shape_providers": _shape_provider_registry_fingerprint(),
            "asset_quality": {
                "strict_highlow": _strict_highlow_cache_flag(),
                "reference_board": self._reference_board_cache_fingerprint(),
            },
        }

    def _reference_board_cache_fingerprint(self) -> dict[str, Any]:
        experimental_refs = self.asset.get("experimental", {}).get("references", {})
        experimental_refs_path = (
            experimental_refs.get("_resolved_path") if isinstance(experimental_refs, dict) else None
        )
        if experimental_refs_path and isinstance(experimental_refs_path, str):
            override = Path(experimental_refs_path)
            return {
                "source": "experimental.references.use",
                **reference_board_fingerprint(override.name, base_path=override.parent),
            }
        experimental_refs_use = experimental_refs.get("use") if isinstance(experimental_refs, dict) else None
        if isinstance(experimental_refs_use, str) and experimental_refs_use:
            return {
                "source": "experimental.references.use",
                "status": "invalid_path",
                "use": experimental_refs_use,
                "files": {},
            }
        return {
            "source": "default_convention",
            **reference_board_fingerprint(self.asset_name),
        }

    def _publish_reference_board_context(self) -> None:
        """Publish reference-board context before generation and validation."""
        experimental_refs = self.asset.get("experimental", {}).get("references", {})
        experimental_refs_path = (
            experimental_refs.get("_resolved_path") if isinstance(experimental_refs, dict) else None
        )
        experimental_refs_use = experimental_refs.get("use") if isinstance(experimental_refs, dict) else None
        if experimental_refs_path and isinstance(experimental_refs_path, str):
            self.runtime["_reference_board"] = _safe_load_reference_board(
                self.asset_name, experimental_path=experimental_refs_path
            )
            self.runtime["_reference_board_user_provided_via_experimental"] = True
        elif isinstance(experimental_refs_use, str) and experimental_refs_use:
            self.runtime["_reference_board"] = make_reference_board_error(
                self.asset_name,
                reason="reference_invalid_path",
                message=(
                    "experimental.references.use did not resolve to a contained "
                    f"reference directory: {experimental_refs_use}"
                ),
                path=experimental_refs_use,
            )
            self.runtime["_reference_board_user_provided_via_experimental"] = True
        else:
            self.runtime["_reference_board"] = _safe_load_reference_board(self.asset_name)
            self.runtime["_reference_board_user_provided_via_experimental"] = False

    def _publish_pre_shape_quality_context(self) -> None:
        """Build Phase 14C art-direction quality context before shape generation."""
        self._publish_reference_board_context()
        quality_generation = build_generation_quality_context(self.asset, self.runtime)
        self.runtime["_quality_generation"] = quality_generation
        if self.out_dir.exists():
            dump_json(self.out_dir / "quality_generation_context.json", quality_generation)

    def build(self) -> dict[str, Any]:
        """Build.

        Returns:
            The result.
        """
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

        self._publish_pre_shape_quality_context()
        shape_bundle = stage_shape.run(self)
        topology_bundle = stage_topology.run(self, shape_bundle)
        uv_bundle = stage_uv.run(self, topology_bundle)
        surface_bundle = stage_surface.run(self, uv_bundle)
        rig_bundle = stage_rig.run(self, surface_bundle)
        interfaces_bundle = stage_interfaces.run(self, rig_bundle)
        physics_bundle = stage_physics.run(self, interfaces_bundle)
        optimize_bundle = stage_optimize.run(self, physics_bundle)
        stage_execution.run(self, optimize_bundle)
        # Phase 10: publish a redacted snapshot of the runtime config so the
        # vision-critique validator can read the optional ``vision_critique``
        # provider block without ever seeing raw api keys / endpoints.
        self.runtime["_runtime_config"] = redact_secrets(self.runtime_config)
        # Phase 11: publish the reference / moodboard fixtures so the
        # validator can build the additive ``reference_board`` payload and
        # the design-brief layer can merge reference negatives.
        # Phase 13: honor the optional experimental override path.
        self._publish_reference_board_context()
        # Phase 12: publish the standard hard-surface kit library so the
        # validator can build the additive ``kit_library`` payload.
        self.runtime["_kit_library"] = _safe_load_kit_library()
        validate_bundle = stage_validate.run(self, optimize_bundle)
        repair_rounds: list[dict[str, Any]] = []
        if not validate_bundle["certified"]:
            repair_cfg = self.runtime_config.get("repair") or {}
            if repair_cfg.get("autonomous", True):
                from .repair_loop import run_repair_loop

                validate_bundle, repair_rounds = run_repair_loop(
                    self,
                    validate_bundle,
                    max_rounds=int(repair_cfg.get("max_rounds", 3)),
                    min_improvement=float(repair_cfg.get("min_improvement", 0.01)),
                    budget_seconds=float(repair_cfg.get("budget_seconds", 180.0)),
                )
                # Refresh optimize/execution bundles in case a round regenerated the stack.
                optimize_bundle = self.runtime.get("optimize", {}).get("bundle", optimize_bundle)
                stage_execution.run(self, optimize_bundle)
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
            "runtime_config": redact_secrets(self.runtime_config),
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
            "repair_rounds": repair_rounds,
            "optimize": {
                "lod_manifest_path": optimize_bundle.get("lod_manifest_path"),
                "lods": optimize_bundle.get("lods"),
                "collision": optimize_bundle.get("collision"),
            },
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
        """Build surface stage.

        Args:
            repair_mode: repair_mode argument.

        Returns:
            The result.
        """
        self._prepare_uncached_build()
        self._publish_pre_shape_quality_context()
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
        """Validate surface stage.

        Returns:
            The result.
        """
        surface_result = self.build_surface_stage()
        report = evaluate_surface_quality(self.asset, self.runtime)
        dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": report["ok"],
            "surface_bundle_path": surface_result["surface_bundle_path"],
            "surface_quality_report_path": relpath(
                self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"
            ),
            "surface_validation_ir": self.runtime["surface"]["bundle"].get("surface_validation_ir", {}),
            "metrics": report["metrics"],
            "diagnostics": report["diagnostics"],
        }

    def repair_surface_stage(self) -> dict[str, Any]:
        """Repair surface stage.

        Returns:
            The result.
        """
        initial = self.validate_surface_stage()
        if initial["ok"]:
            return {**initial, "repaired": False, "repair_reason": "surface_already_valid"}
        repaired_bundle = stage_surface.run(
            self, self.runtime["uv"]["bundle"], repair_mode="surface_enhance_v1"
        )
        repaired_report = evaluate_surface_quality(self.asset, self.runtime)
        dump_json(self.stage_dirs["surface"] / "surface_quality_report.json", repaired_report)
        return {
            "asset": self.asset_name,
            "out_dir": str(self.out_dir),
            "ok": repaired_report["ok"],
            "repaired": True,
            "repair_reason": "surface_enhance_v1",
            "surface_bundle_path": relpath(self.out_dir, self.stage_dirs["surface"] / "bundle.json"),
            "surface_quality_report_path": relpath(
                self.out_dir, self.stage_dirs["surface"] / "surface_quality_report.json"
            ),
            "surface_repair_ir": repaired_bundle.get("surface_repair_ir", {}),
            "before": {
                "ok": initial["ok"],
                "metrics": initial["metrics"],
                "diagnostics": initial["diagnostics"],
            },
            "after": {
                "ok": repaired_report["ok"],
                "metrics": repaired_report["metrics"],
                "diagnostics": repaired_report["diagnostics"],
            },
        }

    def _restore_cached_build(self) -> dict[str, Any] | None:
        if not self.cache_dir.exists():
            return None
        cached_report_path = self.cache_dir / "build_report.json"
        if not cached_report_path.is_file():
            return None
        try:
            report = json.loads(cached_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(report, dict):
            return None
        manifest_path = self.cache_dir / CACHE_MANIFEST_FILENAME
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if not isinstance(manifest, dict):
                return None
            if manifest.get("cache_version") != BUILD_CACHE_VERSION:
                return None
            if manifest.get("cache_key") not in (None, self.cache_key):
                return None
        try:
            if self.out_dir.exists():
                shutil.rmtree(self.out_dir)
            self.out_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.cache_dir, self.out_dir)
            report_path = self.out_dir / "build_report.json"
            if report_path.exists():
                # JSON ingress — internal controlled payload from our own cached build_report.json (copytree'd from a prior build out_dir); safe without schema validation.
                report["out_dir"] = str(self.out_dir)
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                return report
        except (OSError, shutil.Error):
            return None
        return None

    def _persist_build_cache(self) -> None:
        staging_dir: Path | None = None
        try:
            self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
            if self.cache_dir.exists():
                return
            staging_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{self.cache_key}.",
                    suffix=".tmp",
                    dir=self.cache_dir.parent,
                )
            )
            shutil.rmtree(staging_dir)
            shutil.copytree(self.out_dir, staging_dir)
            dump_json(staging_dir / CACHE_MANIFEST_FILENAME, self._cache_manifest())
            staging_dir.rename(self.cache_dir)
            staging_dir = None
        except (OSError, shutil.Error) as exc:
            # Caching is best-effort; surface IO/permission/dest-exists failures
            # as debug diagnostics rather than aborting the build.
            log_debug(
                log,
                "lathe.executor.cache_persist_failed",
                "failed to persist build cache at {cache_dir}: {error}",
                cache_dir=self.cache_dir,
                error=exc,
            )
        finally:
            if staging_dir is not None:
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _cache_manifest(self) -> dict[str, Any]:
        variant_name = None
        for variant in self.program.get("variants", []) or []:
            if isinstance(variant, dict) and variant.get("name") == self.asset_name:
                variant_name = self.asset_name
                break
        return {
            "schema": "lathe.cache_manifest.v1",
            "cache_version": BUILD_CACHE_VERSION,
            "cache_key": self.cache_key,
            "asset": self.asset_name,
            "variant": variant_name,
            "kind": self.asset.get("kind"),
            "backend_stack": self.backend_stack,
            "source_fingerprint": hash_obj(self.normalized_program),
            "created_time": time.time(),
        }

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
        attempts.append(
            {
                "candidate_id": self.runtime["shape"]["bundle"].get("selected_candidate_id"),
                "reason": "surface_reauthor_repair",
                "score": repaired_validate.get("score"),
            }
        )
        return (
            surface_bundle,
            rig_bundle,
            interfaces_bundle,
            physics_bundle,
            optimize_bundle,
            repaired_validate,
        )

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
    """Build asset.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        out_dir: out_dir argument.
        runtime_config: runtime_config argument.
        execution_profile_override: execution_profile_override argument.

    Returns:
        The result.
    """
    return BuildExecutor(
        program,
        asset_name,
        out_dir,
        runtime_config=runtime_config,
        execution_profile_override=execution_profile_override,
    ).build()


def build_surface_stage(
    program: dict[str, Any],
    asset_name: str,
    out_dir: str | Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build surface stage.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        out_dir: out_dir argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).build_surface_stage()


def validate_surface_stage(
    program: dict[str, Any],
    asset_name: str,
    out_dir: str | Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate surface stage.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        out_dir: out_dir argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).validate_surface_stage()


def repair_surface_stage(
    program: dict[str, Any],
    asset_name: str,
    out_dir: str | Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Repair surface stage.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        out_dir: out_dir argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    return BuildExecutor(program, asset_name, out_dir, runtime_config=runtime_config).repair_surface_stage()
