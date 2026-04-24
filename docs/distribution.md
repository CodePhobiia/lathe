# Distribution

This document defines how Lathe reaches users. It covers Day-1 channels (what
must exist before the first public release) and Month-5 additions (channels we
add once the project has a track record and a signed tag history).

Distribution is not marketing. Distribution is the act of placing Lathe in the
package managers, asset libraries, and extension platforms where users already
live. A user who has to clone a repo and read a README is a user who bounced.

## Principles

- Meet users where they already run their tooling. Python devs expect `pip`.
  Godot devs expect the AssetLib search bar inside the editor. Blender users
  expect the Extensions Platform. macOS power users expect Homebrew. Windows
  power users expect Scoop.
- Every artifact we publish is signed, reproducible, and backed by a release
  note in `CHANGELOG.md`. No opaque builds.
- Every artifact ships an SBOM. If downstream CI cannot audit what went into
  the build, we have not met the production-grade bar we set for ourselves.
- The public language contract (`profile`, `contract`, `critic`, `asset`,
  `variant`, and the stage names) is covered by the versioning policy in
  `docs/versioning.md`. A package manager bump that changes public semantics
  is a major release.

## Day-1 channels

### 1. PyPI: `pip install lathe`

PyPI is the primary channel. The `lathe` console script and `python -m
lathe.cli` entry point must both work from a fresh virtualenv after a single
`pip install`.

Publishing is wired through OIDC Trusted Publishing in
`.github/workflows/release.yml` (landed in Wave 1). The workflow is triggered
by a pushed `v*` tag and requires no long-lived PyPI credentials in the repo.

PyPI release checklist:

1. Confirm `CHANGELOG.md` has a populated entry for the new version. Stubs
   are not acceptable.
2. Bump the version in `pyproject.toml`. Lathe follows semver with the
   language contract as the stable surface: breaking language changes bump
   MAJOR; additive language or backend changes bump MINOR; bug fixes and
   non-semantic internal changes bump PATCH.
3. Bump the version string referenced in `lathe/__init__.py` if present, so
   `lathe --version` and the emitted manifest agree.
4. Run `python -m pytest -q` and `scripts/lathe_smoke.sh` locally. Green is
   a precondition, not a nice-to-have.
5. Commit, tag (`git tag -s v<version>`), and push the tag. The signed tag
   is what the release workflow consumes.
6. The workflow runs `python -m build`, then uploads the resulting sdist and
   wheel via `pypa/gh-action-pypi-publish@release/v1` using the project's
   Trusted Publisher configuration on PyPI.
7. The workflow attaches the SBOM (CycloneDX JSON, generated from
   `cyclonedx-py` over the built wheel) to the GitHub Release.
8. The workflow generates release notes from `CHANGELOG.md` and posts them
   to the GitHub Release.
9. Within 15 minutes, verify that `pip install lathe==<version>` in a clean
   virtualenv installs cleanly and `lathe doctor` exits 0.

Known constraints:

- `python -m lathe.cli` must remain the canonical invocation. The console
  script is an ergonomic shortcut. This is asserted in `CLAUDE.md` and any
  release that silently breaks `python -m lathe.cli` is a regression.
- `.lathe_lark_cache/` is never shipped in the wheel. It is regenerated on
  first parse.
- Optional runtime backends (Hunyuan HTTP, VGGT) are not installed by
  default. They are opt-in extras (`pip install lathe[hunyuan]`, etc.) and
  their absence must not degrade the conservative fallback path.

### 2. GitHub Releases (signed tarballs)

Every tagged release publishes a GitHub Release with:

- source tarball and wheel (the same artifacts uploaded to PyPI)
- `SHA256SUMS` file
- detached GPG signature over `SHA256SUMS`
- SBOM (CycloneDX JSON)
- release notes generated from `CHANGELOG.md`

This channel serves two audiences. First, studios with air-gapped or
review-gated CI that cannot pull directly from PyPI. Second, forensic
auditors who need to pin a specific build artifact rather than a PyPI
version string.

GitHub Release checklist:

1. The PyPI workflow must complete successfully first. The GitHub Release
   is produced by the same workflow in a follow-on job so the artifacts
   match byte-for-byte.
2. The signing key is stored as a repository secret and rotated annually.
3. Release notes follow the Keep-a-Changelog format already used in
   `CHANGELOG.md`.
4. Release notes must call out (a) breaking language changes, (b) new
   stable contract IDs, (c) deprecations with their removal version, and
   (d) any backend default flips.

### 3. Godot AssetLib: `lathe-godot` addon

The `lathe-godot` addon is the primary surface for the Godot wedge described
in `docs/blog/04_godot_integration_walkthrough.md`. It exposes watch-mode
rebuilds and in-editor import of the certified `.glb` plus manifest.

Submission prerequisites:

- A tagged release in the `lathe-godot` repository (separate from the main
  Lathe repo, because AssetLib submissions are per-addon and Godot-version
  scoped).
- An `icon.png` (128×128) and at least one screenshot demonstrating the
  editor experience.
- A `plugin.cfg` with a clear `description`, the current `version`, and the
  minimum Godot version supported (target Godot 4.3+ for Day-1).
