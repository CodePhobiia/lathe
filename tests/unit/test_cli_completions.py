from __future__ import annotations

import os
import subprocess
import sys

import pytest
from lathe.cli import _build_parser
from lathe.cli.completions_cmd import render_completion_script


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


@pytest.mark.parametrize(
    ("shell", "expected"),
    [
        ("bash", "complete -F _lathe_completion -- lathe"),
        ("zsh", "compdef _lathe_completion lathe"),
        ("powershell", "Register-ArgumentCompleter -CommandName 'lathe'"),
    ],
)
def test_completions_command_emits_shell_script(shell: str, expected: str) -> None:
    result = _cli("completions", shell)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert expected in result.stdout
    assert "build" in result.stdout
    assert "--runtime-config" in result.stdout


def test_completion_script_includes_nested_commands_and_options() -> None:
    script = render_completion_script(_build_parser(), "bash")

    assert "[__root__]" in script
    assert "bridge" in script
    assert "bridge doctor" in script
    assert "--execution-profile" in script
    assert "__root__:completions" in script
    assert "[completions]='-h --help --program bash zsh powershell'" in script


def test_completion_program_name_is_configurable() -> None:
    result = _cli("completions", "powershell", "--program", "lathe-dev")

    assert result.returncode == 0, result.stderr
    assert "Register-ArgumentCompleter -CommandName 'lathe-dev'" in result.stdout
