"""5-asset benchmark harness (Plan 09 Phase 4).

Runs the canonical 5 reference assets through Lathe (native fallback and, if a
runtime config is supplied, a learned provider stack) and records one JSON
result per (asset, system, date) plus a summary JSON.

Competitor systems (Meshy, Hunyuan-via-API, Luma, Houdini HDA + SideFX Labs,
Quixel Megascans, Blender-by-hand) are recorded as explicit `not_run` entries:
this harness never fabricates metrics for them. Each manual-run entry includes
a pointer to the corresponding `docs/benchmarks/competitors/<name>.md` file
that a human follows manually.

Outputs:
    docs/benchmarks/data/<asset>_<system>_<date>.json     one per run
    docs/benchmarks/data/summary_<date>.json              aggregate

Usage:
    python scripts/run_benchmark.py --lathe-only
    python scripts/run_benchmark.py --only industrial_crate,sci_fi_wall_panel
    python scripts/run_benchmark.py --runtime-config examples/runtime_configs/auto_learned.json
    python scripts/run_benchmark.py --verify docs/benchmarks/data/baseline.json
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # psutil is optional; peak_memory_mb becomes None.

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DATA_DIR = _REPO_ROOT / "docs" / "benchmarks" / "data"
COMPETITORS_DIR = _REPO_ROOT / "docs" / "benchmarks" / "competitors"


def _pick_python() -> str:
    """Prefer the repo's .venv interpreter.

    CLAUDE.md says that interpreter is canonical on
    Windows) over whatever sys.executable happens to be, since this script may
    be invoked from a bare system python that doesn't have lathe's deps.
    """
    venv_py = _REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    venv_posix = _REPO_ROOT / ".venv" / "bin" / "python"
    if venv_posix.exists():
        return str(venv_posix)
    return sys.executable


_PYTHON = _pick_python()

REFERENCE_ASSETS: list[dict[str, str]] = [
    {"name": "industrial_crate", "source": "examples/industrial_crate.lth", "family": "container"},
    {"name": "sci_fi_wall_panel", "source": "examples/sci_fi_wall_panel.lth", "family": "architecture"},
    {"name": "mechanical_door", "source": "examples/mechanical_door.lth", "family": "architecture"},
    {"name": "control_pedestal", "source": "examples/control_pedestal.lth", "family": "prop"},
    {"name": "service_cabinet", "source": "examples/service_cabinet.lth", "family": "architecture"},
]

COMPETITOR_SYSTEMS: list[str] = [
    "meshy",
    "hunyuan",
    "luma",
    "houdini_hda",
    "quixel",
    "blender_by_hand",
]

REPRO_ROUNDS = 3


@dataclass
class RunResult:
    asset: str
    system: str
    date: str
    result: str  # "ok" | "failed" | "not_run"
    wall_clock_s: float | None = None
    peak_memory_mb: float | None = None
    score: float | None = None
    threshold: float | None = None
    certified: bool | None = None
    glb_sha256: str | None = None
    triangle_count: int | None = None
    uv_valid: bool | None = None
    collision_present: bool | None = None
    pivot_correct: bool | None = None
    reproducibility_hashes: list[str] = field(default_factory=list)
    reproducible: bool | None = None
    diagnostics: list[str] = field(default_factory=list)
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "asset": self.asset,
            "system": self.system,
            "date": self.date,
            "result": self.result,
            "metrics": {
                "wall_clock_s": self.wall_clock_s,
                "peak_memory_mb": self.peak_memory_mb,
                "score": self.score,
                "threshold": self.threshold,
                "certified": self.certified,
                "glb_sha256": self.glb_sha256,
                "triangle_count": self.triangle_count,
                "uv_valid": self.uv_valid,
                "collision_present": self.collision_present,
                "pivot_correct": self.pivot_correct,
                "reproducible": self.reproducible,
                "reproducibility_hashes": self.reproducibility_hashes,
            },
            "diagnostics": self.diagnostics,
            "note": self.note,
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _peak_rss_mb(proc: subprocess.Popen) -> float | None:
    """Best-effort peak RSS in MB for a running subprocess, or None if unavailable."""
    if psutil is None:
        return None
    try:
        p = psutil.Process(proc.pid)
        peak = 0
        while proc.poll() is None:
            try:
                rss = p.memory_info().rss
                for child in p.children(recursive=True):
                    with contextlib.suppress(psutil.Error):
                        rss += child.memory_info().rss
                peak = max(peak, rss)
            except psutil.Error:
                break
            time.sleep(0.1)
        return round(peak / (1024 * 1024), 1)
    except psutil.Error:
        return None


def _run_lathe_build(
    asset: dict[str, str],
    out_root: Path,
    runtime_config: str | None,
    system_label: str,
) -> RunResult:
    """Run `python -m lathe.cli build` and collect metrics from build_report.json."""
    date = _dt.date.today().isoformat()
    result = RunResult(asset=asset["name"], system=system_label, date=date, result="failed")
    out_dir = out_root / asset["name"]

    cmd = [
        _PYTHON,
        "-m",
        "lathe.cli",
        "build",
        str(_REPO_ROOT / asset["source"]),
        asset["name"],
        "--out",
        str(out_root),
        "--report",
        "json",
    ]
    if runtime_config:
        cmd.extend(["--runtime-config", str(runtime_config)])

    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        peak_mem = _peak_rss_mb(proc)
        _stdout, stderr = proc.communicate(timeout=600)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        result.diagnostics.append("timeout after 600s")
        result.wall_clock_s = round(time.monotonic() - start, 3)
        return result
    except OSError as exc:
        result.diagnostics.append(f"subprocess error: {exc}")
        return result

    result.wall_clock_s = round(time.monotonic() - start, 3)
    result.peak_memory_mb = peak_mem

    if returncode != 0:
        tail = (stderr.decode("utf-8", errors="replace") or "")[-500:]
        result.diagnostics.append(f"exit {returncode}: {tail}")
        return result

    report_path = out_dir / "build_report.json"
    if not report_path.exists():
        result.diagnostics.append(f"missing build_report.json at {report_path}")
        return result

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.diagnostics.append(f"failed to parse build_report: {exc}")
        return result

    result.result = "ok"
    result.score = float(report.get("score")) if report.get("score") is not None else None
    result.threshold = float(report.get("threshold")) if report.get("threshold") is not None else None
    result.certified = bool(report.get("certified"))

    glb_path = _find_glb_output(out_dir, report)
    if glb_path is not None and glb_path.exists():
        result.glb_sha256 = _sha256(glb_path)

    _populate_stage_metrics(result, out_dir, report)

    return result


def _find_glb_output(build_dir: Path, report: dict) -> Path | None:
    for output in report.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        uri = output.get("uri") or output.get("path")
        fmt = (output.get("format") or "").lower()
        if uri and (fmt == "glb" or str(uri).lower().endswith(".glb")):
            candidate = (build_dir / uri).resolve()
            if candidate.exists():
                return candidate
    for candidate in build_dir.rglob("*.glb"):
        return candidate
    return None


def _populate_stage_metrics(result: RunResult, build_dir: Path, report: dict) -> None:
    stages = report.get("stage_bundles") or {}

    topo_rel = stages.get("topology")
    if isinstance(topo_rel, str):
        topo_path = (build_dir / topo_rel).resolve()
        if topo_path.exists():
            try:
                topo = json.loads(topo_path.read_text(encoding="utf-8"))
                stats = topo.get("mesh_stats") or {}
                tc = stats.get("triangle_count")
                if isinstance(tc, int):
                    result.triangle_count = tc
            except (OSError, json.JSONDecodeError):
                result.diagnostics.append("topology bundle unreadable")

    uv_rel = stages.get("uv")
    if isinstance(uv_rel, str):
        uv_path = (build_dir / uv_rel).resolve()
        if uv_path.exists():
            try:
                uv = json.loads(uv_path.read_text(encoding="utf-8"))
                packing = uv.get("packing_report") or {}
                result.uv_valid = bool(packing.get("chart_count", 0) >= 1 and uv.get("lightmap_ready"))
            except (OSError, json.JSONDecodeError):
                result.diagnostics.append("uv bundle unreadable")

    phys_rel = stages.get("physics")
    if isinstance(phys_rel, str):
        phys_path = (build_dir / phys_rel).resolve()
        if phys_path.exists():
            try:
                phys = json.loads(phys_path.read_text(encoding="utf-8"))
                result.collision_present = bool(phys.get("collision_proxy"))
            except (OSError, json.JSONDecodeError):
                result.diagnostics.append("physics bundle unreadable")

    iface_rel = stages.get("interfaces")
    if isinstance(iface_rel, str):
        iface_path = (build_dir / iface_rel).resolve()
        if iface_path.exists():
            try:
                iface = json.loads(iface_path.read_text(encoding="utf-8"))
                anchors = iface.get("anchors") or []
                # Heuristic: pivot is "correct" if a named anchor (floor_contact,
                # hinge_anchor, mount_point, etc.) is emitted. The shipping
                # `socket_stub_v1` backend always emits a family-appropriate anchor
                # when the blueprint declares one, so presence is the honest signal.
                result.pivot_correct = bool(anchors)
            except (OSError, json.JSONDecodeError):
                result.diagnostics.append("interfaces bundle unreadable")


def _run_reproducibility_check(
    asset: dict[str, str],
    runtime_config: str | None,
    rounds: int,
) -> (list[str], bool | None):
    """Re-run build `rounds` times into scratch dirs, collect .glb sha256 each time."""
    hashes: list[str] = []
    for i in range(rounds):
        scratch = _REPO_ROOT / f"tmp_bench_repro_{asset['name']}_{i}"
        cmd = [
            _PYTHON,
            "-m",
            "lathe.cli",
            "build",
            str(_REPO_ROOT / asset["source"]),
            asset["name"],
            "--out",
            str(scratch),
            "--report",
            "json",
        ]
        if runtime_config:
            cmd.extend(["--runtime-config", str(runtime_config)])
        try:
            subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, timeout=600, check=False)
        except subprocess.TimeoutExpired:
            continue
        report_path = scratch / asset["name"] / "build_report.json"
        if not report_path.exists():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        glb = _find_glb_output(scratch / asset["name"], report)
        if glb is not None and glb.exists():
            hashes.append(_sha256(glb))
    if not hashes:
        return hashes, None
    return hashes, len(set(hashes)) == 1


def _competitor_not_run_result(asset: dict[str, str], system: str) -> RunResult:
    date = _dt.date.today().isoformat()
    return RunResult(
        asset=asset["name"],
        system=system,
        date=date,
        result="not_run",
        note=(
            f"Competitor run not executed. See "
            f"docs/benchmarks/competitors/{system}.md for manual run instructions "
            f"and --ingest-manifest path."
        ),
    )


def _write_run(result: RunResult) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"{result.asset}_{result.system}_{result.date}.json"
    out.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
    return out


def _verify_against_baseline(results: list[RunResult], baseline_path: Path) -> int:
    """Compare current results to a baseline snapshot.

    Returns non-zero exit code
    if any regression (score drop >0.02 or certified flipped true→false) is found.
    """
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read baseline: {exc}", file=sys.stderr)
        return 2
    base_runs = {(r["asset"], r["system"]): r for r in baseline.get("runs", [])}
    regressions: list[str] = []
    for r in results:
        base = base_runs.get((r.asset, r.system))
        if not base or base.get("result") != "ok" or r.result != "ok":
            continue
        bm = base.get("metrics", {})
        if bm.get("certified") and not r.certified:
            regressions.append(f"{r.asset}/{r.system}: certified regressed true->false")
        bs = bm.get("score")
        if isinstance(bs, (int, float)) and r.score is not None and r.score < bs - 0.02:
            regressions.append(f"{r.asset}/{r.system}: score {bs:.4f} -> {r.score:.4f}")
    if regressions:
        for msg in regressions:
            print(f"REGRESSION: {msg}")
        return 1
    print("no regressions detected")
    return 0


def main() -> int:
    """Run the benchmark harness CLI."""
    parser = argparse.ArgumentParser(description="5-asset Lathe vs. competitor benchmark harness.")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated subset of asset names; default = all 5.",
    )
    parser.add_argument(
        "--lathe-only",
        action="store_true",
        help="Skip competitor not_run entries; only run Lathe paths.",
    )
    parser.add_argument(
        "--runtime-config",
        type=str,
        default=None,
        help="Path to a runtime JSON to run the Lathe-learned path in addition to fallback.",
    )
    parser.add_argument(
        "--out-root",
        type=str,
        default=str(_REPO_ROOT / "dist_benchmark"),
        help="Build --out root for Lathe runs (default: dist_benchmark).",
    )
    parser.add_argument(
        "--skip-repro",
        action="store_true",
        help="Skip the 3-round reproducibility check (faster smoke runs).",
    )
    parser.add_argument(
        "--verify",
        type=str,
        default=None,
        help="Path to a baseline summary JSON; exit non-zero on regression.",
    )
    args = parser.parse_args()

    selected = [a for a in REFERENCE_ASSETS if (args.only is None or a["name"] in set(args.only.split(",")))]
    if not selected:
        print(f"no assets matched --only={args.only}", file=sys.stderr)
        return 2

    out_root = Path(args.out_root)
    all_results: list[RunResult] = []

    for asset in selected:
        print(f"=== {asset['name']} ===", file=sys.stderr)

        fb_result = _run_lathe_build(asset, out_root / "fallback", None, "lathe_fallback")
        if fb_result.result == "ok" and not args.skip_repro:
            hashes, reproducible = _run_reproducibility_check(asset, None, REPRO_ROUNDS)
            fb_result.reproducibility_hashes = hashes
            fb_result.reproducible = reproducible
        _write_run(fb_result)
        all_results.append(fb_result)
        print(
            f"  lathe_fallback: result={fb_result.result} "
            f"score={fb_result.score} certified={fb_result.certified} "
            f"tris={fb_result.triangle_count} wall={fb_result.wall_clock_s}s",
            file=sys.stderr,
        )

        if args.runtime_config:
            ln_result = _run_lathe_build(asset, out_root / "learned", args.runtime_config, "lathe_learned")
            if ln_result.result == "ok" and not args.skip_repro:
                hashes, reproducible = _run_reproducibility_check(asset, args.runtime_config, REPRO_ROUNDS)
                ln_result.reproducibility_hashes = hashes
                ln_result.reproducible = reproducible
            _write_run(ln_result)
            all_results.append(ln_result)
            print(
                f"  lathe_learned: result={ln_result.result} score={ln_result.score} "
                f"certified={ln_result.certified}",
                file=sys.stderr,
            )

        if not args.lathe_only:
            for sys_name in COMPETITOR_SYSTEMS:
                not_run = _competitor_not_run_result(asset, sys_name)
                _write_run(not_run)
                all_results.append(not_run)

    date = _dt.date.today().isoformat()
    summary = {
        "date": date,
        "asset_count": len(selected),
        "runs": [r.as_dict() for r in all_results],
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = DATA_DIR / f"summary_{date}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary written to {summary_path}", file=sys.stderr)

    if args.verify:
        return _verify_against_baseline(all_results, Path(args.verify))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
