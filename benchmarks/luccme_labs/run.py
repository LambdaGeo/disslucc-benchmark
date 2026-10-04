#!/usr/bin/env python3
"""Run disslucc on the LuccME labs and compare it, year by year, with the TerraME goldens.

    python benchmarks/luccme_labs/run.py                 # every scenario in labs.toml
    python benchmarks/luccme_labs/run.py lab03 lab15     # some of them
    python benchmarks/luccme_labs/run.py --coverage      # which of the 21 labs disslucc covers

Exit status 1 if any scenario with `expect = "match"` misses its criteria (or its
provenance checks fail). `expect = "differs"` scenarios are reported and never fail the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import references as ref  # noqa: E402

LABS = tomllib.loads((HERE / "labs.toml").read_text())
CATALOG = tomllib.loads((HERE / "catalog.toml").read_text())
LOG_RE = re.compile(r"Demand allocated correctly in (\d+)\s+Number of iterations: (\d+)\s+Maximum error: ([\d.eE+-]+)")
NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def provenance(name: str, spec: dict, scenario) -> list[str]:
    """Problems with the chain golden → manifest → Lua script → transcribed parameters."""
    files, problems = ref.lab_files(scenario.lab), []
    manifest = json.loads(files["manifest"].read_text())
    sha = hashlib.sha256(files["lua"].read_bytes()).hexdigest()
    if manifest["status"] != "ok":
        problems.append(f"golden status is {manifest['status']!r}")
    if manifest["source"]["sha256"] != sha:
        problems.append("the golden was generated from a different Lua script than the pinned one")
    in_lua = {float(x) for x in NUMBER_RE.findall(files["lua"].read_text())}
    missing = sorted({v for v in scenario.declared if float(v) not in in_lua})
    if missing:
        problems.append(f"values not found in {scenario.lab}.lua (transcription error?): {missing}")
    return problems


def terrame_log(path: Path) -> dict[int, tuple[int, float]]:
    return {int(y): (int(n), float(e)) for y, n, e in LOG_RE.findall(path.read_text())}


def compare(name: str, spec: dict, scenario, result) -> dict:
    files = ref.lab_files(scenario.lab)
    manifest = json.loads(files["manifest"].read_text())
    golden = pd.read_csv(files["golden"]).set_index(["year", "row", "col"]).sort_index()
    years = sorted(golden.index.get_level_values("year").unique())
    joined = result.table.join(golden[result.table.columns], how="outer", rsuffix="_ref")
    out = {"cells": int(golden.groupby(level="year").size().iloc[0]), "years": f"{years[0]}–{years[-1]}", "columns": {}}
    out["aligned"] = bool(joined.notna().all().all())
    for col in result.table.columns:
        err = (joined[col] - joined[f"{col}_ref"]).abs()
        by_year = err.groupby(level="year")
        out["columns"][col] = {
            "mae": float(err.mean()), "max": float(err.max()),
            "worst_year": int(by_year.max().idxmax()), "mae_by_year": {int(y): float(v) for y, v in by_year.mean().items()},
        }
    ref_iter = [manifest["iterations_per_year"][str(y)] for y in years]
    out["iterations"] = {"disslucc": result.iterations, "terrame": ref_iter, "match": result.iterations == ref_iter}
    if result.max_error is not None:
        log = terrame_log(files["log"])
        theirs = [log[y][1] for y in years]
        rel = max(abs(a - b) / max(abs(b), 1e-300) for a, b in zip(result.max_error, theirs, strict=True))
        out["max_error_rel_diff"] = float(rel)
    out["worst_max"] = max(c["max"] for c in out["columns"].values())
    out["worst_mae"] = max(c["mae"] for c in out["columns"].values())
    return out


def verdict(spec: dict, res: dict) -> tuple[bool, list[str]]:
    failed = []
    if spec.get("iterations") == "exact" and not res["iterations"]["match"]:
        failed.append("iterations per year differ from TerraME")
    if "max_abs_error" in spec and res["worst_max"] > spec["max_abs_error"]:
        failed.append(f"max |error| {res['worst_max']:.3g} > {spec['max_abs_error']:g}")
    if "mae" in spec and res["worst_mae"] > spec["mae"]:
        failed.append(f"MAE {res['worst_mae']:.3g} > {spec['mae']:g}")
    if "max_error_rel" in spec and res.get("max_error_rel_diff", 0) > spec["max_error_rel"]:
        failed.append("maximum error per year differs from the TerraME log")
    if not res["aligned"]:
        failed.append("cells do not align with the golden")
    return not failed, failed


def render(results: list[dict]) -> str:
    lines = [
        "| Scenario | Lab | Cells | Years | Iterations vs TerraME | MAE (worst col.) | Max abs err | Criterion | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        res, spec = r["result"], r["spec"]
        crit = []
        if spec.get("iterations") == "exact":
            crit.append("iterations exact")
        if "max_abs_error" in spec:
            crit.append(f"max ≤ {spec['max_abs_error']:g}")
        if "mae" in spec:
            crit.append(f"MAE ≤ {spec['mae']:g}")
        if "max_error_rel" in spec:
            crit.append("log max error")
        status = r["status"]
        lines.append(
            f"| `{r['name']}` | {r['lab']} | {res['cells']:,} | {res['years']} | "
            f"{'identical' if res['iterations']['match'] else 'differ'} | {res['worst_mae']:.2e} | {res['worst_max']:.2e} | "
            f"{', '.join(crit) or 'reported only'} | {status} |"
        )
    return "\n".join(lines)


def coverage() -> str:
    covered = {name.split("/")[0] for name, s in LABS.items() if s.get("expect", "match") == "match"}
    rows = ["| Lab | Paradigm | Components | disslucc components | Validated against goldens |", "| --- | --- | --- | --- | --- |"]
    for lab in CATALOG["lab"]:
        ok = lab["id"] in covered
        rows.append(
            f"| {lab['id']} | {lab['paradigm']} | {lab['components']} | {lab['implemented']} | "
            f"{'**yes**' if ok else 'no'} |"
        )
    n_impl = sum(1 for lab in CATALOG["lab"] if lab["implemented"] == "all")
    rows += ["", f"Validated: {len(covered)} of {len(CATALOG['lab'])} labs. Components all implemented in disslucc: {n_impl} of {len(CATALOG['lab'])}."]
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="scenario names from labs.toml (default: all)")
    ap.add_argument("--coverage", action="store_true", help="print the coverage of the 21 labs and exit")
    ap.add_argument("--report-dir", default=str(HERE.parent.parent / "reports"))
    args = ap.parse_args()
    if args.coverage:
        print(coverage())
        return 0

    from scenarios import SCENARIOS  # imports disslucc (slow), so only when running

    names = args.scenarios or list(LABS)
    unknown = [n for n in names if n not in LABS or n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {unknown}; available: {list(LABS)}", file=sys.stderr)
        return 2

    results, failures = [], 0
    for name in names:
        spec, scenario = LABS[name], SCENARIOS[name]
        print(f"==> {name} ({scenario.lab})", file=sys.stderr)
        problems = provenance(name, spec, scenario)
        res = compare(name, spec, scenario, scenario.run())
        ok, failed = verdict(spec, res)
        failed = problems + failed
        expect = spec.get("expect", "match")
        status = "differs (by design)" if expect == "differs" else ("match" if not failed else "FAIL: " + "; ".join(failed))
        if expect == "match" and failed:
            failures += 1
        results.append({"name": name, "lab": scenario.lab, "spec": spec, "result": res, "status": status, "problems": problems})

    header = (
        f"disslucc {version('disslucc')} · dissmodel {version('dissmodel')} · "
        f"goldens: luccme-goldens @ {ref.COMMIT[:12]} (TerraME 2.0.1 + LuccME 3.1)"
    )
    table = render(results)
    print(f"\n{header}\n\n{table}")
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "luccme_labs.json").write_text(json.dumps(
        {"disslucc": version("disslucc"), "dissmodel": version("dissmodel"), "goldens_commit": ref.COMMIT,
         "scenarios": [{k: v for k, v in r.items() if k != "spec"} | {"spec": r["spec"]} for r in results]}, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a").write(f"### {header}\n\n{table}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
