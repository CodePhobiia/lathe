"""Signed reproducibility receipts (SEC-NEW-2, V0.2 P0).

A reproducibility receipt is an ed25519-signed JSON document that binds
a completed Lathe build to its environment fingerprint + stage digests.
Third parties verify a receipt with the public key embedded in the
receipt itself; a mismatch (tampered stage hash, wrong signer, bad
signature) yields a verification failure.

Schema: ``schema/reproducibility_receipt.schema.json``.

Input: a build directory with ``.lathe_snapshot.json`` (RPT-4) present.
Output: ``<target>/reproducibility_receipt.json`` — a JSON object with:

* ``schema_version`` — receipt schema integer, currently 1.
* ``snapshot`` — embedded ``.lathe_snapshot.json`` contents (stage hashes,
  buildHash, certified flag, score).
* ``signer_id`` — caller-supplied identifier (email, CI job id, …).
* ``timestamp`` — ISO-8601 UTC.
* ``env_fingerprint`` — python version, git commit, manifold3d version.
* ``signature`` — ``{algorithm, value_hex, public_key_hex}`` (ed25519).

The signed payload is the JSON-canonical form of the receipt minus
``signature`` (sorted keys, no whitespace) so that re-serialisation
round-trips byte-identically.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # Optional dep — the ``publish`` extra pulls it in.
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519
    from cryptography.hazmat.primitives import serialization as _serialization
    _CRYPTOGRAPHY_OK = True
except ImportError:  # pragma: no cover - only when extra is absent
    _ed25519 = None  # type: ignore[assignment]
    _serialization = None  # type: ignore[assignment]
    _CRYPTOGRAPHY_OK = False


RECEIPT_SCHEMA_VERSION: int = 1
RECEIPT_FILENAME: str = "reproducibility_receipt.json"
_SNAPSHOT_FILENAME: str = ".lathe_snapshot.json"

_LOG = logging.getLogger(__name__)


class ReproVerifyError(RuntimeError):
    """Raised when a receipt cannot be produced or verified."""


@dataclass
class ReproReceipt:
    """In-memory view of a reproducibility receipt."""

    schema_version: int
    snapshot: dict[str, Any]
    signer_id: str
    timestamp: str
    env_fingerprint: dict[str, Any]
    signature: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "snapshot": dict(self.snapshot),
            "signer_id": str(self.signer_id),
            "timestamp": str(self.timestamp),
            "env_fingerprint": dict(self.env_fingerprint),
            "signature": dict(self.signature),
        }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifold_version() -> str:
    try:
        import manifold3d  # type: ignore[import-not-found]

        return str(getattr(manifold3d, "__version__", "unknown"))
    except ImportError:
        return "not_installed"


def _git_head(cwd: Path) -> str:
    """Best-effort git SHA read without shelling out.

    Falls back to ``unknown`` if the build directory is not inside a
    git worktree (happens during tests that seed a temp build_dir).
    """
    probe = cwd
    for _ in range(6):
        head = probe / ".git" / "HEAD"
        if head.is_file():
            try:
                ref_line = head.read_text(encoding="utf-8").strip()
            except OSError:
                return "unknown"
            if ref_line.startswith("ref: "):
                ref_path = probe / ".git" / ref_line[5:].strip()
                if ref_path.is_file():
                    try:
                        return ref_path.read_text(encoding="utf-8").strip() or "unknown"
                    except OSError:
                        return "unknown"
            return ref_line or "unknown"
        if probe.parent == probe:
            break
        probe = probe.parent
    return "unknown"


def _env_fingerprint(build_dir: Path) -> dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(terse=True),
        "git_sha": _git_head(build_dir),
        "manifold3d_version": _manifold_version(),
    }


def _load_snapshot(build_dir: Path) -> dict[str, Any]:
    snapshot_path = build_dir / _SNAPSHOT_FILENAME
    if not snapshot_path.is_file():
        raise ReproVerifyError(
            f"missing {_SNAPSHOT_FILENAME} in {build_dir}; run `lathe snapshot` or "
            f"`lathe build` with snapshotting enabled before signing"
        )
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproVerifyError(f"failed to read {snapshot_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReproVerifyError(f"{snapshot_path} did not decode to a JSON object")
    return data


def _load_private_key(key_path: Path) -> Any:
    if not _CRYPTOGRAPHY_OK:
        raise ReproVerifyError("cryptography package is not installed; install the 'publish' extra")
    if not key_path.is_file():
        raise ReproVerifyError(f"signing key does not exist: {key_path}")
    raw = key_path.read_bytes()
    try:
        if len(raw) == 32:
            return _ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        return _serialization.load_pem_private_key(raw, password=None)
    except (ValueError, TypeError) as exc:
        raise ReproVerifyError(f"invalid signing key: {exc}") from exc


def sign_receipt(
    build_dir: Path | str,
    *,
    signing_key_path: str | Path | None = None,
    signer_id: str | None = None,
    out_path: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Sign a reproducibility receipt for ``build_dir``.

    Args:
        build_dir: completed build directory (must contain ``.lathe_snapshot.json``).
        signing_key_path: ed25519 private key (raw 32 bytes or PEM).
            Falls back to ``LATHE_PUBLISH_SIGNING_KEY`` env.
        signer_id: identifier recorded in the receipt.
            Defaults to ``LATHE_SIGNER_ID`` or ``"anonymous"``.
        out_path: receipt destination. Defaults to ``<build_dir>/reproducibility_receipt.json``.
        timestamp: override the recorded timestamp (useful for deterministic tests).

    Returns:
        Absolute path of the written receipt.

    Raises:
        ReproVerifyError: snapshot missing, key unavailable, or cryptography
            package not importable.
    """
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise ReproVerifyError(f"not a build directory: {build_dir}")
    snapshot = _load_snapshot(build_dir)

    env_key = os.getenv("LATHE_PUBLISH_SIGNING_KEY")
    key = signing_key_path or env_key
    if not key:
        raise ReproVerifyError(
            "no signing key configured; set LATHE_PUBLISH_SIGNING_KEY or pass signing_key_path"
        )
    private_key = _load_private_key(Path(key))

    signer = signer_id or os.getenv("LATHE_SIGNER_ID") or "anonymous"
    receipt_payload: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "snapshot": snapshot,
        "signer_id": str(signer),
        "timestamp": str(timestamp) if timestamp else _now_iso(),
        "env_fingerprint": _env_fingerprint(build_dir),
    }
    payload_bytes = _canonical_bytes(receipt_payload)
    signature = private_key.sign(payload_bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=_serialization.Encoding.Raw,
        format=_serialization.PublicFormat.Raw,
    )
    receipt_payload["signature"] = {
        "algorithm": "ed25519",
        "value_hex": signature.hex(),
        "public_key_hex": public_bytes.hex(),
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
    }

    target = Path(out_path) if out_path is not None else build_dir / RECEIPT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(receipt_payload, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _LOG.info("publish: wrote reproducibility receipt %s (signer=%s)", target, signer)
    return target


def verify_receipt(receipt_path: Path | str) -> ReproReceipt:
    """Verify a receipt and return a structured view.

    Args:
        receipt_path: path to ``reproducibility_receipt.json``.

    Returns:
        :class:`ReproReceipt` reflecting the verified payload.

    Raises:
        ReproVerifyError: invalid JSON, tampered payload, wrong signature,
            or cryptography package not importable.
    """
    if not _CRYPTOGRAPHY_OK:
        raise ReproVerifyError("cryptography package is not installed; install the 'publish' extra")
    receipt_path = Path(receipt_path)
    if not receipt_path.is_file():
        raise ReproVerifyError(f"receipt not found: {receipt_path}")
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproVerifyError(f"failed to read receipt: {exc}") from exc
    if not isinstance(data, dict):
        raise ReproVerifyError("receipt is not a JSON object")

    for required in ("schema_version", "snapshot", "signer_id", "timestamp", "env_fingerprint", "signature"):
        if required not in data:
            raise ReproVerifyError(f"receipt missing required key: {required}")

    sig = data.get("signature") or {}
    if not isinstance(sig, dict):
        raise ReproVerifyError("receipt signature block is not a JSON object")
    if sig.get("algorithm") != "ed25519":
        raise ReproVerifyError(f"unsupported signature algorithm: {sig.get('algorithm')}")
    value_hex = sig.get("value_hex")
    public_hex = sig.get("public_key_hex")
    if not value_hex or not public_hex:
        raise ReproVerifyError("receipt signature missing value_hex or public_key_hex")

    payload = {k: v for k, v in data.items() if k != "signature"}
    payload_bytes = _canonical_bytes(payload)
    try:
        signature_bytes = bytes.fromhex(value_hex)
        public_key = _ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
    except ValueError as exc:
        raise ReproVerifyError(f"malformed signature hex: {exc}") from exc
    try:
        public_key.verify(signature_bytes, payload_bytes)
    except Exception as exc:  # noqa: BLE001 - cryptography.exceptions.InvalidSignature
        raise ReproVerifyError("signature verification failed") from exc

    recorded_sha = sig.get("payload_sha256")
    actual_sha = hashlib.sha256(payload_bytes).hexdigest()
    if recorded_sha and recorded_sha != actual_sha:
        raise ReproVerifyError("payload_sha256 mismatch: receipt tampered")

    return ReproReceipt(
        schema_version=int(data.get("schema_version", RECEIPT_SCHEMA_VERSION)),
        snapshot=dict(data.get("snapshot", {})),
        signer_id=str(data.get("signer_id", "")),
        timestamp=str(data.get("timestamp", "")),
        env_fingerprint=dict(data.get("env_fingerprint", {})),
        signature=dict(sig),
    )


__all__ = [
    "RECEIPT_FILENAME",
    "RECEIPT_SCHEMA_VERSION",
    "ReproReceipt",
    "ReproVerifyError",
    "sign_receipt",
    "verify_receipt",
]
