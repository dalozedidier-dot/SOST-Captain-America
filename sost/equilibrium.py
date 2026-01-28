"""sost.equilibrium

E (Equilibrium).

Consumes a DD-R report and emits a minimal equilibrium-oriented description.
This is intentionally lightweight and descriptive.
"""

from __future__ import annotations

from typing import Any, Dict


def compute_e(ddr_report: Dict[str, Any]) -> Dict[str, Any]:
    rel = ddr_report.get("relative_differences") or []
    magnitudes = [abs(float(it.get("rel_delta", 0.0))) for it in rel]
    if not magnitudes:
        return {
            "version": "0.1",
            "ddr_ref": {"version": ddr_report.get("version")},
            "equilibrium_state": "unknown",
            "metrics": {"pressure": 0.0, "dispersion": 0.0},
            "warnings": ["empty_relative_differences"],
        }

    pressure = sum(magnitudes) / len(magnitudes)
    mean = pressure
    dispersion = (sum((m - mean) ** 2 for m in magnitudes) / max(1, len(magnitudes) - 1)) ** 0.5

    # Non-normative state label: just partitions of pressure magnitude
    if pressure < 0.05:
        state = "meta-stable"
    elif pressure < 0.25:
        state = "drifting"
    else:
        state = "reconfiguring"

    return {
        "version": "0.1",
        "ddr_ref": {"version": ddr_report.get("version"), "dd_ref": ddr_report.get("dd_ref")},
        "equilibrium_state": state,
        "metrics": {"pressure": float(pressure), "dispersion": float(dispersion)},
        "warnings": ddr_report.get("warnings") or [],
    }
