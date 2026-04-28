"""Hero output gallery renderer.

For each hero in `lathe.hero_manifest.HEROES`:

1. Runs `python -m lathe.cli build <src> <asset> --out docs/gallery/<asset>`
   (uses the existing build cache — reruns are cheap).
2. If Blender is available (via `LATHE_BLENDER_PATH` env var or `blender` on
   PATH), invokes `scripts/_gallery_blender.py` in Blender's embedded Python
   to render 5 PNG turntable stills and an optional 24-frame WebP. If Blender
   is not available, writes a `no_blender.txt` placeholder instead — the
   gallery landing page still renders.
3. Produces `docs/gallery/<asset>/index.html` from the template in
   `docs/templates/gallery_index.html.j2`.
4. Produces a top-level `docs/gallery/index.html` landing page listing every
   hero with score / threshold / certified status / preview link.

Generated output under `docs/gallery/<asset>/` is git-ignored — CI uploads
it as an artifact or pushes to `gh-pages` separately.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import string
import subprocess
import sys
from pathlib import Path

# Allow importing the lathe package when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lathe.hero_manifest import HEROES, Hero

GALLERY_DIR = _REPO_ROOT / "docs" / "gallery"
TEMPLATE_PATH = _REPO_ROOT / "docs" / "templates" / "gallery_index.html.j2"
BLENDER_SCRIPT = _REPO_ROOT / "scripts" / "_gallery_blender.py"


def _load_template() -> string.Template:
    return string.Template(TEMPLATE_PATH.read_text(encoding="utf-8"))


def _find_blender() -> str | None:
    env_path = os.environ.get("LATHE_BLENDER_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    return shutil.which("blender")


def _run_build(hero: Hero, asset_dir: Path) -> dict:
    """Run `lathe build` so build artifacts land inside ``asset_dir``.

    `python -m lathe.cli build <src> <asset> --out <dir>` creates
    ``<dir>/<asset_name>/build_report.json``. We want everything
    directly in ``asset_dir`` so gallery HTML can link to ``asset.glb``
    with relative paths — so we point ``--out`` at the parent and then
    flatten the resulting `<asset_name>/` subtree into ``asset_dir``.
    """
    asset_dir.mkdir(parents=True, exist_ok=True)
    build_root = asset_dir.parent / f"_build_{hero.asset_name}"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)
    cmd = [
        sys.executable,
        "-m",
        "lathe.cli",
        "build",
        str(hero.source_path),
        hero.asset_name,
        "--out",
        str(build_root),
    ]
    subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))
    produced = build_root / hero.asset_name
    if not produced.exists():
        raise RuntimeError(f"lathe build did not produce {produced}")
    for item in produced.iterdir():
        dest = asset_dir / item.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(item), str(dest))
    shutil.rmtree(build_root, ignore_errors=True)
    report_path = asset_dir / "build_report.json"
    return json.loads(report_path.read_text(encoding="utf-8"))


def _find_glb(out_dir: Path, report: dict) -> Path | None:
    for output in report.get("outputs", []) or []:
        rel = output.get("path") if isinstance(output, dict) else None
        if rel and rel.lower().endswith(".glb"):
            candidate = (out_dir / rel).resolve()
            if candidate.exists():
                return candidate
    for candidate in out_dir.rglob("*.glb"):
        return candidate
    return None


def _render_with_blender(blender: str, glb: Path, render_dir: Path) -> list[Path]:
    render_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        blender,
        "--background",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--glb",
        str(glb),
        "--out",
        str(render_dir),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))
    except subprocess.CalledProcessError as exc:
        (render_dir / "blender_failed.txt").write_text(
            f"blender exit code {exc.returncode}\n", encoding="utf-8"
        )
        return []
    return sorted(render_dir.glob("render_*.png"))


def render_hero_page(
    hero: Hero,
    report: dict,
    glb: Path | None,
    renders: list[Path],
    template: string.Template,
    out_dir: Path,
) -> Path:
    """Render one hero gallery page."""
    certified = bool(report.get("certified"))
    if renders:
        imgs = "\n".join(f'    <a href="{r.name}"><img src="{r.name}" alt="{r.stem}"></a>' for r in renders)
        renders_block = f'<div class="renders">\n{imgs}\n</div>'
    else:
        renders_block = (
            '<div class="placeholder">No renders available '
            "(Blender not on PATH or render step skipped).</div>"
        )
    glb_rel = glb.name if glb else "(not found)"
    html = template.safe_substitute(
        asset_name=hero.asset_name,
        score=f"{float(report.get('score', 0.0)):.6f}",
        threshold=f"{hero.threshold:.2f}",
        certified="certified" if certified else "not certified",
        certified_class="yes" if certified else "no",
        glb_path=glb_rel,
        renders_block=renders_block,
    )
    page_path = out_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path


def render_landing(results: list[dict]) -> Path:
    """Render the gallery landing page."""
    rows = []
    for r in results:
        cert = "yes" if r["certified"] else "no"
        cert_class = "yes" if r["certified"] else "no"
        preview = f'<a href="{r["asset_name"]}/index.html">view</a>' if r["has_page"] else "—"
        rows.append(
            f"<tr><td>{r['asset_name']}</td>"
            f"<td>{r['family']}</td>"
            f"<td><code>{r['score']:.6f}</code></td>"
            f"<td><code>{r['threshold']:.2f}</code></td>"
            f'<td class="certified-{cert_class}">{cert}</td>'
            f"<td>{preview}</td></tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="6">No builds.</td></tr>'
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Lathe hero gallery</title>
<style>
 body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
 th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #e1e4e8; }}
 th {{ background: #f6f8fa; }}
 .certified-yes {{ color: #1a7f37; font-weight: 600; }}
 .certified-no {{ color: #cf222e; font-weight: 600; }}
 code {{ background: #f6f8fa; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style></head>
<body>
<h1>Lathe hero gallery</h1>
<p>Auto-generated from <code>scripts/render_gallery.py</code>.</p>
<table>
<thead><tr><th>Asset</th><th>Family</th><th>Score</th><th>Threshold</th><th>Certified</th><th>Preview</th></tr></thead>
<tbody>
{body}
</tbody></table>
</body></html>
"""
    landing_path = GALLERY_DIR / "index.html"
    landing_path.write_text(html, encoding="utf-8")
    return landing_path