- MIT or Apache-2.0 license file in the repo root. Lathe uses MIT; the
  addon inherits.
- A README that points to `docs/blog/04_godot_integration_walkthrough.md`
  for the end-to-end story.

Submission process:

1. Log into godotengine.org/asset-library with the maintainer account.
2. "Submit Asset", fill in repository URL, commit hash of the tagged
   release, category ("Tools / Import"), and the Godot version.
3. Category choice matters: "Tools" surfaces the addon under the in-editor
   AssetLib tab, which is the user-visible channel. "Demos" and "Addons"
   are lower traffic for our audience.
4. The review queue is volunteer-run. Expect a 3-14 day turnaround on
   first submission, faster on subsequent revisions.
5. Reviewers will check: the repo exists at the pinned commit, the license
   is permissive, the `plugin.cfg` is well-formed, and the addon loads in
   a blank Godot project without errors. Run all four of these checks
   before submitting.
6. On acceptance, the addon appears in the in-editor AssetLib search for
   "Lathe". On rejection, the reviewer posts feedback; address and
   resubmit against the same entry.

Review cadence after acceptance: every tagged `lathe-godot` release is a
new AssetLib submission against the existing asset entry. No auto-update
from Git; users click "Update" in the editor UI.

## Month-5 additions

These channels are added once Lathe has (a) a 5+ release history, (b)
stable semver discipline demonstrated over those releases, and (c) an
installable artifact story that is boring enough that packagers can trust
it without handholding.

### Homebrew tap

A Homebrew tap (`homebrew-lathe`) ships a `lathe.rb` formula that wraps the
PyPI install in a Python venv managed by Homebrew. Users run
`brew install lathe-project/lathe/lathe`.

Prerequisites:

- Stable PyPI release cadence (no yanks for 3 consecutive releases).
- A `lathe.rb` formula that pins to a specific PyPI version and SHA256.
- Tap repository hosted at `github.com/lathe-project/homebrew-lathe`.
- The formula declares a `depends_on "python@3.12"` (or whichever minor
  version is our floor at the time).
- `test do` block in the formula that runs `lathe doctor` and asserts
  exit 0.

Not submitting to `homebrew-core`: the formula review there is strict
about dependency counts and we have optional ML extras that would be
rejected. A tap is the right channel.

### Scoop manifest

Scoop is the Windows equivalent. A `scoop-lathe` bucket ships a JSON
manifest with the PyPI-backed install command. Users run
`scoop bucket add lathe https://github.com/lathe-project/scoop-lathe` and
then `scoop install lathe`.

Prerequisites:

- Same stable release cadence bar as Homebrew.
- A manifest that declares the architecture, version, and the `bin` entry
  pointing to the wrapper script.
- A `checkver` block so scoop can auto-detect new releases from PyPI.
- A `hash` block so installs are verified against the PyPI SHA256.

### Blender Extensions Platform

If we ship a Lathe inspector addon for Blender (a Blender-side companion
to the `.blend` artifacts retained by V1.3), that addon lands on the
Blender Extensions Platform at extensions.blender.org.

Prerequisites:

- A separate repository (`lathe-blender`) mirroring the `lathe-godot`
  model. The addon is not bundled into the main Lathe wheel.
- A valid `blender_manifest.toml` declaring the addon ID, schema version,
  minimum Blender version, and explicit `permissions` entries for
  filesystem read access (to load `.blend` artifacts from `dist/`).
- Tagged releases with SHA-pinned zip archives uploaded to the
  Extensions Platform dashboard.
- Addon must pass the automated `blender --factory-startup
  --command extension validate` check before submission.
- Human review by the Blender Foundation follows; cadence has historically
  been 1-3 weeks.

The Blender Extensions Platform requires GPL-compatible licensing for
anything that links against Blender's Python API in a non-trivial way.
Our inspector addon, if it uses `bpy` directly, inherits GPL. The main
Lathe library (which calls Blender out-of-process via subprocess) is
unaffected and stays MIT.

## Out of scope for Day-1 and Month-5

These are deferred until there is user demand and maintainer capacity:

- Conda / conda-forge packaging. Conda-forge has strict feedstock review
  and non-trivial maintenance overhead. We will revisit once we have a
  repeated request from a studio CI environment that is conda-only.
- Debian / RPM packages. Distro packaging is a long tail; the PyPI path
  works inside venvs on every mainstream distro and is sufficient.
- Docker image on Docker Hub. A container is useful for CI certification
  but is out of scope here; see the CI certification story in
  `docs/blog/05_certification_as_the_product.md`.

## Release cadence

- Patch releases: on-demand, within a week of a user-visible bug fix
  landing on `main`.
- Minor releases: roughly every 4-6 weeks, aligned to the end of a
  planning wave.
- Major releases: driven by language-contract changes; never surprise
  users with a bare major bump in a minor cycle.

## Related documents

- `docs/versioning.md` — semver policy and public surface definition.
- `docs/roadmap_public.md` — milestone schedule, including Month-5.
- `docs/security/` — signing keys, SBOM policy, vulnerability disclosure.
- `docs/blog/04_godot_integration_walkthrough.md` — the addon's story.
- `docs/blog/05_certification_as_the_product.md` — the CI-SaaS angle.
