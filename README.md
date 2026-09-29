# AI Product Advisor MVP

An AI-powered multimodal product recommendation assistant (Mirai Labs evaluation project).

## Make targets

```bash
make setup    # create venv, install dependencies
make ingest   # run offline pipeline: clean → index → fake-review flags
make run      # start Streamlit UI
make eval     # run evaluation harness (replay mode by default)
make test     # run pytest unit tests
make lint     # run ruff linter
make probe    # probe live LLM quotas and write configs/limits.yaml
```

## Status

Gate: **pending sign-off** — see `docs/SIGNOFF.md`.
No feature code before sign-off (AGENTS.md §Gate).