def main(argv: list[str] | None = None) -> int:
    """Run the gallery renderer CLI."""
    parser = argparse.ArgumentParser(description="Render the hero output gallery.")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing build_report.json in docs/gallery/<asset> instead of rebuilding.",
    )
    parser.add_argument(
        "--only",
        action="append",
        help="Restrict to a specific hero asset_name (repeatable).",
    )
    args = parser.parse_args(argv)

    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    template = _load_template()
    blender = _find_blender()
    heroes = HEROES
    if args.only:
        wanted = set(args.only)
        heroes = [h for h in HEROES if h.asset_name in wanted]

    results: list[dict] = []
    for hero in heroes:
        asset_dir = GALLERY_DIR / hero.asset_name
        asset_dir.mkdir(parents=True, exist_ok=True)
        report: dict
        if args.skip_build and (asset_dir / "build_report.json").exists():
            report = json.loads((asset_dir / "build_report.json").read_text(encoding="utf-8"))
        else:
            try:
                report = _run_build(hero, asset_dir)
            except subprocess.CalledProcessError as exc:
                print(f"[gallery] build failed for {hero.asset_name}: {exc}", file=sys.stderr)
                (asset_dir / "build_failed.txt").write_text(
                    f"lathe build exit code {exc.returncode}\n", encoding="utf-8"
                )
                results.append(
                    {
                        "asset_name": hero.asset_name,
                        "family": hero.family,
                        "score": 0.0,
                        "threshold": hero.threshold,
                        "certified": False,
                        "has_page": False,
                    }
                )
                continue

        glb = _find_glb(asset_dir, report)
        render_dir = asset_dir / "renders"
        renders: list[Path] = []
        if blender and glb is not None and BLENDER_SCRIPT.exists():
            renders = _render_with_blender(blender, glb, render_dir)
        else:
            (asset_dir / "no_blender.txt").write_text(
                "Blender not available (LATHE_BLENDER_PATH unset and `blender` not on PATH); "
                "renders skipped.\n",
                encoding="utf-8",
            )

        render_hero_page(hero, report, glb, renders, template, asset_dir)
        results.append(
            {
                "asset_name": hero.asset_name,
                "family": hero.family,
                "score": float(report.get("score", 0.0)),
                "threshold": hero.threshold,
                "certified": bool(report.get("certified")),
                "has_page": True,
            }
        )

    render_landing(results)
    print(f"[gallery] wrote {len(results)} asset page(s) to {GALLERY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
