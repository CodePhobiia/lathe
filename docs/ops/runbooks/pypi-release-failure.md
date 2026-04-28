# Runbook: PyPI Release Failure

The `release.yml` GitHub Actions workflow fails, or a partial/corrupt package was published to PyPI.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `release.yml` workflow exits non-zero on `twine upload` step.
- Package appears on PyPI but `pip install lathe==0.2.0rc1` fails with a hash mismatch or missing file.
- `twine check dist/*` fails locally.

## First response (≤5 min)

1. Check the Actions workflow log for the exact error: `gh run view <run-id> --log-failed`.
2. Do **not** attempt to re-upload before diagnosing — a partial second upload can create inconsistent metadata on PyPI.

## Investigation

Reproduce the build and check locally:

```bash
python -m build
twine check dist/*
```

Common failures:
- **Metadata error:** `pyproject.toml` or `setup.cfg` has a field that does not meet PyPI's validation schema (e.g., invalid classifier, missing `long_description_content_type`). Fix the metadata, rebuild, recheck.
- **Dependency sync drift:** a dependency listed in `pyproject.toml` is pinned to a version that does not exist on PyPI or has been yanked upstream. Run `pip-audit --strict` to catch CVE-related yanks, and `pip check` for inconsistency.
- **Workflow secrets:** `PYPI_API_TOKEN` may have expired or been revoked. Verify via `gh secret list`.
- **Partial publish:** if one wheel (e.g., `sdist`) uploaded but the `.whl` did not, the package is in an inconsistent state. Yank the partial release (see Mitigation) before re-uploading.

## Mitigation

**If the package was not published at all:** fix the issue, push a corrected commit or tag, and rerun the workflow.

**If the package was partially published:**

1. Yank the partial release immediately via the PyPI web UI (`Manage → Release history → Yank`) or:
   ```bash
   # PyPI yank requires web UI or the PyPI API token with yank permissions
   # Use the PyPI web UI at https://pypi.org/manage/project/lathe/releases/
   ```
2. Post a brief notice in the GitHub Release notes: "v0.2.0rc1 was briefly yanked due to a packaging issue; re-release forthcoming."
3. Fix the root cause, rebuild (`python -m build`), recheck (`twine check dist/*`), and re-upload.

**If the workflow token expired:** rotate `PYPI_API_TOKEN` in the repo secrets (`gh secret set PYPI_API_TOKEN`) and rerun the workflow.

## Communication

If a partial release was live for more than a few minutes, open a pinned GitHub issue noting the yank and ETA for a clean re-release. Update CHANGELOG.md with a note under the affected version.

## Escalation

Escalates to release blocker if the publish failure prevents the release from shipping within the launch window, or if a corrupt package was downloaded by users (see `docs/ops/runbooks/corrupted-release-artifact.md`).

## Postmortem trigger

Any confirmed partial publish or corrupt-package download by end users.
