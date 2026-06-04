"""Signed package + repro evidence.

Per northstar §11 Phase 5. A signed package envelope holds the
manifest hash + every sidecar's hash + a signature digest that
verifies the package was built from a specific seed + parameters +
Foundry version triple. Repro evidence states the exact dependency
versions used.

The signing here is HMAC-SHA256 with a configurable shared secret
(simple deterministic envelope, not full crypto). External
signers can wrap this with real X.509 / Sigstore later.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SIGNED_PACKAGE_VERSION = "lathe.asset_foundry.signed_package_v1"
SIGNED_WORLD_VERSION = "lathe.asset_foundry.signed_world_v1"


@dataclass(frozen=True)
class ReproEvidence:
    """Repro evidence captured at signing time."""

    python_version: str
    foundry_version: str
    capability_matrix_version: str
    lthpkg_version: str
    dependency_versions: Mapping[str, str]
    """e.g. ``{"manifold3d": "3.4.1", "trimesh": "4.x", ...}``."""
    host_platform: str = ""
    """e.g. ``windows-10-amd64`` (informational only)."""


@dataclass(frozen=True)
class SignedPackageEnvelope:
    version: str
    asset_id: str
    pkg_dir: str
    manifest_hash_hex: str
    sidecar_hashes: Mapping[str, str]
    """``filename -> sha256 hex``."""
    signed_digest_hex: str
    """HMAC-SHA256 over the canonical-JSON envelope body."""
    signing_algorithm: str = "hmac_sha256_v1"
    signed_at_unix: float = field(default_factory=time.time)
    repro_evidence: ReproEvidence | None = None


@dataclass(frozen=True)
class SignedWorldEnvelope:
    """Signed envelope for a multi-asset ``.lthworld`` directory."""

    version: str
    world_id: str
    world_dir: str
    world_manifest_hash_hex: str
    file_hashes: Mapping[str, str]
    """``relative/path -> sha256 hex`` for every non-signature file."""
    nested_package_hashes: Mapping[str, str]
    """Subset of ``file_hashes`` under ``assets/*.lthpkg``."""
    signed_digest_hex: str
    signing_algorithm: str = "hmac_sha256_v1"
    signed_at_unix: float = 0.0
    repro_evidence: Mapping[str, Any] = field(default_factory=dict)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _canonical_body(
    asset_id: str,
    manifest_hash: str,
    sidecar_hashes: Mapping[str, str],
    repro_evidence: ReproEvidence | None,
) -> str:
    body = {
        "asset_id": asset_id,
        "manifest_hash_hex": manifest_hash,
        "sidecar_hashes": dict(sidecar_hashes),
        "repro_evidence": (
            {
                "python_version": repro_evidence.python_version,
                "foundry_version": repro_evidence.foundry_version,
                "capability_matrix_version": repro_evidence.capability_matrix_version,
                "lthpkg_version": repro_evidence.lthpkg_version,
                "dependency_versions": dict(repro_evidence.dependency_versions),
                "host_platform": repro_evidence.host_platform,
            }
            if repro_evidence is not None
            else None
        ),
    }
    return json.dumps(body, sort_keys=True)


def _canonical_world_body(
    world_id: str,
    world_manifest_hash: str,
    file_hashes: Mapping[str, str],
    nested_package_hashes: Mapping[str, str],
    repro_evidence: Mapping[str, Any],
) -> str:
    body = {
        "world_id": world_id,
        "world_manifest_hash_hex": world_manifest_hash,
        "file_hashes": dict(file_hashes),
        "nested_package_hashes": dict(nested_package_hashes),
        "repro_evidence": dict(repro_evidence),
    }
    return json.dumps(body, sort_keys=True, default=str)


def _hash_lthworld_files(root: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    manifest_path = root / "world_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"world_manifest.json missing in {root}")
    world_manifest_hash = _sha256_file(manifest_path)
    file_hashes: dict[str, str] = {}
    nested_package_hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if rel == "signature.json":
            continue
        digest = _sha256_file(p)
        file_hashes[rel] = digest
        if rel.startswith("assets/") and ".lthpkg/" in rel:
            nested_package_hashes[rel] = digest
    return world_manifest_hash, file_hashes, nested_package_hashes


def _signed_world_envelope_from_dict(payload: Mapping[str, Any]) -> SignedWorldEnvelope:
    return SignedWorldEnvelope(
        version=str(payload.get("version") or SIGNED_WORLD_VERSION),
        world_id=str(payload.get("world_id") or ""),
        world_dir=str(payload.get("world_dir") or ""),
        world_manifest_hash_hex=str(payload.get("world_manifest_hash_hex") or ""),
        file_hashes={str(k): str(v) for k, v in dict(payload.get("file_hashes") or {}).items()},
        nested_package_hashes={
            str(k): str(v) for k, v in dict(payload.get("nested_package_hashes") or {}).items()
        },
        signed_digest_hex=str(payload.get("signed_digest_hex") or ""),
        signing_algorithm=str(payload.get("signing_algorithm") or "hmac_sha256_v1"),
        signed_at_unix=float(payload.get("signed_at_unix") or 0.0),
        repro_evidence=dict(payload.get("repro_evidence") or {}),
    )


def sign_lthpkg_directory(
    pkg_dir: str | Path,
    *,
    secret: str = "lathe-shared-default",
    asset_id: str | None = None,
    repro_evidence: ReproEvidence | None = None,
) -> SignedPackageEnvelope:
    """Compute hashes + HMAC signature for a .lthpkg directory.

    Walks every JSON sidecar + ``mesh.glb`` if present + the manifest.
    Returns the typed envelope; the caller persists it as
    ``signature.json`` alongside the package.
    """
    root = Path(pkg_dir)
    if not root.is_dir():
        raise ValueError(f"pkg_dir does not exist: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"manifest.json missing in {root}")
    manifest_hash = _sha256_file(manifest_path)
    sidecar_hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and p.name != "signature.json":
            rel = str(p.relative_to(root)).replace("\\", "/")
            sidecar_hashes[rel] = _sha256_file(p)
    resolved_asset_id = asset_id
    if resolved_asset_id is None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            resolved_asset_id = str(manifest.get("asset_id", "unknown"))
        except Exception:
            resolved_asset_id = "unknown"
    canonical = _canonical_body(
        resolved_asset_id, manifest_hash, sidecar_hashes, repro_evidence
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return SignedPackageEnvelope(
        version=SIGNED_PACKAGE_VERSION,
        asset_id=resolved_asset_id,
        pkg_dir=str(root),
        manifest_hash_hex=manifest_hash,
        sidecar_hashes=sidecar_hashes,
        signed_digest_hex=digest,
        repro_evidence=repro_evidence,
    )


def verify_lthpkg_signature(
    pkg_dir: str | Path,
    envelope: SignedPackageEnvelope,
    *,
    secret: str = "lathe-shared-default",
) -> tuple[bool, str]:
    """Verify a signed envelope against the package on disk.

    Returns (valid, reason). When valid is False, reason names the
    mismatch (``manifest_hash_drift``, ``sidecar_hash_drift_<name>``,
    ``signature_digest_mismatch``).
    """
    root = Path(pkg_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return False, "manifest_missing"
    current_manifest_hash = _sha256_file(manifest_path)
    if current_manifest_hash != envelope.manifest_hash_hex:
        return False, "manifest_hash_drift"
    for rel, expected in envelope.sidecar_hashes.items():
        p = root / rel
        if not p.is_file():
            return False, f"sidecar_missing_{rel}"
        if _sha256_file(p) != expected:
            return False, f"sidecar_hash_drift_{rel}"
    canonical = _canonical_body(
        envelope.asset_id,
        envelope.manifest_hash_hex,
        envelope.sidecar_hashes,
        envelope.repro_evidence,
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, envelope.signed_digest_hex):
        return False, "signature_digest_mismatch"
    return True, "ok"


def sign_lthworld_directory(
    world_dir: str | Path,
    *,
    secret: str = "lathe-shared-default",
    world_id: str | None = None,
    repro_evidence: Mapping[str, Any] | None = None,
) -> SignedWorldEnvelope:
    """Compute hashes + HMAC signature for a ``.lthworld`` directory."""

    root = Path(world_dir)
    if not root.is_dir():
        raise ValueError(f"world_dir does not exist: {root}")
    manifest_path = root / "world_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"world_manifest.json missing in {root}")
    resolved_world_id = world_id
    if resolved_world_id is None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            resolved_world_id = str(manifest.get("world_id") or "unknown")
        except Exception:
            resolved_world_id = "unknown"
    manifest_hash, file_hashes, nested_package_hashes = _hash_lthworld_files(root)
    canonical = _canonical_world_body(
        resolved_world_id,
        manifest_hash,
        file_hashes,
        nested_package_hashes,
        dict(repro_evidence or {}),
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return SignedWorldEnvelope(
        version=SIGNED_WORLD_VERSION,
        world_id=resolved_world_id,
        world_dir=str(root),
        world_manifest_hash_hex=manifest_hash,
        file_hashes=file_hashes,
        nested_package_hashes=nested_package_hashes,
        signed_digest_hex=digest,
        repro_evidence=dict(repro_evidence or {}),
    )


def verify_lthworld_signature(
    world_dir: str | Path,
    envelope: SignedWorldEnvelope | Mapping[str, Any] | None = None,
    *,
    secret: str = "lathe-shared-default",
) -> tuple[bool, str]:
    """Verify a signed world envelope against a ``.lthworld`` directory."""

    root = Path(world_dir)
    if not root.is_dir():
        return False, "world_dir_missing"
    if envelope is None:
        signature_path = root / "signature.json"
        if not signature_path.is_file():
            return False, "signature_missing"
        try:
            payload = json.loads(signature_path.read_text(encoding="utf-8"))
            parsed_envelope = _signed_world_envelope_from_dict(payload)
        except Exception:
            return False, "signature_unreadable"
    elif isinstance(envelope, SignedWorldEnvelope):
        parsed_envelope = envelope
    else:
        parsed_envelope = _signed_world_envelope_from_dict(envelope)

    try:
        manifest_hash, file_hashes, nested_package_hashes = _hash_lthworld_files(root)
    except ValueError as exc:
        return False, str(exc)
    if manifest_hash != parsed_envelope.world_manifest_hash_hex:
        return False, "world_manifest_hash_drift"
    expected_paths = set(parsed_envelope.file_hashes)
    actual_paths = set(file_hashes)
    if expected_paths != actual_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        if missing:
            return False, f"world_file_missing_{missing[0]}"
        if extra:
            return False, f"world_file_extra_{extra[0]}"
    for rel, expected in parsed_envelope.file_hashes.items():
        if file_hashes.get(rel) != expected:
            return False, f"world_file_hash_drift_{rel}"
    if nested_package_hashes != dict(parsed_envelope.nested_package_hashes):
        return False, "nested_package_hash_index_drift"

    canonical = _canonical_world_body(
        parsed_envelope.world_id,
        parsed_envelope.world_manifest_hash_hex,
        parsed_envelope.file_hashes,
        parsed_envelope.nested_package_hashes,
        parsed_envelope.repro_evidence,
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, parsed_envelope.signed_digest_hex):
        return False, "signature_digest_mismatch"
    return True, "ok"


__all__ = [
    "SIGNED_PACKAGE_VERSION",
    "SIGNED_WORLD_VERSION",
    "ReproEvidence",
    "SignedPackageEnvelope",
    "SignedWorldEnvelope",
    "sign_lthpkg_directory",
    "sign_lthworld_directory",
    "verify_lthpkg_signature",
    "verify_lthworld_signature",
]
