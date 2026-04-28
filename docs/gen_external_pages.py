"""mkdocs-gen-files hook: mirror external repo pages into docs/ at build time.

Files like ``spec/lathe-v0.1.md`` and ``CONTRIBUTING.md`` live outside
``docs/`` but we want them in the navigation. ``mkdocs-gen-files`` lets
us generate virtual pages without committing copies that would drift.

Used by ``mkdocs.yml`` plugins -> gen-files scripts.
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
