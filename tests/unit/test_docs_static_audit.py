from __future__ import annotations

import json
import re
import shlex
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
PUBLIC_TEXT_PATHS = (REPO_ROOT / "README.md",)
SOURCE_TEXT_ROOTS = (REPO_ROOT / "lathe",)
RUNTIME_CONFIG_DOCS = (
    "docs/cookbook/08_runtime_config.md",
    "docs/cookbook/runtime_config_schema.md",
)
RUNTIME_CONFIG_TOP_LEVELS = {
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "repair",
    "publish",
}
CANONICAL_GALLERY = REPO_ROOT / "docs/gallery.md"
CANONICAL_COMMANDS = REPO_ROOT / "docs/canonical_commands.md"
EXAMPLES_CATALOG = REPO_ROOT / "docs/examples_catalog.md"
RELEASE_CHECKLIST = REPO_ROOT / "docs/release/release-checklist.md"
CONTRIBUTING_GUIDE = REPO_ROOT / "docs/contributing.md"
VERSIONED_RELEASE_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs/release/quality-bar.md",
    REPO_ROOT / "docs/release/support-matrix.md",
    REPO_ROOT / "docs/release/provenance.md",
)
README_REQUIRED_TOPICS = {
    "package version": "0.2.0rc1",
    "stability level": "alpha/pre-release reference compiler scaffold",
    "public contract": "lathe.shape.intent_mesh_handoff_v1",
    "core build workflow": "lathe build examples/courier_drone.lth courier_drone",
    "provider modes": "Provider Modes And Limits",
    "fallback mode": "Offline/fallback mode",
    "learned provider mode": "Learned-provider mode",
    "limitations": "Current limitations",
}
TUTORIAL_WORKFLOW_DOCS = {
    "generate": ("docs/tutorial/first_asset.md", "examples/tutorial_bookshelf.lth"),
    "reconstruct": ("docs/tutorial/second_asset_reconstruct.md", "reconstruct_courier_from_views"),
    "fallback provider": ("docs/tutorial/fallback_provider.md", "dist_fallback"),
    "learned provider": ("docs/tutorial/learned_provider.md", "hunyuan_http.json"),
    "engine export": ("docs/tutorial/engine_export.md", "lathe_for_godot"),
}
COMMANDS_WITH_ASSET_NAME = {
    "build",
    "check",
    "diff-asset",
    "fit",
    "materialize",
    "patch",
    "plan",
    "render-eval",
    "surface-build",
    "surface-plan",
    "surface-repair",
    "surface-validate",
}
INTERNAL_MODULE_DOC_ALLOWED_PREFIXES = (
    "docs/adr/",
    "docs/api/",
    "docs/architecture/",
)
INTERNAL_MODULE_PATTERNS = {
    "lathe.core.stages": re.compile(r"\blathe\.core\.stages\b"),
    "lathe.providers.adapters": re.compile(r"\blathe\.providers\.adapters\b"),
    "lathe.providers.transport": re.compile(r"\blathe\.providers\.transport\b"),
    "lathe.shape.geometry": re.compile(r"\blathe\.shape\.geometry\b"),
    "lathe.scaffold_compiler": re.compile(r"\blathe\.scaffold_compiler\b"),
    "lathe.feature_fusion": re.compile(r"\blathe\.feature_fusion\b"),
    "lathe.engine_manifests.impl": re.compile(r"\blathe\.engine_manifests\.(?:godot|unity|unreal)\b"),
}
ARCHITECTURE_REQUIRED_TOPICS = {
    "parser": "parser.py",
    "normalizer": "normalizer.py",
    "resolver": "resolver.py",
    "checker": "checker.py",
    "planner": "planner.py",
    "shape handoff": "lathe.shape.intent_mesh_handoff_v1",
    "executor": "executor.py",
    "validators": "validators",
    "packaging": "package",
}
BACKEND_PROVIDER_DOCS = (
    "docs/architecture/backends.md",
    "docs/cookbook/08_runtime_config.md",
    "docs/security/threat_model.md",
)
BACKEND_PROVIDER_REQUIRED_TOPICS = {
    "contracts": "stable ids",
    "runtime config": "shape.provider",
    "offline behavior": "offline deterministic mode",
    "network policy": "url_allowlist",
    "test doubles": "provider test double",
}
CONTRIBUTING_GUIDE_REQUIRED_TOPICS = {
    "code style": "## Code style",
    "error style": "## Error style",
    "diagnostic style": "## Diagnostic style",
    "test expectations": "## Test expectations",
    "validation commands": "## Validation commands",
    "behavior change updates": "## Update checklist",
    "CLI error codes": "docs/error_codes.md",
    "checker diagnostics": "lathe.checker.diag",
}
RELEASE_REVIEW_ARTIFACTS = {
    "build report": "build_report.json",
    "selector manifest": "selector_manifest.json",
    "validation report": "stages/validate/report.json",
    "package manifest": "stages/package/package_manifest.json",
    "trace manifest": "stages/package/trace_manifest.json",
    "turntable preview": "stages/package/previews/turntable.png",
    "wireframe preview": "stages/package/previews/wireframe.png",
    "UV preview": "stages/package/previews/uv_layout.png",
    "LOD preview": "stages/package/previews/lod_sheet.png",
    "GLB output": ".glb",
    "USD output": ".usda",
    "Godot manifest": ".lathe_for_godot.json",
    "Unity manifest": ".lathe_for_unity.yaml",
    "Unreal manifest": ".lathe_for_unreal.json",
}
PREVIEW_ARTIFACTS = (
    "stages/package/previews/turntable.png",
    "stages/package/previews/wireframe.png",
    "stages/package/previews/uv_layout.png",
    "stages/package/previews/lod_sheet.png",
)
LOCAL_MEDIA_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
GALLERY_PREVIEW_ASSETS = {
    "industrial_crate": "docs/assets/gallery/industrial_crate_turntable.png",
    "courier_drone": "docs/assets/gallery/courier_drone_turntable.png",
    "courier_drone_mobile": "docs/assets/gallery/courier_drone_mobile_turntable.png",
    "reconstruct_courier_from_mesh": "docs/assets/gallery/reconstruct_courier_from_mesh_turntable.png",
    "console_terminal_mobile": "docs/assets/gallery/console_terminal_mobile_turntable.png",
}
FORBIDDEN_STALE_ARTIFACT_DOC_PATTERNS = {
    "root manifest claim": re.compile(r"root-level\s+`?manifest\.json`?", re.IGNORECASE),
    "root trace claim": re.compile(r"root-level\s+`?trace\.json`?", re.IGNORECASE),
    "old manifest tree comment": re.compile(r"manifest\.json\s+# what was produced", re.IGNORECASE),
    "old trace tree comment": re.compile(r"trace\.json\s+# what ran", re.IGNORECASE),
    "old usd extension": re.compile(r"\bcourier_drone\.usd\b", re.IGNORECASE),
}
DEPRECATED_DOC_TERMS = {
    "--strict-shape-provider": re.compile(r"--strict-shape-provider", re.IGNORECASE),
}


