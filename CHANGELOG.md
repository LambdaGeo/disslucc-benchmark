# Changelog

## 0.2.0 (2026-10-07)

- Engine: `requirements.txt` now pins the released `disslucc==0.5.0` (PyPI, DOI 10.5281/zenodo.23219338)
  instead of a git commit. Re-run with it: the same 10 of 21 labs and both `maxDifference` variants reproduce
  TerraME with identical iteration counts (max abs error 2.96e-06, lab07); 57 tests pass.

- Scenarios `lab04`, `lab05`, `lab16` and `lab17`: lab02 and lab15 with the demand computed from the layers
  (`DemandComputeTwoDates` / `DemandComputeThreeDates`). All four reproduce TerraME with identical iteration
  counts; max abs error 2.4e-06, 2.3e-06, 1.2e-07 and 1.2e-07. Validated labs: 10 of 21. Requires disslucc
  `3e32384` or later; `requirements.txt` is pinned to it. Their reference files are pinned in `references.toml`
  (hashes read from the `v1.1.0` tag).
- `tests/test_lua_differential.py` (35 tests), moved from disslucc: the Python ports of the saturation
  allocation and the spatial-lag potential against the original LuccME Lua components, run through
  `lupa` on synthetic cases that reach what the goldens never do (`correctCellChange`, the saturation
  branch, log-transformed classes). The Lua files are not copied: they are downloaded from
  `terrame-docker` v0.4.2 and SHA-256-checked (`[lua_source]` and `[lua_files]` in `references.toml`).
  `requirements.txt` adds `lupa`.
- Wording: the LuccME guard that never runs `correctCellChange` is described as a field-name mismatch.

- Scenarios `lab02` and `lab07`: the spatial-lag potential of lab03 with the plain CClueLike allocation
  (lab07 to 2025, with the 2009 and 2020 driver updates). Both reproduce TerraME with components that
  already existed in disslucc, iterations identical, max abs error 2.3e-06 and 3.0e-06. Validated labs: 6 of 21 at that point.

- `citation.yml`: validates `CITATION.cff` against the CFF 1.2.0 schema, exports it the way Zenodo
  reads it, checks the ORCID checksum and that `date-released` is not in the future, and on a `v*`
  tag that the version matches the tag.
- `CITATION.cff`: author ORCID, and the references to `luccme-goldens` v1.1.0 and `terrame-docker` 0.4.2
  (with their DOIs). The Zenodo record of 0.1.0 does not have them; the next release will.

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
