#!/usr/bin/env python3
"""Time and peak memory of the disslucc scenarios, next to TerraME's own elapsed time.

    python benchmarks/luccme_labs/timing.py                 # every scenario in labs.toml, 5 reps
    python benchmarks/luccme_labs/timing.py lab15 --reps 3
    make timing REPS=5            # LAB=lab03 for one scenario

Each scenario runs in a fresh Python process (so peak memory is that process's own). The
timed span is the whole scenario: reading the layers, building the model, simulating every
year and recording each year's state; the import of disslucc is not timed. Repetition 0 is a
warm-up and is excluded. Writes reports/timing_disslucc.json with the median, range, peak
memory and a description of the machine.

INFORMATIONAL ONLY: nothing here passes or fails. The TerraME figure is the `Elapsed time`
line of the golden's terrame.log, i.e. ONE run, at 1-second resolution, measured inside
Docker on another machine while the recorder also wrote every year's snapshot. It tells
the order of magnitude, not a speed ratio. A controlled TerraME measurement (several
repetitions, fixed CPU/memory limits, environment recorded) exists in luccme-goldens only for
the `fill` datasets of disscube-benchmark (goldens/timing/).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import resource
import statistics
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import references as ref  # noqa: E402

ELAPSED_RE = re.compile(r"Elapsed time:\s*(\d+):(\d{2}):(\d{2})")


def terrame_elapsed_s(golden: str, lua: str | None = None) -> int | None:
    """Seconds in the `Elapsed time: hh:mm:ss` line of the golden's terrame.log (None if absent)."""
    m = ELAPSED_RE.search(ref.lab_files(golden, lua)["log"].read_text())
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


def _ram_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                return round(int(line.split()[1]) / 1024)
    except OSError:
        pass
    return None


def environment() -> dict:
    return {
        "python": platform.python_version(), "os": platform.platform(), "cpu_model": _cpu_model(),
        "cores": os.cpu_count(), "ram_mb": _ram_mb(),
        "disslucc": version("disslucc"), "dissmodel": version("dissmodel"),
        "numpy": version("numpy"), "geopandas": version("geopandas"),
    }


def worker(name: str) -> None:
    """One timed run in this process; prints a JSON line."""
    from scenarios import SCENARIOS  # noqa: E402  (imports disslucc; not timed)

    t0 = time.perf_counter()
    SCENARIOS[name].run()
    run_s = time.perf_counter() - t0
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KB on Linux
    print(json.dumps({"run_s": run_s, "max_rss_mb": rss_kb / 1024}))


def measure(name: str, reps: int) -> dict:
    rows = []
    for rep in range(reps + 1):
        r = subprocess.run([sys.executable, str(Path(__file__)), "--worker", name], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{name}: {r.stderr[-800:]}")
        out = json.loads(r.stdout.strip().splitlines()[-1])
        rows.append({"rep": rep, "run_s": round(out["run_s"], 3), "max_rss_mb": round(out["max_rss_mb"], 1)})
    kept = rows[1:]  # rep 0 is the warm-up
    run = [r["run_s"] for r in kept]
    return {
        "reps": len(kept),
        "run_s": {"median": statistics.median(run), "min": min(run), "max": max(run)},
        "max_rss_mb": max(r["max_rss_mb"] for r in kept),
        "runs": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="scenario names from labs.toml (default: all)")
    ap.add_argument("--reps", type=int, default=5, help="measured repetitions after one warm-up (default 5)")
    ap.add_argument("--out", default=str(HERE.parent.parent / "reports" / "timing_disslucc.json"))
    ap.add_argument("--worker", metavar="SCENARIO", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        worker(a.worker)
        return 0

    import tomllib
    labs = tomllib.loads((HERE / "labs.toml").read_text())
    names = a.scenarios or list(labs)
    unknown = [n for n in names if n not in labs]
    if unknown:
        sys.exit(f"unknown scenario(s): {unknown}; available: {list(labs)}")

    from scenarios import SCENARIOS  # noqa: E402

    result = {"engine": f"disslucc {version('disslucc')}", "goldens_ref": ref.REF, "environment": environment(),
              "warmup": "rep 0 excluded", "scenarios": {}}
    print(f"{'scenario':<32}{'disslucc median (min–max)':<30}{'peak MB':>9}   TerraME elapsed (1 run, 1 s resolution)")
    for name in names:
        sc = SCENARIOS[name]
        res = measure(name, a.reps)
        res["terrame_elapsed_s"] = terrame_elapsed_s(sc.golden_name, sc.lab)
        result["scenarios"][name] = res
        t = res["run_s"]
        theirs = res["terrame_elapsed_s"]
        print(f"{name:<32}{t['median']:>6.2f} s ({t['min']:.2f}–{t['max']:.2f}){'':<8}{res['max_rss_mb']:>9.0f}   "
              f"{'' if theirs is None else f'{theirs} s'}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nwrote {out}. Informational only: the TerraME figure is a single uncontrolled run, not a speed ratio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
