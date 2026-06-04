"""mkdocs-gen-files hook: mirror external repo pages into docs/ at build time.

Files like ``spec/lathe-v0.1.md`` and ``CONTRIBUTING.md`` live outside
``docs/`` but we want them in the navigation. ``mkdocs-gen-files`` lets
us generate virtual pages without committing copies that would drift.

Used by ``mkdocs.yml`` plugins -> gen-files scripts.

In addition to markdown mirrors, this hook also copies the JSON schema
files under ``<repo-root>/schema/`` into ``<docs_dir>/schema/`` so that
mkdocs-strict link resolution finds the targets that ``docs/api/`` and
``docs/llm/`` pages reference. Authors continue to write ``../../schema/X``
links in source docs (which navigate from ``docs/X/Y.md`` up to the repo
root then back into ``schema/``); after the mirror, the same path
resolves to ``docs_dir/schema/X`` inside the built site.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

_REPO_ROOT = Path(__file__).resolve().parent.parent

# (source_path, output_path_under_docs_dir)
_MIRRORS: list[tuple[Path, str]] = [
    (_REPO_ROOT / "spec" / "lathe-v0.1.md", "spec/lathe-v0.1.md"),
    (_REPO_ROOT / "CONTRIBUTING.md", "contributing.md"),
    (_REPO_ROOT / "CONTRIBUTING.md", "CONTRIBUTING.md"),
    (_REPO_ROOT / "AGENTS.md", "AGENTS.md"),
    (_REPO_ROOT / "SECURITY.md", "SECURITY.md"),
    (_REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md", "pull_request_template.md"),
]


# Link rewrites applied to mirrored content so mkdocs --strict resolves all
# internal references. Keys are source substrings; values are replacements
# that point to files we know are inside docs_dir (either native or mirrored).
_LINK_REWRITES: list[tuple[str, str]] = [
    (".github/PULL_REQUEST_TEMPLATE.md", "pull_request_template.md"),
]


for src, dst in _MIRRORS:
    if not src.exists():
        continue
    text = src.read_text(encoding="utf-8")
    for old, new in _LINK_REWRITES:
        text = text.replace(old, new)
    with mkdocs_gen_files.open(dst, "w") as out:
        out.write(text)
    mkdocs_gen_files.set_edit_path(dst, src.relative_to(_REPO_ROOT).as_posix())


# Mirror every JSON schema referenced by docs into ``docs_dir/schema/`` so
# that ``../schema/X.schema.json`` style links from ``docs/**/page.md``
# resolve under mkdocs --strict. The mirrored files are virtual (gen-files
# adds them to the built site without writing them to the source tree).
# We don't call ``set_edit_path`` for the schemas because mkdocs-gen-files
# warns when an edit-path target is a non-markdown asset; the link target
# itself is what matters for strict mode.
_SCHEMA_DIR = _REPO_ROOT / "schema"
if _SCHEMA_DIR.is_dir():
    for schema_path in sorted(_SCHEMA_DIR.rglob("*.schema.json")):
        relative = schema_path.relative_to(_SCHEMA_DIR).as_posix()
        target = f"schema/{relative}"
        try:
            content = schema_path.read_bytes()
        except OSError:
            continue
        with mkdocs_gen_files.open(target, "wb") as out:
            out.write(content)
