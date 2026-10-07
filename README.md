# disslucc-benchmark

[![CI](https://github.com/LambdaGeo/disslucc-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/LambdaGeo/disslucc-benchmark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![luccme-goldens v1.1.0: Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23161342.svg)](https://doi.org/10.5281/zenodo.23161342)
[![Engine: disslucc](https://img.shields.io/badge/Engine-disslucc-green.svg)](https://github.com/DisSModel/disslucc)

**How much of LuccME does disslucc implement? This repository measures it, lab by lab, against TerraME reference outputs.**

It runs `disslucc` on the LuccME 3.1 functional labs and compares, for every cell and every simulated year, land use (`<lu>_out`), potential (`<lu>_pot`), the number of iterations of the allocation's convergence loop and, where the lab reports it, the maximum error against the demand, with the goldens that TerraME 2.0.1 produced. No TerraME installation is needed.

No reference data is stored here. Goldens, lab scripts and input layers are downloaded from one exact release of [`luccme-goldens`](https://github.com/LambdaGeo/luccme-goldens) (`v1.1.0`) and verified by SHA-256 before use.

---

## 1. Quick start

```bash
git clone https://github.com/LambdaGeo/disslucc-benchmark && cd disslucc-benchmark
make install        # disslucc 0.5.0 (PyPI) + dependencies
make benchmark      # downloads the references (~20 MB, once), runs, prints the table; exit 1 if a criterion is missed
make coverage       # which of the 21 labs disslucc covers
make timing         # time and peak memory of each scenario (informational)
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

disslucc 0.5.0 · dissmodel 0.6.5 · goldens: `luccme-goldens` `v1.1.0` (TerraME 2.0.1 + LuccME 3.1).

| Scenario | Components | Cells | Years | Iterations vs TerraME | MAE (worst column) | Max abs error | Criterion | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `lab01` | PreComputed + CLinearRegression + CClueLike (`maxDifference` 5000) | 6,574 | 2008–2014 | identical | 3.0e-08 | 5.1e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab02` | PreComputed + CSpatialLagRegression + CClueLike (1643) | 6,574 | 2008–2014 | identical | 1.5e-08 | 2.3e-06 | iterations exact, max ≤ 1e-5 | match |
| `lab03` | PreComputed + CSpatialLagRegression + CClueLikeSaturation (1643) | 6,574 | 2008–2014 | identical | 2.3e-13 | 5.0e-13 | iterations exact, max ≤ 1e-9, log max error rel ≤ 1e-9 | match |
| `lab04` | lab02 with `DemandComputeTwoDates` (final year 2014, layers `f2014`/`d2014`) instead of a demand table | 6,574 | 2008–2014 | identical | 1.5e-08 | 2.4e-06 | iterations exact, max ≤ 1e-5 | match |
| `lab05` | lab04 with `DemandComputeThreeDates` (middle year 2011, final year 2014) | 6,574 | 2008–2014 | identical | 1.5e-08 | 2.3e-06 | iterations exact, max ≤ 1e-5 | match |
| `lab06` | same as lab03 + `updateYears = {2009}` (`ti` from `csAC_2009`) | 6,574 | 2008–2014 | identical | 2.3e-13 | 5.0e-13 | same as lab03 | match |
| `lab07` | same as lab02 to 2025, `updateYears = {2009, 2020}` (`ti` from `csAC_2009`; `uc_us`, `uc_pi` from `csAC_cenarioA_2020`) | 6,574 | 2008–2025 | identical | 1.7e-08 | 3.0e-06 | iterations exact, max ≤ 1e-5 | match |
| `lab15` | PreComputed + DLogisticRegression + DClueSLike (300) | 5,914 | 1999–2004 | identical | 3.0e-08 | 1.2e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab16` | lab15 with `DemandComputeTwoDates` (final year 2004, layers `f04`/`d04`) | 5,914 | 1999–2004 | identical | 3.0e-08 | 1.2e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab17` | lab16 with `DemandComputeThreeDates` (middle year 2004, final year 2007) | 5,914 | 1999–2004 | identical | 3.0e-08 | 1.2e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab01_md1643` | `lab01` with `maxDifference` 1643 (`MD=1643`): the convergence loop runs, **0,0,8,26,18,17,17** iterations per year | 6,574 | 2008–2014 | identical | 3.0e-08 | 5.1e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab15_md10` | `lab15` with `maxDifference` 10 (`MD=10`): **0,67,56,56,61,61** iterations per year | 5,914 | 1999–2004 | identical | 3.0e-08 | 1.2e-07 | iterations exact, max ≤ 1e-6 | match |
| `lab01_md1643/cell_correction` | `lab01_md1643` with disslucc's default: **0,0,0,14,17,16,16** iterations per year (TerraME: 0,0,8,26,18,17,17) | 6,574 | 2008–2014 | differ | 2.6e-03 | 2.7e-02 | reported only | differs (by design) |
| `lab01/cell_correction` | `lab01` with disslucc's default | 6,574 | 2008–2014 | identical | 1.4e-03 | 3.9e-02 | reported only | differs (by design) |

The 5e-13 of lab03/lab06 is the precision of the goldens (12 decimals). The 1e-7 of lab01/lab15/lab16/lab17 and the up to 3e-6 of lab02/lab04/lab05/lab07 (almost all in the `f` potential) are float32 noise of the raster backend and of the CClueLike path.

### Where disslucc differs from LuccME on purpose

`lab01/cell_correction` and `lab01_md1643/cell_correction`: LuccME's `AllocationCClueLike` never runs `correctCellChange`: its guard reads the field `cell.regionregionAloc` instead of `regionAloc`, so it is always false. disslucc runs the correction by default (the intended algorithm). The `lab01` and `lab01_md1643` scenarios set `cell_correction=False`, which reproduces TerraME in every year and every iteration count; the two extra scenarios pin the size of the deviation with the default.

In `lab01_md1643/cell_correction` the 2014 MAE is **0.0036** in `f` and in `d` (0 in `outros`, max 0.027): the figure `docs/validation.md` of disslucc reports as within the official 0.01 tolerance. All of it is the cell correction that TerraME skips, and the iteration counts also change (0,0,0,14,17,16,16 instead of 0,0,8,26,18,17,17).

## 4. Coverage of the 21 labs

`make coverage` prints the table; the source is `benchmarks/luccme_labs/catalog.toml`, read from each lab's Lua script.

**Validated: 10 of 21 labs** (lab01, lab02, lab03, lab04, lab05, lab06, lab07, lab15, lab16, lab17), plus two `maxDifference` variants that exercise the convergence loop. **All components implemented in disslucc: 10 of 21**: exactly those ten, so no remaining lab can be validated with the components that exist today. Labs missing a single component: lab08, lab09, lab13, lab14, lab18 and lab21 (one potential or allocation each). The missing components of every lab are in the `missing` field of the catalog.

> `catalog.toml` differs from the table in the `luccme-goldens` README in some labs (for example lab09 and lab13). The catalog follows the Lua scripts, which are what TerraME ran.

## 5. Limits of this evidence

- **The package labs barely exercise the convergence loop.** In lab01 to lab07 and lab15 to lab17 the allocation is accepted at the first pass every year (iterations are `0`), so "iterations identical" says little there. That is why the two variants exist: with a smaller `maxDifference` the loop runs 8 to 67 times per year, and disslucc reproduces TerraME's iteration count in every year.
- **The variants are the same lab with `MD=` overriding `maxDifference`.** The golden's manifest records the override and the benchmark checks it against the scenario. They reproduce, to 1e-12, the copies kept in the disslucc repository, which came from the original scripts (`lab1_main.lua` and `lab6_main.lua`).
- **lab04, lab05, lab16 and lab17 check the demand components, not new allocation behaviour.** Each is lab02 or lab15 with the demand computed from the layers, so their outputs are close to those of the lab they derive from (compare the errors in the table). lab17 ends in 2004, before its final year 2007, so it uses only the first segment and gives the same result as lab16.
- **lab15 (package) is nearly non-discriminative.** With `maxDifference` 300 a static ranking by `prob_d − prob_f` already reproduces its output; the match shows the regression coefficients were transcribed correctly. `lab15_md10` is the one that exercises CLUE-S.
- **lab03 and lab06 do not reach `correctCellChange` nor saturation** (`changeLimiarValue = 1`). Those branches are checked against the original Lua on synthetic cases in the disslucc repository (`tests/test_lua_differential.py`), which are not part of this benchmark.
- **The scenarios do not exercise the executor or the rasterization.** They build each lab's model by hand and match cells by their own `row`/`col`; the executor and TOML path that a user runs rasterizes the layer at a `resolution` and, for `cs_moju`, loses cells (5,842 of 5,914 in the lab15 example), so it cannot be compared cell by cell with a TerraME golden.
- This is **engineering validation** (same results as a reference run), not scientific validation against observed data.

## 6. Timing (informational)

```bash
make timing REPS=5            # LAB=lab03 for one scenario
```

Each scenario runs in a fresh process, one warm-up repetition and `REPS` measured ones. The timed span is the whole scenario (reading the layers, building the model, simulating every year, recording each year's state); importing disslucc is not timed. `reports/timing_disslucc.json` gets the median, range, peak memory and a description of the machine. **Nothing here passes or fails**: times depend on the machine and on CI load.

Next to it the report shows the `Elapsed time` that TerraME printed in the golden's `terrame.log`. Read it as an order of magnitude, **not as a speed ratio**: it is a single run, at 1-second resolution, measured inside Docker on another machine, and it also includes the recorder that wrote every year's snapshot. `luccme-goldens` has a controlled TerraME measurement (repetitions, fixed CPU and memory limits, environment recorded) only for the `fill` datasets of [disscube-benchmark](https://github.com/LambdaGeo/disscube-benchmark); if one is added for the labs, this report can pin it the same way.

The scenarios call the disslucc models directly and **do not go through the executor** of dissmodel, so the per-phase times (`time_load_sec`, `time_run_sec`) that its lifecycle records are not available here.

## 7. Reproducibility chain

| Level | Artifact | Pinned version |
| --- | --- | --- |
| Engine | [`disslucc`](https://github.com/DisSModel/disslucc) | `0.5.0` on PyPI, DOI [10.5281/zenodo.23219338](https://doi.org/10.5281/zenodo.23219338) (`requirements.txt`) |
| Reference outputs, lab scripts, input layers | [`luccme-goldens`](https://github.com/LambdaGeo/luccme-goldens) | `v1.1.0`, DOI [10.5281/zenodo.23161342](https://doi.org/10.5281/zenodo.23161342) (`references.toml`, every file with its SHA-256) |
| Lua components (differential test) | [`terrame-docker`](https://github.com/profsergiocosta/terrame-docker) | `v0.4.2`, DOI [10.5281/zenodo.23160784](https://doi.org/10.5281/zenodo.23160784) (`[lua_files]` in `references.toml`, SHA-256) |
| Reference generator | [`terrame-docker`](https://github.com/LambdaGeo/terrame-docker) / `profsergiocosta/terrame-luccme` | TerraME 2.0.1 + LuccME 3.1, recorded in each golden's `manifest.json` |
| Benchmark | this repository | `v0.2.1` (DOI of this release on Zenodo; see `CITATION.cff`) |

To use another version of the goldens: `make pins REF=<tag> GOLDENS=../luccme-goldens [DOI=...]`. It rewrites `references.toml` with the hashes read from `git show <ref>:<path>`, so nothing is copied by hand; a modified file fails with a hash mismatch.

## 8. Repository structure and what is still pending

```text
disslucc-benchmark/
├── Makefile                      # install, benchmark, coverage, references, test
├── requirements.txt              # disslucc pinned to the released 0.5.0
├── benchmarks/luccme_labs/
│   ├── references.toml           # luccme-goldens release + SHA-256 of every file used
│   ├── references.py             # download + hash check (pooch)
│   ├── pin_references.py         # re-pin to another luccme-goldens ref (make pins)
│   ├── timing.py                 # time and peak memory, informational (make timing)
│   ├── scenarios.py              # the labs, as disslucc models (parameters from the Lua)
│   ├── labs.toml                 # criteria per scenario (match | differs)
│   ├── catalog.toml              # the 21 labs and their components, from the Lua
│   └── run.py                    # run, compare, provenance checks, tables
├── tests/test_labs.py            # pytest wrapper
├── tests/test_lua_differential.py # the Python ports against the original LuccME Lua (lupa)
└── .github/workflows/ci.yml      # runs on push, PR and weekly
```

Pending:

- Next labs: those missing a single component (section 4).
- Not migrated from disslucc: the discriminance tests and the Pontius & Millones metrics; they test the implementation rather than parity with a golden. (The finding of the lab15 test is recorded in section 5.)
- Remove `benchmark/` from disslucc and point its tests and docs here, once this benchmark is accepted.

## 9. Citation

See `CITATION.cff`. Upstream TerraME and LuccME are Copyright (C) 2001–2017 INPE and TerraLAB/UFOP.
