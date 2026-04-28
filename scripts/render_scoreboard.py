"""Hero benchmark scoreboard generator.

Emits `docs/benchmarks/scoreboard.md` — a markdown table covering every hero
in `lathe.hero_manifest.HEROES`. Data sources, in priority order:

1. A JSON file at `docs/benchmarks/data/<asset>.json` (optional, committed
   alongside historical benchmark snapshots).
2. The `build_report.json` written by a fresh
   `python -m lathe.cli build ... --out <dir>` under either
   `docs/gallery/<asset>` (the default gallery location) or a `--out` passed
   on the CLI.

For each hero we extract: score, threshold, certified, build_time_s (if
present), and the `.glb` SHA256. Missing heroes render as `n/a` so the
table always has exactly as many rows as `HEROES`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lathe.hero_manifest import HEROES, Hero

DATA_DIR = _REPO_ROOT / "docs" / "benchmarks" / "data"
SCOREBOARD_PATH = _REPO_ROOT / "docs" / "benchmarks" / "scoreboard.md"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_glb(build_dir: Path, report: dict) -> Path | None:
    for output in report.get("outputs", []) or []:
        rel = output.get("path") if isinstance(output, dict) else None
        if rel and rel.lower().endswith(".glb"):
            candidate = (build_dir / rel).resolve()
            if candidate.exists():
                return candidate
    for candidate in build_dir.rglob("*.glb"):
        return candidate
    return None


def _read_snapshot(hero: Hero) -> dict | None:
    snap_path = DATA_DIR / f"{hero.asset_name}.json"
    if not snap_path.exists():
        return None
    try:
        return json.loads(snap_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_build_report(build_dir: Path, hero: Hero) -> dict | None:
    report_path = build_dir / hero.asset_name / "build_report.json"
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    glb = _find_glb(build_dir / hero.asset_name, report)
    return {
        "score": float(report.get("score", 0.0)),
        "threshold": float(report.get("threshold", hero.threshold)),
        "certified": bool(report.get("certified")),
        "build_time_s": report.get("build_time_s"),
        "glb_sha256": _sha256(glb) if glb else None,
    }


def collect_row(hero: Hero, build_dir: Path) -> dict:
    """Collect the scoreboard row for one hero."""
    row: dict = {
        "asset_name": hero.asset_name,
        "family": hero.family,
        "threshold": hero.threshold,
        "score": None,
        "certified": None,
        "build_time_s": None,
        "glb_sha256": None,
        "source": "none",
    }
    snap = _read_snapshot(hero)
    if snap is not None:
        row.update(
            {
                "score": snap.get("score"),
                "threshold": float(snap.get("threshold", hero.threshold)),
                "certified": snap.get("certified"),
                "build_time_s": snap.get("build_time_s"),
                "glb_sha256": snap.get("glb_sha256"),
                "source": "snapshot",
            }
        )
        return row
    fresh = _read_build_report(build_dir, hero)
    if fresh is not None:
        row.update(fresh)
        row["source"] = "build_report"
    return row


def _fmt_score(v: float | None) -> str:
    return "n/a" if v is None else f"{float(v):.6f}"


def _fmt_threshold(v: float) -> str:
    return f"{v:.2f}"


def _fmt_certified(v: bool | None) -> str:
    if v is None:
        return "n/a"
    return "yes" if v else "no"


def _fmt_time(v) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):.1f}s"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_hash(v: str | None) -> str:
    if not v:
        return "n/a"
    return f"`{v[:16]}…`"


def render_markdown(rows: list[dict], now: _dt.datetime) -> str:
    """Render scoreboard rows as markdown."""
    lines = [
        "# Lathe hero scoreboard",
        "",
        f"_Last updated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}_",
        "",
        "| Hero | Family | Score | Threshold | Certified | Build time | .glb SHA256 | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    r["asset_name"],
                    r["family"],
                    _fmt_score(r["score"]),
                    _fmt_threshold(r["threshold"]),
                    _fmt_certified(r["certified"]),
                    _fmt_time(r["build_time_s"]),
                    _fmt_hash(r["glb_sha256"]),
                    r["source"],
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the scoreboard renderer CLI."""
    parser = argparse.ArgumentParser(description="Render the hero scoreboard.")
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=_REPO_ROOT / "docs" / "gallery",
        help="Directory containing <asset>/build_report.json (default: docs/gallery).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SCOREBOARD_PATH,
        help="Path to write the scoreboard markdown (default: docs/benchmarks/scoreboard.md).",
    )
    args = parser.parse_args(argv)

    rows = [collect_row(hero, args.build_dir) for hero in HEROES]
    markdown = render_markdown(rows, _dt.datetime.now(_dt.UTC))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"[scoreboard] wrote {args.out} ({len(rows)} heroes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
