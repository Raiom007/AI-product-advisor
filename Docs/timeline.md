# Timeline — AI Product Advisor MVP

Source: `Docs/ARCHITECTURE.md` §11.
Risk key: ⚠️ = high-risk item (scheduled earliest per §11 guidance).

> **Buffer note — Days 6–7:**
> PROMPTS.md §Index lists **eight prompts** (P13–P19) for Days 6–7.
> Parallelism is mandatory (see PROMPTS.md "Parallel agents" note).
> After P15 is merged, run P16 / P17 / P18 in parallel branches on disjoint directories (`ranking/`, `vision/`, `explain/`).
> After P12/P14 are merged, run P13 + P14 in parallel.
> **Do not attempt these days serially** — it will not fit in the time budget.
> Keep a 1-hour integration buffer each evening to resolve merge conflicts.

---

## Day-by-day plan

| Day | Date | Checkable end-of-day output | ⚠️ Risk | Prompt(s) |
|-----|------|-----------------------------|---------|-----------|
| 1 | Mon 28 Sep | Questions sent to Hemanth by **2:00 PM** · Private repo created and shared · SOW-derived data-cleaning checklist · Draft of `Docs/ARCHITECTURE.md` | | P0 |
| 2 | Tue 29 Sep | `Docs/ARCHITECTURE.md` v0.2 + `docs/timeline.md` + 6 ADR seeds + `docs/architecture_audit.md` submitted by **6:00 PM** · Repo, rules, gate committed (`chore: repo, rules, architecture v0.2`) · No feature code | | P1 |
| 3 | Wed 30 Sep | Repo skeleton (`src/advisor/` packages) · `core/schemas.py` exactly as §4 · `configs/*.yaml` stubs · Data profiled (`data/profile/profile.md` + `profile.json`) · `data/sample/` (200 products, PII-redacted) · SQLite loaded with cleaned products + reviews · `docs/data_cleaning.md` + `data/processed/cleaning_log.jsonl` · `make setup && make test` green | ⚠️ Spec parsing fidelity drives "0 violations" criterion | P2, P3, P4, P5, P6 |
| 4 | Thu 1 Oct | FTS5 + ChromaDB indices built · Hybrid retrieval (BM25 + semantic + RRF) working · Naive baseline (`eval/baseline.py`) · `scripts/probe_models.py` run → `configs/limits.yaml` filled · LLM gateway (`llm/gateway.py`) with cache / rate-limiter / fake provider passing tests | ⚠️ Free-tier model availability — probe on Day 4 morning; gate blocks everything downstream | P7, P8, P9, P10 |
| 5 | Fri 2 Oct | First **25 gold queries** labelled (pooled method) · Retrieval NDCG@5 vs baseline numbers on dev set · Fake-review detector v1: precision/recall on 50 seeded dev fakes ≥ 80/70 · Guardrails skeleton + adversarial test set · **Mid-point review with Zuhair** | ⚠️ Gold labelling is time-consuming; start pool on Day 4 to have labels ready | P10 (labels), P11, P12 |
| 6 | Mon 5 Oct | Query understanding + clarify (`understanding/`) · Review summariser + use-case sentiment (`reviews/`) · Agent state machine + tools + tracer wired · Guardrail hooks wired · `service.advise()` callable end-to-end (no ranking yet) | *See buffer note above — parallelise P13 + P14 after P12/P14 merge* | P13, P14, P15 |
| 7 | Tue 6 Oct | Visual verifier (`vision/`) · Ranking + explainer (`ranking/`, `explain/`) · Composer + grounding validator · Streamlit chat + trace tab + fake-review inspector · End-to-end demo path produces a grounded `AdvisorResponse` | *See buffer note above — parallelise P16/P17/P18 after P15 merge* | P16, P17, P18, P19 |
| 8 | Wed 7 Oct | Remaining **25 gold queries** (test set) labelled · Image claims dataset (≥ 30 hand-checked) · Adversarial set complete (≥ 10, aim 20) · `make eval` produces a full metrics report · Weights tuned on dev set **only** | | P20 |
| 9 | Thu 8 Oct | Eval report with ≥ 3 concrete failure analyses (`eval/reports/eval_report.md`) · `README.md` complete · `docs/user_guide.md` · Demo video recorded · UI polish · **Code freeze 6:00 PM** | | P20, P21 |
| 10 | Fri 9 Oct | Live defense · Rehearse "why A above B" from `explain_rank.py` output · Kill-network degradation demo · Hostile review injection live | | P22 |

---

## Riskiest items — scheduled earliest

| # | Risk | Scheduled | Why first |
|---|------|-----------|-----------|
| ⚠️ 1 | **Free-tier model availability** — `gemini-2.0-flash` and `text-embedding-004` reportedly shut down; real RPM/RPD/TPM unknown | Day 4 morning (`make probe`) | Every LLM-dependent module (understanding, summariser, vision, composer) is blocked until limits are confirmed. |
| ⚠️ 2 | **Spec parsing + constraint fidelity** — messy CSV columns, unknown format variants; drives the "0 hard-constraint violations" criterion | Day 3 (P6) | The hard-constraint gate is re-checked on every final output; failure here cascades to ranking, grounding, and the graded eval. |
| ⚠️ 3 | **Gold labelling** — 50 queries × pool-then-label is slow; graded relevance (0–3) requires human judgment | Pool starts Day 4, labels locked Day 5 (dev) + Day 8 (test) | NDCG@5 and Recall@10 cannot be reported without labels; delay blocks the entire eval section of the SOW. |
