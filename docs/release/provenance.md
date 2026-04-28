# Release provenance

This page records the current release provenance story for Lathe package
artifacts. It separates what the repository enforces today from the stable
release target described in the distribution plan.

## Current supported evidence

For the `0.2.0rc1` release-candidate line, package provenance is supported by:

- a signed Git tag created by the maintainer before pushing the release tag
- GitHub Actions build logs for the sdist and wheel produced from that tag
- PyPI Trusted Publishing, including PyPI artifact attestations from the
  release workflow
- CycloneDX SBOM files attached to the GitHub Release
- package metadata and version agreement checks from
  `python scripts/check_release_metadata.py`

Before cutting a candidate tag, run:

```powershell
python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1
```

After checking out the exact release commit or in the tag-triggered release
workflow, run the stricter tag check:

```powershell
python scripts/check_release_metadata.py --expected-tag v0.2.0-rc.1 --require-current-tag
```

The checker verifies that `pyproject.toml`, `lathe.__version__`,
`CHANGELOG.md`, release docs, package classifiers, license metadata, Python
support, runtime dependencies, contributor dependency groups, console script,
and the expected release tag agree.

## Signing status

Detached signatures for the built wheel, source distribution, and a
`SHA256SUMS` file are not yet implemented in `.github/workflows/release.yml`.
Until that release job grows either a repository-managed signing key or a
keyless signing step, Lathe must not claim detached package artifact signing
as completed.

The current release-candidate exception is:

- the Git tag is signed by the maintainer
- PyPI Trusted Publishing and PyPI attestations are enabled
- SBOMs are produced and attached
- detached GPG or cosign signatures for wheel/sdist/SHA256SUMS are deferred
  and must be called out in the release notes

This exception is acceptable only for pre-release candidates. A stable public
release must either attach detached artifact signatures or record an approved
release exception in the release notes before promotion.

## Version labels

Lathe uses PEP 440 package versions in Python metadata and SemVer-style labels
in tags and changelog headings:

| Surface | Example |
|---|---|
| `pyproject.toml` / `lathe.__version__` | `0.2.0rc1` |
| Git tag | `v0.2.0-rc.1` |
| `CHANGELOG.md` heading | `[0.2.0-rc.1]` |
| README / release docs | either form, as long as it normalizes to the package version |

The release metadata checker normalizes those forms and fails when they drift.
