# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.2.0 pre-releases | Yes |
| 0.1.x | Best-effort security fixes until 0.2.0 final |
| < 0.1 | No |

Until Lathe reaches a stable `1.0.0`, security fixes target `main` first and
may be backported to the latest published pre-release when users are affected.
See `docs/release/support-matrix.md` for the current support window.

## Reporting A Vulnerability

Preferred channel: GitHub Security Advisories once the repo is public. Use the
**Report a vulnerability** button on the repository's Security tab.

Alternative channel: email **talmerri@gmail.com** with subject prefix
`[SECURITY]`. A PGP key fingerprint will be published here once generated.

### Response SLA

| Stage | Target |
|---|---|
| Acknowledgement | 3 business days |
| Initial triage and severity assessment | 10 business days |
| Fix, patch release, and advisory | 90 days from initial report |

## Coordinated Disclosure

We follow a 90-day coordinated disclosure window. Reporters are asked not to
publicly disclose the issue until a fix is released or the window elapses,
whichever is sooner. Extensions are available for complex issues.

## Safe Harbor

Good-faith security research that complies with this policy is authorized and
welcome. Good faith means:

- You work only against your own local environment and test accounts.
- You do not compromise user data, disrupt operation, or access systems beyond
  what is strictly necessary to prove a vulnerability.
- You do not publicly disclose the issue before coordination completes.

## Scope

In scope:

- The `lathe` Python package and CLI.
- Official runtime configs in `examples/runtime_configs/`.
- The reference compiler pipeline and validators.
- Published GitHub Actions workflows.
- Container images published from this repository.

Out of scope:

- Third-party optional dependencies such as Blender, xatlas, trimesh,
  Hunyuan3D, VGGT, and Codex ImageGen. Report upstream issues to upstream
  maintainers. Lathe integration bugs that amplify an upstream issue remain in
  scope.
- Documentation typos, broken links, and stylistic issues. File a regular bug.
- Issues requiring physical access to a developer's machine.

## Maintainer Security Hygiene

- Maintainer accounts use 2FA with a hardware security key.
- Release publishing uses PyPI Trusted Publishing where available.
- Release artifacts ship or attach CycloneDX SBOMs when the SBOM workflow runs
  on a release tag.
- `pre-commit` and `gitleaks` run locally and in CI on every push.
- `pip-audit` runs weekly and on every `pyproject.toml` or
  `requirements*.txt` change.

## Known Risk Areas

The current threat model lives at `docs/security/threat_model.md`. Key risk
personas:

- Malicious `.lth` author: path traversal via refs, zip-bomb textures, Blender
  `.blend` driver RCE. Mitigated by input validation, path hardening, image
  reference limits, mesh parser hardening, and the Blender sandbox.
- Malicious model server: SSRF, oversized responses, unsafe redirects, or
  private-network access through provider URLs. Mitigated by safe URL
  validation, allowlists, timeout limits, and provider tests.
- Supply-chain compromise: typosquat, upstream takeover, or vulnerable
  dependency. Mitigated by pinned lockfiles, `pip-audit`, Dependabot, SBOMs,
  and signed release planning.

## Acknowledgements

Reporters will be credited at `docs/security/acknowledgements.md` once the
first report resolves. Anonymous reporting is honored on request.
