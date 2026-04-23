"""Top-level pytest configuration for the Lathe test suite.

Provides capability-based skip markers, shared fixtures, and CI-full-matrix
enforcement. See `tests/README.md` for the full taxonomy and Plan 04 for the
coverage plan.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from typing import Iterator

import pytest


# ---------------------------------------------------------------------------
# Capability probes
# ---------------------------------------------------------------------------

def _blender_available() -> bool:
    explicit = os.environ.get("LATHE_BLENDER_PATH", "").strip()
    if explicit:
        return Path(explicit).exists()
    return shutil.which("blender") is not None


def _xatlas_available() -> bool:
    return importlib.util.find_spec("xatlas") is not None


def _torch_available() -> bool:
    return importlib.util.find_spec("torch") is not None


def _network_available() -> bool:
    return os.environ.get("LATHE_TESTS_ALLOW_NETWORK", "") == "1"


_CAPABILITY_PROBES = {
    "requires_blender": ("Blender executable not available", _blender_available),
    "requires_xatlas": ("xatlas package not installed", _xatlas_available),
    "requires_torch": ("torch package not installed", _torch_available),
    "requires_network": (
        "network tests disabled (set LATHE_TESTS_ALLOW_NETWORK=1)",
        _network_available,
    ),
}


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    for marker, (reason, _) in _CAPABILITY_PROBES.items():
        config.addinivalue_line("markers", f"{marker}: {reason}")
    config.addinivalue_line(
        "markers",
        "property: marks a property-based (Hypothesis) test",
    )
    config.addinivalue_line(
        "markers",
        "golden: marks a golden/snapshot test",
    )
    config.addinivalue_line(
        "markers",
        "contract: marks a stable-contract test (e.g. intent_mesh_handoff_v1)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    full_matrix = os.environ.get("LATHE_CI_FULL", "") == "1"
    missing_in_full: list[tuple[str, str, str]] = []

    for item in items:
        for marker_name, (reason, probe) in _CAPABILITY_PROBES.items():
            if item.get_closest_marker(marker_name) is None:
                continue
            if probe():
                continue
            if full_matrix:
                missing_in_full.append((item.nodeid, marker_name, reason))
            else:
                item.add_marker(pytest.mark.skip(reason=reason))

    if full_matrix and missing_in_full:
        lines = [
            f"  - {nodeid} [{marker}] — {reason}"
            for nodeid, marker, reason in missing_in_full
        ]
        pytest.exit(
            "LATHE_CI_FULL=1 but capability-gated tests would skip:\n"
            + "\n".join(lines)
            + "\nInstall the missing extras (blender/xatlas/torch/network) "
            "or drop LATHE_CI_FULL to allow skipping.",
            returncode=4,
        )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """Per-test scratch directory.

    Thin wrapper over ``tmp_path`` so that tests can refer to a semantic
    name when they use the directory as a build/artifact workspace. Kept as
    a fixture so Wave 3 tests can later add structured subdirs without
    churning call sites.
    """
    return tmp_path


_ENV_KEEP = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "PYTHONIOENCODING",
    "PYTEST_CURRENT_TEST",
    "VIRTUAL_ENV",
}


@pytest.fixture()
def lathe_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Clean, deterministic subset of env vars for build runs.

    Strips Lathe-scoped env vars (``LATHE_*``) plus anything else that could
    leak nondeterminism from the host (locale overrides, proxies). Returns
    the resulting env as a dict for tests that want to inspect it.
    """
    for key in list(os.environ.keys()):
        if key.startswith("LATHE_"):
            monkeypatch.delenv(key, raising=False)
        elif key.startswith("HTTP_PROXY") or key.startswith("HTTPS_PROXY"):
            monkeypatch.delenv(key, raising=False)
        elif key not in _ENV_KEEP and not key.startswith("_"):
            pass
    return {k: v for k, v in os.environ.items() if k in _ENV_KEEP or k.startswith("LATHE_")}


@pytest.fixture()
def repo_root() -> Path:
    """Absolute path to the repository root (the directory containing ``tests/``)."""
    return Path(__file__).resolve().parent.parent
