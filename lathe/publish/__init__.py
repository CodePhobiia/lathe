"""Publish runner and drivers (Plan 08 Phase 1 / BL-31).

The publish stage takes a completed build directory (the output of
``lathe build``) and uploads / copies the package artifacts + a signed
manifest to a configurable target (local filesystem, S3, Supabase Storage,
or git-lfs).

The runner intentionally sits below the stage dispatcher: stage-body
``lathe.core.stages.publish.run`` parses runtime_config and delegates here.
The ``lathe publish`` CLI subcommand is another entry point that re-runs
publish against an already-built directory.

Driver contract (Protocol):

    class PublishDriver(Protocol):
        def publish(self, build_dir: Path, target_config: dict) -> dict: ...

Drivers return a manifest dict describing what was published. The manifest
schema is pinned in ``schema/publish_manifest.schema.json``.

Signing: ed25519 via ``cryptography.hazmat.primitives.asymmetric.ed25519``
when the ``cryptography`` package is importable and a key path is configured.
Missing key OR missing library ⇒ skip signing with a warning logged to the
returned manifest (``signature.skipped_reason``). This keeps the publish
runner useful in the default smoke-test environment.

The package also exports SEC-NEW-2 signed reproducibility receipts via
:mod:`lathe.publish.signed_repro`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import __version__ as _lathe_version_value
from ..logging_utils import warning as log_warning
from ..net import NetGuardError, safe_urlopen
from ..paths import PathGuardError, safe_resolve
from ..security import redact_secrets
from ..subproc import run_sandboxed
from .signed_repro import (
    ReproReceipt,
    ReproVerifyError,
    sign_receipt,
    verify_receipt,
)

try:  # Optional dep — ships under the ``[publish]`` extra.
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives import serialization as _serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519

    _CRYPTOGRAPHY_OK = True
except ImportError:  # pragma: no cover - exercised only when extra absent
    _InvalidSignature = None  # type: ignore[assignment]
    _ed25519 = None  # type: ignore[assignment]
    _serialization = None  # type: ignore[assignment]
    _CRYPTOGRAPHY_OK = False

try:  # Optional dep — S3 driver only.
    import boto3 as _boto3  # type: ignore[import-not-found]

    _BOTO3_OK = True
except ImportError:
    _boto3 = None  # type: ignore[assignment]
    _BOTO3_OK = False


__all__ = [
    "PUBLISH_DRIVERS",
    "GitLFSDriver",
    "GitLFSPublishError",
    "LocalFSDriver",
    "PublishDriver",
    "PublishManifestError",
    "ReproReceipt",
    "ReproVerifyError",
    "S3Driver",
    "SupabaseDriver",
    "build_manifest",
    "get_driver",
    "register_driver",
    "sign_manifest",
    "sign_receipt",
    "verify_receipt",
    "verify_signature",
]


_LOG = logging.getLogger(__name__)
_MAX_PUBLISH_ARTIFACT_BYTES = 512 * 1024 * 1024
_RAW_ED25519_PRIVATE_KEY_BYTES = 32
_SAFE_OBJECT_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")
_SAFE_BUCKET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
_SIGNATURE_VERIFY_ERRORS: tuple[type[BaseException], ...] = (
    (_InvalidSignature,) if _InvalidSignature is not None else ()
)


class GitLFSPublishError(RuntimeError):
    """Raised when a git-lfs publish step fails."""

    def __init__(self, step: str, returncode: int, stderr_tail: str) -> None:
        message = f"git-lfs publish step failed: {step} exited {returncode}"
        if stderr_tail:
            message = f"{message}: {stderr_tail[-400:]}"
        super().__init__(message)
        self.step = step
        self.returncode = int(returncode)
        self.stderr_tail = stderr_tail[-400:] if stderr_tail else ""


class PublishManifestError(ValueError):
    """Raised when a build's package manifest references invalid artifacts."""


@runtime_checkable
class PublishDriver(Protocol):
    """Publish-driver Protocol: upload a build directory to a target."""

    def publish(self, build_dir: Path, target_config: dict[str, Any]) -> dict[str, Any]:
        """Publish ``build_dir`` to the target. Returns a manifest dict."""
        ...


