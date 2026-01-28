from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import List, Tuple

from sost.dd_coherence import compute_dd
from sost.dd_restoration import compute_ddr
from sost.equilibrium import compute_e


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv_series(path: Path) -> Tuple[List[str], List[float]]:
    """Read a minimal CSV time series.

Expected columns:
  - t (time)  or time
  - value     or y

Any extra columns are ignored.
"""
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")

        t_key = "t" if "t" in reader.fieldnames else ("time" if "time" in reader.fieldnames else None)
        v_key = "value" if "value" in reader.fieldnames else ("y" if "y" in reader.fieldnames else None)
        if t_key is None or v_key is None:
            raise ValueError("CSV must contain columns (t|time) and (value|y)")

        ts: List[str] = []
        vs: List[float] = []
        for row in reader:
            ts.append(str(row[t_key]))
            vs.append(float(row[v_key]))
    return ts, vs


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run SOST DD → DD-R → E (descriptive-only)")
    ap.add_argument("--input", required=True, help="CSV input (columns: t/time and value/y)")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--run-id", default=None, help="Optional run id (folder name). If omitted, uses 'run'")
    ap.add_argument("--split-index", type=int, default=None, help="Optional split index for DD windows")
    args = ap.parse_args()

    input_path = Path(args.input)
    out_root = Path(args.out)
    run_id = args.run_id or "run"
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ts, values = _read_csv_series(input_path)

    dd_dir = run_dir / "dd"
    ddr_dir = run_dir / "ddr"
    e_dir = run_dir / "e"

    dd_report = compute_dd(values, split_index=args.split_index)
    dd_report["run_id"] = run_id
    dd_report["input"] = {"path": str(input_path), "sha256": _sha256_file(input_path), "n": len(values)}
    _write_json(dd_dir / "dd_report.json", dd_report)

    ddr_report = compute_ddr(dd_report)
    ddr_report["run_id"] = run_id
    _write_json(ddr_dir / "ddr_report.json", ddr_report)

    e_report = compute_e(ddr_report)
    e_report["run_id"] = run_id
    _write_json(e_dir / "e_report.json", e_report)

    # Minimal run manifest (notarisation-lite)
    manifest = {
        "run_id": run_id,
        "input": {"path": str(input_path), "sha256": _sha256_file(input_path)},
        "artifacts": {
            "dd": "dd/dd_report.json",
            "ddr": "ddr/ddr_report.json",
            "e": "e/e_report.json",
        },
        "hashes": {
            "dd_report.json": _sha256_file(dd_dir / "dd_report.json"),
            "ddr_report.json": _sha256_file(ddr_dir / "ddr_report.json"),
            "e_report.json": _sha256_file(e_dir / "e_report.json"),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
