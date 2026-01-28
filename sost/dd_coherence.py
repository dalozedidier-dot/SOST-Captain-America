"""sost.dd_coherence

DD (Descriptive Differences).

This is a deliberately *non-normative* implementation meant to make the
framework operational and produce stable, machine-readable reports.

What it does:
- reads a univariate time series
- splits it into two windows (pre/post)
- computes simple descriptive statistics
- emits a DD report describing differences and invariants

What it does NOT do:
- claim causality
- predict
- judge usefulness or "quality" of the data
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class WindowStats:
    n: int
    mean: float
    std: float
    min: float
    max: float


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float], mean: float) -> float:
    if len(xs) < 2:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


def _stats(xs: Sequence[float]) -> WindowStats:
    if not xs:
        return WindowStats(n=0, mean=0.0, std=0.0, min=0.0, max=0.0)
    m = _mean(xs)
    return WindowStats(
        n=len(xs),
        mean=float(m),
        std=float(_std(xs, m)),
        min=float(min(xs)),
        max=float(max(xs)),
    )


def compute_dd(
    values: Sequence[float],
    split_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute DD report (structure-first).

    Parameters
    - values: univariate series
    - split_index: index separating pre/post windows. If None, uses midpoint.

    Returns
    - dict serializable to JSON
    """
    n = len(values)
    if n == 0:
        return {
            "version": "0.1",
            "windowing": {"split_index": 0, "n": 0},
            "pre": {"stats": asdict(_stats([]))},
            "post": {"stats": asdict(_stats([]))},
            "differences": [],
            "invariants": [],
            "warnings": ["empty_series"],
        }

    if split_index is None:
        split_index = n // 2
    split_index = max(1, min(n - 1, int(split_index)))

    pre = list(map(float, values[:split_index]))
    post = list(map(float, values[split_index:]))

    pre_stats = _stats(pre)
    post_stats = _stats(post)

    diffs: List[Dict[str, Any]] = [
        {
            "metric": "mean",
            "pre": pre_stats.mean,
            "post": post_stats.mean,
            "delta": post_stats.mean - pre_stats.mean,
        },
        {
            "metric": "std",
            "pre": pre_stats.std,
            "post": post_stats.std,
            "delta": post_stats.std - pre_stats.std,
        },
        {
            "metric": "min",
            "pre": pre_stats.min,
            "post": post_stats.min,
            "delta": post_stats.min - pre_stats.min,
        },
        {
            "metric": "max",
            "pre": pre_stats.max,
            "post": post_stats.max,
            "delta": post_stats.max - pre_stats.max,
        },
    ]

    invariants: List[Dict[str, Any]] = [
        {"name": "monotonic_time_assumed", "value": True},
        {"name": "univariate_series", "value": True},
    ]

    warnings: List[str] = []
    if pre_stats.n < 3 or post_stats.n < 3:
        warnings.append("small_window")

    return {
        "version": "0.1",
        "windowing": {"split_index": split_index, "n": n},
        "pre": {"stats": asdict(pre_stats)},
        "post": {"stats": asdict(post_stats)},
        "differences": diffs,
        "invariants": invariants,
        "warnings": warnings,
    }
