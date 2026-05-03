"""Silhouette validator.

Runs render-level silhouette checks to ensure the built asset
matches the intended silhouette envelope.
"""

from __future__ import annotations

from typing import Any


def _ratio_signature(extents: list[float]) -> list[float]:
    if not extents:
        return []
    largest = max(1e-06, *extents)
    return [float(value) / largest for value in extents]


def _profile_bins(values: list[float]) -> list[float]:
    if not values:
        return [0.0, 0.0, 0.0]
    lo = min(values)
    hi = max(values)
    span = max(1e-6, hi - lo)
    bins = [0.0, 0.0, 0.0]
    for value in values:
        normalized = (value - lo) / span
        index = max(0, min(2, int(normalized * 3.0)))
        bins[index] += 1.0
    total = max(1.0, sum(bins))
    return [item / total for item in bins]


def compare_scaffold_signature(
    scaffold_signature: dict[str, Any],
    actual_extents: list[float],
    part_groups: list[dict[str, Any]] | None = None,
) -> float:
    """Compare scaffold signature.

    Args:
        scaffold_signature: scaffold_signature argument.
        actual_extents: actual_extents argument.
        part_groups: part_groups argument.

    Returns:
        The result.
    """
    expected_ratio = scaffold_signature.get("projected_ratio")
    if not expected_ratio:
        return 0.5
    actual_ratio = _ratio_signature(actual_extents)
    diff = sum(abs(left - right) for left, right in zip(expected_ratio, actual_ratio, strict=False)) / max(
        1, len(expected_ratio)
    )
    ratio_score = max(0.0, min(1.0, 1.0 - diff / 0.45))
    if not part_groups:
        return round(ratio_score, 6)

    centers = [
        (
            (group["bounds_min"][0] + group["bounds_max"][0]) / 2.0,
            (group["bounds_min"][1] + group["bounds_max"][1]) / 2.0,
            (group["bounds_min"][2] + group["bounds_max"][2]) / 2.0,
        )
        for group in part_groups
    ]
    region_spread = scaffold_signature.get("region_spread", [0.0, 0.0, 0.0])
    xs = [point[0] for point in centers]
    ys = [point[1] for point in centers]
    zs = [point[2] for point in centers]
    extents_largest = max(1e-06, *actual_extents) if actual_extents else 1e-06
    actual_spread = [
        (max(xs) - min(xs)) / extents_largest if xs else 0.0,
        (max(ys) - min(ys)) / extents_largest if ys else 0.0,
        (max(zs) - min(zs)) / extents_largest if zs else 0.0,
    ]
    spread_diff = sum(
        abs(left - right) for left, right in zip(region_spread, actual_spread, strict=False)
    ) / max(1, len(region_spread))
    spread_score = max(0.0, min(1.0, 1.0 - spread_diff / 0.75))

    expected_profiles = [
        scaffold_signature.get("width_profile", [0.0, 0.0, 0.0]),
        scaffold_signature.get("vertical_profile", [0.0, 0.0, 0.0]),
        scaffold_signature.get("depth_profile", [0.0, 0.0, 0.0]),
    ]
    actual_profiles = [_profile_bins(xs), _profile_bins(ys), _profile_bins(zs)]
    profile_diffs = []
    for expected, actual in zip(expected_profiles, actual_profiles, strict=False):
        profile_diffs.append(
            sum(abs(left - right) for left, right in zip(expected, actual, strict=False))
            / max(1, len(expected))
        )
    profile_score = max(
        0.0,
        min(1.0, 1.0 - (sum(profile_diffs) / max(1, len(profile_diffs))) / 0.70),
    )

    expected_regions = int(scaffold_signature.get("expected_region_count", len(part_groups)))
    region_score = min(1.0, len(part_groups) / max(1, expected_regions))
    return round(
        (0.42 * ratio_score) + (0.24 * spread_score) + (0.24 * profile_score) + (0.10 * region_score),
        6,
    )
