"""Small file I/O helpers for scene package artifacts."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

_LOCKS_GUARD = threading.Lock()
_TARGET_LOCKS: dict[Path, threading.Lock] = {}


def _lock_for(path: Path) -> threading.Lock:
    key = path.resolve(strict=False)
    with _LOCKS_GUARD:
        return _TARGET_LOCKS.setdefault(key, threading.Lock())


def _replace_with_retry(temp_path: Path, target: Path) -> None:
    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            temp_path.replace(target)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == 4:
                break
            time.sleep(0.02 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise PermissionError(f"Could not replace {target}")


def write_text_atomic(path: Path, text: str) -> None:
    """Write text through a unique same-directory temp file, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        with _lock_for(path):
            _replace_with_retry(temp_path, path)
    except (OSError, UnicodeError):
        with suppress(OSError):
            temp_path.unlink()
        raise


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Write bytes through a unique same-directory temp file, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        with _lock_for(path):
            _replace_with_retry(temp_path, path)
    except OSError:
        with suppress(OSError):
            temp_path.unlink()
        raise


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON object with stable formatting through an atomic replace."""
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")
