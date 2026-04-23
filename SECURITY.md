# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✓         |
| < 0.1   | ✗         |

Only the latest `0.1.x` release receives security fixes.

## Reporting a vulnerability

**Preferred channel:** GitHub Security Advisories once the repo is public — use the **Report a vulnerability** button on the repository's Security tab.

**Alternative channel:** email **talmerri@gmail.com** with subject prefix `[SECURITY]`. A PGP key fingerprint will be published here once generated.

### Response SLA

| Stage | Target |
|-------|--------|
| Acknowledgement | 3 business days |
| Initial triage + severity assessment | 10 business days |
| Fix, patch release, and advisory | 90 days from initial report |

## Coordinated disclosure

We follow a 90-day coordinated disclosure window. Reporters are asked not to publicly disclose the issue until a fix is released or the window elapses, whichever is sooner. Extensions are available for complex issues.

## Safe harbor

Good-faith security research that complies with this policy is authorized and welcome. Good faith means:

- You work only against your own local environment and test accounts.
- You do not compromise user data, disrupt operation, or access systems beyond what is strictly necessary to prove a vulnerability.
- You do not publicly disclose the issue before coordination completes.

## Scope

**In scope:**
- The `lathe` Python package and CLI
- Official runtime configs in `examples/runtime_configs/`
- The reference compiler pipeline and validators
- Published GitHub Actions workflows
- Container images published from this repository

**Out of scope:**
- Third-party optional dependencies (Blender, xatlas, trimesh, Hunyuan3D, VGGT, Codex ImageGen) — report to upstream. Integration bugs in Lathe that amplify an upstream issue are in scope.
- Documentation typos, broken links, stylistic issues — file a regular bug.
- Issues requiring physical access to a developer's machine.

## Maintainer security hygiene

- Maintainer accounts use **2FA with a hardware security key**.
- Release publishing uses PyPI Trusted Publishing (OIDC, no long-lived tokens).
- Release artifacts will ship SPDX and CycloneDX SBOMs starting in Wave 3.
- `pre-commit` + `gitleaks` run locally and in CI on every push.
- `pip-audit` runs weekly and on every `pyproject.toml` / `requirements*.txt` change.

## Known risk areas

Full threat model lands at `docs/security/threat_model.md` in Wave 3. Key risk personas:

- **Malicious `.lth` author** — path traversal via refs, zip-bomb textures, Blender `.blend` driver RCE. Mitigated by Plan 07 (input validation, path hardening, Blender sandbox) and Plan 10 (binary parser hardening).
- **Malicious model server** (attacker-controlled Hunyuan/Codex URL) — SSRF, oversized responses. Mitigated by Plan 07 Phase 3 (SSRF).
- **Supply-chain compromise** — typosquat, upstream takeover. Mitigated by pinned lockfile, `pip-audit`, Dependabot, signed releases.

## Acknowledgements

Reporters will be credited at `docs/security/acknowledgements.md` once the first report resolves. Anonymous reporting is honored on request.