# ---------------------------------------------------------------------------
# Manifest construction + signing
# ---------------------------------------------------------------------------


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_build_artifact(build_dir: Path, uri: Any) -> Path:
    raw_uri = str(uri)
    try:
        path = safe_resolve(build_dir, raw_uri)
    except (PathGuardError, TypeError, ValueError, OSError) as exc:
        message = f"publish package artifact URI is unsafe: {raw_uri!r}"
        raise PublishManifestError(message) from exc
    if not path.exists() or not path.is_file():
        message = f"publish package artifact is missing: {raw_uri!r}"
        raise PublishManifestError(message)
    try:
        if path.stat().st_size > _MAX_PUBLISH_ARTIFACT_BYTES:
            message = f"publish package artifact exceeds size limit: {raw_uri!r}"
            raise PublishManifestError(message)
    except OSError as exc:
        message = f"publish package artifact cannot be inspected: {raw_uri!r}"
        raise PublishManifestError(message) from exc
    return path


def _host_allowlist(target_config: dict[str, Any], driver_name: str) -> set[str]:
    raw_allowlist = target_config.get("url_allowlist")
    if not isinstance(raw_allowlist, list):
        message = f"{driver_name} requires target_config['url_allowlist'] with the destination host"
        raise ValueError(message)
    allowlist = {str(item).strip().lower() for item in raw_allowlist if str(item).strip()}
    if not allowlist:
        message = f"{driver_name} requires target_config['url_allowlist'] with the destination host"
        raise ValueError(message)
    return allowlist


def _require_host_allowlisted(host: str, allowlist: set[str], driver_name: str) -> None:
    normalized = host.strip().lower()
    if normalized not in allowlist:
        message = f"{driver_name} destination host must be present in target_config['url_allowlist']"
        raise ValueError(message)


def _s3_endpoint_host(target_config: dict[str, Any]) -> tuple[str | None, str]:
    endpoint_url = target_config.get("endpoint_url")
    if endpoint_url:
        text = str(endpoint_url).strip().rstrip("/")
        parsed = urllib.parse.urlsplit(text)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            message = "S3Driver endpoint_url must be an http(s) origin URL without path, query, or fragment"
            raise ValueError(message)
        return text, parsed.hostname.lower()
    region = str(target_config.get("region") or "").strip()
    if region and region != "us-east-1":
        return None, f"s3.{region}.amazonaws.com"
    return None, "s3.amazonaws.com"


def _target_subdir(root: Path, asset: Any, version: Any) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    try:
        return safe_resolve(root, f"{asset}/{version}")
    except PathGuardError as exc:
        message = "publish target asset/version must stay under target_dir"
        raise ValueError(message) from exc


def _copy_no_overwrite(src: Path, dst: Path) -> None:
    if dst.exists():
        message = f"publish destination already exists: {dst}"
        raise FileExistsError(message)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _write_text_no_overwrite(path: Path, text: str) -> None:
    if path.exists():
        message = f"publish destination already exists: {path}"
        raise FileExistsError(message)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_object_key(*parts: Any) -> str:
    raw_parts = [str(part).strip("/") for part in parts if str(part).strip("/")]
    key = "/".join(raw_parts)
    key_parts = key.split("/") if key else []
    if not key or any(
        part in {"", ".", ".."}
        or "\\" in part
        or any(ord(char) < 32 or ord(char) == 127 for char in part)
        or not _SAFE_OBJECT_SEGMENT_RE.fullmatch(part)
        for part in key_parts
    ):
        message = "publish object key contains unsafe path components"
        raise ValueError(message)
    return key


def _safe_bucket_name(bucket: Any) -> str:
    value = str(bucket).strip()
    if not value or not _SAFE_BUCKET_RE.fullmatch(value):
        message = "publish bucket name contains unsafe characters"
        raise ValueError(message)
    return value


def _quote_object_key(key: str) -> str:
    return "/".join(urllib.parse.quote(part, safe="") for part in key.split("/"))


def _supabase_base_url(raw: Any) -> str:
    text = str(raw).strip().rstrip("/")
    parsed = urllib.parse.urlsplit(text)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.query
        or parsed.fragment
        or not parsed.netloc
        or parsed.path not in {"", "/"}
    ):
        message = "Supabase base_url must be an http(s) origin URL without path, query, or fragment"
        raise ValueError(message)
    return text


def _private_key_permissions_unsafe(key_file: Path) -> bool:
    if os.name != "posix":
        return False
    return bool(key_file.stat().st_mode & 0o077)


