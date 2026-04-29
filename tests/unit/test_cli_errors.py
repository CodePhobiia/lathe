from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lathe.cli import _build_parser
from lathe.cli.build_cmd import run_build


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )


def _json_error(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["diagnostics"]
    assert "Traceback (most recent call last)" not in result.stdout
    return payload


def test_missing_source_file_emits_cli_error_without_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lth"
    result = _cli("check", str(missing))
    assert result.returncode == 2
    assert "lathe error [lathe.cli.file_not_found]" in result.stderr
    assert str(missing) in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.stdout == ""


def test_debug_traceback_env_preserves_python_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lth"
    result = _cli("check", str(missing), env={"LATHE_DEBUG_TRACEBACK": "1"})
    assert result.returncode != 0
    assert "Traceback (most recent call last)" in result.stderr
    assert "FileNotFoundError" in result.stderr


def test_debug_traceback_flag_preserves_python_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lth"
    result = _cli("--debug-traceback", "check", str(missing))
    assert result.returncode != 0
    assert "Traceback (most recent call last)" in result.stderr
    assert "FileNotFoundError" in result.stderr


def test_build_report_json_invalid_syntax_is_machine_readable(tmp_path: Path) -> None:
    source = tmp_path / "bad.lth"
    source.write_text("asset {", encoding="utf-8")

    result = _cli("build", str(source), "bad", "--out", "dist", "--report", "json")

    assert result.returncode == 1
    payload = _json_error(result)
    assert payload["code"] == "lathe.cli.parse_error"
    assert payload["source_path"] == str(source)
    assert payload["diagnostics"][0]["code"] == "lathe.cli.parse_error"


def test_parse_invalid_syntax_emits_structured_error_without_traceback(tmp_path: Path) -> None:
    source = tmp_path / "bad.lth"
    source.write_text("asset {", encoding="utf-8")

    result = _cli("parse", str(source))

    assert result.returncode == 1
    assert result.stdout == ""
    assert "lathe error [lathe.cli.parse_error]" in result.stderr
    assert str(source) in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_check_semantic_resolution_failure_returns_structured_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "bad_resolution.lth"
    source.write_text(
        "module test.bad\nasset demo: prop uses missing_profile {\n}\n",
        encoding="utf-8",
    )

    result = _cli("check", str(source))

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "L2102"
    assert payload["diagnostics"][0]["phase"] == "resolve"
    assert "Unknown use reference 'missing_profile'" in payload["diagnostics"][0]["message"]
    assert "Traceback (most recent call last)" not in result.stdout


@pytest.mark.parametrize("command", ["plan", "materialize"])
def test_asset_resolution_commands_emit_structured_error_without_traceback(command: str) -> None:
    result = _cli(command, "examples/courier_drone.lth", "missing_asset")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "lathe error [lathe.cli.error]" in result.stderr
    assert "Unknown asset or variant 'missing_asset'" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_build_report_json_semantic_check_failure_has_cli_error_code(tmp_path: Path) -> None:
    source = tmp_path / "duplicate_profile.lth"
    source.write_text(
        Path("examples/courier_drone.lth").read_text(encoding="utf-8") + "\nprofile mobile_runtime {}\n",
        encoding="utf-8",
    )
    env = {"LATHE_ALLOW_EXTERNAL_OUT": "1"}

    result = _cli(
        "build",
        str(source),
        "courier_drone",
        "--out",
        str(tmp_path / "out"),
        "--report",
        "json",
        env=env,
    )

    assert result.returncode == 1
    payload = _json_error(result)
    assert payload["code"] == "lathe.cli.build.build_failed"
    assert payload["diagnostics"][0]["code"] == "L2001"
    assert payload["diagnostics"][0]["phase"] == "resolve"


def test_build_report_json_bad_asset_ref_is_machine_readable() -> None:
    result = _cli("build", "examples/courier_drone.lth", "missing_asset", "--out", "dist", "--report", "json")

    assert result.returncode == 1
    payload = _json_error(result)
    assert payload["code"] == "lathe.cli.error"
    assert "Unknown asset or variant 'missing_asset'" in payload["message"]
    assert payload["source_path"] == "examples/courier_drone.lth"


def test_ref_parse_bad_token_emits_structured_error() -> None:
    result = _cli("ref", "parse", "not-a-lathe-ref")

    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["error"]["code"]
    assert payload["error"]["token"] == "not-a-lathe-ref"
    assert "Traceback (most recent call last)" not in result.stderr


def test_build_report_json_invalid_runtime_config_is_machine_readable(tmp_path: Path) -> None:
    config = tmp_path / "bad_runtime.json"
    config.write_text("{ nope", encoding="utf-8")
    env = {"LATHE_ALLOW_EXTERNAL_OUT": "1"}

    result = _cli(
        "build",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        str(tmp_path / "out"),
        "--runtime-config",
        str(config),
        "--report",
        "json",
        env=env,
    )

    assert result.returncode == 1
    payload = _json_error(result)
    assert payload["code"] == "lathe.cli.runtime_config_error"
    assert payload["source_path"] == str(config)
    assert "invalid JSON" in payload["message"]


def test_build_report_json_provider_unavailable_stays_machine_readable(tmp_path: Path) -> None:
    env = {"LATHE_ALLOW_EXTERNAL_OUT": "1"}

    result = _cli(
        "build",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        str(tmp_path / "out"),
        "--shape-provider",
        "definitely_missing_provider",
        "--strict-shape-provider",
        "--report",
        "json",
        env=env,
    )

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "lathe.cli.build.provider_failed"
    assert payload["diagnostics"][0]["code"] == "unknown_provider"
    assert payload["diagnostics"][0]["provider_id"] == "definitely_missing_provider"


def test_build_strict_flag_replaces_deprecated_strict_shape_provider_alias(tmp_path: Path) -> None:
    env = {"LATHE_ALLOW_EXTERNAL_OUT": "1"}

    result = _cli(
        "build",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        str(tmp_path / "out"),
        "--shape-provider",
        "definitely_missing_provider",
        "--strict",
        "--report",
        "json",
        env=env,
    )

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["code"] == "lathe.cli.build.provider_failed"
    assert payload["diagnostics"][0]["code"] == "unknown_provider"


def test_build_package_io_failure_has_cli_error_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from lathe import executor

    def fail_package(*_args, **_kwargs):
        raise FileExistsError("package artifact already exists: stages/package/lod0.glb")

    monkeypatch.setenv("LATHE_ALLOW_EXTERNAL_OUT", "1")
    monkeypatch.setattr(executor, "build_asset", fail_package)
    args = argparse.Namespace(
        file="examples/courier_drone.lth",
        name="courier_drone",
        out=str(tmp_path / "out"),
        runtime_config=None,
        shape_provider=None,
        strict_shape_provider=False,
        allow_fallback=False,
        codex_imagegen=None,
        execution_profile=None,
        publish=None,
        report="json",
        deterministic=False,
    )

    with pytest.raises(SystemExit) as exc:
        run_build(args)

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["code"] == "lathe.cli.build.package_failed"
    assert payload["diagnostics"][0]["code"] == "package_io_error"
    assert payload["diagnostics"][0]["phase"] == "package"
    assert "Traceback (most recent call last)" not in captured.out


def test_build_report_json_unwritable_output_path_is_machine_readable(tmp_path: Path) -> None:
    out_file = tmp_path / "out_file"
    out_file.write_text("not a directory", encoding="utf-8")
    env = {"LATHE_ALLOW_EXTERNAL_OUT": "1"}

    result = _cli(
        "build",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        str(out_file),
        "--report",
        "json",
        env=env,
    )

    assert result.returncode == 1
    payload = _json_error(result)
    assert payload["code"] == "lathe.cli.io_error"
    assert payload["source_path"] == str(out_file)


def test_cache_status_json_tolerates_corrupt_manifest(tmp_path: Path) -> None:
    entry = tmp_path / "builds" / "corrupt"
    entry.mkdir(parents=True)
    (entry / "manifest.json").write_text("{not json", encoding="utf-8")
    (entry / "blob.bin").write_bytes(b"x" * 8)

    result = _cli("cache", "status", "--json", env={"LATHE_CACHE_DIR": str(tmp_path)})

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["entry_count"] == 1
    assert payload["entries"][0]["key"] == "corrupt"
    assert payload["entries"][0]["asset"] is None
    assert payload["entries"][0]["metadata_source"] is None


def test_cache_clean_invalid_duration_emits_cli_error_without_traceback() -> None:
    result = _cli("cache", "clean", "--older-than", "nope", "--dry-run")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.cache.invalid_duration]" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_cache_clean_requires_confirmation_without_traceback() -> None:
    result = _cli("cache", "clean", "--older-than", "7d")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.cache.confirm_required]" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_cache_warm_missing_source_emits_cli_error_without_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lth"
    result = _cli("cache", "warm", str(missing), "missing_asset")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.file_not_found]" in result.stderr
    assert str(missing) in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_mode_build_mismatch_emits_cli_error_without_traceback(tmp_path: Path) -> None:
    result = _cli(
        "adapt",
        "examples/courier_drone.lth",
        "courier_drone",
        "--out",
        str(tmp_path / "out"),
        env={"LATHE_ALLOW_EXTERNAL_OUT": "1"},
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "lathe error [lathe.cli.build.mode_mismatch]" in result.stderr
    assert "shape.mode=generate, not adapt" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_patch_missing_value2_emits_cli_error_without_traceback() -> None:
    result = _cli(
        "patch",
        "examples/courier_drone.lth",
        "--op",
        "widen_search_bounds",
        "--target",
        "courier_drone",
        "--value",
        "feature_density",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.patch.missing_value2]" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_patch_invalid_value2_emits_cli_error_without_traceback() -> None:
    result = _cli(
        "patch",
        "examples/courier_drone.lth",
        "--op",
        "widen_search_bounds",
        "--target",
        "courier_drone",
        "--value",
        "feature_density",
        "--value2",
        "bad",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.patch.invalid_value2]" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_patch_nonnumeric_value2_emits_cli_error_without_traceback() -> None:
    result = _cli(
        "patch",
        "examples/courier_drone.lth",
        "--op",
        "widen_search_bounds",
        "--target",
        "courier_drone",
        "--value",
        "feature_density",
        "--value2",
        "low:high",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lathe error [lathe.cli.patch.invalid_value2]" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


_NEGATIVE_COMMAND_PATHS = [
    ("adapt",),
    ("assemble",),
    ("audit",),
    ("backends",),
    ("bake-audit",),
    ("bench",),
    ("bridge", "doctor"),
    ("bridge", "plan"),
    ("build",),
    ("cache", "clean"),
    ("cache", "migrate"),
    ("cache", "status"),
    ("cache", "warm"),
    ("check",),
    ("completions",),
    ("diff",),
    ("diff-asset",),
    ("doctor",),
    ("explain",),
    ("explain-fit",),
    ("export-blend",),
    ("fit",),
    ("fmt",),
    ("inspect",),
    ("inspect-blend",),
    ("library", "sync"),
    ("materialize",),
    ("normalize",),
    ("parse",),
    ("patch",),
    ("plan",),
    ("probe-blender",),
    ("probe-providers",),
    ("publish",),
    ("reconstruct",),
    ("ref", "copy"),
    ("ref", "diff"),
    ("ref", "inspect"),
    ("ref", "parse"),
    ("ref", "planes"),
    ("render-eval",),
    ("render-fixture",),
    ("schema",),
    ("scene", "assemble"),
    ("scene", "bench"),
    ("scene", "branch"),
    ("scene", "camera-lighting"),
    ("scene", "curiosity"),
    ("scene", "diff"),
    ("scene", "expand-anchor"),
    ("scene", "export"),
    ("scene", "inspect-render"),
    ("scene", "memory", "append"),
    ("scene", "memory", "inspect"),
    ("scene", "layout"),
    ("scene", "materialize"),
    ("scene", "merge"),
    ("scene", "rollback"),
    ("scene", "package", "init"),
    ("scene", "package", "inspect"),
    ("scene", "package", "validate"),
    ("scene", "build"),
    ("scene", "check"),
    ("scene", "patch"),
    ("scene", "plan"),
    ("scene", "propose-repairs"),
    ("scene", "repair"),
    ("scene", "render"),
    ("scene", "roblox-export"),
    ("scene", "roblox-manifest"),
    ("scene", "scene-graph-to-source"),
    ("scene", "style-pack"),
    ("scene", "source-to-scene-graph"),
    ("scene", "validate"),
    ("serve",),
    ("shape-providers",),
    ("snapshot",),
    ("surface-build",),
    ("surface-plan",),
    ("surface-repair",),
    ("surface-validate",),
    ("telemetry", "clear"),
    ("telemetry", "disable"),
    ("telemetry", "enable"),
    ("telemetry", "status"),
    ("test",),
    ("wonder", "alpha-gate"),
    ("wonder", "append-memory-event"),
    ("wonder", "apply-patch"),
    ("wonder", "brief-to-scene"),
    ("wonder", "branch-history"),
    ("wonder", "catalog-examples"),
    ("wonder", "apply-semantic-patch"),
    ("wonder", "capabilities"),
    ("wonder", "check-brief-scene"),
    ("wonder", "check-scene-graph"),
    ("wonder", "compare-renders"),
    ("wonder", "decompose-brief"),
    ("wonder", "diagnose-for-llm"),
    ("wonder", "demo-before-after"),
    ("wonder", "env-probe"),
    ("wonder", "evidence-trace"),
    ("wonder", "generate-scene-plan"),
    ("wonder", "init-package"),
    ("wonder", "lock-camera"),
    ("wonder", "lower-brief"),
    ("wonder", "redact-memory"),
    ("wonder", "readiness-report"),
    ("wonder", "repair-playbook"),
    ("wonder", "rollback-scene"),
    ("wonder", "schema"),
    ("wonder", "schemas"),
    ("wonder", "status"),
    ("wonder", "validate-brief"),
    ("wonder", "validate-example"),
    ("wonder", "validate-asset-provenance-scene"),
    ("wonder", "validate-camera-lock"),
    ("wonder", "validate-game-readiness"),
    ("wonder", "validate-layout-plan"),
    ("wonder", "validate-llm-repair-playbook"),
    ("wonder", "validate-package-manifest"),
    ("wonder", "validate-patch"),
    ("wonder", "validate-plan"),
    ("wonder", "validate-roblox-export-bundle"),
    ("wonder", "validate-roblox-fbx-handoff"),
    ("wonder", "validate-roblox-manifest"),
    ("wonder", "validate-roblox-profile"),
    ("wonder", "validate-scene-assembly"),
    ("wonder", "validate-scene-benchmark-report"),
    ("wonder", "validate-scene-branch"),
    ("wonder", "validate-scene-diff"),
    ("wonder", "validate-scene-history"),
    ("wonder", "validate-scene-manifest"),
    ("wonder", "validate-scene-materialization-manifest"),
    ("wonder", "validate-render-comparison"),
    ("wonder", "validate-render-inspection"),
    ("wonder", "validate-scene"),
    ("wonder", "validate-scene-quality-report"),
    ("wonder", "validate-scene-repair-report"),
    ("wonder", "validate-style-pack"),
    ("wonder", "validate-wonder-report"),
    ("wonder", "validate-world-memory"),
]


def _leaf_command_paths(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            paths: set[tuple[str, ...]] = set()
            for name, subparser in action.choices.items():
                child_paths = _leaf_command_paths(subparser, (*prefix, name))
                paths.update(child_paths or {(*prefix, name)})
            return paths
    return set()


def test_negative_cli_matrix_covers_every_leaf_command() -> None:
    assert set(_NEGATIVE_COMMAND_PATHS) == _leaf_command_paths(_build_parser())


@pytest.mark.parametrize("command_path", _NEGATIVE_COMMAND_PATHS, ids=lambda item: " ".join(item))
def test_every_command_rejects_bad_option_with_actionable_usage_error(
    command_path: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args([*command_path, "--definitely-not-a-real-flag"])

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "lathe usage error [lathe.cli.usage]" in captured.err
    assert "Next step:" in captured.err
    assert " --help" in captured.err
    assert "Traceback (most recent call last)" not in captured.err
