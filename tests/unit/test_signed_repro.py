"""Tests for :mod:`lathe.publish.signed_repro` (SEC-NEW-2, V0.2 P0)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from lathe.publish.signed_repro import (
    RECEIPT_SCHEMA_VERSION,
    ReproVerifyError,
    sign_receipt,
    verify_receipt,
)

ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")


def _write_key(dir_: Path) -> Path:
    private_key = ed25519.Ed25519PrivateKey.generate()
    raw = private_key.private_bytes_raw() if hasattr(private_key, "private_bytes_raw") else None
    if raw is None:
        # Fall back for older cryptography versions.
        raw = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    path = dir_ / "signing_key.ed25519"
    path.write_bytes(raw)
    return path


def _seed_build_dir(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    snapshot = {
        "schemaVersion": 1,
        "latheVersion": "0.1.0",
        "sourcePath": "examples/courier_drone.lth",
        "buildHash": "abc123",
        "stages": {
            "shape": "0" * 64,
            "topology": "1" * 64,
        },
        "timestamp": "2026-04-24T00:00:00Z",
    }
    (build_dir / ".lathe_snapshot.json").write_text(
        json.dumps(snapshot, sort_keys=True),
        encoding="utf-8",
    )
    return build_dir


def test_sign_and_verify_round_trip(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    receipt_path = sign_receipt(
        build_dir,
        signing_key_path=key_path,
        signer_id="ci@example.com",
        timestamp="2026-04-24T12:00:00Z",
    )
    assert receipt_path.exists()
    receipt = verify_receipt(receipt_path)
    assert receipt.signer_id == "ci@example.com"
    assert receipt.schema_version == RECEIPT_SCHEMA_VERSION
    assert receipt.snapshot["buildHash"] == "abc123"


def test_tampered_receipt_fails_verification(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    receipt_path = sign_receipt(build_dir, signing_key_path=key_path, signer_id="a")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["signer_id"] = "mallory"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(ReproVerifyError):
        verify_receipt(receipt_path)


def test_tampered_snapshot_fails_verification(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    receipt_path = sign_receipt(build_dir, signing_key_path=key_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["snapshot"]["stages"]["shape"] = "f" * 64
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(ReproVerifyError):
        verify_receipt(receipt_path)


def test_missing_snapshot_raises(tmp_path: Path) -> None:
    build_dir = tmp_path / "empty"
    build_dir.mkdir()
    key_path = _write_key(tmp_path)
    with pytest.raises(ReproVerifyError):
        sign_receipt(build_dir, signing_key_path=key_path)


def test_missing_key_raises(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    with pytest.raises(ReproVerifyError):
        sign_receipt(build_dir, signing_key_path=None)


def test_missing_configured_key_error_does_not_include_path(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    missing = tmp_path / "secret-signing-key.ed25519"

    with pytest.raises(ReproVerifyError) as exc:
        sign_receipt(build_dir, signing_key_path=missing)

    assert str(missing) not in str(exc.value)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_world_readable_signing_key_is_rejected(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    key_path.chmod(0o644)

    with pytest.raises(ReproVerifyError, match="permissions are unsafe"):
        sign_receipt(build_dir, signing_key_path=key_path)


def test_receipt_matches_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    receipt_path = sign_receipt(build_dir, signing_key_path=key_path, signer_id="ci")

    schema_path = Path(__file__).resolve().parents[2] / "schema" / "reproducibility_receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def test_verify_receipt_rejects_wrong_key(tmp_path: Path) -> None:
    build_dir = _seed_build_dir(tmp_path)
    key_path = _write_key(tmp_path)
    receipt_path = sign_receipt(build_dir, signing_key_path=key_path, signer_id="a")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    # Replace only the public key — signature no longer matches.
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()

    other_raw = other_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload["signature"]["public_key_hex"] = other_raw.hex()
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(ReproVerifyError):
        verify_receipt(receipt_path)
