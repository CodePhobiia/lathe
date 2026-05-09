"""Diff two validate report.json files side-by-side."""
import json
import sys
from pathlib import Path


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix] = float(obj)
    return out


def main(baseline_path: str, current_path: str) -> None:
    baseline = flatten(json.loads(Path(baseline_path).read_text()))
    current = flatten(json.loads(Path(current_path).read_text()))

    print(f"baseline: {baseline_path}")
    print(f"current:  {current_path}")
    print()

    keys = set(baseline) | set(current)
    rows = []
    for k in keys:
        b = baseline.get(k)
        c = current.get(k)
        if b is None or c is None:
            continue
        delta = c - b
        rows.append((k, b, c, delta))
    rows.sort(key=lambda r: abs(r[3]), reverse=True)

    print(f"{'metric':<70} {'baseline':>12} {'current':>12} {'delta':>12}")
    print("-" * 110)
    for k, b, c, d in rows:
        if abs(d) < 0.005:
            continue
        marker = " ↑" if d > 0 else " ↓"
        print(f"{k:<70} {b:>12.4f} {c:>12.4f} {d:>+12.4f}{marker}")

    print()
    print("=== headline ===")
    for k in ("score", "threshold", "certified"):
        b = baseline.get(k) if k != "certified" else None
        c = current.get(k) if k != "certified" else None
        if b is not None or c is not None:
            print(f"  {k}: baseline={b} current={c}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
