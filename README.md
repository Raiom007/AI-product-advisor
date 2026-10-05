# AI Product Advisor MVP (v1.0)

An AI-powered multimodal product recommendation assistant (Mirai Labs evaluation project).

## Prerequisites
- Python 3.11
- Windows PowerShell (or Bash)
- Valid API keys for Groq and Google Gemini

## One-Command Setup

In your terminal, create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

*Note: For Windows, we run the python modules directly instead of using GNU Make.*

## Data Setup & Ingestion

Since the raw datasets are git-ignored, you must run the offline ingestion pipeline first. This script will index the McAuley-Lab Amazon Reviews dataset (or your local `data/raw`) into SQLite and ChromaDB.

```powershell
python -m advisor.ingest --raw-dir "$env:ADVISOR_RAW_DIR" --db data/advisor.db --log data/processed/cleaning_log.jsonl --docs docs/data_cleaning.md
python -m advisor.ingest.build_index --db data/advisor.db --chroma data/chroma
```

## Running the Application

Set up your API keys and profile in your environment, then start the Streamlit UI:

```powershell
$env:ADVISOR_PROFILE="prod"
$env:GEMINI_API_KEY="your_api_key"
$env:GROQ_API_KEY="your_api_key"

python -m streamlit run src/advisor/ui/app.py
```

## Running the Evaluation Harness

To run the live 50-query End-to-End Evaluation Suite:

```powershell
python -m advisor.eval.run_eval --mode live --suite e2e
```

*Results are dumped to `eval/metrics.json` and formatted via `eval/eval_report.md`.*

## Status

Gate: **Approved** — MVP is complete (Code Freeze).
