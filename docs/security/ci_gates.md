# CI Security Gates

Reference for the automated security checks enforced on every push / PR
to `main`. Each gate runs independently; a failure in one does not mask
another. Local equivalents are listed so contributors can reproduce
findings before pushing.

The gates land from roadmap tickets **SEC-3** (secret scanning),
**SEC-4** (SBOM), and **SEC-5** (SAST: CodeQL, Bandit, Semgrep).

## Summary

| Gate        | What it scans                                                  | Workflow                         | How to fix failures                                                                                    | Bypass mechanism                                    |
|-------------|----------------------------------------------------------------|----------------------------------|--------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| gitleaks    | High-entropy strings + known token formats in diffs + history  | `.github/workflows/security.yml` (PR/push), `.github/workflows/gitleaks.yml` (weekly full history) | Rotate the exposed credential first, then rewrite history or allowlist the false positive (see below). | Allowlist in `.gitleaks.toml`, or commit-level `nosec-equivalent` via path exclusion.           |
| bandit      | Python stdlib misuse (eval, subprocess, yaml.load, pickle, ...)| `.github/workflows/security.yml` | Refactor to the safe alternative Bandit suggests, or annotate the line with a justified `# nosec`.     | `# nosec B###  # justification` inline comment.     |
| semgrep     | Multi-pack rules: `p/python`, `p/security-audit`, `p/owasp-top-ten` | `.github/workflows/security.yml` | Fix the flagged pattern. If the rule doesn't apply, annotate with `# nosemgrep: <rule-id>`.           | `# nosemgrep: <rule-id>  # justification` inline.   |
| CodeQL      | GitHub's security-extended + security-and-quality packs for maintained Python/docs/workflow paths | `.github/workflows/codeql.yml`, `.github/codeql/codeql-config.yml`   | Address the finding in code, or add a dismissal in the Security tab with a reason.                     | Dismiss via GitHub Security tab (requires write).   |
| CycloneDX SBOM | Dependency graph of project + dev extras (SBOM emission, not a gate) | `.github/workflows/sbom.yml` | Not a gate — the workflow emits `sbom.json` + `sbom.xml` artifacts; failures usually mean a broken dep tree. | N/A (advisory artifact).                            |
| pip-audit   | Published CVEs against the pinned dependency graph             | `.github/workflows/pip-audit.yml` | Upgrade or pin the fixed version; if no fix exists, add an explicit `--ignore-vuln` with a ticket link. | `--ignore-vuln GHSA-xxxx-...` flag.                 |

## Local reproduction

Install the dev extras, then run the equivalent command locally:

```bash
python -m pip install -e ".[dev]"
python -m pip install "bandit[toml]==1.7.9" "cyclonedx-bom==4.5.0" "pip-audit"

pre-commit run --all-files           # ruff + gitleaks + bandit + the rest
just security-local                  # local mirror of the CI security scanners
bandit -c bandit.yaml -r lathe/ --severity-level medium --confidence-level medium
semgrep --error --config p/python --config p/security-audit --config p/owasp-top-ten lathe/
gitleaks detect --config=.gitleaks.toml --source=. --verbose
grep -vE '^-e[[:space:]]+\.' requirements.txt > /tmp/lathe-requirements-audit.txt
grep -vE '^-e[[:space:]]+\.' requirements-dev.txt > /tmp/lathe-requirements-dev-audit.txt
pip-audit --strict --no-deps --requirement /tmp/lathe-requirements-audit.txt
pip-audit --strict --no-deps --requirement /tmp/lathe-requirements-dev-audit.txt
```

Before cutting a release candidate, run `just release-local`. It executes the
release metadata check, lint, full pytest suite, strict docs build, package
build/twine validation, and CycloneDX SBOM generation.

CodeQL cannot be run fully locally without the CodeQL CLI bundle; if you
need a local reproduction, install the CLI from
`https://github.com/github/codeql-cli-binaries/releases` and run
`codeql database create --codescanning-config .github/codeql/codeql-config.yml`
plus `codeql database analyze` against the Python pack.

## Fixing failures

### gitleaks

1. **If the finding is a real credential:** rotate it immediately at the
   provider (not just in the commit — git history preserves it). Then
   remove the credential from the repo, ideally via `git filter-repo`
   (not `git reset`), and coordinate with maintainers before force-push.
2. **If the finding is a false positive:** add the path to
   `[allowlist].paths` in `.gitleaks.toml` if a whole file is
   intentionally illustrative (docs, examples, env templates), or add a
   regex to `[allowlist].regexes` if the pattern matches a canonical
   placeholder (e.g. `your-api-key-here`). Do not add a broad regex that
   would silence real tokens.

### bandit

Annotate individual lines with `# nosec B###` and a short justification:

```python
# Blender invocation path is validated in lathe/bridge/blender_plan.py.
subprocess.run(argv, check=True, timeout=300)  # nosec B603
```

Prefer refactoring over annotation when the rule points to a genuinely
safer API (e.g. `yaml.safe_load` over `yaml.load`). Update `bandit.yaml`
`skips:` only when a rule is globally wrong for this codebase, never as
a way to hide a single offending line.

### semgrep

Use `# nosemgrep: <rule-id>` at the end of the flagged line:

```python
path = base / user_input  # nosemgrep: python.lang.security.audit.path-traversal
```

Include the rule ID explicitly so future reviewers know *what* was
silenced; a bare `# nosemgrep` is deliberately discouraged.

### CodeQL

Findings surface in the **Security → Code scanning** tab of the
repository. Either fix the flagged code path or dismiss the alert with
one of GitHub's documented reasons (`false positive`, `won't fix`,
`used in tests`). Dismissals are audited — prefer a fix.

The CodeQL config intentionally excludes ignored/generated workspaces such as
`external/`, `site/`, `_codex_tmp/`, bytecode caches, and virtual
environments. Those paths are not part of a clean release checkout and should
not be used as production Lathe runtime code.

## Maintenance

- Gitleaks rule updates: pin versions in `.pre-commit-config.yaml` and
  `security.yml` / `gitleaks.yml` are bumped via Dependabot (`github-actions` ecosystem).
- Bandit / Semgrep versions: the pre-commit pins and the workflow/container
  pins must move together to avoid local-vs-CI drift.
- Rule pack updates for Semgrep flow through `p/python`, `p/security-audit`,
  and `p/owasp-top-ten` on the Semgrep Registry; update
  `.github/workflows/security.yml` and the local command above together if the
  pack list changes. `.semgrep.yml` is reserved for future custom local rules.
- SBOM artifacts older than 90 days are purged automatically by the
  workflow retention policy. Release-tag SBOMs attach to the GitHub
  Release and persist with the release.

## Cross-references

- Disclosure policy: [`SECURITY.md`](https://github.com/talmerri/lathe/blob/main/SECURITY.md)
- Dependency audit cadence: `.github/workflows/pip-audit.yml`
- Dependency ingress policy: [`docs/dependency_policy.md`](../dependency_policy.md)
- JSON-ingress audit trail: [`docs/security/json_ingress_audit.md`](json_ingress_audit.md)