def _docs_markdown_files() -> list[Path]:
    return sorted(DOCS_ROOT.rglob("*.md"))


def _public_markdown_files() -> list[Path]:
    return [*PUBLIC_TEXT_PATHS, *_docs_markdown_files()]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _package_version() -> str:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    assert isinstance(version, str)
    return version


def _release_label(version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)rc(\d+)", version)
    if match:
        return f"{match.group(1)}-rc.{match.group(2)}"
    return version


def _normalize_release_token(token: str) -> str:
    normalized = token.removeprefix("v")
    match = re.fullmatch(r"(\d+\.\d+\.\d+)-rc\.(\d+)", normalized)
    if match:
        return f"{match.group(1)}rc{match.group(2)}"
    return normalized


def test_docs_do_not_leak_this_checkout_absolute_path() -> None:
    root_tokens = {
        REPO_ROOT.as_posix().lower(),
        str(REPO_ROOT).replace("\\", "/").lower(),
        str(REPO_ROOT).lower(),
    }
    failures: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        lower_text = text.lower()
        for token in sorted(root_tokens):
            if not token:
                continue
            start = lower_text.find(token)
            if start != -1:
                relative = path.relative_to(REPO_ROOT).as_posix()
                failures.append(f"{relative}:{_line_number(text, start)} leaks {token!r}")

    assert failures == []


