# Known limitations

This page separates deliberate alpha limits from defects. A limitation may
ship in a pre-release only when it is visible, bounded, and does not invalidate
the support matrix or quality bar.

## Deliberate pre-release limits

| Limit | Why it is acceptable for now | Release impact |
|---|---|---|
| Lathe is still a reference compiler scaffold | The language and stable handoff contracts are the product center while implementation depth grows. | Must be described as pre-release, not stable. |
| Learned providers are optional proposal sources | External model runtimes are not required for the conservative build path. | Provider failures must be explicit and traceable, not silent. |
| Surface output is still partly procedural | The V1.2 surface lane emits governed maps and reports, but authored material polish is still improving. | Release notes must avoid implying finished art direction. |
| Some example assets are expected certification failures | The examples catalog tracks assets that intentionally stay below their own threshold so regressions remain visible. | Expected failures must remain listed in `docs/examples_catalog.md`. |
| Full validation can be slow | Build-heavy, golden, property, fuzz, benchmark, and visual-quality checks run in split lanes. | A release candidate still needs the complete required gate evidence. |
| Optional Blender, xatlas, Hunyuan, and VGGT paths vary by machine | These tools depend on host installs, bindings, or model services. | The support matrix must identify which paths are supported, preview, or experimental. |

## Defects

The following are defects, not acceptable limitations:

- a supported clean install fails
- `python -m lathe.cli` breaks on the supported matrix
- a public contract changes without the versioning process
- a fallback hides failure or emits success-shaped output without trace evidence
- a documented artifact path is missing after the documented command succeeds
- a certified example regresses without an expected-failure entry and owner
- a security, privacy, or untrusted-input bug remains open without an approved exception

## Release-blocker severity

| Severity | Definition | Release action |
|---|---|---|
| Critical | Security exposure, data loss, arbitrary code execution, broken install, or public-contract break. | Block release. No exception unless maintainers formally defer a non-exploitable false positive. |
| Major | Supported workflow cannot complete, certification lies, or docs would lead users to a broken path. | Block release unless an exception records a workaround and owner. |
| Minor | Usability issue, slow path, confusing message, or unsupported experimental mode failure. | May ship with an exception or known-limitations entry. |
| Trivial | Typo or cosmetic doc/report issue with no behavior risk. | May ship if tracked. |

## Review cadence

Known limitations are reviewed before every release candidate. Items are
removed only after the underlying behavior is fixed and the matching regression
test or docs update has landed.
