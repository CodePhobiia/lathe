# Runbook: Docs Site Broken

`mkdocs build --strict` fails or published pages return 404.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- The `docs.yml` workflow fails on `mkdocs build --strict`.
- A docs page that previously existed returns 404 in the browser.
- A link in the docs points to a non-existent anchor or page (broken-link check catches this).
- A nav entry in `mkdocs.yml` references a file that has been moved or deleted.

## First response (≤5 min)

1. Check the `docs.yml` workflow log: `gh run list --workflow=docs.yml --limit 3`.
2. Reproduce locally: `mkdocs build --strict 2>&1 | head -50`.

## Investigation

```bash
# Reproduce the build failure
mkdocs build --strict

# Check for nav drift — missing files referenced in mkdocs.yml
python -c "
import yaml, os
cfg = yaml.safe_load(open('mkdocs.yml'))
# Walk the nav tree and check each file exists
def walk(nav, prefix='docs/'):
    for item in (nav or []):
        if isinstance(item, dict):
            for k, v in item.items():
                if isinstance(v, str):
                    p = prefix + v
                    if not os.path.exists(p): print('MISSING:', p)
                elif isinstance(v, list):
                    walk(v, prefix)
walk(cfg.get('nav', []))
"
```

For broken links in production (404s): compare `docs.yml` deploy step against `mkdocs.yml` `site_url` and the GitHub Pages branch/path config in repo settings. A mismatch in the `docs_dir` or `site_dir` can cause all pages to 404.

For a page deleted but still referenced from other pages: `grep -r "old-page-name" docs/` to find all inbound links.

## Mitigation

- **Nav drift (file renamed or deleted):** update `mkdocs.yml` nav to point to the new path, or restore the file.
- **Broken inbound links:** fix the links in the source pages; `mkdocs build --strict` will catch them.
- **Production 404 after deploy:** check the GitHub Pages source branch (`gh-pages`) and the `site_url` in `mkdocs.yml`. If the site was deployed to the wrong path, redeploy with the correct config.
- **User-visible outage:** add a banner to the repo README noting the docs are temporarily unavailable, then fix and redeploy.
- **Revert approach:** if the breakage was introduced by a specific PR, revert that PR to restore the last-known-good docs state, then fix forward.

## Communication

For a production 404 affecting users, add a pinned issue with the status and ETA: `gh issue create --label docs --pin --title "Docs site temporarily unavailable"`.

## Escalation

Escalates to release blocker if the docs site is down at launch time. A transient build failure that does not affect the currently-published pages is P1.

## Postmortem trigger

Any docs outage that lasted more than 2 h in production, or any case where broken docs were linked from the PyPI page or GitHub release notes.
