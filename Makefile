# ==============================================================================
# Makefile — disslucc-benchmark
# Reproducible validation of disslucc against the LuccME 3.1 labs (TerraME goldens)
# ==============================================================================

SHELL := /bin/bash
PY ?= python3
LAB ?=

.PHONY: help install benchmark coverage references timing pins test clean
REPS ?= 5
GOLDENS ?= ../luccme-goldens
REF ?=
DOI ?=

help:
	@echo "disslucc-benchmark — Command Reference"
	@echo "------------------------------------------------------------------"
	@echo "  make install              Install disslucc (pinned) and dependencies"
	@echo "  make benchmark            Run every scenario and compare with the goldens"
	@echo "  make benchmark LAB=lab03  Run one scenario (names are in benchmarks/luccme_labs/labs.toml)"
	@echo "  make coverage             Which of the 21 LuccME labs disslucc covers"
	@echo "  make references           Download and SHA-256-verify every pinned reference file"
	@echo "  make timing [REPS=5]      Time and peak memory of the scenarios (informational; LAB=lab03 for one)"
	@echo "  make pins REF=v1.1.0      Re-pin references.toml to a luccme-goldens ref (GOLDENS=../luccme-goldens DOI=...)"
	@echo "  make test                 pytest wrapper around the scenarios"
	@echo "  make clean                Remove downloaded references and reports"

install:
	$(PY) -m pip install -r requirements.txt

benchmark:
	$(PY) benchmarks/luccme_labs/run.py $(LAB)

coverage:
	$(PY) benchmarks/luccme_labs/run.py --coverage

references:
	$(PY) -c "import sys; sys.path.insert(0, 'benchmarks/luccme_labs'); import references as r; [r.fetch(p) for p in r.SPEC['files']]; print(len(r.SPEC['files']), 'files verified at', r.COMMIT)"

timing:
	$(PY) benchmarks/luccme_labs/timing.py $(LAB) --reps $(REPS)

pins:
	@test -n "$(REF)" || (echo "usage: make pins REF=v1.1.0 [GOLDENS=../luccme-goldens] [DOI=10.5281/zenodo.N]"; exit 2)
	$(PY) benchmarks/luccme_labs/pin_references.py --goldens $(GOLDENS) --ref $(REF) $(if $(DOI),--doi $(DOI),)

test:
	$(PY) -m pytest -q

clean:
	rm -rf .cache reports benchmarks/luccme_labs/__pycache__ .pytest_cache
