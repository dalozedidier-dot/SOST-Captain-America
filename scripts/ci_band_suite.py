from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def run_capture(cmd: List[str], cwd: Path, env: Dict[str, str]) -> Tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p.returncode, p.stdout


def read_help(script: Path, repo: Path, env: Dict[str, str]) -> str:
    rc, out = run_capture([sys.executable, str(script), "--help"], cwd=repo, env=env)
    if out:
        return out
    return ""


def pick_flags(help_text: str) -> Tuple[Optional[str], Optional[str]]:
    # input flag
    input_flag = None
    for cand in ["--input-csv", "--input_csv", "--input", "-i"]:
        if cand in help_text:
            input_flag = cand
            break

    # outdir flag
    outdir_flag = None
    for cand in ["--outdir", "--out-dir", "--output-dir", "-o"]:
        if cand in help_text:
            outdir_flag = cand
            break

    return input_flag, outdir_flag


@dataclass
class BandResult:
    band: str
    csv: str
    rc: int
    outdir: str
    reports: Dict[str, Dict[str, str]]
    log_file: str


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="test_data/band_*.csv", help="Glob de CSV à tester")
    ap.add_argument("--outdir", default="_ci_out", help="Répertoire CI de sortie")
    args = ap.parse_args()

    repo = Path(".").resolve()
    outdir = (repo / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    run_sost = repo / "scripts" / "run_sost.py"
    if not run_sost.exists():
        (outdir / "band_suite_failures.txt").write_text(
            "Missing scripts/run_sost.py\n", encoding="utf-8"
        )
        print("Missing scripts/run_sost.py")
        return 2

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    help_text = read_help(run_sost, repo, env)
    input_flag, outdir_flag = pick_flags(help_text)

    csv_files = sorted(repo.glob(args.pattern))
    if not csv_files:
        (outdir / "band_suite_failures.txt").write_text(
            f"No CSV matched pattern: {args.pattern}\n", encoding="utf-8"
        )
        print(f"No CSV matched pattern: {args.pattern}")
        return 2

    results: List[BandResult] = []
    failures: List[str] = []

    for csv_path in csv_files:
        band = csv_path.stem
        band_out = outdir / f"sost_out_{band}"
        band_out.mkdir(parents=True, exist_ok=True)

        cmd = [sys.executable, str(run_sost)]
        if input_flag:
            cmd += [input_flag, str(csv_path)]
        else:
            cmd += [str(csv_path)]

        if outdir_flag:
            cmd += [outdir_flag, str(band_out)]

        rc, log = run_capture(cmd, cwd=repo, env=env)

        log_file = outdir / f"{band}.log"
        log_file.write_text(log, encoding="utf-8")

        reports: Dict[str, Dict[str, str]] = {}
        for name in ["dd_report.json", "ddr_report.json", "e_report.json"]:
            p = band_out / name
            if p.exists():
                reports[name] = {"path": str(p), "sha256": sha256_file(p)}

        results.append(
            BandResult(
                band=band,
                csv=str(csv_path),
                rc=rc,
                outdir=str(band_out),
                reports=reports,
                log_file=str(log_file),
            )
        )

        if rc != 0:
            failures.append(f"{band} rc={rc} csv={csv_path}")

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pattern": args.pattern,
        "total": len(results),
        "ok": sum(1 for r in results if r.rc == 0),
        "failed": sum(1 for r in results if r.rc != 0),
        "bands": [r.__dict__ for r in results],
        "run_sost_help_detect": {"input_flag": input_flag, "outdir_flag": outdir_flag},
    }

    (outdir / "band_suite_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if failures:
        (outdir / "band_suite_failures.txt").write_text(
            "\n".join(failures) + "\n", encoding="utf-8"
        )
        print("Band suite FAILED:")
        print("\n".join(failures))
        return 1

    print(f"Band suite OK: {summary['ok']}/{summary['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
