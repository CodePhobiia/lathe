"""Opt-in anonymous build-ping telemetry.

Plan 09 Phase 10b. Default MUST be disabled; emission is failure-silent.
Payload excludes asset content, paths, raw salts, and environment variables.

Persistence
-----------
Config file lives at an OS-appropriate user config dir:

- ``$XDG_CONFIG_HOME/lathe/telemetry.json`` (or ``~/.config/lathe/...``) on POSIX
- ``%APPDATA%\\lathe\\telemetry.json`` on Windows
- ``~/Library/Application Support/lathe/telemetry.json`` on macOS

If ``platformdirs`` is importable we defer to it; otherwise we fall back to
the paths above.

States
------
- ``unset``: no config file — treated as disabled.
- ``enabled``: config file with ``enabled=True`` and a persistent 16-byte
  hex ``user_salt``.
- ``disabled``: config file with ``enabled=False``; salt is preserved.

The persistent ``user_salt`` stays local.  It is used only to derive
``build_id_hash`` as ``sha256(salt + build_id)[:16]`` so ingest cannot
recompute or link build identities without access to the local salt.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

TELEMETRY_INGEST_URL: str = "https://telemetry.lathe.dev/ingest"
_TELEMETRY_TIMEOUT_S: float = 2.0
_TELEMETRY_MAX_BYTES: int = 64 * 1024
_SALT_BYTES: int = 16


def _user_config_dir() -> Path:
    """Return the user config directory for Lathe, creating OS-appropriate paths.

    Uses :mod:`platformdirs` if available, else falls back to hand-rolled paths.
    """
    try:
        import platformdirs  # type: ignore[import-not-found]
    except ImportError:
        platformdirs = None  # type: ignore[assignment]

    if platformdirs is not None:
        return Path(platformdirs.user_config_dir("lathe", appauthor=False))

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "lathe"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "lathe"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "lathe"
    return Path.home() / ".config" / "lathe"


def _config_path() -> Path:
    return _user_config_dir() / "telemetry.json"


def _read_config() -> dict[str, Any] | None:
    path = _config_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_config(data: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            if tmp_path.exists():
                raise


def is_enabled() -> bool:
    """Return True iff telemetry is explicitly enabled."""
    cfg = _read_config()
    if not cfg:
        return False
    return bool(cfg.get("enabled", False))


def enable(user_salt: str | None = None) -> dict[str, Any]:
    """Enable telemetry and persist a stable anonymous salt.

    If a salt already exists in the config file it is preserved; otherwise a
    fresh 16-byte hex salt is generated (or the ``user_salt`` override is
    used verbatim).
    """
    cfg = _read_config() or {}
    salt = user_salt or cfg.get("user_salt") or secrets.token_hex(_SALT_BYTES)
    cfg.update({"enabled": True, "user_salt": salt})
    _write_config(cfg)
    return dict(cfg)


def disable() -> dict[str, Any]:
    """Disable telemetry. Preserves ``user_salt`` so re-enable keeps identity stable."""
    cfg = _read_config() or {}
    cfg["enabled"] = False
    if "user_salt" not in cfg:
        cfg["user_salt"] = secrets.token_hex(_SALT_BYTES)
    _write_config(cfg)
    return dict(cfg)


def status() -> dict[str, Any]:
    """Return the public telemetry state.

    ``salt_prefix`` is the first four chars of the persistent salt (enough
    for humans to sanity-check; not enough to correlate across users).
    """
    cfg = _read_config()
    path = _config_path()
    if cfg is None:
        return {
            "state": "unset",
            "enabled": False,
            "salt_prefix": None,
            "last_ping_ts": None,
            "config_path": str(path),
            "ingest_url": TELEMETRY_INGEST_URL,
        }
    salt = cfg.get("user_salt") or ""
    return {
        "state": "enabled" if cfg.get("enabled") else "disabled",
        "enabled": bool(cfg.get("enabled", False)),
        "salt_prefix": salt[:4] if salt else None,
        "last_ping_ts": cfg.get("last_ping_ts"),
        "config_path": str(path),
        "ingest_url": TELEMETRY_INGEST_URL,
    }


def clear() -> bool:
    """Delete the telemetry config file. Returns True if it existed."""
    path = _config_path()
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _lathe_version() -> str:
    try:
        from . import __version__ as v

        return str(v)
    except ImportError:
        return "0.0.0"


def _hash_build_id(salt: str, build_id: str) -> str:
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(build_id.encode("utf-8"))
    return h.hexdigest()[:16]


def _extract_build_id(build_report: dict) -> str:
    """Derive a cache-key-like build id from the report without exposing paths."""
    for key in ("build_id", "cache_key", "id"):
        val = build_report.get(key)
        if isinstance(val, str) and val:
            return val
    outputs = []
    for item in build_report.get("outputs") or []:
        if not isinstance(item, dict):
            continue
        outputs.append(
            {
                "format": item.get("format"),
                "sha256": item.get("sha256"),
                "size_bytes": item.get("size_bytes"),
            }
        )
    fingerprint_source = {
        "kind": build_report.get("kind"),
        "backend_stack": _extract_stack_id(build_report),
        "certified": _extract_certified(build_report),
        "outputs": sorted(outputs, key=lambda item: (str(item.get("format")), str(item.get("sha256")))),
    }
    if any(fingerprint_source.values()):
        encoded = json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    return ""


def _extract_stack_id(build_report: dict) -> str:
    backend_stack = build_report.get("backend_stack")
    if isinstance(backend_stack, dict):
        stack_id = backend_stack.get("id")
        if isinstance(stack_id, str):
            return stack_id
    for key in ("stack_id", "backend_id"):
        val = build_report.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _extract_certified(build_report: dict) -> bool | None:
    certified = build_report.get("certified")
    if isinstance(certified, bool):
        return certified
    ok = build_report.get("ok")
    if isinstance(ok, bool):
        return ok
    return None


def _build_payload(build_report: dict, *, salt: str) -> dict[str, Any]:
    build_id = _extract_build_id(build_report)
    stack_id = _extract_stack_id(build_report)
    certified = _extract_certified(build_report)
    exit_code = build_report.get("exit_code", 0 if build_report.get("ok", True) else 1)
    wall_ms = build_report.get("wall_ms")
    if wall_ms is None:
        wall_ms = build_report.get("duration_ms", 0)
    try:
        wall_ms = int(wall_ms)
    except (TypeError, ValueError):
        wall_ms = 0
    return {
        "lathe_version": _lathe_version(),
        "build_id_hash": _hash_build_id(salt, build_id) if build_id else "",
        "build_kind": str(build_report.get("kind") or ""),
        "stack_id": str(stack_id),
        "certified": certified,
        "exit_code": int(exit_code) if isinstance(exit_code, (int, bool)) else 0,
        "wall_ms": wall_ms,
    }


def emit_build_ping(build_report: dict) -> bool:
    """Post an anonymous build ping if telemetry is enabled.

    Returns True on successful dispatch, False otherwise. Never raises.
    """
    try:
        cfg = _read_config()
        if not cfg or not cfg.get("enabled"):
            return False
        salt = cfg.get("user_salt")
        if not salt:
            return False

        payload = _build_payload(build_report, salt=str(salt))
        body = json.dumps(payload).encode("utf-8")

        from .net import safe_urlopen  # local import keeps net as soft dep

        safe_urlopen(
            TELEMETRY_INGEST_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
            timeout_s=_TELEMETRY_TIMEOUT_S,
            max_bytes=_TELEMETRY_MAX_BYTES,
            expect_content_type=None,
            allowlist=["telemetry.lathe.dev"],
        )

        try:
            cfg["last_ping_ts"] = int(time.time())
            _write_config(cfg)
        except (OSError, TypeError, ValueError):
            return True

        return True
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return False
