from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd: list[str], cwd: Path, env: dict[str, str]) -> bool:
    print("\n== Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=str(cwd), env=env, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print("Command failed:", e.returncode)
        return False


def pick_first(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return sorted(paths, key=lambda p: (len(p.as_posix()), p.as_posix()))[0]


def find_artifact(root: Path, filename: str) -> Path | None:
    return pick_first(list(root.glob(f"**/{filename}")))


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def summarize(dd: Path | None, ddr: Path | None, e: Path | None) -> dict:
    out: dict = {}

    if dd and dd.exists():
        j = load_json(dd)
        out["dd_present"] = True
        out["split_index"] = (j.get("windowing", {}) or {}).get("split_index")
        out["dd_warnings"] = len(j.get("warnings", []) or [])
    else:
        out["dd_present"] = False

    if ddr and ddr.exists():
        j = load_json(ddr)
        out["ddr_present"] = True
        out["ddr_status"] = j.get("DDR") or (j.get("status", {}) or {}).get("compatibilite")
        out["ddr_warnings"] = len(j.get("warnings", []) or [])
    else:
        out["ddr_present"] = False

    if e and e.exists():
        j = load_json(e)
        out["e_present"] = True
        out["e_state"] = j.get("E") or j.get("equilibrium_state")
        out["e_warnings"] = len(j.get("warnings", []) or [])
    else:
        out["e_present"] = False

    return out


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    test_data = repo / "test_data"
    bands = sorted(test_data.glob("band_*.csv"))

    if not bands:
        print("No band_*.csv found in test_data/")
        return 2

    runner = repo / "scripts" / "run_sost.py"
    if not runner.exists():
        print("Missing scripts/run_sost.py")
        return 2

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    out_root = repo / "_ci_out_bands"
    shutil.rmtree(out_root, ignore_errors=True)
    out_root.mkdir(parents=True, exist_ok=True)

    default_out = repo / "_ci_out"
    minimal = test_data / "minimal_timeseries.csv"
    minimal_bak = test_data / "minimal_timeseries.csv.bak"

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bands": [],
    }

    ok_count = 0

    for band in bands:
        band_name = band.stem
        print("\n==============================")
        print("BAND:", band_name)
        print("==============================")

        band_dir = out_root / band_name
        band_dir.mkdir(parents=True, exist_ok=True)

        shutil.rmtree(default_out, ignore_errors=True)

        tried = []
        variants = [
            ["python", "scripts/run_sost.py", "--input", str(band), "--outdir", "_ci_out"],
            ["python", "scripts/run_sost.py", "--input-csv", str(band), "--outdir", "_ci_out"],
            ["python", "scripts/run_sost.py", str(band)],
        ]

        success = False
        for cmd in variants:
            tried.append(cmd)
            if run_cmd(cmd, repo, env):
                success = True
                break

        replaced_minimal = False
        if not success:
            try:
                if minimal.exists():
                    shutil.copy2(minimal, minimal_bak)
                shutil.copy2(band, minimal)
                replaced_minimal = True
                if run_cmd(["python", "scripts/run_sost.py"], repo, env):
                    success = True
            finally:
                if replaced_minimal and minimal_bak.exists():
                    shutil.copy2(minimal_bak, minimal)
                    minimal_bak.unlink(missing_ok=True)

        dd = find_artifact(default_out, "dd_report.json")
        ddr = find_artifact(default_out, "ddr_report.json")
        er = find_artifact(default_out, "e_report.json")

        if dd:
            shutil.copy2(dd, band_dir / "dd_report.json")
        if ddr:
            shutil.copy2(ddr, band_dir / "ddr_report.json")
        if er:
            shutil.copy2(er, band_dir / "e_report.json")

        artifacts = []
        for name in ["dd_report.json", "ddr_report.json", "e_report.json"]:
            p = band_dir / name
            if p.exists():
                artifacts.append({"path": name, "sha256": sha256_file(p)})

        manifest = {
            "version": "0.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "band": band_name,
            "input_csv": str(band.as_posix()),
            "artifacts": artifacts,
            "attempted_commands": [" ".join(x) for x in tried],
        }
        (band_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )

        band_summary = summarize(
            band_dir / "dd_report.json" if (band_dir / "dd_report.json").exists() else None,
            band_dir / "ddr_report.json" if (band_dir / "ddr_report.json").exists() else None,
            band_dir / "e_report.json" if (band_dir / "e_report.json").exists() else None,
        )
        band_summary["band"] = band_name
        band_summary["success"] = bool(success and artifacts)
        summary["bands"].append(band_summary)

        if success and artifacts:
            ok_count += 1

    (out_root / "bands_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    print("\nBands OK:", ok_count, "/", len(bands))
    return 0 if ok_count > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
