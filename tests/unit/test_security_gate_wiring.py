from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _read_workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_local_gate_recipes_mirror_security_and_release_requirements() -> None:
    justfile = _read("Justfile")
    makefile = _read("Makefile")

    assert "\nsecurity-local:" in justfile
    assert "bandit --configfile bandit.yaml" in justfile
    assert "semgrep --error" in justfile
    assert "gitleaks detect --config=.gitleaks.toml" in justfile
    assert "pip-audit --strict --no-deps" in justfile
    assert "\nrelease-local:" in justfile
    assert "scripts/check_release_metadata.py" in justfile
    assert "python -m pytest -q" in justfile
    assert "mkdocs build --strict" in justfile
    assert "twine check dist/*" in justfile
    assert "cyclonedx-py environment --output-format JSON" in justfile
    assert "security-local:" in makefile
    assert "release-local:" in makefile


def test_security_workflows_wire_required_scanners_as_failing_gates() -> None:
    security = _read_workflow("security.yml")
    pip_audit = _read_workflow("pip-audit.yml")
    codeql = _read_workflow("codeql.yml")
    codeql_config = _read(".github/codeql/codeql-config.yml")

    assert "gitleaks/gitleaks-action" in security
    assert "GITLEAKS_CONFIG: .gitleaks.toml" in security
    assert "bandit" in security
    assert "--configfile bandit.yaml" in security
    assert "semgrep" in security
    assert "--error" in security
    assert "p/security-audit" in security
    assert "pip-audit --strict --no-deps" in pip_audit
    assert "github/codeql-action/init@v3" in codeql
    assert "security-extended,security-and-quality" in codeql
    assert "config-file: ./.github/codeql/codeql-config.yml" in codeql
    assert "external/**" in codeql_config
    assert "_codex_tmp/**" in codeql_config
    assert "**/__pycache__/**" in codeql_config

    for workflow in (security, pip_audit, codeql):
        assert "continue-on-error" not in workflow


def test_release_workflow_keeps_security_gates_before_publish() -> None:
    release = _read_workflow("release.yml")

    for job in ("quality", "dependency-audit", "sast", "semgrep", "codeql", "build", "sbom", "publish"):
        assert f"  {job}:" in release
    for required_need in ("quality", "dependency-audit", "sast", "semgrep", "codeql"):
        assert f"      - {required_need}" in release
    assert "pip-audit --strict --no-deps" in release
    assert "bandit --configfile bandit.yaml" in release
    assert "gitleaks/gitleaks-action" in release
    assert "semgrep \\" in release
    assert "github/codeql-action/analyze@v3" in release
    assert "config-file: ./.github/codeql/codeql-config.yml" in release
    assert "cyclonedx-py environment --output-format JSON" in release
    assert "pypa/gh-action-pypi-publish" in release
    assert "attestations: true" in release
    assert "continue-on-error" not in release


def test_scheduled_gitleaks_advisory_run_rethrows_failures() -> None:
    gitleaks = _read_workflow("gitleaks.yml")

    assert "continue-on-error: true" in gitleaks
    assert "Open issue on finding" in gitleaks
    assert "Propagate failure" in gitleaks
    assert "run: exit 1" in gitleaks