def test_public_docs_do_not_contain_private_path_or_secret_literals() -> None:
    patterns = {
        "windows_user_path": re.compile(r"[A-Z]:[/\\]Users[/\\][^`\\s]+", re.IGNORECASE),
        "private_key": re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
        "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
        # ``long_provider_secret`` catches realistic secret-shaped values assigned to a
        # provider/token/key name, both quoted and unquoted. The unquoted branch
        # rejects ``token = _python_identifier(...)`` shapes by requiring the value
        # to start with an alphanumeric (negative lookahead ``(?!_)``) and to contain
        # at least one digit, both characteristic of real provider tokens and
        # uncharacteristic of Python identifier RHS expressions.
        "long_provider_secret": re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret)\s*[:=]\s*(?:"
            r"['\"][A-Za-z0-9_\-+/=]{24,}['\"]"
            r"|"
            r"(?!_)(?=[A-Za-z0-9\-+/=]*\d)[A-Za-z0-9\-+/=]{24,}\b"
            r")"
        ),
    }
    failures: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                relative = path.relative_to(REPO_ROOT).as_posix()
                failures.append(f"{relative}:{_line_number(text, match.start())} matched {name}")

    assert failures == []


def test_source_and_public_docs_do_not_contain_private_path_or_secret_literals() -> None:
    patterns = {
        "checkout_path": re.compile(r"\b[A-Z]:[/\\][^`'\"]*lathe_v0_1\b", re.IGNORECASE),
        "windows_user_path": re.compile(r"[A-Z]:[/\\]Users[/\\][^`\\s]+", re.IGNORECASE),
        "private_key": re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
        "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
        # Same shape as the public-only patterns above. See the docstring there.
        "long_provider_secret": re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret)\s*[:=]\s*(?:"
            r"['\"][A-Za-z0-9_\-+/=]{24,}['\"]"
            r"|"
            r"(?!_)(?=[A-Za-z0-9\-+/=]*\d)[A-Za-z0-9\-+/=]{24,}\b"
            r")"
        ),
    }
    files = [*_public_markdown_files()]
    for root in SOURCE_TEXT_ROOTS:
        files.extend(path for path in root.rglob("*.py") if path.is_file())

    failures: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            for match in pattern.finditer(text):
                relative = path.relative_to(REPO_ROOT).as_posix()
                failures.append(f"{relative}:{_line_number(text, match.start())} matched {name}")

    assert failures == []


def test_release_version_docs_match_package_metadata() -> None:
    package_version = _package_version()
    init_text = (REPO_ROOT / "lathe/__init__.py").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert init_match is not None
    assert init_match.group(1) == package_version

    release_label = _release_label(package_version)
    allowed_versions = {package_version, release_label, f"v{release_label}"}
    version_pattern = re.compile(r"\bv?\d+\.\d+\.\d+(?:rc\d+|-rc\.\d+)\b")
    failures: list[str] = []
    for path in VERSIONED_RELEASE_DOCS:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        if not any(version in text for version in allowed_versions):
            failures.append(f"{relative}: does not mention current release `{package_version}`")
        for match in version_pattern.finditer(text):
            token = match.group(0)
            if _normalize_release_token(token) != package_version:
                failures.append(f"{relative}:{_line_number(text, match.start())} has stale release `{token}`")

    assert failures == []


def test_readme_covers_current_version_workflows_provider_modes_and_limits() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    missing = [label for label, token in README_REQUIRED_TOPICS.items() if token not in readme]

    assert missing == []


