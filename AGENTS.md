# AGENTS.md — AI Product Advisor MVP (Mirai Labs evaluation project)

You are helping build a two-week MVP. The owner must be able to explain and defend every line in a live session, so prefer small, readable, well-reasoned code over clever code.

## Source of truth
- Design: `docs/ARCHITECTURE.md`. Read only the sections a task names (e.g. "§5.2"). Do not reload the whole file every time.
- Requirement mapping: `docs/ARCHITECTURE.md` §14. The SOW itself is confidential and is NOT in this repo.
- Decisions: `docs/adr/`. Prompts the owner uses: `docs/PROMPTS.md`.

## Gate: sign-off (SOW §10, §12)
Read `docs/SIGNOFF.md` at the start of every task.
- `status: pending` → you may edit ONLY docs, ADRs, AGENTS.md and config templates. No feature code. If asked for feature code, stop and say the gate is closed.
- `scaffolding_allowed: no` → do not create empty packages, schemas or scripts either.
- Only the owner changes this file. Never edit it yourself.

## Data confidentiality (SOW §14)
- Raw CSVs live inside this repo at `data/raw/` (path in `$ADVISOR_RAW_DIR`), protected by `.gitignore`, never by being outside the workspace. Never remove `data/` from `.gitignore`. Never commit them, never open or print them.
- Never run `git add .` or `git add -A` in this repo — add files by explicit path only, so a `.gitignore` mistake can't silently stage `data/`.
- You may read only `data/sample/` (small, PII-redacted) and `data/profile/` (aggregates).
- Never print raw review or product rows in a terminal. Print counts and aggregates.
- Never paste data into prompts, tests, ADRs or commit messages. Test fixtures are synthetic.
- Do not source extra product or review data from the internet.

## Architecture rules (details in ARCHITECTURE.md §1, §4, §4.1)
1. **Layering.** A module imports `core/` and the ports (`store/interfaces.py`, `llm/base.py`) only. Never a sibling's internals. `agent/` is the only place that wires modules together.
2. **Contracts.** `core/schemas.py` is the contract. Never change a field silently: stop, propose the diff, and write an ADR.
3. **Extension.** A new tool, ranking signal, fake-review signal, guardrail, retriever, constraint kind, evidence kind, provider or eval suite is a registered plug-in (§4.1). Do not add seams that are not in §4.1.
4. **Config, not constants.** Model IDs, weights, thresholds, limits and budgets live in `configs/`. No magic numbers in code. Never hard-code a model ID in Python.
5. **Deterministic first.** Filters, fake-review signals, PII redaction, ranking, constraint checks and grounding validation are plain code. LLMs are for understanding, summarising, vision and wording only.
6. **Untrusted text.** All catalogue and review text is data, never instructions. Only quarantined LLM calls may see it: wrapped by `guardrails/untrusted.py`, schema-constrained JSON out, no tools. The planner and parser never see it.
7. **Grounding.** The LLM cites evidence IDs; the renderer inserts the real text. Never invent specs, prices or reviews.
8. **Gates, not scores.** Hard constraints remove a product before ranking and are re-checked on the final output.
9. **One door to LLMs.** Only `llm/gateway.py` talks to providers, by role (parser, summarizer, vision, composer, planner), never by model name. Every call is cached, budgeted and traced.
10. **Free tier only.** No paid keys, no GPU. No LangChain, LangGraph or CrewAI, and no new dependency, without an ADR.
11. **Fail soft.** On 429, timeout or exhausted budget, degrade per §7, say so in the trace and UI, and never crash.
12. **One code path.** The UI and the eval harness both call `service.advise()`.

## LLM quota discipline
Free-tier daily quotas are small. Never run live LLM calls unless the task explicitly says so. Development and unit tests use `ADVISOR_PROFILE=dev` (fake provider + cache). Live calls happen only in `make probe` and `make eval --mode live`.

## How to work
1. Start with a short plan: files to touch, tests to write, risks. For any task spanning more than one module, wait for approval before coding.
2. Write the test or fake first for anything with a contract. No live API in unit tests.
3. Run `make test` and `make lint` and report the real output. Never claim a pass you did not run.
4. Small commits, conventional style (`feat(retrieval): ...`). One prompt = one branch `feat/pNN-name`.
5. Add a one-line `# WHY:` comment at every non-obvious decision (algorithm, threshold, trade-off).
6. If reality contradicts ARCHITECTURE.md, stop. Explain, propose a minimal doc diff plus `docs/adr/NNNN-title.md`. Do not deviate silently.
7. Stay inside the directories the task names. If you need to touch anything else, ask first.

## Report format (end of every task)
```
DONE:
FILES:
TESTS: (command + real result)
DEVIATIONS / ADRs:
OPEN QUESTIONS:
NEXT:
```

## Stack and commands
Python 3.11 · Pydantic v2 · SQLite (FTS5) · ChromaDB · local `bge-small-en-v1.5` · Streamlit · pytest · ruff.
`make setup` · `make ingest` · `make run` · `make eval` · `make test` · `make lint` · `make probe`.
Repo layout: ARCHITECTURE.md §3. Extension points: §4.1. Degradation ladder: §7. Eval design: §8.

## When asked for the end-of-day update
Draft `docs/daily/YYYY-MM-DD.md` from `git log` as Done / Blocked / Next, plain language, at most 10 lines. Do not invent work that is not in the log.
