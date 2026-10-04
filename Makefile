# ==============================================================================
# Makefile — disslucc-benchmark
# Reproducible validation of disslucc against the LuccME 3.1 labs (TerraME goldens)
# ==============================================================================

SHELL := /bin/bash
PY ?= python3
LAB ?=

.PHONY: help install benchmark coverage references test clean

help:
	@echo "disslucc-benchmark — Command Reference"
	@echo "------------------------------------------------------------------"
	@echo "  make install              Install disslucc (pinned) and dependencies"
	@echo "  make benchmark            Run every scenario and compare with the goldens"
	@echo "  make benchmark LAB=lab03  Run one scenario (names are in benchmarks/luccme_labs/labs.toml)"
	@echo "  make coverage             Which of the 21 LuccME labs disslucc covers"
	@echo "  make references           Download and SHA-256-verify every pinned reference file"
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

test:
	$(PY) -m pytest -q

clean:
	rm -rf .cache reports benchmarks/luccme_labs/__pycache__ .pytest_cache
