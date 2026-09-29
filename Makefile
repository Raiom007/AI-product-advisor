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
	@echo "not implemented yet (P5 — data cleaning + SQLite load)"

run:
	@echo "not implemented yet (P19 — Streamlit UI)"

eval:
	@echo "not implemented yet (P20 — full eval harness)"

probe:
	@echo "not implemented yet (P9 — LLM model probe + limits.yaml)"
