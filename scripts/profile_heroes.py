"""Hero performance profiler (BL-38, Plan 08 Phase 10 — Performance).

Iterates ``lathe.hero_manifest.HEROES``; runs ``python -m lathe.cli build``
for each hero and records wall-clock + per-stage-bundle write times into
``perf/budgets.json``. The companion timestamped record is written to
``perf/heroes_<UTC-date>.json``.

Modes
-----

``--write``     (default) Re-build heroes, write fresh budgets.json and a
                historical record. Stage-elapsed numbers are recovered
                opportunistically from ``build_report.json["stages"]`` if
                BL-33/BL-36 wired them; otherwise we fall back to bundle
                file mtime deltas (coarse but monotonic) and tag the
                stage with ``"source": "mtime_delta"``.

``--verify``    Read the existing budgets.json, run a fresh build, and
                fail (exit 2) if any stage exceeds its budget by >20 %%.

``--only NAME`` Restrict to a single hero by name.

This is the **proof-of-concept** scope from Plan 08 Phase 10. Full
per-stage instrumentation in the executor and CI gate enforcement are
Wave 5 items — see ``perf/README.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lathe.hero_manifest import HEROES, Hero  # noqa: E402

PERF_DIR = _REPO_ROOT / "perf"
BUDGETS_PATH = PERF_DIR / "budgets.json"
MANIFEST_PATH = PERF_DIR / "manifest.json"
TMP_OUT_ROOT = _REPO_ROOT / "tmp_profile"

# Stages we attempt to time (matches the canonical ``stages/`` subdirs
# created by the executor). ``execution`` may be absent for hero builds
# that short-circuit before Blender execution.
STAGE_ORDER = [
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
]

# Budget headroom: current measurement * factor = budget. >factor is a
# regression. 1.2 == 20% headroom (Wave 4.IV.f scope; Wave 5 may tune).
BUDGET_HEADROOM = 1.2


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _run_build(hero: Hero, out_root: Path) -> Dict[str, Any]:
    """Run the build CLI for ``hero``. Returns the parsed build_report.json."""
    out_dir = out_root / hero.asset_name
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "lathe.cli",
        "build",
        str(hero.source_path),
        hero.asset_name,
        "--out",
        str(out_root),
    ]
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise RuntimeError(f"lathe build failed for {hero.asset_name} (exit {proc.returncode})")
    report_path = out_dir / "build_report.json"
    if not report_path.exists():
        raise RuntimeError(f"build_report.json missing for {hero.asset_name}")
    return json.loads(report_path.read_text(encoding="utf-8"))


def _stage_bundle_paths(out_dir: Path) -> Dict[str, Path]:
    """Map stage name -> bundle path (or report.json for validate)."""
    base = out_dir / "stages"
    paths: Dict[str, Path] = {}
    for stage in STAGE_ORDER:
        if stage == "validate":
            p = base / stage / "report.json"
        else:
            p = base / stage / "bundle.json"
        if p.exists():
            paths[stage] = p
    return paths


def _per_stage_timings(report: Dict[str, Any], out_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Recover per-stage elapsed_ms.

    Prefers ``report["stages"][<stage>]["elapsed_ms"]`` if BL-33/BL-36 wired
    it; otherwise computes coarse mtime deltas between consecutive stage
    bundles and tags ``source="mtime_delta"``.
    """
    out: Dict[str, Dict[str, Any]] = {}
    structured = report.get("stages") if isinstance(report.get("stages"), dict) else None

    bundle_paths = _stage_bundle_paths(out_dir)
    # mtime fallback: order stages by their bundle mtime; first-stage
    # delta is undefined so we attribute (mtime[shape] - build start) =
    # report["build_started_ts"] if present, else 0 (recorded as None).
    mtimes: List[tuple[str, float]] = sorted(
        [(s, p.stat().st_mtime) for s, p in bundle_paths.items()],
        key=lambda t: t[1],
    )
    deltas: Dict[str, float] = {}
    for i, (stage, mt) in enumerate(mtimes):
        if i == 0:
            # No prior bundle; we mark this as the "first stage delta unknown" case.
            deltas[stage] = float("nan")
        else:
            deltas[stage] = max(0.0, (mt - mtimes[i - 1][1]) * 1000.0)

    for stage in STAGE_ORDER:
        if structured and stage in structured and isinstance(structured[stage], dict) and "elapsed_ms" in structured[stage]:
            out[stage] = {
                "current_ms": float(structured[stage]["elapsed_ms"]),
                "source": "build_report",
            }
            continue
        if stage in deltas:
            d = deltas[stage]
            if d != d:  # NaN: first-stage, unknown
                out[stage] = {"current_ms": None, "source": "mtime_delta_first_stage_unknown"}
            else:
                out[stage] = {"current_ms": round(d, 2), "source": "mtime_delta"}
        else:
            out[stage] = {"current_ms": None, "source": "stage_not_present"}
    return out


