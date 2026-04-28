"""Top-level pytest configuration for the Lathe test suite.

Provides capability-based skip markers, shared fixtures, and CI-full-matrix
enforcement. See `tests/README.md` for the full taxonomy and Plan 04 for the
coverage plan.
"""

from __future__ import annotations

import errno
import importlib.util
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

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

_DEDICATED_LANE_DIRS = frozenset({"fuzz", "golden", "property"})
_SKIP_MARKERS_REQUIRING_REASONS = frozenset({"skip", "skipif", "xfail"})
_TEST_TEMP_ENV_KEYS = ("TMP", "TEMP", "TMPDIR")
_ORIGINAL_MKDTEMP = tempfile.mkdtemp
_ORIGINAL_TEMPORARY_DIRECTORY = tempfile.TemporaryDirectory
_ORIGINAL_TMP_PATH_FACTORY_GETBASETEMP = TempPathFactory.getbasetemp
_ORIGINAL_TMP_PATH_FACTORY_MKTEMP = TempPathFactory.mktemp
_PREVIOUS_TEMP_DIR: str | None = None
_PREVIOUS_TEMP_ENV: dict[str, str | None] = {}


def _windows_workspace_mkdtemp(suffix=None, prefix=None, dir=None):  # type: ignore[no-untyped-def]
    """Create temp directories with sandbox-writable Windows permissions."""
    prefix, suffix, dir, output_type = tempfile._sanitize_params(prefix, suffix, dir)  # type: ignore[attr-defined]

    names = tempfile._get_candidate_names()  # type: ignore[attr-defined]
    if output_type is bytes:
        names = map(os.fsencode, names)

    for seq in range(tempfile.TMP_MAX):
        name = next(names)
        file = os.path.join(dir, prefix + name + suffix)
        sys.audit("tempfile.mkdtemp", file)
        try:
            os.mkdir(file, 0o777)
        except FileExistsError:
            continue
        except PermissionError:
            if os.name == "nt" and os.path.isdir(dir) and seq < tempfile.TMP_MAX - 1:
                continue
            raise
        return os.path.abspath(file)

    raise FileExistsError(errno.EEXIST, "No usable temporary directory name found")


class _WindowsWorkspaceTemporaryDirectory(_ORIGINAL_TEMPORARY_DIRECTORY):  # type: ignore[misc]
    """TemporaryDirectory variant that tolerates sandbox cleanup denial."""

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["ignore_cleanup_errors"] = True
        super().__init__(*args, **kwargs)


def _workspace_tmp_path_factory_getbasetemp(self: TempPathFactory) -> Path:
    """Return a pytest tmp_path base directory that stays writable on Windows."""
    if self._basetemp is None:
        root = Path(tempfile.gettempdir()) / f"pytest-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        root.mkdir(parents=True)
        self._basetemp = root.resolve()
        self._trace("new basetemp", self._basetemp)
    return self._basetemp


def _workspace_tmp_path_factory_mktemp(self: TempPathFactory, basename: str, numbered: bool = True) -> Path:
    basename = self._ensure_relative_to_basetemp(basename)
    base = self.getbasetemp()
    if numbered:
        suffix = getattr(self, "_lathe_tmp_path_counter", 0)
        self._lathe_tmp_path_counter = suffix + 1
        path = base / f"{basename}{suffix}"
    else:
        path = base / basename
    path.mkdir()
    self._trace("mktemp", path)
    return path


def _configure_workspace_temp_root(config: pytest.Config) -> None:
    """Keep legacy tempfile users inside the workspace during pytest runs."""
    global _PREVIOUS_TEMP_DIR, _PREVIOUS_TEMP_ENV

    if getattr(config.option, "collectonly", False):
        return

    raw_root = os.environ.get("LATHE_TEST_TMP_ROOT")
    temp_root = Path(raw_root) if raw_root else Path(config.rootpath) / ".tmp_tests"
    if not temp_root.is_absolute():
        temp_root = Path(config.rootpath) / temp_root
    temp_root = temp_root.resolve()
    temp_root.mkdir(parents=True, exist_ok=True)

    _PREVIOUS_TEMP_DIR = tempfile.tempdir
    _PREVIOUS_TEMP_ENV = {key: os.environ.get(key) for key in _TEST_TEMP_ENV_KEYS}
    tempfile.tempdir = str(temp_root)
    if os.name == "nt":
        tempfile.mkdtemp = _windows_workspace_mkdtemp
        tempfile.TemporaryDirectory = _WindowsWorkspaceTemporaryDirectory
        TempPathFactory.getbasetemp = _workspace_tmp_path_factory_getbasetemp
        TempPathFactory.mktemp = _workspace_tmp_path_factory_mktemp
    if raw_root:
        for key in _TEST_TEMP_ENV_KEYS:
            os.environ[key] = str(temp_root)


