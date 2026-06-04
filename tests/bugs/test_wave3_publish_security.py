"""Wave 3 regression tests: publish/path/network hardening.

Covers:

- M1  ``GitLFSDriver.publish`` rejects option-style remote/branch and inserts
      ``--`` before user-derived positionals.
- M2  ``_resolve_publish_repo_dir`` requires ``LATHE_ALLOW_EXTERNAL_PUBLISH``
      for absolute paths and routes relative paths through ``safe_resolve``.
- M3  ``ref.resolve_ref`` returns ``target_kind="missing"`` for absolute
      and traversal-style refs (instead of following them).
- M4  ``build_manifest`` recomputes sha256 / size from disk and refuses a
      mismatched declared value.
- M16 ``runtime_config.load_runtime_config`` enforces a hard byte cap with
      no stat/read TOCTOU.
- M17 ``imaging.open_guarded`` promotes ``DecompressionBombWarning`` to
      ``DecompressionBombError``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from lathe import imaging, publish, ref, runtime_config
from lathe.errors import RuntimeConfigError
from lathe.paths import PathGuardError
from PIL import Image

# --- M1 -------------------------------------------------------------


@pytest.mark.parametrize(
    "remote",
    [
        "--upload-pack=touch /tmp/x",
        "-oProxyCommand=evil",
        "evil ; rm -rf /",
    ],
)
def test_gitlfs_publish_rejects_unsafe_remote(tmp_path: Path, remote: str) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    driver = publish.GitLFSDriver()
    with pytest.raises(ValueError, match="git remote name"):
        driver.publish(
            tmp_path / "build",
            {"repo_dir": str(repo_dir.relative_to(tmp_path)), "remote": remote},
        )


@pytest.mark.parametrize(
    "branch",
    ["--upload-pack=cmd", "-oCmd=x", "-evil-branch", "spaces here"],
)
def test_gitlfs_publish_rejects_unsafe_branch(tmp_path: Path, branch: str) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    driver = publish.GitLFSDriver()
    with pytest.raises(ValueError, match="git branch name"):
        driver.publish(
            tmp_path / "build",
            {
                "repo_dir": str(repo_dir.relative_to(tmp_path)),
                "branch": branch,
            },
        )


# --- M2 -------------------------------------------------------------


def test_resolve_publish_repo_dir_rejects_absolute_without_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LATHE_ALLOW_EXTERNAL_PUBLISH", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathGuardError, match="absolute"):
        publish._resolve_publish_repo_dir(str(tmp_path / "outside"))


def test_resolve_publish_repo_dir_accepts_relative_under_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "repo").mkdir()
    monkeypatch.chdir(tmp_path)
    resolved = publish._resolve_publish_repo_dir("repo")
    assert resolved == (tmp_path / "repo").resolve()


def test_resolve_publish_repo_dir_with_env_allows_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LATHE_ALLOW_EXTERNAL_PUBLISH", "1")
    target = tmp_path / "external"
    target.mkdir()
    resolved = publish._resolve_publish_repo_dir(str(target))
    assert resolved == target.resolve()


# --- M3 -------------------------------------------------------------


def test_resolve_ref_marks_absolute_target_as_missing(tmp_path: Path) -> None:
    node = ref.RefNode(raw="@lathe[/etc/passwd]", target="/etc/passwd", selector=None)
    result = ref.resolve_ref(node, repo_root=tmp_path)
    assert result["target_kind"] == "missing"


def test_resolve_ref_marks_traversal_target_as_missing(tmp_path: Path) -> None:
    node = ref.RefNode(
        raw="@lathe[../../etc/passwd]",
        target="../../etc/passwd",
        selector=None,
    )
    result = ref.resolve_ref(node, repo_root=tmp_path)
    assert result["target_kind"] == "missing"


# --- M4 -------------------------------------------------------------


def _seed_build_with_manifest(
    build_dir: Path, *, declared_sha: str | None, declared_size: int | None
) -> None:
    package_dir = build_dir / "stages" / "package"
    package_dir.mkdir(parents=True)
    artifact = build_dir / "demo.glb"
    artifact.write_bytes(b"glb-bytes-go-here")
    output: dict[str, Any] = {"format": "glb", "uri": "demo.glb"}
    if declared_sha is not None:
        output["sha256"] = declared_sha
    if declared_size is not None:
        output["size_bytes"] = declared_size
    (package_dir / "package_manifest.json").write_text(
        json.dumps({"asset_id": "demo", "outputs": [output]}),
        encoding="utf-8",
    )


def test_build_manifest_rejects_sha_mismatch(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    _seed_build_with_manifest(build_dir, declared_sha="0" * 64, declared_size=None)
    with pytest.raises(publish.PublishManifestError, match="sha256 mismatch"):
        publish.build_manifest(build_dir, asset="demo")


def test_build_manifest_rejects_size_mismatch(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    _seed_build_with_manifest(build_dir, declared_sha=None, declared_size=999)
    with pytest.raises(publish.PublishManifestError, match="size mismatch"):
        publish.build_manifest(build_dir, asset="demo")


def test_build_manifest_recomputes_sha_when_omitted(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    _seed_build_with_manifest(build_dir, declared_sha=None, declared_size=None)
    manifest = publish.build_manifest(build_dir, asset="demo")
    actual_sha = hashlib.sha256(b"glb-bytes-go-here").hexdigest()
    assert manifest["package_formats"][0]["sha256"] == actual_sha
    assert manifest["package_formats"][0]["size_bytes"] == len(b"glb-bytes-go-here")


# --- M16 ------------------------------------------------------------


def test_runtime_config_rejects_oversize_payload(tmp_path: Path) -> None:
    cfg = tmp_path / "rt.json"
    payload = "x" * (runtime_config._MAX_CONFIG_BYTES + 1)
    cfg.write_text(payload, encoding="utf-8")
    with pytest.raises(RuntimeConfigError, match="exceeds 256 KiB"):
        runtime_config.load_runtime_config(cfg)


# --- M17 ------------------------------------------------------------


def test_open_guarded_raises_decompression_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    img_path = tmp_path / "img.png"
    Image.new("RGB", (200, 200), "white").save(img_path)
    # Lowering MAX_IMAGE_PIXELS forces the warning that open_guarded
    # promotes to an error.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1024)
    with pytest.raises(Image.DecompressionBombError):
        with imaging.open_guarded(img_path) as opened:
            opened.load()