def test_tutorials_cover_generate_reconstruct_provider_and_engine_workflows() -> None:
    failures: list[str] = []
    tutorial_index = (REPO_ROOT / "docs/tutorial/index.md").read_text(encoding="utf-8")
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for label, (relative_path, required_text) in TUTORIAL_WORKFLOW_DOCS.items():
        path = REPO_ROOT / relative_path
        if not path.is_file():
            failures.append(f"{relative_path} missing for {label} workflow")
            continue
        text = path.read_text(encoding="utf-8")
        if required_text not in text:
            failures.append(f"{relative_path} missing `{required_text}` for {label} workflow")
        nav_target = relative_path.removeprefix("docs/")
        if Path(nav_target).name not in tutorial_index:
            failures.append(f"docs/tutorial/index.md missing `{Path(nav_target).name}`")
        if nav_target not in mkdocs:
            failures.append(f"mkdocs.yml missing `{nav_target}`")

    assert failures == []


def _runtime_schema() -> dict[str, Any]:
    return json.loads((REPO_ROOT / "schema/runtime_config.schema.json").read_text(encoding="utf-8"))


def _schema_has_path(schema: dict[str, Any], dotted_path: str) -> bool:
    node: dict[str, Any] = schema
    for part in dotted_path.split("."):
        properties = node.get("properties", {})
        if part == "<name>":
            return bool(node.get("additionalProperties"))
        if part not in properties:
            return False
        child = properties[part]
        if not isinstance(child, dict):
            return False
        node = child
    return True


def _documented_runtime_config_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for match in re.finditer(r"`([^`]+)`", text):
        code = match.group(1).strip()
        candidate = re.split(r"\s|=", code, maxsplit=1)[0].strip()
        if "." not in candidate:
            continue
        top_level = candidate.split(".", 1)[0]
        if top_level in RUNTIME_CONFIG_TOP_LEVELS:
            paths.add(candidate.rstrip("."))
    return paths


def test_documented_runtime_config_keys_exist_in_schema() -> None:
    schema = _runtime_schema()
    failures: list[str] = []
    for relative_path in RUNTIME_CONFIG_DOCS:
        path = REPO_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        for dotted_path in sorted(_documented_runtime_config_paths(text)):
            if not _schema_has_path(schema, dotted_path):
                failures.append(f"{relative_path}: documents unknown runtime config key `{dotted_path}`")

    assert failures == []


def _shell_commands(text: str) -> list[str]:
    commands: list[str] = []
    pending: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        if line.startswith("$ "):
            line = line[2:].strip()
        if pending is None:
            line = line.strip("`")
            if not line.startswith("python -m lathe.cli"):
                continue
        if pending is not None:
            pending = f"{pending} {line}"
        else:
            pending = line
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        commands.append(pending)
        pending = None
    if pending is not None:
        commands.append(pending)
    return commands


def _declared_asset_names(source_path: Path) -> set[str]:
    text = source_path.read_text(encoding="utf-8")
    return set(re.findall(r"(?m)^\s*(?:asset|variant)\s+([A-Za-z_][A-Za-z0-9_]*)\b", text))


def test_documented_concrete_lathe_cli_examples_reference_existing_files_and_assets() -> None:
    failures: list[str] = []
    for path in _docs_markdown_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for command in _shell_commands(text):
            if "..." in command or "<" in command:
                continue
            try:
                tokens = shlex.split(command, posix=True)
            except ValueError as exc:
                failures.append(f"{relative}: could not parse command {command!r}: {exc}")
                continue
            if tokens[:4] != ["python", "-m", "lathe.cli"]:
                continue
            command_name = tokens[4] if len(tokens) > 4 else ""
            source_token: str | None = None
            for token in tokens[5:]:
                if token.startswith("examples/") and token.endswith((".lth", ".json")):
                    candidate = REPO_ROOT / token
                    if not candidate.is_file():
                        failures.append(f"{relative}: command references missing `{token}`")
                    if token.endswith(".lth"):
                        source_token = token
            if command_name not in COMMANDS_WITH_ASSET_NAME or source_token is None:
                continue
            source_index = tokens.index(source_token)
            if source_index + 1 >= len(tokens):
                continue
            asset_name = tokens[source_index + 1]
            if asset_name.startswith("-"):
                continue
            declared_names = _declared_asset_names(REPO_ROOT / source_token)
            if asset_name not in declared_names:
                failures.append(f"{relative}: `{source_token}` does not declare asset/variant `{asset_name}`")

    assert failures == []