def _restore_workspace_temp_root() -> None:
    global _PREVIOUS_TEMP_DIR, _PREVIOUS_TEMP_ENV

    tempfile.tempdir = _PREVIOUS_TEMP_DIR
    tempfile.mkdtemp = _ORIGINAL_MKDTEMP
    tempfile.TemporaryDirectory = _ORIGINAL_TEMPORARY_DIRECTORY
    TempPathFactory.getbasetemp = _ORIGINAL_TMP_PATH_FACTORY_GETBASETEMP
    TempPathFactory.mktemp = _ORIGINAL_TMP_PATH_FACTORY_MKTEMP
    for key, value in _PREVIOUS_TEMP_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _lane_path_requested(config: pytest.Config, lane_dir: Path) -> bool:
    repo_root = Path(__file__).resolve().parent.parent
    for raw_arg in config.invocation_params.args:
        arg = str(raw_arg)
        if not arg or arg.startswith("-"):
            continue
        requested = Path(arg)
        if not requested.is_absolute():
            requested = repo_root / requested
        try:
            requested = requested.resolve()
        except OSError:
            continue
        if requested == lane_dir or _path_is_relative_to(requested, lane_dir):
            return True
    return False


def _lane_marker_requested(config: pytest.Config, lane: str) -> bool:
    args = [str(arg) for arg in config.invocation_params.args]
    for index, arg in enumerate(args[:-1]):
        if arg == "-m":
            marker_expr = args[index + 1]
            return lane in marker_expr.replace("(", " ").replace(")", " ").split()
        if arg.startswith("-m") and len(arg) > 2:
            marker_expr = arg[2:].strip()
            return lane in marker_expr.replace("(", " ").replace(")", " ").split()
    markexpr = str(getattr(config.option, "markexpr", "") or "")
    if not markexpr or f"not {lane}" in markexpr:
        return False
    return lane in markexpr.replace("(", " ").replace(")", " ").split()


def _marker_has_reason(marker: pytest.Mark) -> bool:
    reason = marker.kwargs.get("reason")
    if reason is None:
        string_args = [arg for arg in marker.args if isinstance(arg, str)]
        reason = string_args[-1] if string_args else None
    return isinstance(reason, str) and bool(reason.strip())


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Keep default pytest from importing dev-only dedicated lanes.

    Marker deselection happens after module import, so a minimal clean-clone
    install can fail collecting fuzz/golden tests before they are deselected.
    Explicit lane paths or positive marker selection still collect normally.
    """
    path = Path(collection_path).resolve()
    tests_root = Path(__file__).resolve().parent
    for lane in _DEDICATED_LANE_DIRS:
        lane_dir = tests_root / lane
        if path == lane_dir or _path_is_relative_to(path, lane_dir):
            if _lane_path_requested(config, lane_dir) or _lane_marker_requested(config, lane):
                return None
            return True
    return None


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    _configure_workspace_temp_root(config)
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


def pytest_unconfigure(config: pytest.Config) -> None:
    _restore_workspace_temp_root()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    full_matrix = os.environ.get("LATHE_CI_FULL", "") == "1"
    slow_requested = _lane_marker_requested(config, "slow")
    deselected_slow: list[pytest.Item] = []
    selected_items: list[pytest.Item] = []
    unreasoned_skips: list[tuple[str, str]] = []
    missing_in_full: list[tuple[str, str, str]] = []

    for item in items:
        if item.get_closest_marker("slow") is not None and not slow_requested:
            deselected_slow.append(item)
            continue
        selected_items.append(item)
        for marker in item.iter_markers():
            if marker.name in _SKIP_MARKERS_REQUIRING_REASONS and not _marker_has_reason(marker):
                unreasoned_skips.append((item.nodeid, marker.name))

        for marker_name, (reason, probe) in _CAPABILITY_PROBES.items():
            if item.get_closest_marker(marker_name) is None:
                continue
            if probe():
                continue
            if full_matrix:
                missing_in_full.append((item.nodeid, marker_name, reason))
            else:
                item.add_marker(pytest.mark.skip(reason=reason))

    if deselected_slow:
        config.hook.pytest_deselected(items=deselected_slow)
        items[:] = selected_items

    if unreasoned_skips:
        lines = [f"  - {nodeid} [{marker}]" for nodeid, marker in unreasoned_skips]
        pytest.exit(
            "Skip/xfail markers must include an explicit, non-empty reason:\n" + "\n".join(lines),
            returncode=4,
        )

    if full_matrix and missing_in_full:
        lines = [f"  - {nodeid} [{marker}] — {reason}" for nodeid, marker, reason in missing_in_full]
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
        if key.startswith("LATHE_") or key.startswith("HTTP_PROXY") or key.startswith("HTTPS_PROXY"):
            monkeypatch.delenv(key, raising=False)
        elif key not in _ENV_KEEP and not key.startswith("_"):
            pass
    return {k: v for k, v in os.environ.items() if k in _ENV_KEEP or k.startswith("LATHE_")}


@pytest.fixture()
def repo_root() -> Path:
    """Absolute path to the repository root (the directory containing ``tests/``)."""
    return Path(__file__).resolve().parent.parent
