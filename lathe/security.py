"""Small security helpers shared by artifact-producing and ingress code."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|apikey|authorization|bearer|credential|password|private[_-]?key|secret|"
    r"service[_-]?key|signing[_-]?key|token)",
    re.IGNORECASE,
)
_REDACTED = "[redacted]"
_ERR_BOUNDARY_NAME = "boundary policy name must be non-empty"
_ERR_BOUNDARY_CONTROLS = "untrusted boundary policy must name at least one control"
_ERR_BOUNDARY_CONTROL = "boundary policy controls must be non-empty"
_ERR_BOUNDARY_POLICY = "at least one boundary policy is required"
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?P<key>\b(?:api[_-]?key|apikey|authorization|bearer|credential|password|"
    r"private[_-]?key|secret|service[_-]?key|signing[_-]?key|token)\b)"
    r"\s*['\"]?\s*[:=]\s*['\"]?(?:Bearer\s+)?(?P<value>[^'\"\s,;}\]]+)",
    re.IGNORECASE,
)
_PATH_SEGMENT_SECRET_RE = re.compile(
    r"(?P<prefix>[/\\](?:api[_-]?key|apikey|authorization|bearer|credential|password|"
    r"private[_-]?key|secret|service[_-]?key|signing[_-]?key|token)[_-]?[/\\])"
    r"(?P<value>[^/\\\s]+)",
    re.IGNORECASE,
)
_COMMON_SECRET_VALUE_RE = re.compile(r"\b(?:sk|pk|ghp|gho|glpat)-[A-Za-z0-9_=-]{8,}\b")


class TrustLevel(StrEnum):
    """Trust classification for data crossing a compiler boundary."""

    TRUSTED_INTERNAL = "trusted_internal"
    UNTRUSTED = "untrusted"


class InputClass(StrEnum):
    """Known classes of untrusted input accepted by the reference compiler."""

    LATHE_SOURCE = "lathe_source"
    ASSET_REF_PATH = "asset_ref_path"
    EXTERNAL_IMAGE = "external_image"
    EXTERNAL_MESH = "external_mesh"
    RUNTIME_CONFIG = "runtime_config"
    NETWORK_PROVIDER = "network_provider"
    WONDER_CONTRACT = "wonder_contract"


@dataclass(frozen=True)
class BoundaryPolicy:
    """Machine-checkable trust-boundary metadata for an ingress function."""

    name: str
    input_class: InputClass
    trust_level: TrustLevel
    controls: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate that untrusted boundaries name their controls."""
        if not self.name.strip():
            raise ValueError(_ERR_BOUNDARY_NAME)
        if self.trust_level == TrustLevel.UNTRUSTED and not self.controls:
            raise ValueError(_ERR_BOUNDARY_CONTROLS)
        for control in self.controls:
            if not control.strip():
                raise ValueError(_ERR_BOUNDARY_CONTROL)

    @property
    def untrusted(self) -> bool:
        """Return True when the boundary accepts attacker-controlled input."""
        return self.trust_level == TrustLevel.UNTRUSTED


def boundary_policy(
    *,
    name: str,
    input_class: InputClass,
    trust_level: TrustLevel = TrustLevel.UNTRUSTED,
    controls: Iterable[str],
) -> BoundaryPolicy:
    """Build an enforceable boundary policy from explicit controls."""
    return BoundaryPolicy(
        name=name,
        input_class=input_class,
        trust_level=trust_level,
        controls=tuple(controls),
    )


def ingress_boundary(*policies: BoundaryPolicy) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach trust-boundary policy metadata to an ingress function.

    Tests assert these annotations stay on the choke points where untrusted
    source, refs, provider responses, and runtime configs enter the compiler.
    """
    if not policies:
        raise ValueError(_ERR_BOUNDARY_POLICY)

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__lathe_boundary_policies__ = tuple(policies)
        return func

    return decorate


def get_boundary_policies(func: Callable[..., Any]) -> tuple[BoundaryPolicy, ...]:
    """Return boundary policies attached by :func:`ingress_boundary`."""
    return tuple(getattr(func, "__lathe_boundary_policies__", ()))


def is_sensitive_key(key: object) -> bool:
    """Return True when a mapping key conventionally carries a secret value."""
    return isinstance(key, str) and bool(_SENSITIVE_KEY_RE.search(key))


def _redact_secret_text(value: str) -> str:
    redacted = _BEARER_RE.sub("Bearer [redacted]", value)
    redacted = _KEY_VALUE_SECRET_RE.sub(lambda match: f"{match.group('key')}=[redacted]", redacted)
    redacted = _PATH_SEGMENT_SECRET_RE.sub(lambda match: f"{match.group('prefix')}[redacted]", redacted)
    return _COMMON_SECRET_VALUE_RE.sub("[redacted]", redacted)


def redact_secrets(value: Any) -> Any:
    """Return a JSON-friendly copy with secret-bearing fields redacted."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            redacted[key] = _REDACTED if is_sensitive_key(key) else redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _redact_secret_text(value)
    return value


__all__ = [
    "BoundaryPolicy",
    "InputClass",
    "TrustLevel",
    "boundary_policy",
    "get_boundary_policies",
    "ingress_boundary",
    "is_sensitive_key",
    "redact_secrets",
]
