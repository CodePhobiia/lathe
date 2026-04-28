from __future__ import annotations

import pytest
from lathe.mesh_ingest import safe_load_mesh
from lathe.net import safe_urlopen
from lathe.parser import parse_file, parse_text
from lathe.paths import safe_resolve
from lathe.runtime_config import load_runtime_config
from lathe.security import InputClass, TrustLevel, boundary_policy, get_boundary_policies, ingress_boundary
from lathe.shape.geometry.conditioning import collect_shape_conditioning


def _input_classes(func) -> set[InputClass]:
    return {policy.input_class for policy in get_boundary_policies(func)}


def test_untrusted_ingress_functions_are_marked_with_enforceable_policies() -> None:
    expected = {
        parse_file: {InputClass.LATHE_SOURCE},
        parse_text: {InputClass.LATHE_SOURCE},
        safe_resolve: {InputClass.ASSET_REF_PATH},
        safe_load_mesh: {InputClass.EXTERNAL_MESH},
        collect_shape_conditioning: {InputClass.EXTERNAL_IMAGE, InputClass.EXTERNAL_MESH},
        load_runtime_config: {InputClass.RUNTIME_CONFIG},
        safe_urlopen: {InputClass.NETWORK_PROVIDER},
    }

    for func, classes in expected.items():
        policies = get_boundary_policies(func)
        assert _input_classes(func) == classes
        for policy in policies:
            assert policy.trust_level == TrustLevel.UNTRUSTED
            assert policy.controls


def test_untrusted_boundary_policy_requires_named_controls() -> None:
    with pytest.raises(ValueError, match="at least one control"):
        boundary_policy(
            name="missing_controls",
            input_class=InputClass.RUNTIME_CONFIG,
            trust_level=TrustLevel.UNTRUSTED,
            controls=(),
        )


def test_ingress_boundary_requires_at_least_one_policy() -> None:
    with pytest.raises(ValueError, match="at least one boundary policy"):
        ingress_boundary()
