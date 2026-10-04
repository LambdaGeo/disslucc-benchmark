# disslucc-benchmark

[![CI](https://github.com/LambdaGeo/disslucc-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/LambdaGeo/disslucc-benchmark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Goldens: Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23107748.svg)](https://doi.org/10.5281/zenodo.23107748) <!-- TODO: DOI of the luccme-goldens release that includes the per-year goldens (v1.0.0 has only the last-year ones) -->
[![Engine: disslucc](https://img.shields.io/badge/Engine-disslucc-green.svg)](https://github.com/DisSModel/disslucc)

**How much of LuccME does disslucc implement? This repository measures it, lab by lab, against TerraME reference outputs.**

It runs `disslucc` on the LuccME 3.1 functional labs and compares, for every cell and every simulated year, land use (`<lu>_out`), potential (`<lu>_pot`), the number of iterations of the allocation's convergence loop and, where the lab reports it, the maximum error against the demand, with the goldens that TerraME 2.0.1 produced. No TerraME installation is needed.

No reference data is stored here. Goldens, lab scripts and input layers are downloaded from one exact commit of [`luccme-goldens`](https://github.com/LambdaGeo/luccme-goldens) and verified by SHA-256 before use.

---

## 1. Quick start

```bash
git clone https://github.com/LambdaGeo/disslucc-benchmark && cd disslucc-benchmark
make install        # disslucc (pinned commit) + dependencies
make benchmark      # downloads the references (~16 MB, once), runs, prints the table; exit 1 if a criterion is missed
make coverage       # which of the 21 labs disslucc covers
make benchmark LAB=lab03   # one scenario
```

The run takes seconds. Every scenario prints one row (section 3) and the tables are also written to `reports/luccme_labs.json` and, in CI, to the job summary.

## 2. What is checked, and why it can be trusted

For each scenario `benchmarks/luccme_labs/run.py`:

1. **Verifies provenance.** The golden's `manifest.json` must say `status: ok` and carry the SHA-256 of the Lua script pinned here, so the golden really comes from that lab. Every number transcribed from the Lua into `scenarios.py` (demand, coefficients, `maxDifference`...) is looked up in the Lua text; a mistyped value fails before any simulation is compared.
2. **Runs the lab with disslucc** on the same cells the lab used (by each cell's own `row`/`col`; no resampling, so no alignment error).
3. **Compares with the golden**, cell by cell and year by year: largest and mean absolute error per column, iterations per year (must be equal), and "Maximum error" per year against `terrame.log`.
4. **Applies the criterion** declared in `labs.toml`. `expect = "match"` scenarios make the run exit 1 if missed; `expect = "differs"` scenarios are reported only.

The thresholds are **regression guards**, set just above what was measured, not claims of equivalence beyond that. The tests of the checker itself: tightening a threshold fails the run, and a mistyped coefficient fails the provenance check (see `tests/`).

## 3. Results

disslucc `450f4db` (0.4.0) · dissmodel 0.6.5 · goldens: `luccme-goldens` @ `a393b157df42` (TerraME 2.0.1 + LuccME 3.1).

| Scenario | Components | Cells | Years | Iterations vs TerraME | MAE (worst column) | Max abs error | Criterion | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `lab01` | PreComputed + CLinearRegression + CClueLike (`maxDifference` 5000) | 6,574 | 2008–2014 | identical | 3.0e-08 | 5.1e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab03` | PreComputed + CSpatialLagRegression + CClueLikeSaturation (1643) | 6,574 | 2008–2014 | identical | 2.3e-13 | 5.0e-13 | iterations exact, max ≤ 1e-9, log max error rel ≤ 1e-9 | match |
| `lab06` | same as lab03 + `updateYears = {2009}` (`ti` from `csAC_2009`) | 6,574 | 2008–2014 | identical | 2.3e-13 | 5.0e-13 | same as lab03 | match |
| `lab15` | PreComputed + DLogisticRegression + DClueSLike (300) | 5,914 | 1999–2004 | identical | 3.0e-08 | 1.2e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab01/cell_correction` | `lab01` with disslucc's default | 6,574 | 2008–2014 | identical | 1.4e-03 | 3.9e-02 | reported only | differs (by design) |

The 5e-13 of lab03/lab06 is the precision of the goldens (12 decimals). The ~1e-7 of lab01/lab15 is float32 noise of the raster backend.

### Where disslucc differs from LuccME on purpose

`lab01/cell_correction`: LuccME's `AllocationCClueLike` never runs `correctCellChange`: its guard reads `cell.regionregionAloc`, a typo for `regionAloc`, so it is always false. disslucc runs the correction by default (the intended algorithm). The `lab01` scenario sets `cell_correction=False`, which reproduces TerraME in every year and every iteration count; the extra scenario pins the size of the deviation with the default.

## 4. Coverage of the 21 labs

`make coverage` prints the table; the source is `benchmarks/luccme_labs/catalog.toml`, read from each lab's Lua script.

**Validated: 4 of 21 labs** (lab01, lab03, lab06, lab15). **All components implemented in disslucc: 6 of 21**: the four above plus lab02 and lab07, which have no scenario yet. Missing components, by lab, are in the `missing` field of the catalog (`DemandComputeTwoDates`/`ThreeDates`, `AllocationDSimpleOrdering`, the neighbourhood-based discrete potentials, `AllocationDClueSNeighOrdering`, the sample-based potentials and `PotentialCSpatialLagLinearRegressionMix`).

> `catalog.toml` differs from the table in the `luccme-goldens` README in some labs (for example lab09 and lab13). The catalog follows the Lua scripts, which are what TerraME ran.

## 5. Limits of this evidence

- **The package labs barely exercise the convergence loop.** In all four, the allocation is accepted at the first pass every year (iterations are `0`), so "iterations identical" is weak evidence here. The variants with a smaller `maxDifference` iterate up to 67 times per year; they are **not in this repository yet** (see section 7).
- **lab15 is nearly non-discriminative.** A static ranking by `prob_d − prob_f` already reproduces its output; the match shows the regression coefficients were transcribed correctly, not that CLUE-S is faithful. The `lab15` golden also passes with iterations at zero.
- **lab03 and lab06 do not reach `correctCellChange` nor saturation** (`changeLimiarValue = 1`). Those branches are checked against the original Lua on synthetic cases in the disslucc repository (`tests/test_lua_differential.py`), which are not part of this benchmark.
- This is **engineering validation** (same results as a reference run), not scientific validation against observed data.

## 6. Reproducibility chain

| Level | Artifact | Pinned version |
| --- | --- | --- |
| Engine | [`disslucc`](https://github.com/DisSModel/disslucc) | commit `450f4db` (`requirements.txt`) |
| Reference outputs, lab scripts, input layers | [`luccme-goldens`](https://github.com/LambdaGeo/luccme-goldens) | commit `a393b157df42` (`references.toml`, every file with its SHA-256) <!-- TODO: replace with a release tag + DOI once the per-year goldens are released --> |
| Reference generator | [`terrame-docker`](https://github.com/LambdaGeo/terrame-docker) / `profsergiocosta/terrame-luccme` | TerraME 2.0.1 + LuccME 3.1, recorded in each golden's `manifest.json` |
| Benchmark | this repository | `v0.1.0` <!-- TODO: DOI --> |

To use another version of the goldens, change `commit` in `references.toml` and regenerate the hashes; a modified file fails with a hash mismatch.

## 7. Repository structure and what is still pending

```text
disslucc-benchmark/
├── Makefile                      # install, benchmark, coverage, references, test
├── requirements.txt              # disslucc pinned by commit
├── benchmarks/luccme_labs/
│   ├── references.toml           # luccme-goldens commit + SHA-256 of every file used
│   ├── references.py             # download + hash check (pooch)
│   ├── scenarios.py              # the labs, as disslucc models (parameters from the Lua)
│   ├── labs.toml                 # criteria per scenario (match | differs)
│   ├── catalog.toml              # the 21 labs and their components, from the Lua
│   └── run.py                    # run, compare, provenance checks, tables
├── tests/test_labs.py            # pytest wrapper
└── .github/workflows/ci.yml      # runs on push, PR and weekly
```

Pending:

- Variants `lab01_md1643` and `lab15_md10` (the former headline numbers of the disslucc docs, with the convergence loop exercised): decide whether to regenerate them in `luccme-goldens` (`make run-labs-per-year LAB=15 MD=10`, needs Docker) or keep them as extra goldens.
- Next cheap labs: lab02 and lab07 (all components exist).
- Not migrated from disslucc: the Lua differential tests, the discriminance tests and the Pontius & Millones metrics; they test the implementation rather than parity with a golden.
- Remove `benchmark/` from disslucc and point its tests and docs here, once this benchmark is accepted.

## 8. Citation

See `CITATION.cff`. Upstream TerraME and LuccME are Copyright (C) 2001–2017 INPE and TerraLAB/UFOP.
