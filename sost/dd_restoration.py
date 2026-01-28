"""sost.dd_restoration

DD-R (Descriptive Differences – Relative).

Consumes a DD report and produces a relative view of the same differences.
Still descriptive-only: no causal inference, no prediction, no normative
"good/bad" judgement.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _rel_delta(pre: float, post: float) -> float:
    denom = abs(pre) if pre != 0 else 1.0
    return (post - pre) / denom


def compute_ddr(dd_report: Dict[str, Any]) -> Dict[str, Any]:
    """Compute DD-R from DD report (structure-first)."""
    diffs = dd_report.get("differences") or []

    rel: List[Dict[str, Any]] = []
    for d in diffs:
        try:
            pre = float(d.get("pre"))
            post = float(d.get("post"))
            rel.append(
                {
                    "metric": d.get("metric"),
                    "pre": pre,
                    "post": post,
                    "rel_delta": _rel_delta(pre, post),
                }
            )
        except Exception:
            continue

    # A purely descriptive "class" label, based on magnitude only.
    # This is not a quality judgement, just a bucket to make outputs readable.
    buckets = {"small": [], "medium": [], "large": []}
    for item in rel:
        r = abs(item["rel_delta"])
        if r < 0.05:
            buckets["small"].append(item["metric"])
        elif r < 0.25:
            buckets["medium"].append(item["metric"])
        else:
            buckets["large"].append(item["metric"])

    return {
        "version": "0.1",
        "dd_ref": {"version": dd_report.get("version"), "windowing": dd_report.get("windowing")},
        "relative_differences": rel,
        "buckets": buckets,
        "warnings": dd_report.get("warnings") or [],
    }
