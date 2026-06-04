"""mkdocs-gen-files hook: auto-generate docs/stdlib/index.md from std/*.lth.

For each `.lth` file under `std/`, this script extracts a leading ``// doc:``
comment block (if present) and emits an entry. Doc blocks are added in Wave 3;
files without one degrade to a path-only entry so the index still renders.

A doc block looks like:

    // doc:
    // purpose: Brass-bound hero chest family.
    // exports: chest_family, chest_handle_component
    // stability: stable

Lines are read until the first non-comment line.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import mkdocs_gen_files

STD_ROOT = Path("std")
OUTPUT = "stdlib/index.md"


def _iter_lth(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.lth") if p.is_file())


def _extract_doc_block(path: Path) -> dict[str, str]:
    """Return a dict of doc-block fields, or an empty dict if none is present."""
    fields: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fields

    in_block = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not in_block:
            if stripped.startswith("//") and "doc:" in stripped.lower():
                in_block = True
                continue
            if stripped == "" or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            break
        if not stripped.startswith("//"):
            break
        body = stripped.lstrip("/").strip()
        if not body:
            continue
        if ":" in body:
            key, _, value = body.partition(":")
            fields[key.strip().lower()] = value.strip()
    return fields


def _render_entry(path: Path, fields: dict[str, str]) -> str:
    rel = path.as_posix()
    if fields:
        purpose = fields.get("purpose", "").strip()
        exports = fields.get("exports", "").strip()
        stability = fields.get("stability", "").strip()
        lines = [f"### `{rel}`"]
        if purpose:
            lines.append("")
            lines.append(purpose)
        meta_parts = []
        if exports:
            meta_parts.append(f"**Exports:** {exports}")
        if stability:
            meta_parts.append(f"**Stability:** {stability}")
        if meta_parts:
            lines.append("")
            lines.append(" &middot; ".join(meta_parts))
        return "\n".join(lines) + "\n"
    return f"- `{rel}`\n"


def _generate() -> str:
    files = list(_iter_lth(STD_ROOT))
    out: list[str] = [
        "# Standard library",
        "",
        (
            "Auto-generated index of Lathe's source stdlib under `std/`. "
            "Entries with doc blocks include purpose, exports, and stability; "
            "files without a `// doc:` block fall back to a path-only entry."
        ),
        "",
    ]
    if not files:
        out.append("_No `std/*.lth` files found._\n")
        return "\n".join(out)

    groups: dict[str, list[Path]] = {}
    for path in files:
        parts = path.relative_to(STD_ROOT).parts
        group = parts[0] if len(parts) > 1 else "_root"
        groups.setdefault(group, []).append(path)

    for group in sorted(groups):
        heading = group if group != "_root" else "(top level)"
        out.append(f"## {heading}")
        out.append("")
        for path in groups[group]:
            fields = _extract_doc_block(path)
            out.append(_render_entry(path, fields))
        out.append("")

    return "\n".join(out).rstrip() + "\n"


with mkdocs_gen_files.open(OUTPUT, "w") as fd:
    fd.write(_generate())
