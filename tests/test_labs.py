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
