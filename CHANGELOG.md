# Changelog

## 0.1.0 (2026-10-04)

First release.

- Runs disslucc on the LuccME 3.1 labs and compares it, year by year and cell by cell, with the
  TerraME 2.0.1 goldens of `luccme-goldens`, pinned to its release `v1.1.0` (DOI
  10.5281/zenodo.23161342) with the SHA-256 of every file (`references.toml`). Nothing from the
  references is stored in this repository. `make pins REF=<tag>` re-pins it, reading the hashes from
  `git show <ref>:<path>`.
- Scenarios: `lab01`, `lab03`, `lab06`, `lab15` (package labs) and `lab01_md1643`, `lab15_md10`
  (the same labs with a smaller `maxDifference`, so the allocation's convergence loop runs).
  disslucc reproduces TerraME's iteration count in every year of all six, with a maximum
  absolute error of 5e-13 (lab03, lab06), 1e-07 (lab15, lab15_md10) and 5e-07 (lab01, lab01_md1643).
- Reported deviations: `lab01/cell_correction` and `lab01_md1643/cell_correction` (disslucc runs
  `correctCellChange`; TerraME never does, because of a typo in its guard). The latter reproduces
  the 0.0036 MAE of the disslucc documentation.
- Provenance checks: the golden's manifest must be `ok`, carry the SHA-256 of the pinned Lua
  script and the expected `maxDifference` override; every number transcribed from the Lua is looked
  up in the script.
- Catalog of the 21 labs with their components (`make coverage`): 4 validated, 6 with every
  component implemented in disslucc.
- `make timing`: time and peak memory of each scenario (fresh process, one warm-up repetition,
  median and range), with the machine described and TerraME's `Elapsed time` from the golden's log
  shown next to it. Informational only; the TerraME figure is a single run at 1-second resolution,
  not a speed ratio.
- Known limit: the scenarios build the models by hand and match cells by `row`/`col`; they do not
  exercise the executor or the rasterization that a user's TOML run goes through.
- CI on push, pull request and weekly.
