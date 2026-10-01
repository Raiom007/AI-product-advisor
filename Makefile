# WHY: Makefile chosen over shell scripts so every task has a one-word name
# that is the same on every machine (SOW requirement, §9 "Repro" row).
.PHONY: setup test lint ingest run eval probe

# Cross-platform venv Python detection.
# WHY: Windows puts the interpreter under Scripts/, Unix under bin/.
ifeq ($(OS),Windows_NT)
    VENV_PYTHON := .venv/Scripts/python.exe
    VENV_PIP    := .venv/Scripts/pip.exe
else
    VENV_PYTHON := .venv/bin/python
    VENV_PIP    := .venv/bin/pip
endif

# ---------------------------------------------------------------------------
setup:
	python -m venv .venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install -e .
	$(VENV_PYTHON) -c "\
from pathlib import Path; \
[Path(d).mkdir(parents=True, exist_ok=True) for d in [\
'data/raw','data/sample','data/profile',\
'data/processed','data/cache','data/index','data/traces']];\
print('data/ directories created (gitignored)')"

# ---------------------------------------------------------------------------
test:
	$(VENV_PYTHON) -m pytest

# ---------------------------------------------------------------------------
lint:
	$(VENV_PYTHON) -m ruff check src tests

# ---------------------------------------------------------------------------
# Targets below are stubs until the relevant prompts are implemented.
# ---------------------------------------------------------------------------
ingest:
	$(VENV_PYTHON) -m advisor.ingest \
	    --raw-dir "$${ADVISOR_RAW_DIR:-data/dev_fixtures}" \
	    --db data/advisor.db \
	    --log data/processed/cleaning_log.jsonl \
	    --docs docs/data_cleaning.md
	$(VENV_PYTHON) -m advisor.ingest.build_index \
	    --db data/advisor.db \
	    --chroma data/chroma


run:
	$(VENV_PYTHON) -m streamlit run src/advisor/ui/app.py

eval:
	$(VENV_PYTHON) -m advisor.eval.run_eval --mode replay --suite e2e
	$(VENV_PYTHON) -m advisor.eval.report

probe:
	$(VENV_PYTHON) scripts/probe_models.py
