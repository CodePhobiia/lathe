# Release checklist

Use this checklist for every release candidate. It turns the quality bar into
an ordered promotion process and records the evidence reviewers need before a
tag is cut.

## 1. Version and changelog

- Confirm `pyproject.toml`, `lathe.__version__`, README, docs, changelog, and
  release branch name agree on the target version.
- Run `python scripts/check_release_metadata.py --expected-tag v<version>` to
  verify package metadata, dependency groups, classifiers, license metadata,
  Python support, changelog, docs, and the expected release tag agree. On the
  tagged release commit, add `--require-current-tag`.
- Move user-visible changes from `CHANGELOG.md` `Unreleased` into the target
  version section.
- Verify the changelog summarizes user impact, migrations, security notes,
  deprecations, and known release exceptions.
- Confirm stable contract IDs changed only through the documented versioning
  process.

## 2. Clean checkout setup

- Start from a clean checkout of the release candidate branch.
- Run the documented bootstrap command for each supported platform in the
  support matrix.
- Confirm `python -m lathe.cli doctor` and the documented smoke-test command
  pass after bootstrap.
- Record any platform-specific exception in the release notes before
  promotion.

## 3. Tests and examples

- Run the documented fast test lane.
- Run the full release test lane, including contract, golden, property, fuzz,
  slow, benchmark, visual-quality, and example-corpus partitions.
- Run canonical examples through `normalize`, `check`, `plan`, `materialize`,
  and expected build/certification commands.
- For each release-candidate canonical build, archive and review
  `build_report.json`, `selector_manifest.json`,
  `stages/validate/report.json`, `stages/package/package_manifest.json`,
  `stages/package/trace_manifest.json`, GLB output (`.glb`), USD output
  (`.usda`), engine manifests (`.lathe_for_godot.json`,
  `.lathe_for_unity.yaml`, `.lathe_for_unreal.json`), and preview media
  (`stages/package/previews/turntable.png`,
  `stages/package/previews/wireframe.png`,
  `stages/package/previews/uv_layout.png`,
  `stages/package/previews/lod_sheet.png`).
- Review `flaky-test` labeled issues and recent CI reruns; promotion is blocked
  by any unexplained flaky failure in a required release lane.
- Verify every fixed release-blocking bug has a regression test or a recorded
  exception explaining why a test is not feasible.

## 4. Docs review

- Rebuild public docs with strict link checking.
- Regenerate or verify docs-visible CLI examples against the current parser
  help, command output, and artifact layout.
- Confirm quickstart artifact paths exist after the documented quickstart
  build.
- Confirm known limitations, release exceptions, support matrix, and
  troubleshooting guidance match the release candidate behavior.

## 5. Security review

- Run Bandit, pip-audit, Gitleaks, Semgrep, CodeQL, and repo-specific security
  tests using the commands documented in `docs/security/ci_gates.md`.
- Review any scanner suppressions for a specific rule, path, owner, and
  rationale.
- Confirm telemetry, provider config, image refs, cache metadata, archive
  writes, and subprocess sandboxing have current negative tests.
- Confirm no secrets, local paths, prompts, or private identifiers are present
  in generated release artifacts.

## 6. SBOM, signing, and package artifacts

- Build the source distribution and wheel from the clean checkout.
- Generate CycloneDX SBOMs for runtime and dev dependency graphs.
- Verify package metadata, classifiers, license files, and Python version
  requirements with `python scripts/check_release_metadata.py`.
- Review [Asset and dependency provenance](asset-provenance.md) and confirm
  every checked-in binary reference or fixture is listed.
- Produce hashes for release artifacts.
- Sign release artifacts or record an approved exception that says signing is
  not supported for this release channel. See
  [Release provenance](provenance.md) for the current pre-release exception.
- Attach SBOMs, hashes, signatures, and reproducibility receipts to the release
  record.

## 7. Promotion decision

- Confirm all required CI workflows are green on the release branch.
- Confirm no critical or major bug remains open without an approved release
  exception.
- Confirm the release notes describe user-visible value, known limitations, and
  migration steps.
- Have a reviewer who did not implement the final fixes reassess the 10/10
  score evidence before promotion.
- Cut the tag only after the evidence bundle is complete and reviewable.