def _budgetize(stage_timings: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Attach a ``budget_ms`` field = current_ms * BUDGET_HEADROOM."""
    out: Dict[str, Dict[str, Any]] = {}
    for stage, info in stage_timings.items():
        cur = info.get("current_ms")
        budget = round(cur * BUDGET_HEADROOM, 2) if isinstance(cur, (int, float)) and cur is not None else None
        out[stage] = {**info, "budget_ms": budget}
    return out


def _profile_hero(hero: Hero, out_root: Path) -> Dict[str, Any]:
    t0 = time.perf_counter()
    report = _run_build(hero, out_root)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    out_dir = out_root / hero.asset_name
    timings = _per_stage_timings(report, out_dir)
    return {
        "wall_ms": round(wall_ms, 2),
        "stages": _budgetize(timings),
        "score": report.get("score"),
        "threshold": report.get("threshold"),
        "certified": report.get("certified"),
    }


def _load_existing_budgets() -> Dict[str, Any]:
    if not BUDGETS_PATH.exists():
        return {"heroes": {}}
    return json.loads(BUDGETS_PATH.read_text(encoding="utf-8"))


def _load_manifest() -> Optional[Dict[str, Any]]:
    """Load the hand-authored ``perf/manifest.json`` if present (PERF-4)."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _manifest_rows(hero_name: str, current: Dict[str, Any], manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute pass/warn/fail rows for ``hero_name`` against the manifest.

    A row has: {stage, current_ms, ms_max, status}. status is one of:
      - "pass": current_ms <= ms_max
      - "warn": current_ms > 0.9 * ms_max but <= ms_max (heads-up; still passes)
      - "fail": current_ms > ms_max
      - "skip": no budget or no measurement for this stage
    A synthetic row for "__total__" against total_ms_max is included.
    """
    rows: List[Dict[str, Any]] = []
    hero_entry = manifest.get("heroes", {}).get(hero_name)
    if not hero_entry:
        rows.append({
            "stage": "__hero__",
            "current_ms": None,
            "ms_max": None,
            "status": "skip",
            "reason": f"hero {hero_name!r} not listed in perf/manifest.json",
        })
        return rows

    stage_budgets = hero_entry.get("stages", {}) or {}
    for stage in STAGE_ORDER:
        info = current.get("stages", {}).get(stage) or {}
        cur = info.get("current_ms")
        budget_entry = stage_budgets.get(stage) or {}
        ms_max = budget_entry.get("ms_max")
        if cur is None or ms_max is None:
            rows.append({
                "stage": stage,
                "current_ms": cur,
                "ms_max": ms_max,
                "status": "skip",
            })
            continue
        if cur > ms_max:
            status = "fail"
        elif cur > 0.9 * ms_max:
            status = "warn"
        else:
            status = "pass"
        rows.append({
            "stage": stage,
            "current_ms": cur,
            "ms_max": ms_max,
            "status": status,
        })

    total_max = hero_entry.get("total_ms_max")
    wall_ms = current.get("wall_ms")
    if isinstance(total_max, (int, float)) and isinstance(wall_ms, (int, float)):
        if wall_ms > total_max:
            tstatus = "fail"
        elif wall_ms > 0.9 * total_max:
            tstatus = "warn"
        else:
            tstatus = "pass"
        rows.append({
            "stage": "__total__",
            "current_ms": wall_ms,
            "ms_max": total_max,
            "status": tstatus,
        })
    return rows


def _print_rows(hero_name: str, rows: List[Dict[str, Any]], stream=sys.stderr) -> None:
    """Print a short per-hero per-stage table to ``stream``."""
    print(f"[{hero_name}]", file=stream)
    for row in rows:
        stage = row["stage"]
        cur = row["current_ms"]
        ms_max = row["ms_max"]
        status = row["status"]
        cur_s = f"{cur:>10.2f}" if isinstance(cur, (int, float)) else f"{'--':>10}"
        max_s = f"{ms_max:>10.2f}" if isinstance(ms_max, (int, float)) else f"{'--':>10}"
        tag = f"[{status.upper():<4}]"
        print(f"  {tag} {stage:<12} {cur_s} ms / {max_s} ms", file=stream)


def _verify(hero_name: str, current: Dict[str, Any], budgets: Dict[str, Any]) -> List[str]:
    """Return a list of regression messages for ``hero_name``.

    Legacy verifier (BL-43) — still supported for back-compat with
    inferred ``budgets.json``. Prefer ``_manifest_rows`` for PERF-4.
    """
    msgs: List[str] = []
    hero_budget = budgets.get("heroes", {}).get(hero_name)
    if not hero_budget:
        msgs.append(f"{hero_name}: no recorded budget — run --write to baseline")
        return msgs
    for stage, info in current["stages"].items():
        cur = info.get("current_ms")
        budget = hero_budget.get("stages", {}).get(stage, {}).get("budget_ms")
        if cur is None or budget is None:
            continue
        if cur > budget:
            msgs.append(
                f"{hero_name}.{stage}: current {cur}ms > budget {budget}ms "
                f"({(cur / budget - 1) * 100:.1f}% over)"
            )
    return msgs


def _heroes_filtered(only: Optional[str]) -> List[Hero]:
    if only:
        matching = [h for h in HEROES if h.asset_name == only]
        if not matching:
            raise SystemExit(f"--only {only!r} matches no hero. Known: {[h.asset_name for h in HEROES]}")
        return matching
    return list(HEROES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--write", action="store_true", help="Refresh budgets.json from current measurements (default if no other mode)")
    parser.add_argument("--verify", action="store_true", help="Compare current run against existing budgets.json; fail on regression > 20%%")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        default=True,
        help="Exit non-zero when --verify detects a regression (default: true). Pair with --no-fail-on-regression to make --verify report-only.",
    )
    parser.add_argument(
        "--no-fail-on-regression",
        dest="fail_on_regression",
        action="store_false",
        help="When set, --verify prints regressions but exits 0 (report-only mode).",
    )
    parser.add_argument("--only", type=str, default=None, help="Restrict to a single hero by name")
    parser.add_argument("--out-root", type=Path, default=TMP_OUT_ROOT, help="Where to write transient build outputs (default: tmp_profile/)")
    parser.add_argument(
        "--manifest",
        action="store_true",
        help=(
            "PERF-4 (V0.2, Wave 6.VI): verify against hand-authored "
            "perf/manifest.json budgets (ms_max) instead of inferred "
            "perf/budgets.json. Emits per-hero per-stage pass/warn/fail "
            "rows and exits non-zero on any 'fail'."
        ),
    )
    args = parser.parse_args()

    if not args.verify and not args.manifest:
        args.write = True  # default

    PERF_DIR.mkdir(parents=True, exist_ok=True)
    args.out_root.mkdir(parents=True, exist_ok=True)

    heroes = _heroes_filtered(args.only)
    print(f"profile_heroes: profiling {len(heroes)} hero(s)", file=sys.stderr)

    measurements: Dict[str, Dict[str, Any]] = {}
    for hero in heroes:
        print(f"  -> {hero.asset_name}", file=sys.stderr)
        measurements[hero.asset_name] = _profile_hero(hero, args.out_root)

    if args.manifest:
        manifest = _load_manifest()
        if manifest is None:
            print(
                f"perf/manifest.json not found at {MANIFEST_PATH} — create it (PERF-4) before running --manifest",
                file=sys.stderr,
            )
            return 2
        any_fail = False
        for name, m in measurements.items():
            rows = _manifest_rows(name, m, manifest)
            _print_rows(name, rows)
            if any(r.get("status") == "fail" for r in rows):
                any_fail = True
        if any_fail and args.fail_on_regression:
            print("PERF-4: one or more stages over ms_max.", file=sys.stderr)
            return 2
        if any_fail:
            print("(--no-fail-on-regression set; exiting 0 despite fails)", file=sys.stderr)
            return 0
        print("PERF-4: all stages within manifest budgets.", file=sys.stderr)
        return 0

    if args.verify:
        existing = _load_existing_budgets()
        regressions: List[str] = []
        for name, m in measurements.items():
            regressions.extend(_verify(name, m, existing))
        if regressions:
            print("REGRESSIONS DETECTED:", file=sys.stderr)
            for msg in regressions:
                print(f"  - {msg}", file=sys.stderr)
            if args.fail_on_regression:
                return 2
            print("(--no-fail-on-regression set; exiting 0 despite regressions)", file=sys.stderr)
            return 0
        print("All stages within budget.", file=sys.stderr)
        return 0

    # --write path: merge with existing budgets so a single-hero run does
    # not nuke other heroes' baselines.
    budgets = _load_existing_budgets()
    budgets.setdefault("heroes", {})
    for name, m in measurements.items():
        budgets["heroes"][name] = m
    budgets["budget_headroom"] = BUDGET_HEADROOM
    budgets["updated_utc"] = datetime.now(timezone.utc).isoformat()
    BUDGETS_PATH.write_text(json.dumps(budgets, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BUDGETS_PATH}", file=sys.stderr)

    # Historical record
    hist_path = PERF_DIR / f"heroes_{_utc_today()}.json"
    hist_path.write_text(
        json.dumps({"heroes": measurements, "recorded_utc": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {hist_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
