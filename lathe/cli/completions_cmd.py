"""Shell completion script generation for the Lathe CLI."""

from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass

ROOT_KEY = "__root__"
SUPPORTED_SHELLS = ("bash", "zsh", "powershell")
_UNSUPPORTED_SHELL_MESSAGE = "unsupported shell {shell!r}; expected one of: {supported}"


@dataclass(frozen=True)
class CompletionNode:
    children: tuple[str, ...]
    options: tuple[str, ...]
    values: tuple[str, ...]


def _completion_nodes(parser: argparse.ArgumentParser) -> dict[str, CompletionNode]:
    nodes: dict[str, CompletionNode] = {}

    def visit(current: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        key = " ".join(path) if path else ROOT_KEY
        children: tuple[str, ...] = ()
        options: list[str] = []
        values: list[str] = []
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                children = tuple(action.choices.keys())
            options.extend(action.option_strings)
            if not action.option_strings and action.choices:
                values.extend(str(choice) for choice in action.choices)
        nodes[key] = CompletionNode(
            children=children,
            options=tuple(dict.fromkeys(options)),
            values=tuple(dict.fromkeys(values)),
        )
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child, child_parser in action.choices.items():
                    visit(child_parser, (*path, child))

    visit(parser, ())
    return nodes


def _completion_transitions(nodes: dict[str, CompletionNode]) -> dict[str, str]:
    transitions: dict[str, str] = {}
    for key, node in nodes.items():
        parent = () if key == ROOT_KEY else tuple(key.split(" "))
        for child in node.children:
            child_key = " ".join((*parent, child))
            transitions[f"{key}:{child}"] = child_key
    return transitions


def _shell_words(words: tuple[str, ...]) -> str:
    return " ".join(words)


def _bash_array(name: str, values: dict[str, str]) -> str:
    lines = [f"declare -gA {name}=("]
    for key, value in values.items():
        lines.append(f"  [{shlex.quote(key)}]={shlex.quote(value)}")
    lines.append(")")
    return "\n".join(lines)


def _render_bash(nodes: dict[str, CompletionNode], program: str) -> str:
    children = {key: _shell_words(node.children) for key, node in nodes.items()}
    options = {key: _shell_words((*node.options, *node.values)) for key, node in nodes.items()}
    transitions = _completion_transitions(nodes)
    quoted_program = shlex.quote(program)
    return "\n".join(
        [
            "# bash completion for Lathe.",
            "# Install: lathe completions bash > ~/.local/share/bash-completion/completions/lathe",
            _bash_array("_lathe_children", children),
            _bash_array("_lathe_options", options),
            _bash_array("_lathe_transitions", transitions),
            "",
            "_lathe_completion() {",
            '  local cur="${COMP_WORDS[COMP_CWORD]}"',
            f'  local key="{ROOT_KEY}"',
            "  local word transition",
            "  local i=1",
            "  while [[ $i -lt $COMP_CWORD ]]; do",
            '    word="${COMP_WORDS[$i]}"',
            '    transition="${_lathe_transitions["${key}:${word}"]}"',
            '    if [[ -n "$transition" ]]; then',
            '      key="$transition"',
            "    fi",
            "    ((i++))",
            "  done",
            '  local candidates="${_lathe_children[$key]} ${_lathe_options[$key]}"',
            '  COMPREPLY=( $(compgen -W "$candidates" -- "$cur") )',
            "  if [[ ${#COMPREPLY[@]} -eq 0 ]]; then",
            '    COMPREPLY=( $(compgen -f -- "$cur") )',
            "  fi",
            "}",
            f"complete -F _lathe_completion -- {quoted_program}",
            "",
        ]
    )


def _zsh_array(name: str, values: dict[str, str]) -> str:
    lines = [f"typeset -gA {name}", f"{name}=("]
    for key, value in values.items():
        lines.append(f"  {shlex.quote(key)} {shlex.quote(value)}")
    lines.append(")")
    return "\n".join(lines)


def _render_zsh(nodes: dict[str, CompletionNode], program: str) -> str:
    children = {key: _shell_words(node.children) for key, node in nodes.items()}
    options = {key: _shell_words((*node.options, *node.values)) for key, node in nodes.items()}
    transitions = _completion_transitions(nodes)
    quoted_program = shlex.quote(program)
    return "\n".join(
        [
            f"#compdef {program}",
            "# zsh completion for Lathe.",
            "# Install: lathe completions zsh > ${fpath[1]}/_lathe",
            _zsh_array("_lathe_children", children),
            _zsh_array("_lathe_options", options),
            _zsh_array("_lathe_transitions", transitions),
            "",
            "_lathe_completion() {",
            f'  local key="{ROOT_KEY}"',
            "  local word transition candidates",
            "  local -a completions",
            "  local i=2",
            "  while (( i < CURRENT )); do",
            '    word="${words[$i]}"',
            '    transition="${_lathe_transitions[${key}:${word}]}"',
            '    if [[ -n "$transition" ]]; then',
            '      key="$transition"',
            "    fi",
            "    ((i++))",
            "  done",
            '  candidates="${_lathe_children[$key]} ${_lathe_options[$key]}"',
            "  completions=(${=candidates})",
            "  _describe 'lathe completions' completions && return",
            "  _files",
            "}",
            f"compdef _lathe_completion {quoted_program}",
            "",
        ]
    )


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_map(name: str, values: dict[str, tuple[str, ...] | str]) -> str:
    lines = [f"${name} = @{{"]
    for key, value in values.items():
        if isinstance(value, str):
            rendered = _ps_quote(value)
        else:
            rendered = "@(" + ", ".join(_ps_quote(item) for item in value) + ")"
        lines.append(f"  {_ps_quote(key)} = {rendered}")
    lines.append("}")
    return "\n".join(lines)


def _render_powershell(nodes: dict[str, CompletionNode], program: str) -> str:
    children = {key: node.children for key, node in nodes.items()}
    options = {key: (*node.options, *node.values) for key, node in nodes.items()}
    transitions = _completion_transitions(nodes)
    return "\n".join(
        [
            "# PowerShell completion for Lathe.",
            "# Install: lathe completions powershell | Out-String | Invoke-Expression",
            _powershell_map("LatheChildren", children),
            _powershell_map("LatheOptions", options),
            _powershell_map("LatheTransitions", transitions),
            "",
            f"Register-ArgumentCompleter -CommandName {_ps_quote(program)} -ScriptBlock {{",
            "  param($wordToComplete, $commandAst, $cursorPosition)",
            f"  $key = {_ps_quote(ROOT_KEY)}",
            "  $tokens = @($commandAst.CommandElements | ForEach-Object { $_.ToString() })",
            "  $end = $tokens.Count - 1",
            "  if ($commandAst.ToString().EndsWith(' ')) { $end = $tokens.Count }",
            "  for ($i = 1; $i -lt $end; $i++) {",
            '    $transitionKey = "$key`:$($tokens[$i])"',
            "    if ($LatheTransitions.ContainsKey($transitionKey)) {",
            "      $key = $LatheTransitions[$transitionKey]",
            "    }",
            "  }",
            "  $candidates = @()",
            "  if ($LatheChildren.ContainsKey($key)) { $candidates += $LatheChildren[$key] }",
            "  if ($LatheOptions.ContainsKey($key)) { $candidates += $LatheOptions[$key] }",
            '  $candidates | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {',
            "    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)",
            "  }",
            "}",
            "",
        ]
    )


def render_completion_script(parser: argparse.ArgumentParser, shell: str, *, program: str = "lathe") -> str:
    """Render a static shell completion script from Lathe's argparse tree."""
    nodes = _completion_nodes(parser)
    if shell == "bash":
        return _render_bash(nodes, program)
    if shell == "zsh":
        return _render_zsh(nodes, program)
    if shell == "powershell":
        return _render_powershell(nodes, program)
    supported = ", ".join(SUPPORTED_SHELLS)
    raise ValueError(_UNSUPPORTED_SHELL_MESSAGE.format(shell=shell, supported=supported))


def run_completions(args: argparse.Namespace) -> None:
    """Emit the requested shell completion script."""
    parser = args._completion_parser
    print(render_completion_script(parser, args.shell, program=args.program), end="")
