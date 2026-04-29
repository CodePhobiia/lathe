"""Stable identifier helpers for Wonder scene contracts."""

from __future__ import annotations

import hashlib
import re
from typing import Final

MAX_ID_BODY: Final[int] = 80
SNAKE_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]{2,79}$"
SCENE_ENTITY_PATTERNS: Final[dict[str, str]] = {
    "object": r"^obj_[a-z0-9_]{3,80}$",
    "region": r"^region_[a-z0-9_]{3,80}$",
    "relationship": r"^rel_[a-z0-9_]{3,80}$",
    "material": r"^mat_[a-z0-9_]{3,80}$",
    "light": r"^light_[a-z0-9_]{3,80}$",
    "camera": r"^camera_[a-z0-9_]{3,80}$",
    "curiosity": r"^curiosity_[a-z0-9_]{3,80}$",
    "hidden": r"^hidden_[a-z0-9_]{3,80}$",
    "memory": r"^mem_[a-z0-9_]{3,80}$",
}

_SNAKE_ID_RE: Final[re.Pattern[str]] = re.compile(SNAKE_ID_PATTERN)
_ENTITY_RE_BY_PREFIX: Final[dict[str, re.Pattern[str]]] = {
    prefix: re.compile(pattern) for prefix, pattern in SCENE_ENTITY_PATTERNS.items()
}


def digest_text(value: object, *, length: int = 8) -> str:
    """Return a deterministic short digest for ID collision suffixes."""
    if length < 4:
        raise ValueError("digest length must be at least 4 characters")
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def slugify_id_body(value: object, *, fallback: str = "item") -> str:
    """Convert arbitrary text into a schema-compatible lower snake-case body."""
    raw = str(value).strip().lower().replace("&", " and ")
    slug = re.sub(r"[^a-z0-9]+", "_", raw)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    if len(slug) < 3:
        slug = f"{slug}_{fallback}"
    return slug


def clamp_id_body(body: str, *, max_body: int = MAX_ID_BODY) -> str:
    """Clamp an ID body without losing deterministic uniqueness signals."""
    if len(body) <= max_body:
        return body
    suffix = digest_text(body)
    trim_length = max_body - len(suffix) - 1
    trimmed = body[:trim_length].rstrip("_")
    if len(trimmed) < 3:
        trimmed = "id"
    return f"{trimmed}_{suffix}"


def snake_id(value: object, *, fallback: str = "item") -> str:
    """Return a generic `snake_id` matching Wonder schema conventions."""
    return clamp_id_body(slugify_id_body(value, fallback=fallback))


def scene_entity_id(prefix: str, value: object, *, suffix: int | None = None) -> str:
    """Return a stable scene entity ID for a supported Scene Graph prefix."""
    if prefix not in SCENE_ENTITY_PATTERNS:
        supported = ", ".join(sorted(SCENE_ENTITY_PATTERNS))
        raise ValueError(f"unsupported scene entity prefix {prefix!r}; supported: {supported}")
    body = slugify_id_body(value, fallback=prefix)
    if suffix is not None:
        body = f"{body}_{suffix:03d}"
    return f"{_prefix_token(prefix)}_{clamp_id_body(body)}"


def is_snake_id(value: object) -> bool:
    """Return true when a value is a generic Wonder snake ID."""
    return isinstance(value, str) and _SNAKE_ID_RE.fullmatch(value) is not None


def is_scene_entity_id(prefix: str, value: object) -> bool:
    """Return true when a value matches the requested Scene Graph entity ID pattern."""
    pattern = _ENTITY_RE_BY_PREFIX.get(prefix)
    return isinstance(value, str) and pattern is not None and pattern.fullmatch(value) is not None


def require_scene_entity_id(prefix: str, value: object) -> str:
    """Return a valid entity ID or raise a clear `ValueError`."""
    if is_scene_entity_id(prefix, value):
        return str(value)
    pattern = SCENE_ENTITY_PATTERNS.get(prefix)
    if pattern is None:
        supported = ", ".join(sorted(SCENE_ENTITY_PATTERNS))
        raise ValueError(f"unsupported scene entity prefix {prefix!r}; supported: {supported}")
    raise ValueError(f"{prefix} ID must match {pattern!r}: {value!r}")


def _prefix_token(prefix: str) -> str:
    if prefix == "object":
        return "obj"
    if prefix == "relationship":
        return "rel"
    if prefix == "material":
        return "mat"
    if prefix == "memory":
        return "mem"
    return prefix


__all__ = [
    "MAX_ID_BODY",
    "SCENE_ENTITY_PATTERNS",
    "SNAKE_ID_PATTERN",
    "clamp_id_body",
    "digest_text",
    "is_scene_entity_id",
    "is_snake_id",
    "require_scene_entity_id",
    "scene_entity_id",
    "slugify_id_body",
    "snake_id",
]
