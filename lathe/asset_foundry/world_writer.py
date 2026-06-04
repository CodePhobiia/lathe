"""`.lthworld` writer for multi-asset Forge compositions.

The writer defines the world package boundary without generating
geometry. It writes parseable sidecars, records missing visual/import
artifacts as explicit ``not_verified`` statuses, and signs the world
directory so downstream tools can detect drift.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..forge import (
    WorldComposition,
    traversal_evidence_from_composition,
    write_asset_canonical_previews,
    write_hero_sunset_png,
    write_minimap_png,
)
from .capability_matrix import build_capability_matrix, capability_matrix_to_dict
from .runtime.signed_package import (
    SignedWorldEnvelope,
    sign_lthworld_directory,
    verify_lthworld_signature,
)
from .world_member_packages import package_results_to_links, package_world_members
from .world_certificate import compute_world_certificate

LTHWORLD_VERSION = "lathe.asset_foundry.lthworld_v1"


@dataclass(frozen=True)
class LthworldWriteResult:
    """Result returned by ``write_lthworld``."""

    world_dir: str
    world_id: str
    files: Mapping[str, str]
    signature_valid: bool
    signature_reason: str
    certified: bool
    certification_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_dir": self.world_dir,
            "world_id": self.world_id,
            "files": dict(self.files),
            "signature_valid": self.signature_valid,
            "signature_reason": self.signature_reason,
            "certified": self.certified,
            "certification_status": self.certification_status,
        }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _capability_matrix_summary() -> dict[str, Any]:
    matrix = build_capability_matrix()
    payload = capability_matrix_to_dict(matrix)
    canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return {
        "version": matrix.version,
        "record_count": matrix.record_count,
        "counts_by_status": dict(matrix.counts_by_status),
        "counts_by_claim_level": dict(matrix.counts_by_claim_level),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _repro_evidence(composition: WorldComposition, mode: str) -> dict[str, Any]:
    return {
        "version": "lathe.asset_foundry.lthworld_repro_evidence_v1",
        "world_id": composition.world_id,
        "prompt": composition.prompt,
        "seed": composition.seed,
        "mode": mode,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "forge_version": composition.version,
        "lthworld_version": LTHWORLD_VERSION,
        "style_pack_id": composition.style.style_pack_id,
        "kit_id": composition.style.kit_id,
        "generator_ids": sorted({asset.generator_id for asset in composition.assets}),
        "capability_matrix": _capability_matrix_summary(),
        "determinism": {
            "timestamps_in_signature_digest": False,
            "world_graph_uses_timestamps": False,
        },
    }


def _visual_quality_gate(certificate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": "lathe.asset_foundry.lthworld_visual_quality_gate_v1",
        "world_id": certificate["world_id"],
        "target_level": certificate["target_level"],
        "achieved_level": certificate["achieved_level"],
        "certified": certificate["certified"],
        "status": "approved" if certificate["certified"] else "not_verified",
        "reason": (
            "world_certificate_certified"
            if certificate["certified"]
            else "world_certificate_has_blocking_or_not_verified_findings"
        ),
        "metrics": dict(certificate["metrics"]),
        "findings": list(certificate["findings"]),
        "repair_recommendations": list(certificate["repair_recommendations"]),
        "style_compatibility": dict(certificate["style_compatibility"]),
    }


def _engine_import_placeholder(world_dir: Path) -> tuple[dict[str, Any], str]:
    payload = {
        "version": "lathe.asset_foundry.engine_import_evidence_v1",
        "status": "not_verified",
        "reason": "no_engine_or_validator_import_log_supplied",
        "accepted_lanes": ["roblox", "unity", "usd", "gltf"],
    }
    rel_path = "engine_import_evidence/not_verified.json"
    _write_json(world_dir / rel_path, payload)
    return payload, rel_path


def _engine_import_evidence(
    world_dir: Path,
    *,
    proxy_gltf_validation: bool,
    validator_workdir: Path,
) -> tuple[dict[str, Any], str]:
    if not proxy_gltf_validation:
        return _engine_import_placeholder(world_dir)
    package_marker = validator_workdir / "node_modules" / "gltf-validator"
    if not package_marker.exists():
        payload, rel_path = _engine_import_placeholder(world_dir)
        payload = {
            **payload,
            "reason": "gltf_validator_node_package_missing",
            "validator_workdir": str(validator_workdir).replace("\\", "/"),
        }
        _write_json(world_dir / rel_path, payload)
        return payload, rel_path
    try:
        from .engine_import_evidence import validate_gltf, write_proxy_gltf

        evidence_dir = world_dir / "engine_import_evidence"
        gltf_path = evidence_dir / "skyborne_proxy_scene.gltf"
        export_summary = write_proxy_gltf(world_dir, gltf_path)
        validation = validate_gltf(gltf_path, validator_workdir=validator_workdir)
        payload = {
            "version": "lathe.skyborne.gltf_validation_evidence_v1",
            "status": validation["status"],
            "claim_level": "proxy",
            "world_id": json.loads((world_dir / "world_graph.json").read_text(encoding="utf-8"))[
                "world_id"
            ],
            "gltf_path": "engine_import_evidence/skyborne_proxy_scene.gltf",
            "export_summary": {
                **dict(export_summary),
                "path": "engine_import_evidence/skyborne_proxy_scene.gltf",
            },
            "validator": validation,
            "rule_of_truth": (
                "This validates a proxy glTF scene generated from the Forge world graph. "
                "It is real Khronos validator evidence for transform/package handoff, "
                "not final per-member mesh import evidence."
            ),
        }
        rel_path = "engine_import_evidence/gltf_validation_evidence.json"
        _write_json(world_dir / rel_path, payload)
        return payload, rel_path
    except Exception as exc:
        payload, rel_path = _engine_import_placeholder(world_dir)
        payload = {
            **payload,
            "reason": "gltf_proxy_validation_failed",
            "error": str(exc),
        }
        _write_json(world_dir / rel_path, payload)
        return payload, rel_path


def _world_evidence(
    composition: WorldComposition,
    *,
    canonical_render_evidence: Mapping[str, Any],
    minimap_evidence: Mapping[str, Any],
    hero_render_evidence: Mapping[str, Any],
    wonder_critique_trace: Mapping[str, Any],
    engine_import_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    repair_histories: list[dict[str, str]] = []
    if wonder_critique_trace.get("status") == "real":
        world_asset_id = str(wonder_critique_trace.get("world_asset_id") or "")
        repair_histories.append(
            {
                "world_asset_id": world_asset_id,
                "asset_id": str(wonder_critique_trace.get("asset_id") or ""),
                "path": f"assets/{str(wonder_critique_trace.get('asset_id') or '')}.lthpkg/repair-history.json",
                "status": "real",
            }
        )
    return {
        "version": "lathe.asset_foundry.lthworld_evidence_v1",
        "world_id": composition.world_id,
        "status": "partial"
        if engine_import_evidence.get("status") == "not_verified"
        else "real",
        "world_renders": {
            "hero_sunset": dict(hero_render_evidence),
            "minimap": dict(minimap_evidence),
        },
        "asset_canonical_view_renders": dict(canonical_render_evidence),
        "wonder_critique_trace": {
            "status": str(wonder_critique_trace.get("status") or "not_verified"),
            "path": "wonder_critique_trace.json",
            "accepted_rounds": int(
                dict(wonder_critique_trace.get("summary") or {}).get("accepted_rounds") or 0
            ),
            "level_delta": int(
                dict(wonder_critique_trace.get("summary") or {}).get("level_delta") or 0
            ),
        },
        "repair_histories": repair_histories,
        "engine_import_evidence": dict(engine_import_evidence),
        "rule_of_truth": (
            "World evidence only marks generated PNGs and repair traces real when the files "
            "exist and are signed; proxy engine import remains explicit."
        ),
    }


def _copy_assets(
    world_dir: Path,
    assets: Mapping[str, str | Path] | None,
) -> dict[str, dict[str, str]]:
    copied: dict[str, dict[str, str]] = {}
    if not assets:
        return copied
    assets_dir = world_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for world_asset_id, source in sorted(assets.items()):
        source_path = Path(source)
        if not source_path.is_dir():
            copied[world_asset_id] = {
                "status": "missing",
                "source": str(source_path),
                "reason": "asset_package_directory_missing",
            }
            continue
        target = assets_dir / source_path.name
        if target.exists():
            copied[world_asset_id] = {
                "status": "blocked",
                "source": str(source_path),
                "target": str(target),
                "reason": "target_asset_package_already_exists",
            }
            continue
        shutil.copytree(source_path, target)
        copied[world_asset_id] = {
            "status": "linked",
            "source": str(source_path),
            "target": str(target.relative_to(world_dir)).replace("\\", "/"),
        }
    return copied


def _world_manifest(
    composition: WorldComposition,
    *,
    sidecars: Mapping[str, str],
    asset_links: Mapping[str, Mapping[str, str]],
    certificate: Mapping[str, Any],
    minimap_evidence: Mapping[str, Any],
    hero_render_evidence: Mapping[str, Any],
    traversal_evidence: Mapping[str, Any],
    wonder_critique_trace: Mapping[str, Any],
    engine_import_evidence: Mapping[str, Any],
    engine_import_path: str,
    mode: str,
) -> dict[str, Any]:
    return {
        "version": LTHWORLD_VERSION,
        "world_id": composition.world_id,
        "prompt": composition.prompt,
        "seed": composition.seed,
        "mode": mode,
        "style_pack_id": composition.style.style_pack_id,
        "kit_id": composition.style.kit_id,
        "asset_count": composition.asset_count(),
        "role_counts": composition.role_counts(),
        "style_pack_ids": list(composition.style_pack_ids()),
        "sidecar_files": dict(sidecars),
        "world_graph_status": "real",
        "traversal_status": str(traversal_evidence.get("nav_status") or "not_verified"),
        "visual_claim_level": "pipeline_certified_only"
        if certificate["achieved_level"] >= 5
        else "not_verified",
        "world_certificate": certificate,
        "style_compatibility": certificate["style_compatibility"],
        "certified": bool(certificate["certified"]),
        "asset_package_summary": {
            "total": composition.asset_count(),
            "linked": sum(1 for entry in asset_links.values() if entry.get("status") == "linked"),
            "planned": composition.asset_count()
            - sum(1 for entry in asset_links.values() if entry.get("status") == "linked"),
            "links": dict(asset_links),
        },
        "artifact_statuses": {
            "hero_sunset.png": {
                "status": hero_render_evidence.get("status", "not_verified"),
                "path": "hero_sunset.png",
                "sha256": hero_render_evidence.get("sha256", ""),
                "style_reference_comparison_status": hero_render_evidence.get(
                    "style_reference_comparison_status",
                    "not_verified",
                ),
                "reason": ""
                if hero_render_evidence.get("status") == "real"
                else "hero_render_not_generated",
            },
            "minimap.png": {
                "status": minimap_evidence.get("status", "not_verified"),
                "path": "minimap.png",
                "sha256": minimap_evidence.get("sha256", ""),
                "reason": ""
                if minimap_evidence.get("status") == "real"
                else "minimap_render_not_generated",
            },
            "engine_import_evidence": {
                "status": str(engine_import_evidence.get("status") or "not_verified"),
                "path": engine_import_path,
                "claim_level": str(engine_import_evidence.get("claim_level") or "not_verified"),
                "reason": ""
                if certificate["metrics"]["engine_import_evidence"] >= 1.0
                else str(engine_import_evidence.get("reason") or "no_import_validator_log_supplied"),
            },
            "wonder_critique_trace": {
                "status": wonder_critique_trace.get("status", "not_verified"),
                "path": "wonder_critique_trace.json",
                "reason": ""
                if wonder_critique_trace.get("status") == "real"
                else str(wonder_critique_trace.get("reason") or "wonder_critique_not_run"),
            },
        },
        "diagnostics": [dict(d) for d in composition.diagnostics],
    }


def write_lthworld(
    composition: WorldComposition,
    out_dir: str | Path,
    *,
    assets: Mapping[str, str | Path] | None = None,
    package_members: bool = False,
    mode: str = "skeleton",
    secret: str = "lathe-shared-default",
    proxy_gltf_validation: bool = True,
    validator_workdir: str | Path = ".tmp_tools/gltf_validator_probe",
) -> LthworldWriteResult:
    """Write a deterministic, signed ``.lthworld`` directory.

    Existing directories are reused, but asset package copies are
    conservative: an existing target asset package is reported as
    blocked rather than overwritten.
    """

    world_dir = Path(out_dir)
    world_dir.mkdir(parents=True, exist_ok=True)
    (world_dir / "assets").mkdir(parents=True, exist_ok=True)
    (world_dir / "engine_import_evidence").mkdir(parents=True, exist_ok=True)

    asset_links: dict[str, dict[str, str]] = {}
    if package_members:
        packaged = package_world_members(composition, world_dir / "assets")
        asset_links.update(package_results_to_links(packaged, world_dir))
    asset_links.update(_copy_assets(world_dir, assets))

    world_graph = composition.to_dict()
    _write_json(world_dir / "world_graph.json", world_graph)
    engine_import, engine_import_path = _engine_import_evidence(
        world_dir,
        proxy_gltf_validation=proxy_gltf_validation,
        validator_workdir=Path(validator_workdir),
    )
    traversal = traversal_evidence_from_composition(composition)
    minimap_evidence = {
        **write_minimap_png(composition, world_dir / "minimap.png"),
        "path": "minimap.png",
    }
    hero_render_evidence = {
        **write_hero_sunset_png(
            composition,
            world_dir / "hero_sunset.png",
        ),
        "path": "hero_sunset.png",
    }
    from ..wonder.critique import run_world_wonder_critique_repair

    wonder_critique_trace = run_world_wonder_critique_repair(
        composition=composition,
        world_dir=world_dir,
        asset_links=asset_links,
    )
    canonical_render_evidence = write_asset_canonical_previews(
        composition,
        world_dir,
        asset_links,
    )
    certificate = compute_world_certificate(
        composition,
        asset_links=asset_links,
        traversal_evidence=traversal,
        minimap_evidence=minimap_evidence,
        engine_import_status=str(engine_import.get("status") or "not_verified"),
        hero_render_status=str(hero_render_evidence.get("status") or "not_verified"),
        wonder_critique_status=str(wonder_critique_trace.get("status") or "not_verified"),
    ).to_dict()
    visual_gate = _visual_quality_gate(certificate)
    repro = _repro_evidence(composition, mode)
    world_evidence = _world_evidence(
        composition,
        canonical_render_evidence=canonical_render_evidence,
        minimap_evidence=minimap_evidence,
        hero_render_evidence=hero_render_evidence,
        wonder_critique_trace=wonder_critique_trace,
        engine_import_evidence=engine_import,
    )
    sidecars = {
        "world_graph": "world_graph.json",
        "traversal_evidence": "traversal_evidence.json",
        "visual_quality_gate": "visual_quality_gate.json",
        "world_evidence": "evidence.json",
        "wonder_critique_trace": "wonder_critique_trace.json",
        "repro_evidence": "repro_evidence.json",
        "minimap_evidence": "minimap_evidence.json",
        "hero_render_evidence": "hero_render_evidence.json",
        "engine_import_evidence": engine_import_path,
        "signature": "signature.json",
    }
    manifest = _world_manifest(
        composition,
        sidecars=sidecars,
        asset_links=asset_links,
        certificate=certificate,
        minimap_evidence=minimap_evidence,
        hero_render_evidence=hero_render_evidence,
        traversal_evidence=traversal,
        wonder_critique_trace=wonder_critique_trace,
        engine_import_evidence=engine_import,
        engine_import_path=engine_import_path,
        mode=mode,
    )
    manifest["engine_import_evidence"] = engine_import

    files = {
        "world_manifest": world_dir / "world_manifest.json",
        "world_graph": world_dir / "world_graph.json",
        "traversal_evidence": world_dir / "traversal_evidence.json",
        "visual_quality_gate": world_dir / "visual_quality_gate.json",
        "world_evidence": world_dir / "evidence.json",
        "wonder_critique_trace": world_dir / "wonder_critique_trace.json",
        "repro_evidence": world_dir / "repro_evidence.json",
        "minimap_evidence": world_dir / "minimap_evidence.json",
        "hero_render_evidence": world_dir / "hero_render_evidence.json",
        "signature": world_dir / "signature.json",
    }
    _write_json(files["world_graph"], world_graph)
    _write_json(files["traversal_evidence"], traversal)
    _write_json(files["visual_quality_gate"], visual_gate)
    _write_json(files["world_evidence"], world_evidence)
    _write_json(files["wonder_critique_trace"], wonder_critique_trace)
    _write_json(files["repro_evidence"], repro)
    _write_json(files["minimap_evidence"], minimap_evidence)
    _write_json(files["hero_render_evidence"], hero_render_evidence)
    _write_json(files["world_manifest"], manifest)

    envelope: SignedWorldEnvelope = sign_lthworld_directory(
        world_dir,
        secret=secret,
        world_id=composition.world_id,
        repro_evidence=repro,
    )
    _write_json(files["signature"], asdict(envelope))
    signature_valid, signature_reason = verify_lthworld_signature(
        world_dir,
        secret=secret,
    )
    return LthworldWriteResult(
        world_dir=str(world_dir),
        world_id=composition.world_id,
        files={key: str(path) for key, path in files.items()},
        signature_valid=signature_valid,
        signature_reason=signature_reason,
        certified=bool(certificate["certified"]),
        certification_status="approved" if certificate["certified"] else "not_verified",
    )


__all__ = [
    "LTHWORLD_VERSION",
    "LthworldWriteResult",
    "write_lthworld",
]
