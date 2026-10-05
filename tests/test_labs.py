"""pytest wrapper: every scenario in labs.toml must meet its stated criteria."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks" / "luccme_labs"))

import run as bench  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

NAMES = list(bench.LABS)


def test_every_scenario_is_declared():
    assert set(NAMES) == set(SCENARIOS)


def test_catalog_has_the_21_labs():
    assert [lab["id"] for lab in bench.CATALOG["lab"]] == [f"lab{i:02d}" for i in range(1, 22)]


@pytest.mark.parametrize("name", NAMES)
def test_scenario(name):
    spec, scenario = bench.LABS[name], SCENARIOS[name]
    assert bench.provenance(name, spec, scenario) == []
    ok, failed = bench.verdict(spec, bench.compare(name, spec, scenario, scenario.run()))
    if spec.get("expect", "match") == "match":
        assert ok, failed


# ── the checker itself ───────────────────────────────────────────────────────────────────────

def test_tighter_threshold_fails():
    scenario = SCENARIOS["lab01"]
    result = bench.compare("lab01", {}, scenario, scenario.run())
    ok, failed = bench.verdict({**bench.LABS["lab01"], "max_abs_error": 1e-9}, result)
    assert not ok and any("max |error|" in f for f in failed)


def test_mistyped_parameter_fails_provenance():
    scenario = SCENARIOS["lab03"]
    broken = type(scenario)(scenario.lab, scenario.run, [*scenario.declared[:-1], 1.5001])
    assert any("1.5001" in p for p in bench.provenance("lab03", {}, broken))


def test_wrong_override_fails_provenance():
    scenario = SCENARIOS["lab01_md1643"]
    broken = type(scenario)(scenario.lab, scenario.run, scenario.declared, scenario.golden, 5000.0)
    assert any("overrides" in p for p in bench.provenance("lab01_md1643", {}, broken))


# ── pins and timing ──────────────────────────────────────────────────────────────────────────

def test_references_are_pinned_to_a_release():
    import references as ref
    assert ref.REF.startswith("v") and len(ref.COMMIT) == 40 and ref.DOI


def test_terrame_elapsed_time_is_read_from_the_golden_log():
    import timing
    assert timing.terrame_elapsed_s("lab15") == 2
    assert timing.terrame_elapsed_s("lab15_md10", "lab15") == 9


def test_timing_report(tmp_path):
    import json
    import subprocess
    out = tmp_path / "timing.json"
    subprocess.run([sys.executable, str(Path(bench.__file__).parent / "timing.py"), "lab15", "--reps", "1", "--out", str(out)],
                   check=True, capture_output=True)
    rep = json.loads(out.read_text())["scenarios"]["lab15"]
    assert rep["reps"] == 1 and rep["run_s"]["median"] > 0 and rep["max_rss_mb"] > 0 and rep["terrame_elapsed_s"] == 2
