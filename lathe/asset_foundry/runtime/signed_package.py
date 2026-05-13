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


__all__ = [
    "SIGNED_PACKAGE_VERSION",
    "ReproEvidence",
    "SignedPackageEnvelope",
    "sign_lthpkg_directory",
    "verify_lthpkg_signature",
]
