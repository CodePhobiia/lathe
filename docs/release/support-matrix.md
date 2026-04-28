# Support matrix

This page is the canonical release support matrix for Lathe. It describes what
maintainers commit to testing for a release candidate and what remains
best-effort or experimental.

## Package status

| Surface | Status | Notes |
|---|---|---|
| Public package | Pre-release | Current package version is `0.2.0rc1`. Stable support starts only after the release quality bar is met. |
| Public language contract | Supported compatibility anchor | `spec/lathe-v0.1.md` and the stable blocks listed in [Versioning](../versioning.md). |
| Stable shape handoff | Supported compatibility anchor | `lathe.shape.intent_mesh_handoff_v1` must remain stable unless a versioned migration is approved. |

## Platforms and Python

| Platform | Python | Release support | CI coverage |
|---|---|---|---|
| Ubuntu latest | 3.11, 3.12 | Supported for the fast/tested release surface | Fast tests, examples, docs, coverage, security, release build jobs. |
| Windows latest | 3.11, 3.12 | Supported for the fast/tested release surface | Fast tests and doctor/check smoke in CI. |
| macOS latest | 3.11, 3.12 | Supported for the fast/tested release surface | Fast tests and doctor/check smoke in CI. |
| Other Linux distributions | 3.11, 3.12 | Best effort | Not directly covered unless reproduced through Ubuntu CI or user reports. |
| Python 3.13+ | N/A | Unsupported | Not declared in package classifiers or CI. |
| Python <=3.10 | N/A | Unsupported | `requires-python` is `>=3.11`. |

## Optional tools

| Tool or extra | Status | Expected behavior when absent |
|---|---|---|
| Base install | Supported | `python -m lathe.cli`, `lathe doctor`, parser/checker/planner, and conservative builds must not require optional learned runtimes. |
| `dev` extra | Supported for contributors | Installs pytest, ruff, mypy, pre-commit, hypothesis, and docs/test helpers. |
| `docs` extra | Supported for docs builds | Required for `mkdocs build --strict`. |
| `xatlas` extra | Optional supported adapter | UV falls back explicitly to the deterministic reference box-atlas path when xatlas is unavailable. |
| Blender executable | Optional supported adapter | Topology falls back explicitly to deterministic reference cleanup when Blender is unavailable or fails quality gates. |
| `vggt` extra plus source install | Experimental optional provider | VGGT reconstruction is opt-in and requires local model/runtime setup beyond the base install. |
| Hunyuan HTTP runtime | Experimental optional provider | Requires a reachable HTTP service; absence must not break the conservative offline path. |
| Network-enabled tests | Opt-in | Tests marked `requires_network` stay disabled unless explicitly enabled. |

## Provider modes

| Mode | Runtime config | Release status | Notes |
|---|---|---|---|
| Reference-conditioned fallback | No runtime config | Supported default | Offline, conservative path for smoke tests and normal contributor workflows. |
| Auto learned routing | `examples/runtime_configs/auto_learned.json` | Preview | Used to exercise learned-provider selection when local prerequisites exist. |
| Hunyuan HTTP | `examples/runtime_configs/hunyuan_http.json` | Experimental | Network/runtime availability is outside the base support promise. |
| VGGT local | `examples/runtime_configs/vggt_local.json` | Experimental | Local Python/model environment is outside the base support promise. |

## Support windows

Until Lathe reaches a stable `1.0.0`, support is tied to the latest published
pre-release and the `main` branch:

- Security fixes target `main` first and may be backported to the latest
  pre-release when users are affected.
- Public contract compatibility is preserved unless the versioning policy
  explicitly introduces a new contract ID or major release.
- Older pre-releases receive best-effort help only after a newer pre-release
  is available.

## Repository remote status

This checkout was verified on April 25, 2026 with `git remote -v`, and no
local Git remotes were configured. `mkdocs.yml` still records the intended
public repository URL as `https://github.com/talmerri/lathe`. Before a public
release candidate is promoted, maintainers must either configure the checkout
against that public remote or update the release docs to state that the release
is private/local-only.