def test_canonical_gallery_assets_exist_and_are_declared() -> None:
    text = CANONICAL_GALLERY.read_text(encoding="utf-8")
    failures: list[str] = []
    commands = [command for command in _shell_commands(text) if " build " in f" {command} "]
    for match in re.finditer(r"`(python -m lathe\.cli build [^`]+)`", text):
        commands.append(match.group(1))
    if not commands:
        failures.append("docs/gallery.md does not document any concrete gallery build commands")
    for command in commands:
        tokens = shlex.split(command, posix=True)
        source_token = next(
            (token for token in tokens if token.startswith("examples/") and token.endswith(".lth")),
            None,
        )
        if source_token is None:
            failures.append(f"gallery command missing example source: {command!r}")
            continue
        source_path = REPO_ROOT / source_token
        if not source_path.is_file():
            failures.append(f"gallery command references missing `{source_token}`")
            continue
        source_index = tokens.index(source_token)
        if source_index + 1 >= len(tokens):
            failures.append(f"gallery command missing asset name: {command!r}")
            continue
        asset_name = tokens[source_index + 1]
        if asset_name not in _declared_asset_names(source_path):
            failures.append(f"`{source_token}` does not declare gallery asset `{asset_name}`")

    assert failures == []


def test_examples_catalog_lists_every_checked_in_lathe_example() -> None:
    catalog = EXAMPLES_CATALOG.read_text(encoding="utf-8")
    missing = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "examples").rglob("*.lth"))
        if f"`{path.relative_to(REPO_ROOT).as_posix()}`" not in catalog
    ]

    assert missing == []


def test_canonical_commands_cover_required_command_families() -> None:
    text = CANONICAL_COMMANDS.read_text(encoding="utf-8")
    required = {
        "normalize",
        "check",
        "plan",
        "materialize",
        "build",
        "cache status",
        "cache clean",
        "cache warm",
        "shape-providers",
        "probe-providers",
        "doctor",
        "--report json",
    }
    missing = [command for command in sorted(required) if command not in text]
    assert missing == []


def test_contributor_guide_covers_style_diagnostics_testing_and_validation() -> None:
    text = CONTRIBUTING_GUIDE.read_text(encoding="utf-8")
    missing = [label for label, token in CONTRIBUTING_GUIDE_REQUIRED_TOPICS.items() if token not in text]

    assert missing == []


def test_release_candidate_artifact_review_names_required_build_evidence() -> None:
    text = RELEASE_CHECKLIST.read_text(encoding="utf-8")
    missing = [label for label, token in RELEASE_REVIEW_ARTIFACTS.items() if token not in text]

    assert missing == []


def test_gallery_quickstart_and_release_checklist_document_preview_media_set() -> None:
    docs = {
        "docs/gallery.md": CANONICAL_GALLERY.read_text(encoding="utf-8"),
        "docs/quickstart.md": (REPO_ROOT / "docs/quickstart.md").read_text(encoding="utf-8"),
        "docs/release/release-checklist.md": RELEASE_CHECKLIST.read_text(encoding="utf-8"),
    }
    failures = [
        f"{relative}: missing preview artifact `{artifact}`"
        for relative, text in docs.items()
        for artifact in PREVIEW_ARTIFACTS
        if artifact not in text
    ]

    assert failures == []


def test_gallery_documents_checked_in_rendered_previews_for_each_flagship_asset() -> None:
    text = CANONICAL_GALLERY.read_text(encoding="utf-8")
    failures: list[str] = []
    for asset, relative_path in GALLERY_PREVIEW_ASSETS.items():
        if asset not in text:
            failures.append(f"docs/gallery.md does not name gallery asset `{asset}`")
        doc_target = relative_path.removeprefix("docs/")
        if doc_target not in text:
            failures.append(f"docs/gallery.md does not embed `{doc_target}`")
        media_path = REPO_ROOT / relative_path
        if not media_path.is_file():
            failures.append(f"`{relative_path}` is missing")
        elif media_path.stat().st_size <= 0:
            failures.append(f"`{relative_path}` is empty")

    assert failures == []


