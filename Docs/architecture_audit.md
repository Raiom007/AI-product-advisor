# Architecture Audit — ARCHITECTURE.md vs SOW

**Date:** 2026-09-29
**Auditor:** Antigravity agent (P1 task)
**Method:** Cross-referenced all SOW section numbers cited in `Docs/ARCHITECTURE.md` (§1–§13) with the components described in that same document. The SOW PDF is confidential and not in the repo; this audit works from the SOW requirements as quoted or referenced in ARCHITECTURE.md and §12 (open questions). Any finding marked **(Q#)** has a corresponding question already in §12; new questions are labelled **(NEW-Q)**.

> **Note:** Because the SOW itself is not attached, this audit cannot enumerate every SOW requirement — only those whose section numbers appear in ARCHITECTURE.md. Submit this document together with the architecture doc and flag any SOW sections not cited there.

---

## 1. SOW requirements with no owning component

| SOW Ref | Requirement (as described in ARCHITECTURE.md) | Gap |
|---------|-----------------------------------------------|-----|
| SOW §3.7 | "Daily commit + end-of-day update (done/blocked/next)" — listed as a process requirement | No code component owns this; it is a manual habit. No tooling is described to enforce or verify it. **Proposed:** `docs/daily/` convention + `make daily` target in the Makefile to draft the update from `git log`. |
| SOW §5 | Data-cleaning checklist is required as a deliverable | `docs/data_cleaning.md` is referenced as output of `make ingest`, but no component is assigned to *create* it before sign-off. The cleaning rules are not yet decided (depends on data delivery — see Q4 in §12). |
| SOW §6.2 | Tracing format specified as a deliverable | `core/tracing.py` owns the trace format (§5.11) but the *UI trace tab* that renders it is mentioned only in §2 and §5 without a component spec. No dedicated §5.N section covers the trace viewer layout, required fields shown, or linkage to `eval/`. |
| SOW §8 | NDCG@5, Recall@10, fake precision/recall, visual agreement, guardrail pass rate, median/p95 latency, calls/request, groundedness rate | All metrics are listed in §8, but `eval/metrics.py` is mentioned only as a filename. No specification exists for how groundedness rate is computed (share of statements with valid evidence IDs) — this needs a deterministic function and a denominator definition. |
| SOW §8 | "Report must list the 10 worst queries" | `report.py auto-lists the 10 worst queries` (§8) — but no component spec for `report.py` exists beyond the filename in §3. |
| SOW §3.9 | Component-level eval suites (retrieval-only, detector-only, parser-only, vision-only, guardrails-only) | §8 lists these but no ownership row in §3 or §5 assigns them to a module. `eval/suites/` appears in the README project structure but not in the ARCHITECTURE.md §3 layout tree. |
| SOW §12.2 | "One-command `make eval` reproduces numbers" | Covered in §13 DoD, but `make probe` (which writes `limits.yaml`) is a pre-condition for `make eval --mode live` — the ordering dependency is not documented as a required step in the onboarding sequence. |
| SOW §7 | Single user / single machine / localhost only | Assumption A1 captures this, but there is no documented test or acceptance criterion verifying the system *works on a clean machine* with only `make setup && make ingest && make run`. §13 bullet 3 lists it as a DoD item but without a CI gate. |

---

## 2. Ambiguities requiring clarification from Hemanth

These are in addition to the 10 questions already in §12. Items from §12 are reproduced where they affect design decisions not yet resolved.

| ID | Ambiguity | Why it blocks design |
|----|-----------|---------------------|
| Q1 (§12) | Which Gemini model IDs are currently on the free tier? `gemini-2.0-flash` reportedly shut down 1 Jun 2026. | `configs/models.yaml` candidates cannot be filled until Day-1 probe confirms available models. The SOW's suggested model IDs are stale. |
| Q4 (§12) | When do the CSVs arrive? Is there a data dictionary (product↔review join key, price column currency, image URL separator character)? | `configs/data.yaml` column mappings cannot be filled. `specs_parser.py` key vocabulary cannot be drafted. The entire ingest pipeline depends on this. |
| Q5 (§12) | Fake-review precision/recall: seeded only, or do organic flags count as false positives? May seeded fakes be LLM-generated? | Affects `scripts/make_seeded_fakes.py` design and the reported metric interpretation. LLM-generated fakes consume quota if run live. |
| Q7 (§12) | Is the "median < 20 s" latency target measured cold-cache (live) or warm-cache (replay)? | Vision calls over free-tier Gemini can easily exceed 20 s cold. If replay is acceptable, the target is easily met; if cold-cache only, vision may need to be skipped in the graded run. |
| Q8 (§12) | On abstention: show labelled nearest alternatives, or strictly refuse? | §5.7 explicitly marks this as "open question (§12)." The `AdvisorResponse` schema has `status=abstained` but no `nearest_alternatives` field — adding one after sign-off would be a schema change requiring an ADR. **Decision should be made before sign-off.** |
| NEW-Q1 | What is the Hinglish input frequency in real user queries? | ARCHITECTURE.md assumes Hinglish normalisation to `query_en` is sufficient for retrieval. If >30% of gold queries are Hinglish, the `bge-small-en-v1.5` embedding quality may be too low and a multilingual fallback may be required on Day 3, not Day 7. |
| NEW-Q2 | What is the expected number of hard constraints per query? | §5.3 produces `hard: list[Constraint]`. The verifier loops check each; performance under many constraints is not benchmarked. Knowing typical constraint count helps size the spec-parser test set. |
| NEW-Q3 | Does the SOW require a multi-turn conversation, or is each query independent? | §5.3 mentions `AWAIT_USER` state for clarification and "session store = in-memory dict, single session." It is unclear whether the SOW requires full multi-turn history (the LLM seeing previous exchanges) or only clarification loops. A full multi-turn chat changes the context assembly in `agent/`. |
| NEW-Q4 | What is the expected image-URL format and failure rate? | §5.1 says "Don't validate 20k URLs at ingest; validate lazily." If the dataset has a >50% broken-URL rate, vision verification on the top-3 products may always degrade, making the visual agreement metric meaningless. |
| NEW-Q5 | Is the `make probe` target required to be run before submission, or only documented? | `probe_models.py` writes `configs/limits.yaml`, which is a committed config file. If probe results change day-to-day (free tier is unstable), the committed `limits.yaml` may be stale by the defense date. |

---

## 3. Internal contradictions in ARCHITECTURE.md

| # | Location | Contradiction | Proposed resolution (diff-style) |
|---|----------|---------------|----------------------------------|
| C1 | §3 layout tree vs. README `Project Structure` | §3 shows `docs/` (lowercase) but the actual directory in the repo is `Docs/` (capital D). The README project structure block also uses `docs/`. | `- docs/  ARCHITECTURE.md  data_cleaning.md  timeline.md  user_guide.md  eval_report.md` → keep as `Docs/` in the tree, or rename the directory. Rename is preferred for cross-platform consistency. |
| C2 | §3 layout tree vs. §8 | §3 does not list `eval/suites/` but §8 describes five component-level eval suites. `eval/` in §3 shows only `data/`, `baseline.py`, `metrics.py`, `run_eval.py`, `report.py`, and `reports/`. | `+ eval/suites/   retrieval_suite.py  detector_suite.py  parser_suite.py  vision_suite.py  guardrail_suite.py` should be added to the §3 tree. |
| C3 | §3 layout tree vs. README `Project Structure` | README lists `configs/features.yaml` and `configs/profiles/` but §3 shows only `models.yaml`, `limits.yaml`, `ranking.yaml`, `fakes.yaml`, `data.yaml`. `features.yaml` is required by the registry (`enabled()` check in ADR 0004). | `+ configs/features.yaml` and `+ configs/profiles/   dev.yaml  eval.yaml  demo.yaml` should be added to the §3 tree. |
| C4 | §5.9 vs. §6 | §5.9 states the `RequestBudget` has `max_model_calls=12` (default) and the call budget is "cap 12." §6 describes the expected call count as "≈ 8, cap 12." These are consistent, but §5.9 also lists "per-role caps (e.g. vision ≤ 3)" without specifying all per-role caps. The vision default is mentioned in §5.5 as `images_per_product` (default 3) but this is not the same as a per-role call cap. | Clarify in §5.9: list all per-role call caps (parser ≤ 1, summarizer ≤ 3, vision ≤ 3, composer ≤ 1, planner ≤ 2) so `configs/limits.yaml` can be pre-populated with the right keys. |
| C5 | §5.3 vs. §5.10 | §5.3 states the session store is "in-memory dict, single session." §5.10 says `AgentState` is "serialisable so clarification can resume." These are compatible but the clarification resume path requires the in-memory dict to survive between HTTP requests. Streamlit reruns on every interaction; a plain `dict` would be lost. | Add a note: "Session store is `st.session_state` (Streamlit) or a process-level dict keyed by `session_id`; serialisability is for future persistence only." |
| C6 | §4 (`AdvisorResponse`) vs. §5.7 (abstention) | `AdvisorResponse.status` includes `abstained`, but §5.7 opens the question of whether to show "labelled nearest alternatives." If implemented, this requires a `nearest: list[Recommendation]` field on `AdvisorResponse` — a schema change. The schema is defined as a contract (§1 principle 2) and changing it requires an ADR. The question in §12 is open at the time of writing. | Before sign-off, decide the abstention behaviour and add or explicitly exclude the field. If excluded, add a note to §4 schema: "nearest_alternatives intentionally absent — see ADR 0007 (if created)." |
| C7 | §11 plan vs. PROMPTS.md index | §11 shows Day 3 as "schemas, configs" but PROMPTS.md P2 (skeleton) and P3 (schemas) are separate prompts both assigned to Day 3. P2 explicitly says "Do NOT implement schemas yet." This is consistent but the §11 table collapses them into one row, making it look like Day 3 is achievable in one step. | `- Day 3: Repo skeleton, schemas, configs` → `+ Day 3: Repo skeleton (P2) + contracts/schemas (P3) + data profiling (P4) + cleaning (P5) + spec parser (P6 starts)`; note that P6 may spill into Day 4. |
| C8 | §5.4 fake-review leakage warning vs. §11 plan | §5.4 says "generate ≥100 seeded fakes" (50 dev / 50 test) and to report precision/recall on the test split only. §11 Day 5 says "fake-review detector v1 on seeded dev fakes." The dev/test split for fakes is only mentioned in §5.4, not in the §11 plan or §8 eval table, creating a risk of accidentally tuning on the test split. | Add to §11 Day 5: "(weights tuned on dev-50 seeded fakes only; test-50 held out until Day 8 `make eval`)" and add to §8: "Seeded fakes: 50 dev (for tuning) / 50 test (reported)." |