def _git_sha(cwd: Path | None = None) -> str | None:
    """Best-effort ``git rev-parse HEAD``. Returns ``None`` when unavailable."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = run_sandboxed(
            [git, "rev-parse", "HEAD"],
            cwd=cwd,
            timeout_s=5.0,
        )
    except (ValueError, TypeError, OSError):
        return None
    if not result.ok:
        return None
    sha = result.stdout.strip()
    return sha or None


def _lathe_version() -> str:
    return str(_lathe_version_value)


def _load_package_manifest(build_dir: Path) -> dict[str, Any]:
    """Read ``stages/package/package_manifest.json`` if present.

    Falls back to a minimal manifest when the build wasn't produced by the
    canonical pipeline (useful for unit tests that seed a build_dir directly).
    """
    candidate = build_dir / "stages" / "package" / "package_manifest.json"
    if candidate.exists():
        try:
            # JSON ingress — our own package stage writes this file in the same build directory.
            return json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    # Fallback: synth a minimal manifest from build_report.json when present.
    report = build_dir / "build_report.json"
    if report.exists():
        try:
            # JSON ingress — our own executor writes build_report.json.
            return json.loads(report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _load_validator_scores(build_dir: Path) -> dict[str, Any]:
    report = build_dir / "stages" / "validate" / "report.json"
    if not report.exists():
        return {}
    try:
        # JSON ingress — our own validate stage writes this file.
        return json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_manifest(
    build_dir: Path,
    *,
    asset: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a publish manifest from an existing build directory.

    The returned dict conforms to ``schema/publish_manifest.schema.json``.
    """
    build_dir = Path(build_dir)
    package_manifest = _load_package_manifest(build_dir)
    validator_scores = _load_validator_scores(build_dir)

    asset_name = asset or package_manifest.get("asset_id") or build_dir.name
    stack_id = ""
    shape_contract = "lathe.shape.intent_mesh_handoff_v1"
    build_report = build_dir / "build_report.json"
    if build_report.exists():
        try:
            # JSON ingress — our own build_report.json.
            report_data = json.loads(build_report.read_text(encoding="utf-8"))
            stack_id = str(report_data.get("backend_stack", ""))
            selected = report_data.get("selected_backends", {}) or {}
            shape_info = selected.get("shape", {}) if isinstance(selected, dict) else {}
            shape_contract = str(shape_info.get("id", shape_contract))
        except (OSError, json.JSONDecodeError):
            pass

    package_formats: list[dict[str, Any]] = []
    for entry in package_manifest.get("outputs", []) or []:
        if not isinstance(entry, dict):
            continue
        uri = entry.get("uri") or entry.get("path")
        if not uri:
            raise PublishManifestError("publish package manifest output is missing a uri")
        abs_path = _resolve_build_artifact(build_dir, uri)
        sha = entry.get("sha256") or _sha256_of(abs_path)
        size = entry.get("size_bytes") or abs_path.stat().st_size
        package_formats.append(
            {
                "format": str(entry.get("format", "")),
                "uri": str(uri),
                "sha256": str(sha),
                "size_bytes": int(size),
            }
        )

    sbom_path = build_dir / "sbom.json"
    sbom_ref = "sbom.json" if sbom_path.exists() else None

    manifest: dict[str, Any] = {
        "asset": asset_name,
        "stack_id": stack_id,
        "shape_contract": shape_contract,
        "package_formats": package_formats,
        "validator_scores": validator_scores,
        "lathe_version": _lathe_version(),
        "git_sha": _git_sha(build_dir),
        "sbom": sbom_ref,
        "signature": None,
    }
    if extra:
        manifest.update(extra)
    return redact_secrets(manifest)