def test_markdown_image_references_point_to_existing_media_files() -> None:
    failures: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(("http://", "https://")):
                continue
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1]
            target_without_fragment = raw_target.split("#", 1)[0].split("?", 1)[0]
            decoded = urllib.parse.unquote(target_without_fragment)
            target = (path.parent / decoded).resolve()
            if target.suffix.lower() not in LOCAL_MEDIA_EXTENSIONS:
                failures.append(
                    f"{relative}:{_line_number(text, match.start())} is not a supported media file"
                )
            if not target.is_file():
                failures.append(
                    f"{relative}:{_line_number(text, match.start())} references missing media `{match.group(1)}`"
                )

    assert failures == []


def test_docs_do_not_use_stale_artifact_names_for_current_outputs() -> None:
    failures: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for label, pattern in FORBIDDEN_STALE_ARTIFACT_DOC_PATTERNS.items():
            for match in pattern.finditer(text):
                failures.append(f"{relative}:{_line_number(text, match.start())} uses stale {label}")

    assert failures == []


def test_deprecated_cli_and_config_terms_are_marked_or_replaced() -> None:
    failures: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for label, pattern in DEPRECATED_DOC_TERMS.items():
            for match in pattern.finditer(text):
                line_number = _line_number(text, match.start())
                lines = text.splitlines()
                context = "\n".join(
                    lines[max(0, line_number - 6) : min(len(lines), line_number + 30)]
                ).lower()
                if "deprecated" not in context and "deprecationwarning" not in context:
                    failures.append(f"{relative}:{line_number} uses deprecated `{label}` without marking it")

    assert failures == []


def test_docs_markdown_links_and_fenced_code_blocks_are_linted() -> None:
    failures: list[str] = []
    schema_dir = REPO_ROOT / "schema"
    for path in _docs_markdown_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        if text.count("```") % 2:
            failures.append(f"{relative}: has an unmatched fenced code block")
        for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1]
            target_without_fragment = raw_target.split("#", 1)[0].split("?", 1)[0]
            if not target_without_fragment:
                continue
            if target_without_fragment.startswith(("app://", "file:")):
                continue
            decoded = urllib.parse.unquote(target_without_fragment)
            target = (path.parent / decoded).resolve()
            # ``docs/<page>.md`` files reference repo-root schemas as
            # ``../schema/X.schema.json``; the schemas live in
            # ``<repo-root>/schema/`` and are mirrored into the built site
            # by ``docs/gen_external_pages.py``. Resolve those references
            # against ``<repo-root>/schema/`` for link-lint purposes.
            if not target.exists() and target.parent.name == "schema":
                schema_candidate = schema_dir / target.name
                if schema_candidate.exists():
                    continue
            if target.exists():
                continue
            failures.append(
                f"{relative}:{_line_number(text, match.start())} references missing link `{match.group(1)}`"
            )

    assert failures == []


def test_user_facing_docs_do_not_depend_on_internal_module_imports() -> None:
    failures: list[str] = []
    for path in _docs_markdown_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(INTERNAL_MODULE_DOC_ALLOWED_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in INTERNAL_MODULE_PATTERNS.items():
            for match in pattern.finditer(text):
                failures.append(
                    f"{relative}:{_line_number(text, match.start())} documents internal `{label}`"
                )

    assert failures == []


def test_architecture_docs_cover_required_compiler_components() -> None:
    architecture_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in sorted((DOCS_ROOT / "architecture").glob("*.md"))
    )
    missing = [
        label
        for label, required_text in ARCHITECTURE_REQUIRED_TOPICS.items()
        if required_text.lower() not in architecture_text
    ]

    assert missing == []


def test_backend_provider_docs_cover_contracts_config_offline_network_and_test_doubles() -> None:
    docs_text = "\n".join(
        (REPO_ROOT / relative).read_text(encoding="utf-8").lower() for relative in BACKEND_PROVIDER_DOCS
    )
    missing = [
        label
        for label, required_text in BACKEND_PROVIDER_REQUIRED_TOPICS.items()
        if required_text.lower() not in docs_text
    ]

    assert missing == []
