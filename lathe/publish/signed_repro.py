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
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from ..logging_utils import info as log_info

try:  # Optional dep — the ``publish`` extra pulls it in.
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives import serialization as _serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519

    _CRYPTOGRAPHY_OK = True
except ImportError:  # pragma: no cover - only when extra is absent
    _InvalidSignature = None  # type: ignore[assignment]
    _ed25519 = None  # type: ignore[assignment]
    _serialization = None  # type: ignore[assignment]
    _CRYPTOGRAPHY_OK = False


RECEIPT_SCHEMA_VERSION: int = 1
RECEIPT_FILENAME: str = "reproducibility_receipt.json"
_SNAPSHOT_FILENAME: str = ".lathe_snapshot.json"
_RAW_ED25519_PRIVATE_KEY_BYTES = 32
_RECEIPT_REQUIRED_KEYS = (
    "schema_version",
    "snapshot",
    "signer_id",
    "timestamp",
    "env_fingerprint",
    "signature",
)
_SIGNATURE_VERIFY_ERRORS: tuple[type[BaseException], ...] = (
    (_InvalidSignature,) if _InvalidSignature is not None else ()
)

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
        """Return the receipt as a JSON-serializable dictionary."""
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
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifold_version() -> str:
    try:
        return metadata.version("manifold3d")
    except metadata.PackageNotFoundError:
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
        message = (
            f"missing {_SNAPSHOT_FILENAME} in {build_dir}; run `lathe snapshot` or "
            f"`lathe build` with snapshotting enabled before signing"
        )
        raise ReproVerifyError(message)
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        message = f"failed to read {snapshot_path}: {exc}"
        raise ReproVerifyError(message) from exc
    if not isinstance(data, dict):
        message = f"{snapshot_path} did not decode to a JSON object"
        raise ReproVerifyError(message)
    return data


def _load_private_key(key_path: Path) -> Any:
    if not _CRYPTOGRAPHY_OK:
        message = "cryptography package is not installed; install the 'publish' extra"
        raise ReproVerifyError(message)
    if not key_path.is_file():
        message = "signing key does not exist"
        raise ReproVerifyError(message)
    if os.name == "posix" and key_path.stat().st_mode & 0o077:
        message = "signing key permissions are unsafe; remove group/world access"
        raise ReproVerifyError(message)
    raw = key_path.read_bytes()
    try:
        if len(raw) == _RAW_ED25519_PRIVATE_KEY_BYTES:
            return _ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        return _serialization.load_pem_private_key(raw, password=None)
    except (ValueError, TypeError) as exc:
        message = f"invalid signing key: {exc}"
        raise ReproVerifyError(message) from exc


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
        message = f"not a build directory: {build_dir}"
        raise ReproVerifyError(message)
    snapshot = _load_snapshot(build_dir)

    env_key = os.getenv("LATHE_PUBLISH_SIGNING_KEY")
    key = signing_key_path or env_key
    if not key:
        message = "no signing key configured; set LATHE_PUBLISH_SIGNING_KEY or pass signing_key_path"
        raise ReproVerifyError(message)
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
    log_info(
        _LOG,
        "lathe.publish.repro_receipt_written",
        "publish: wrote reproducibility receipt {target} (signer={signer})",
        target=target,
        signer=signer,
    )
    return target


def _load_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    if not receipt_path.is_file():
        message = f"receipt not found: {receipt_path}"
        raise ReproVerifyError(message)
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        message = f"failed to read receipt: {exc}"
        raise ReproVerifyError(message) from exc
    if not isinstance(data, dict):
        message = "receipt is not a JSON object"
        raise ReproVerifyError(message)
    for required in _RECEIPT_REQUIRED_KEYS:
        if required not in data:
            message = f"receipt missing required key: {required}"
            raise ReproVerifyError(message)
    return data


def _receipt_signature(data: dict[str, Any]) -> dict[str, Any]:
    sig = data.get("signature") or {}
    if not isinstance(sig, dict):
        message = "receipt signature block is not a JSON object"
        raise ReproVerifyError(message)
    if sig.get("algorithm") != "ed25519":
        message = f"unsupported signature algorithm: {sig.get('algorithm')}"
        raise ReproVerifyError(message)
    if not sig.get("value_hex") or not sig.get("public_key_hex"):
        message = "receipt signature missing value_hex or public_key_hex"
        raise ReproVerifyError(message)
    return sig


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
        message = "cryptography package is not installed; install the 'publish' extra"
        raise ReproVerifyError(message)
    receipt_path = Path(receipt_path)
    data = _load_receipt_payload(receipt_path)
    sig = _receipt_signature(data)
    value_hex = sig.get("value_hex")
    public_hex = sig.get("public_key_hex")

    payload = {k: v for k, v in data.items() if k != "signature"}
    payload_bytes = _canonical_bytes(payload)
    try:
        signature_bytes = bytes.fromhex(value_hex)
        public_key = _ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
    except ValueError as exc:
        message = f"malformed signature hex: {exc}"
        raise ReproVerifyError(message) from exc
    try:
        public_key.verify(signature_bytes, payload_bytes)
    except _SIGNATURE_VERIFY_ERRORS as exc:
        message = "signature verification failed"
        raise ReproVerifyError(message) from exc

    recorded_sha = sig.get("payload_sha256")
    actual_sha = hashlib.sha256(payload_bytes).hexdigest()
    if recorded_sha and recorded_sha != actual_sha:
        message = "payload_sha256 mismatch: receipt tampered"
        raise ReproVerifyError(message)

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