def sign_manifest(
    manifest: dict[str, Any],
    *,
    signing_key_path: str | Path | None,
) -> dict[str, Any]:
    """Sign ``manifest`` in-place with ed25519 when possible.

    Returns the manifest with ``signature`` populated. Missing key or missing
    ``cryptography`` library is not an error — the signature block records
    ``skipped_reason`` so the caller can surface it.
    """
    env_key = os.getenv("LATHE_PUBLISH_SIGNING_KEY")
    key_path = env_key or (str(signing_key_path) if signing_key_path else None)

    if not key_path:
        manifest["signature"] = {
            "algorithm": "ed25519",
            "skipped_reason": "no_signing_key_configured",
        }
        log_warning(
            _LOG,
            "lathe.publish.signing_key_not_configured",
            "publish: no signing key configured; emitting unsigned manifest",
        )
        return manifest

    if not _CRYPTOGRAPHY_OK:
        manifest["signature"] = {
            "algorithm": "ed25519",
            "skipped_reason": "cryptography_not_installed",
        }
        log_warning(
            _LOG,
            "lathe.publish.cryptography_unavailable",
            "publish: cryptography package not available; emitting unsigned manifest. "
            "Install the 'publish' extra to enable signing.",
        )
        return manifest

    key_file = Path(key_path)
    if not key_file.exists():
        manifest["signature"] = {
            "algorithm": "ed25519",
            "skipped_reason": "signing_key_missing",
        }
        log_warning(
            _LOG,
            "lathe.publish.signing_key_missing",
            "publish: configured signing key does not exist",
            key_path=key_file,
        )
        return manifest

    try:
        unsafe_permissions = _private_key_permissions_unsafe(key_file)
    except OSError:
        unsafe_permissions = True
    if unsafe_permissions:
        manifest["signature"] = {
            "algorithm": "ed25519",
            "skipped_reason": "signing_key_permissions_unsafe",
        }
        log_warning(
            _LOG,
            "lathe.publish.signing_key_permissions_unsafe",
            "publish: configured signing key has unsafe permissions; emitting unsigned manifest",
        )
        return manifest

    raw = key_file.read_bytes()
    # Keys are stored as 32 raw bytes OR as a PEM-encoded PKCS#8 blob.
    try:
        if len(raw) == _RAW_ED25519_PRIVATE_KEY_BYTES:
            private_key = _ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        else:
            private_key = _serialization.load_pem_private_key(raw, password=None)
    except (ValueError, TypeError) as exc:
        manifest["signature"] = {
            "algorithm": "ed25519",
            "skipped_reason": f"invalid_signing_key: {type(exc).__name__}",
        }
        return manifest

    payload = json.dumps(
        {k: v for k, v in manifest.items() if k != "signature"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    signature = private_key.sign(payload)

    public_bytes = private_key.public_key().public_bytes(
        encoding=_serialization.Encoding.Raw,
        format=_serialization.PublicFormat.Raw,
    )
    manifest["signature"] = {
        "algorithm": "ed25519",
        "value_hex": signature.hex(),
        "public_key_hex": public_bytes.hex(),
    }
    return manifest


def verify_signature(manifest: dict[str, Any]) -> bool:
    """Verify the ed25519 signature attached to ``manifest``.

    Returns ``True`` on valid signature, ``False`` otherwise (including when
    signing was skipped). Raises ``RuntimeError`` if cryptography is absent.
    """
    if not _CRYPTOGRAPHY_OK:
        message = "cryptography is not installed; cannot verify signature"
        raise RuntimeError(message)
    sig = manifest.get("signature") or {}
    if not isinstance(sig, dict) or "value_hex" not in sig or "public_key_hex" not in sig:
        return False
    try:
        public_key = _ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(sig["public_key_hex"]))
        signature = bytes.fromhex(sig["value_hex"])
    except ValueError:
        return False
    payload = json.dumps(
        {k: v for k, v in manifest.items() if k != "signature"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        public_key.verify(signature, payload)
    except _SIGNATURE_VERIFY_ERRORS:
        return False
    return True


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


class LocalFSDriver:
    """Publish to a local filesystem directory.

    ``target_config`` keys:
    - ``target_dir`` (required): destination root.
    - ``asset`` (optional): asset name; defaults to build_dir basename.
    - ``version`` (optional): version string; defaults to "0.1.0".
    - ``signing_key`` (optional): path to an ed25519 private key.
    """

    name = "local_fs"

    def publish(self, build_dir: Path, target_config: dict[str, Any]) -> dict[str, Any]:
        """Write manifest + signature to ``target_config['target_dir']``."""
        build_dir = Path(build_dir)
        target_dir_cfg = target_config.get("target_dir")
        if not target_dir_cfg:
            message = "LocalFSDriver requires target_config['target_dir']"
            raise ValueError(message)
        asset = target_config.get("asset") or build_dir.name
        version = str(target_config.get("version") or "0.1.0")
        target_dir = _target_subdir(Path(target_dir_cfg), asset, version)
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest = build_manifest(build_dir, asset=asset)
        manifest = sign_manifest(manifest, signing_key_path=target_config.get("signing_key"))

        # Copy referenced package artifacts into the target directory.
        copied: list[str] = []
        for entry in manifest.get("package_formats", []):
            src = _resolve_build_artifact(build_dir, entry["uri"])
            dst = target_dir / Path(entry["uri"]).name
            _copy_no_overwrite(src, dst)
            copied.append(str(dst))

        manifest_path = target_dir / "manifest.json"
        _write_text_no_overwrite(
            manifest_path,
            json.dumps(redact_secrets(manifest), indent=2, sort_keys=False),
        )

        signature_path: Path | None = None
        sig = manifest.get("signature") or {}
        if isinstance(sig, dict) and sig.get("value_hex"):
            signature_path = target_dir / "manifest.sig"
            _write_text_no_overwrite(
                signature_path,
                json.dumps(
                    {
                        "algorithm": sig.get("algorithm", "ed25519"),
                        "value_hex": sig["value_hex"],
                        "public_key_hex": sig.get("public_key_hex", ""),
                    },
                    indent=2,
                ),
            )

        # SEC-NEW-2: emit signed reproducibility receipt when requested.
        receipt_uri: str | None = None
        if target_config.get("emit_repro_receipt"):
            try:
                receipt_path = sign_receipt(
                    build_dir,
                    signing_key_path=target_config.get("signing_key"),
                    signer_id=target_config.get("signer_id"),
                    out_path=target_dir / "reproducibility_receipt.json",
                )
                receipt_uri = str(receipt_path)
            except ReproVerifyError as exc:
                log_warning(
                    _LOG,
                    "lathe.publish.repro_receipt_skipped",
                    "publish: reproducibility receipt skipped: {error}",
                    error=exc,
                )

        return {
            "driver": self.name,
            "target_dir": str(target_dir),
            "manifest_uri": str(manifest_path),
            "signature_uri": str(signature_path) if signature_path else None,
            "reproducibility_receipt_uri": receipt_uri,
            "published_files": copied,
            "manifest": manifest,
        }


class S3Driver:
    """Publish to ``s3://bucket/prefix/<asset>/<version>/`` using boto3."""

    name = "s3"

    def publish(self, build_dir: Path, target_config: dict[str, Any]) -> dict[str, Any]:
        """Upload manifest + package files to S3.

        Requires ``boto3`` (install the ``publish`` optional extra or a
        compatible boto3 pin). Raises a clear error when absent.
        """
        if not _BOTO3_OK:
            message = "S3Driver requires boto3; install with `pip install boto3` or the 'publish' extra"
            raise RuntimeError(message)
        bucket = target_config.get("bucket")
        if not bucket:
            message = "S3Driver requires target_config['bucket']"
            raise ValueError(message)
        prefix = str(target_config.get("prefix") or "").strip("/")
        asset = target_config.get("asset") or Path(build_dir).name
        version = str(target_config.get("version") or "0.1.0")
        base_key = _safe_object_key(prefix, asset, version)
        url_allowlist = _host_allowlist(target_config, "S3Driver")
        endpoint_url, endpoint_host = _s3_endpoint_host(target_config)
        _require_host_allowlisted(endpoint_host, url_allowlist, "S3Driver")

        manifest = build_manifest(Path(build_dir), asset=asset)
        manifest = sign_manifest(manifest, signing_key_path=target_config.get("signing_key"))

        client_kwargs = {"region_name": target_config.get("region")}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        client = _boto3.client("s3", **client_kwargs)
        uploaded: list[str] = []
        for entry in manifest.get("package_formats", []):
            src = _resolve_build_artifact(Path(build_dir), entry["uri"])
            key = _safe_object_key(base_key, Path(entry["uri"]).name)
            client.upload_file(str(src), bucket, key)
            uploaded.append(f"s3://{bucket}/{key}")

        manifest_key = _safe_object_key(base_key, "manifest.json")
        client.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        signature_uri: str | None = None
        sig = manifest.get("signature") or {}
        if isinstance(sig, dict) and sig.get("value_hex"):
            sig_key = _safe_object_key(base_key, "manifest.sig")
            client.put_object(
                Bucket=bucket,
                Key=sig_key,
                Body=json.dumps(
                    {
                        "algorithm": sig.get("algorithm", "ed25519"),
                        "value_hex": sig["value_hex"],
                        "public_key_hex": sig.get("public_key_hex", ""),
                    }
                ).encode("utf-8"),
                ContentType="application/json",
            )
            signature_uri = f"s3://{bucket}/{sig_key}"

        return {
            "driver": self.name,
            "bucket": bucket,
            "prefix": base_key,
            "manifest_uri": f"s3://{bucket}/{manifest_key}",
            "signature_uri": signature_uri,
            "published_files": uploaded,
            "manifest": manifest,
        }


class SupabaseDriver:
    """Publish to a Supabase Storage bucket via its REST API."""

    name = "supabase"

    def publish(self, build_dir: Path, target_config: dict[str, Any]) -> dict[str, Any]:
        """Upload manifest + package files via Supabase Storage PUTs.

        ``target_config`` keys: ``base_url``, ``bucket``, ``service_key``
        (or env ``LATHE_SUPABASE_KEY``), ``url_allowlist``, optional
        ``asset``, ``version``, ``prefix``, ``timeout_s``.
        """
        base_url = target_config.get("base_url")
        bucket = target_config.get("bucket")
        if not base_url or not bucket:
            message = "SupabaseDriver requires target_config['base_url'] and ['bucket']"
            raise ValueError(message)
        base_url = _supabase_base_url(base_url)
        bucket = _safe_bucket_name(bucket)
        url_allowlist = _host_allowlist(target_config, "SupabaseDriver")
        _require_host_allowlisted(
            urllib.parse.urlsplit(base_url).hostname or "",
            url_allowlist,
            "SupabaseDriver",
        )
        service_key = target_config.get("service_key") or os.getenv("LATHE_SUPABASE_KEY")
        if not service_key:
            message = "SupabaseDriver requires target_config['service_key'] or env LATHE_SUPABASE_KEY"
            raise ValueError(message)
        prefix = str(target_config.get("prefix") or "").strip("/")
        asset = target_config.get("asset") or Path(build_dir).name
        version = str(target_config.get("version") or "0.1.0")
        timeout_s = float(target_config.get("timeout_s") or 30.0)
        base_path = _safe_object_key(prefix, asset, version)

        headers = {
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
        }

        manifest = build_manifest(Path(build_dir), asset=asset)
        manifest = sign_manifest(manifest, signing_key_path=target_config.get("signing_key"))

        def _put(object_key: str, body: bytes, content_type: str) -> str:
            quoted_bucket = urllib.parse.quote(bucket, safe="")
            quoted_key = _quote_object_key(object_key)
            url = f"{base_url}/storage/v1/object/{quoted_bucket}/{quoted_key}"
            try:
                safe_urlopen(
                    url,
                    data=body,
                    method="PUT",
                    headers={**headers, "Content-Type": content_type},
                    timeout_s=timeout_s,
                    expect_content_type=("application/json", "text/plain", "application/*"),
                    allowlist=sorted(url_allowlist),
                )
            except NetGuardError as exc:
                message = f"Supabase upload failed ({url}): {exc}"
                raise RuntimeError(message) from exc
            return f"{base_url}/storage/v1/object/public/{quoted_bucket}/{quoted_key}"

        uploaded: list[str] = []
        for entry in manifest.get("package_formats", []):
            src = _resolve_build_artifact(Path(build_dir), entry["uri"])
            object_key = _safe_object_key(base_path, Path(entry["uri"]).name)
            uploaded.append(_put(object_key, src.read_bytes(), "application/octet-stream"))

        manifest_key = _safe_object_key(base_path, "manifest.json")
        manifest_uri = _put(
            manifest_key,
            json.dumps(manifest, indent=2).encode("utf-8"),
            "application/json",
        )
        signature_uri: str | None = None
        sig = manifest.get("signature") or {}
        if isinstance(sig, dict) and sig.get("value_hex"):
            sig_key = _safe_object_key(base_path, "manifest.sig")
            signature_uri = _put(
                sig_key,
                json.dumps(
                    {
                        "algorithm": sig.get("algorithm", "ed25519"),
                        "value_hex": sig["value_hex"],
                        "public_key_hex": sig.get("public_key_hex", ""),
                    }
                ).encode("utf-8"),
                "application/json",
            )

        return {
            "driver": self.name,
            "bucket": bucket,
            "prefix": base_path,
            "manifest_uri": manifest_uri,
            "signature_uri": signature_uri,
            "published_files": uploaded,
            "manifest": manifest,
        }


class GitLFSDriver:
    """Publish by staging into a git-lfs-tracked repo and pushing."""

    name = "git_lfs"

    def publish(self, build_dir: Path, target_config: dict[str, Any]) -> dict[str, Any]:
        """Add manifest + artifacts to a git-lfs repo and push.

        ``target_config`` keys: ``repo_dir`` (required), ``branch`` (optional,
        default ``main``), ``remote`` (optional, default ``origin``), ``asset``,
        ``version``, ``signing_key``, ``timeout_s``.
        """
        repo_dir_cfg = target_config.get("repo_dir")
        if not repo_dir_cfg:
            message = "GitLFSDriver requires target_config['repo_dir']"
            raise ValueError(message)
        repo_dir = Path(repo_dir_cfg).resolve()
        branch = str(target_config.get("branch") or "main")
        remote = str(target_config.get("remote") or "origin")
        asset = target_config.get("asset") or Path(build_dir).name
        version = str(target_config.get("version") or "0.1.0")
        timeout_s = float(target_config.get("timeout_s") or 60.0)

        git_exe = shutil.which("git")
        if git_exe is None:
            message = "GitLFSDriver requires `git` on PATH"
            raise RuntimeError(message)

        target_dir = _target_subdir(repo_dir, asset, version)
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest = build_manifest(Path(build_dir), asset=asset)
        manifest = sign_manifest(manifest, signing_key_path=target_config.get("signing_key"))

        copied: list[str] = []
        for entry in manifest.get("package_formats", []):
            src = _resolve_build_artifact(Path(build_dir), entry["uri"])
            dst = target_dir / Path(entry["uri"]).name
            _copy_no_overwrite(src, dst)
            copied.append(str(dst))

        manifest_path = target_dir / "manifest.json"
        _write_text_no_overwrite(
            manifest_path,
            json.dumps(redact_secrets(manifest), indent=2, sort_keys=False),
        )
        signature_path: Path | None = None
        sig = manifest.get("signature") or {}
        if isinstance(sig, dict) and sig.get("value_hex"):
            signature_path = target_dir / "manifest.sig"
            _write_text_no_overwrite(
                signature_path,
                json.dumps(
                    {
                        "algorithm": sig.get("algorithm", "ed25519"),
                        "value_hex": sig["value_hex"],
                        "public_key_hex": sig.get("public_key_hex", ""),
                    },
                    indent=2,
                ),
            )

        rel_dir = _safe_object_key(asset, version)
        commands = [
            [git_exe, "lfs", "track", f"{rel_dir}/*"],
            [git_exe, "add", ".gitattributes", rel_dir],
            [git_exe, "commit", "-m", f"publish: {asset} {version}"],
            [git_exe, "push", remote, branch],
        ]
        step_reports: list[dict[str, Any]] = []
        for argv in commands:
            result = run_sandboxed(argv, cwd=repo_dir, timeout_s=timeout_s)
            step = " ".join(
                Path(str(part)).name if index == 0 else str(part) for index, part in enumerate(argv[:2])
            )
            step_reports.append(
                {
                    "argv": argv,
                    "returncode": result.returncode,
                    "ok": result.ok,
                    "stderr_tail": result.stderr_tail[-400:] if result.stderr_tail else "",
                }
            )
            if not result.ok:
                raise GitLFSPublishError(step, result.returncode, result.stderr_tail)

        return {
            "driver": self.name,
            "repo_dir": str(repo_dir),
            "target_dir": str(target_dir),
            "manifest_uri": str(manifest_path),
            "signature_uri": str(signature_path) if signature_path else None,
            "published_files": copied,
            "git_steps": step_reports,
            "manifest": manifest,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


PUBLISH_DRIVERS: dict[str, PublishDriver] = {
    "local_fs": LocalFSDriver(),
    "s3": S3Driver(),
    "supabase": SupabaseDriver(),
    "git_lfs": GitLFSDriver(),
}


def register_driver(target_id: str, driver: PublishDriver) -> None:
    """Register a custom publish driver under ``target_id``.

    Overwrites any existing driver registered under the same id.
    """
    if not isinstance(target_id, str) or not target_id:
        message = "register_driver: target_id must be a non-empty string"
        raise ValueError(message)
    PUBLISH_DRIVERS[target_id] = driver


def get_driver(target_id: str) -> PublishDriver:
    """Look up a publish driver by id. Raises ``ValueError`` if unknown."""
    if target_id not in PUBLISH_DRIVERS:
        message = f"Unknown publish target '{target_id}'. Known drivers: {sorted(PUBLISH_DRIVERS)}"
        raise ValueError(message)
    return PUBLISH_DRIVERS[target_id]
