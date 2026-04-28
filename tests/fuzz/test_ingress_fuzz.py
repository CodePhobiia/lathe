"""Fuzz ingress surfaces that accept user- or provider-controlled payloads."""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lathe.cache import _entry_from_dir
from lathe.providers.selection import _redact_provider_config
from lathe.ref import RefParseError, parse_ref
from lathe.runtime_config import RuntimeConfigError, _validate_runtime_config

pytestmark = pytest.mark.fuzz

_EXTENDED = os.environ.get("LATHE_FUZZ_EXTENDED") == "1"
MAX_EXAMPLES = 1000 if _EXTENDED else 100

_JSON_SCALAR = st.one_of(st.none(), st.booleans(), st.integers(-10_000, 10_000), st.text(max_size=40))
_JSON_VALUE = st.recursive(
    _JSON_SCALAR,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=24), children, max_size=6),
    ),
    max_leaves=20,
)
_JSON_OBJECT = st.dictionaries(st.text(min_size=1, max_size=24), _JSON_VALUE, max_size=8)


@given(token=st.text(max_size=160))
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_ref_parser_fuzz_rejects_or_round_trips_cleanly(token: str) -> None:
    """Arbitrary @lathe ref text either parses into a stable node or raises RefParseError."""
    candidate = token if token.startswith("@lathe[") else f"@lathe[{token}]"
    try:
        node = parse_ref(candidate)
    except RefParseError:
        return

    reparsed = parse_ref(node.raw)
    assert reparsed == node


@given(payload=_JSON_OBJECT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_runtime_config_schema_fuzz_rejects_or_accepts_cleanly(payload: dict[str, Any]) -> None:
    """Generated runtime configs must not escape schema validation with random exceptions."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _validate_runtime_config(payload, source="<fuzz>")
    except RuntimeConfigError:
        return

    assert isinstance(payload, dict)


@given(provider_id=st.text(max_size=80), config=_JSON_OBJECT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_provider_config_redaction_fuzz_is_json_safe(provider_id: str, config: dict[str, Any]) -> None:
    """Provider config payloads written into reports must stay JSON-safe and redact secret keys."""
    config["api_key"] = "super-secret-provider-token"
    config["service_key"] = "super-secret-service-token"

    redacted = _redact_provider_config(provider_id, config)
    rendered = json.dumps(redacted, sort_keys=True)

    assert "super-secret-provider-token" not in rendered
    assert "super-secret-service-token" not in rendered


@given(manifest=_JSON_OBJECT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_cache_metadata_fuzz_never_crashes_listing(manifest: dict[str, Any]) -> None:
    """Cache metadata readers tolerate corrupt or surprising manifest payloads."""
    with TemporaryDirectory(prefix="lathe_cache_fuzz_") as tmp:
        entry_dir = Path(tmp) / "entry"
        entry_dir.mkdir()
        (entry_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        entry = _entry_from_dir(entry_dir)

    assert entry.key == "entry"
    assert entry.size_bytes >= 0
