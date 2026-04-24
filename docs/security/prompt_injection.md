# Prompt-Injection Scanner (SEC-8, V0.2 P0)

Lathe's parser runs a static prompt-injection scanner over every
`.lth` source it ingests. The scanner exists to protect **learned
providers** (Hunyuan, VGGT, Codex, custom local models) from coerced
inputs that ride through the compiler pipeline disguised as innocuous
string literals or comments.

Warnings are the default; source parsing proceeds unless the caller
explicitly opts into strict mode.

## Diagnostic codes

| Code   | Name                            | Trigger                                                                          |
|--------|---------------------------------|----------------------------------------------------------------------------------|
| L7001  | `prompt_injection_*`            | Phrase matching a known jailbreak instruction (`ignore previous instructions`…) |
| L7002  | `unicode_direction_override`    | Unicode bidi control characters (U+202A-U+202E, U+2066-U+2069)                   |
| L7003  | `chat_template_sentinel`        | Chat-template sentinels such as `<|im_start|>`, `<|endoftext|>`                  |
| L7004  | `oversized_literal`             | Single string literal longer than 10000 characters                               |
| L7005  | `system_prompt_impersonation`   | Text formatted as a system prompt (`system prompt:`, `you are now a…`)           |

Each diagnostic carries `line`, `column`, truncated `match`, and a
`remediation` hint.

## Invocation

Invoked automatically from `lathe/parser/__init__.py::parse_file` as
a pre-parse pass. The scanner has no dependency on the grammar: it
reads the raw source text and walks string literals + `#` comments.

Callers can invoke it directly:

```python
from lathe.parser import scan_source

result = scan_source(source_text)
if not result.clean:
    for diag in result.diagnostics:
        print(diag.code, diag.message)
```

## Severity modes

| Mode    | Trigger                                                               | Behavior                          |
|---------|-----------------------------------------------------------------------|-----------------------------------|
| warning | Default                                                               | Logged at WARNING, parse proceeds |
| strict  | `--strict-prompt-injection` CLI flag, or `LATHE_STRICT_PROMPT_INJECTION=1` env | `PromptInjectionError` raised, parse aborts |

CI pipelines that treat asset repositories as untrusted should set
`LATHE_STRICT_PROMPT_INJECTION=1` before invoking `python -m lathe.cli
build`.

## Allowlisting legitimate matches

Some legitimate `.lth` content may trip the scanner — a benchmark
description that literally contains `ignore previous instructions` as
test fixture, for example. The recommended pattern is:

1. Move the payload to a dedicated `.lth` fixture under
   `benchmarks/prompt_injection_fixtures/`.
2. In `pyproject.toml`, add the fixture path to
   `tool.lathe.prompt_injection.allowlist_paths` (see `SEC-FUTURE-*`
   for the config surface — today the scanner has no per-file
   allowlist; for short-term bypasses, downgrade `strict` in that run).
3. Document the justification in this file under *Known exceptions*.

## Known exceptions

None at the time of writing. Add rows as allowlist entries accrue:

| Path | Diagnostics allowed | Justification | Reviewer |
|------|---------------------|---------------|----------|

## Cross-references

- Threat model: `docs/security/threat_model.md` §3 (provider HTTP)
- CI gates: `docs/security/ci_gates.md`
- Source: `lathe/parser/prompt_injection.py`
