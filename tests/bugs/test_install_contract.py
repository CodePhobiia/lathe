"""Regression tests for the install-contract fix (C2).

The conservative ``lathe build`` path hard-imports ``scipy``
(``lathe/geometry_kernel.py``) and ``networkx`` (transitive via
``trimesh.repair``). Both were missing from
``pyproject.toml::project.dependencies`` and from
``lathe.doctor._BASE_REQUIRED_PACKAGES``. After the fix they are core
deps and ``doctor`` reports them under base_dependencies.
"""

from __future__ import annotations

import importlib

import pytest

from lathe.doctor import _BASE_REQUIRED_PACKAGES, _package_reports


@pytest.mark.parametrize("package_name", ["scipy", "networkx"])
def test_conservative_build_dependency_is_importable(package_name: str) -> None:
    importlib.import_module(package_name)


@pytest.mark.parametrize("package_name", ["scipy", "networkx"])
def test_doctor_treats_dependency_as_base_required(package_name: str) -> None:
    assert package_name in _BASE_REQUIRED_PACKAGES
    reports = _package_reports()
    assert package_name in reports
    assert reports[package_name]["available"] is True
