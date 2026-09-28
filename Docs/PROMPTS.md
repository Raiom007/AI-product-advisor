# PROMPTS.md — building the AI Product Advisor MVP with Antigravity

Companion to `docs/ARCHITECTURE.md` (v0.2) and the root `AGENTS.md`. Every prompt below is meant to be pasted into an Antigravity agent conversation as-is. Section numbers (§) refer to ARCHITECTURE.md.

---

## 1. One-time setup (about 10 minutes, by hand)

1. Create the private GitHub repo (SOW Day 1) and clone it. Put these three files in it:
   - `AGENTS.md` at the repo root
   - `docs/ARCHITECTURE.md`
   - `docs/PROMPTS.md` (this file)
2. Put the raw CSVs **outside** the repo, e.g. `~/mirai-data/raw/`, and export `ADVISOR_RAW_DIR=~/mirai-data/raw`. Agents work from `data/sample/` and `data/profile/` only (see the confidentiality rules in AGENTS.md, SOW §14).
3. Open the repo folder as the Antigravity workspace.
4. Verify the rules loaded. In a new conversation ask: *"List the rules you loaded from AGENTS.md and tell me the status in docs/SIGNOFF.md."* If it cannot answer, the file is not being picked up; check your Antigravity version's rules location (`.agents/rules/` is the documented default, and a root `AGENTS.md` is read too).
5. Set the terminal policy to **ask before running commands** while you learn what the agent does. The SOW says code you cannot explain is code you did not write.

## 2. How to use ARCHITECTURE.md with an agent

- **Do not paste it into the rules file.** Rules files are size-capped (one guide reports 12,000 characters per file), and ARCHITECTURE.md is far larger. `AGENTS.md` is the short always-on layer; ARCHITECTURE.md is the on-demand layer.
- **Reference it by section in every prompt**: `@docs/ARCHITECTURE.md §5.6`. Attach the file with `@` and name the section so the agent reads the part it needs and nothing else.
- **Treat it as a contract.** Contracts (§4) and seams (§4.1) do not change silently. If the code needs to deviate, the agent stops and proposes a doc diff plus an ADR (use U4 below).
- **Keep it true.** When a decision changes, update the doc first (or in the same commit). On Day 9 the doc is rewritten to "as-built".
- **Use §13 and §14 as checklists.** §13 is the foundation's definition of done. §14 maps every SOW requirement to a component and a proof.

### The loop (every prompt)
1. **New conversation per prompt.** Clean context; AGENTS.md re-anchors it.
2. **Plan first.** Read the plan the agent proposes. Reject it if it touches files outside the named directories.
3. **Approve, let it build, then read the diff.** You are the reviewer; run U3 (conformance review) on anything non-trivial.
4. **Run the tests yourself** (`make test`), not just the agent.
5. **Commit on a branch** `feat/pNN-name`, merge when green.
6. **Log surprises** as ADRs (`docs/adr/`), because the defense asks for every micro-decision.

### Parallel agents (use the Manager view for these only)
Run in parallel **only when directories are disjoint**, each on its own branch:
- After P3: **P9** (`llm/`), **P10** (`eval/`), **P12** (`guardrails/`)
- After P12/P14: **P13** (`understanding/`) with **P14** (`reviews/`)
- After P15: **P16** (`ranking/`), **P17** (`vision/`), **P18** (`explain/`)

Everything else is sequential. Days 6–7 in the plan carry eight prompts, so parallelism there is not optional.

---

## 3. Index

| # | Prompt | Day | Needs sign-off? | Human step after |
|---|---|---|---|---|
| P0 | Repo, rules, gate | 1 | no | share repo with Mirai Labs |
| P1 | Timeline, ADR seeds, SOW audit | 1–2 | no (docs only) | submit doc + timeline by Tue 6 PM |
| — | **SIGN-OFF GATE** | 2 | — | set `status: approved` in `docs/SIGNOFF.md` |
| P2 | Skeleton, tooling, kernel | 3 | yes | — |
| P3 | Contracts + extension-point test | 3 | yes | — |
| P4 | Data profiling | 3 | yes | review `profile.md`, decide cleaning rules |
| P5 | Cleaning, PII, injection flags, SQLite | 3 | yes | read `data_cleaning.md` |
| P6 | Spec parser, constraint kinds, filters | 3–4 | yes | hand-fill 30 expected spec parses |
| P7 | Indices + embedder | 4 | yes | — |
| P8 | Hybrid retrieval + naive baseline | 4 | yes | — |
| P9 | LLM layer + probe | 4 | yes | run `make probe`, choose models |
| P10 | Eval skeleton + labelling tools | 4–5 | yes | write and label queries by hand |
| P11 | Fake-review detector + seeded fakes | 5 | yes | — |
| P12 | Guardrails + adversarial set | 5–6 | yes | — |
| P13 | Query understanding | 6 | yes | supply 15+15 golden queries |
| P14 | Review summariser + sentiment | 6 | yes | — |
| P15 | Agent core + service | 6 | yes | — |
| P16 | Ranking | 6–7 | yes | — |
| P17 | Vision | 7 | yes | hand-check 30 image claims |
| P18 | Explanation + grounding | 7 | yes | — |
| P19 | UI | 7 | yes | — |
| P20 | Full eval, tuning, report | 8–9 | yes | write the failure analysis in your words |
| P21 | Docs, README, demo script, freeze | 9 | yes | record the demo |
| P22 | Defense rehearsal | 9–10 | yes | answer the questions aloud |
| P23 | Extension proof (optional) | after | yes | — |
| U1–U5 | Utility prompts | any | — | — |

---

## 4. Prompts

### P0 — Repo, rules and gate  *(Day 1 · allowed now)*
```
Set up the project workspace. Documentation and config only, no feature code.

1. Read AGENTS.md and docs/ARCHITECTURE.md §3 (layout) and §11 (plan).
2. Create: README.md (stub with the one-line project description and the make targets from AGENTS.md),
   .gitignore, .env.example, docs/adr/.gitkeep, docs/daily/.gitkeep.
3. .gitignore must exclude: .env, data/, *.sqlite, *.db, .venv/, __pycache__/, .chroma/, *.csv, and any file under a private/ folder.
4. .env.example lists GEMINI_API_KEY, GROQ_API_KEY, ADVISOR_RAW_DIR, ADVISOR_PROFILE with NO real values.
5. Create docs/SIGNOFF.md containing exactly these three lines:
     status: pending
     scaffolding_allowed: no
     updated: 2026-09-28
6. Do NOT create Python code, requirements.txt, empty packages or a Makefile yet.
7. git init on branch main; first commit: "chore: repo, rules, architecture v0.2".
8. Print (do not run) the git commands to add the private GitHub remote and push.

Finish with the report format from AGENTS.md.
```

### P1 — Timeline, ADR seeds, SOW audit  *(Day 1–2 · docs only)*
Attach the SOW PDF **to this conversation only**. Do not commit it.
```
Docs only. Three tasks.

A. Create docs/timeline.md from @docs/ARCHITECTURE.md §11: for each of the 10 days a concrete, checkable end-of-day output; mark the 2–3 riskiest items and show they are scheduled earliest;
   add a column "Prompt(s)" mapping days to P-numbers in docs/PROMPTS.md; add a buffer note for Days 6–7.

B. Create ADR seeds in docs/adr/ using this template: Context / Decision / Alternatives rejected / Consequences.
   0001 no orchestration framework (plain-Python plan executor)
   0002 SQLite + ChromaDB
   0003 local embeddings (bge-small-en-v1.5)
   0004 registry pattern for extension points
   0005 LLM roles with ordered candidate lists
   0006 deterministic-first, LLM-second
   Source the reasoning ONLY from ARCHITECTURE.md §1, §5, §9, §10. Do not invent new rationale.

C. Audit ARCHITECTURE.md against the attached SOW. Write docs/architecture_audit.md with:
   (1) every SOW requirement that has no owning component,
   (2) ambiguities that should be questions for Hemanth,
   (3) places where ARCHITECTURE.md contradicts itself.
   Do NOT edit ARCHITECTURE.md; list proposed edits as a diff-style bullet list.

Report format from AGENTS.md.
```
**Then stop.** Submit the architecture doc and timeline by Tue 29 Sep, 6:00 PM. After Mirai Labs signs off, edit `docs/SIGNOFF.md` yourself to `status: approved` (and `scaffolding_allowed: yes`).

---

### P2 — Skeleton, tooling, kernel  *(Day 3)*
```
Gate check: docs/SIGNOFF.md must say status: approved, otherwise stop.
Read @docs/ARCHITECTURE.md §3, §4 (intro), §4.1, §5.9 (cache and budget only), §5.11, §9 (Repro, Config, Tests rows).

Create:
- Repo skeleton exactly as §3 (packages with __init__.py; empty dirs with .gitkeep).
- requirements.txt with pinned versions, ONLY libraries justified in §9. Makefile targets: setup ingest run eval test lint probe
  (ingest/run/eval/probe may print "not implemented yet"). ruff + pytest config.
- configs/*.yaml with the keys named in §3 and placeholder values; profiles dev/eval/demo.
- Kernel in src/advisor/core/: config.py (YAML + env, profile selection, stable config hash), registry.py (generic Registry[T] and the decorator style shown in §4.1),
  events.py (tiny synchronous pub/sub), errors.py (incl. BudgetExceeded), tracing.py (JSONL spans per §5.11), budget.py (RequestBudget per §5.9),
  cache.py (disk cache keyed by hash), manifest.py (RunManifest builder), prompts.py (loads prompts/*.md, returns text + sha256).
- Do NOT implement schemas yet (next prompt).

Tests: registry (register/get/enabled, duplicate-name error), config profile + hash stability, budget exhaustion raises BudgetExceeded,
tracing writes valid JSONL with parent/child spans, cache round-trip, prompt hash changes when the file changes.

Acceptance: `make setup && make test` is green in a fresh venv. Plan first; wait for my approval.
```

### P3 — Contracts + extension-point test  *(Day 3)*
```
Read @docs/ARCHITECTURE.md §4 and §4.1 in full.

1. Implement src/advisor/core/schemas.py EXACTLY as §4: names, fields, types, Literals. Add the generic ToolResult[T] envelope. Add Verdict and GuardResult types where §4.1 needs them.
2. Create core/registries.py instantiating the registries listed in §4.1 (tools, verifiers, ranking_signals, fake_signals, guardrails, constraint_kinds, evidence_kinds, retrievers, providers, eval_suites),
   with decorators (@tool, @verifier, @ranking_signal, @fake_signal, @guardrail(stage=...), @constraint_kind, @evidence_kind, @retriever, @suite) and a features.yaml-driven `enabled()`.
3. Runtime validation: an unknown Constraint.kind or EvidenceRef.kind is rejected by the registry check, not by the schema.
4. Tests: tests/test_schemas.py (validation, JSON round-trip, `ext` preserved, RunManifest stamped on AdvisorResponse);
   tests/test_extension_points.py: from OUTSIDE core/, register a dummy tool, ranking signal, fake signal and guardrail and prove each is discoverable via `enabled()` with zero edits to core.
   (I will ask you to extend this test in P15 and P16 so it runs through the real executor and scorer.)

Do not change any contract field without asking me first. Acceptance: tests green, and show me a ScoreBreakdown containing a dummy signal.
```

### P4 — Data profiling  *(Day 3 · human review after)*
```
Read @docs/ARCHITECTURE.md §5.1 (intro + table) and §0 A4.

The CSVs are at $ADVISOR_RAW_DIR, outside the workspace. Implement src/advisor/ingest/profile.py to read them and write ONLY aggregates to data/profile/profile.md and profile.json:
row counts; column names, types and null rates; duplicate rates (exact and normalised name+brand); price stats and outliers (discounted > retail, <= 0, non-numeric formats);
category-tree depth and top categories; spec-text format variants (pattern counts, no raw rows); image URLs per product, separators and a malformed-URL count (do NOT fetch any URL);
review coverage (reviews per product distribution, orphan rate, date range, reviewer concentration); PII regex hit counts; injection-phrase hit counts.
Also write data/sample/: 200 products with their reviews, PII-redacted, for agents and tests to use.

Never print raw rows. Report the aggregate findings and propose configs/data.yaml column mappings.
STOP after this. I will review profile.md and decide the cleaning rules.
```

### P5 — Cleaning, PII, injection flags, SQLite  *(Day 3)*
```
Read @docs/ARCHITECTURE.md §5.1 (whole), §5.8 (PII and injection rows), §4 (EvidenceRef ids).
Inputs: the column mappings and cleaning decisions I approved after reviewing profile.md:
<<PASTE YOUR DECISIONS HERE>>

Implement:
- ingest/clean_products.py and ingest/clean_reviews.py per the §5.1 table (prices -> float with effective price = discounted; category tree split cat_l1/l2/l3 and taxonomy table;
  duplicates -> canonical + alias_ids with reviews re-pointed; NULL never imputed; orphan reviews -> quarantine table; exact-duplicate reviews counted BEFORE dropping).
- guardrails/pii.py: Indian mobile incl. +91 forms, email, Aadhaar (12 digits + Verhoeff), PAN, card-like numbers (Luhn). Redaction happens at ingest; only redacted text is stored for the app.
- guardrails/injection.py: heuristic phrase flags. Flag, never delete.
- store/sqlite_store.py: schema + loader for products, product_specs (stable ids spec:{pid}:{n}), reviews, review_flags (empty for now), taxonomy, quarantine, image_check_cache.
- Every cleaning decision -> data/processed/cleaning_log.jsonl (rule, before/after counts, example ids only). Generate docs/data_cleaning.md from the log with justifications I can defend aloud.

Tests: synthetic fixtures for each PII type (true positives AND near-miss negatives), injection phrases, duplicate merge, orphan quarantine, idempotent re-run.
Acceptance: running `make ingest` twice produces an identical DB hash.
```

### P6 — Spec parser, constraint kinds, filters  *(Day 3–4 · riskiest item for "0 violations")*
```
Read @docs/ARCHITECTURE.md §5.1 (Specs row), §4.1 (constraint_kinds), §5.3 (post-parse sanity checks), §5.6 (gate).

Implement:
- ingest/specs_parser.py: free-text spec -> {key: value} with normalised units (weight kg, screen inch, RAM/storage GB, battery mAh, port counts and types), driven by vocabulary files in domain/electronics/ (data, not code).
  Keep the original spec lines with stable ids. Unknown keys are kept under `raw`, never dropped.
- Registered constraint kinds: category, brand_exclude, budget, must_have, size_limit, weight_limit. Each has check(product, constraint) -> True | False | None (None = unverifiable)
  and honours unverifiable_policy from configs/ranking.yaml (default: exclude).
- retrieval/filters.py: constraints -> SQL allow-list of product_ids.

Tests: table-driven parser tests over data/sample (create the fixture file with 30 products and leave expected values for ME to fill by hand);
a property test that the gate never returns a product that fails any hard constraint; unverifiable handling for must-have vs soft.
Report parse coverage per key (% of products with a value) so we know which constraints are actually checkable.
```

### P7 — Indices and embedder  *(Day 4)*
```
Read @docs/ARCHITECTURE.md §5.2, §9 (Embeddings, Vector store, Keyword rows).

Implement store/interfaces.py (KeywordIndex, VectorIndex, Embedder ports), FTS5 virtual tables products_fts and reviews_fts in sqlite_store.py,
store/vector_store.py (Chroma persistent, collections `products` and `reviews`, metadata product_id, price, cat_l1..l3, brand, flagged),
a local bge-small-en-v1.5 Embedder adapter (registered under providers), and ingest/build_index.py wired into `make ingest`.
Batch embeddings, show progress, make the build resumable. Texts embedded are the REDACTED texts only.

Tests: ports have contract tests run against a fake adapter and the real one; allow-list restricted search never returns ids outside the allow-list; rebuild is idempotent.
Report index sizes and build time (aggregates only).
```

### P8 — Hybrid retrieval + naive baseline  *(Day 4)*
```
Read @docs/ARCHITECTURE.md §5.2 and §8 (Baseline row).

Implement retrieval/keyword.py, semantic.py, hybrid.py: four rankings (keyword and semantic, over products and over reviews), all restricted to the allow-list from filters;
aggregate review hits to products; fuse with Reciprocal Rank Fusion (k from config); shortlist size from config (default 8, range 5–10).
Register each as a retriever; hybrid fuses whatever features.yaml enables.
Implement eval/baseline.py: the SOW naive baseline = keyword search over product name + description, ranked by rating.
CLI: `python -m advisor.retrieval.demo "<query>"` prints ids, names, prices, scores and which retriever contributed. No LLM calls anywhere in this prompt.

Tests: RRF on toy rankings with known output; allow-list never violated; disabling a retriever in features.yaml changes results; baseline is deterministic.
Report per-stage latency on the real index (aggregates only).
```

### P9 — LLM layer + probe  *(Day 4 · parallel-safe with P10, P12)*
```
Read @docs/ARCHITECTURE.md §5.9, §7, §9 (LLM rows), §0 A3, A6, A7.

Implement in src/advisor/llm/: base.py (LLMProvider port: complete, structured(schema), capabilities; plus the Embedder port import), gemini.py (google-genai SDK), groq.py,
fake.py (deterministic test double that can simulate 429, 5xx, timeouts, malformed JSON and vision input), ratelimit.py (token bucket per model from configs/limits.yaml),
capabilities.py, gateway.py: cache -> budget -> rate limiter -> provider call with timeout -> retry (exponential backoff + jitter, only 429/5xx) -> fallback chain -> degrade signal -> cache write -> trace span.
Structured output: provider JSON-schema mode where available, else parse + Pydantic-validate with ONE repair retry. Cache key includes model, role, prompt hash, schema, params.
configs/models.yaml: roles parser/summarizer/vision/composer/planner -> ORDERED candidate lists with `needs`. Put these first guesses as data, not code:
gemini-3.5-flash, gemini-3.1-flash-lite, openai/gpt-oss-120b. I will confirm them with the probe.
Startup self-check: list models per provider, resolve each role to the first candidate that exists, log the resolution, and fail loudly or degrade when a role has no live candidate.
scripts/probe_models.py (run via `make probe`): lists visible models, tests text, JSON-schema and image support, measures real RPM/RPD/TPM with bursts, writes configs/limits.yaml + a probe report.
It must cap its own total calls (config) and stop at the first sign of daily-quota exhaustion.

Tests use ONLY the fake provider. Never make a live call yourself.
STOP: I will run `make probe` and pick the models.
```

### P10 — Eval skeleton + labelling tools  *(Day 4–5 · parallel-safe with P9, P12)*
```
Read @docs/ARCHITECTURE.md §8 (whole) and §2 (one code path).

Implement:
- eval/metrics.py: NDCG@k with graded relevance 0–3, Recall@k, hard-constraint-violation counter, precision/recall, latency p50/p95, groundedness rate. Pure functions; unit tests with toy data that has hand-computed answers.
- eval/run_eval.py: --mode replay|live, --suite <name>, --resume, fixed seeds; writes data hash + config hash + prompt hashes into the report header. E2E suites call service.advise() (a stub returning canned responses until P15).
- eval/suites/: registered suites for retrieval, baseline_compare, fakes, vision, guardrails, e2e, parser. With empty datasets they must FAIL LOUDLY ("no data"), never pass.
- scripts/label_pool.py: for each query, build the labelling pool = union of top-20 from baseline + hybrid + BM25-only; write it for me to label 0–3.
  Provide a tiny terminal or Streamlit labeller (name, price, key specs) that saves my labels. I do the labelling; you only build the tool.
- eval/report.py: renders metrics.json -> eval_report.md with the baseline comparison table and the ten worst queries.

Acceptance: `make eval` runs on toy data and two replay runs are byte-identical.
```

### P11 — Fake-review detector + seeded fakes  *(Day 5)*
```
Read @docs/ARCHITECTURE.md §5.4 (detector + leakage warning) and §8 (Seeded fakes row).

Implement:
- reviews/features.py: four registered fake_signals, each returning (score in [0,1], human-readable reason): near-duplicate/template (MinHash on word 5-shingles and embedding cosine, within and across products),
  burst (per-product 48h window vs that product's own baseline), extreme sentiment with no detail (rating 1 or 5, short, low specificity), reviewer pattern (same reviewer, >= k products, same day).
- reviews/fake_detector.py: weighted sum from configs/fakes.yaml -> ReviewFlag with action exclude/downweight/keep; writes review_flags with the reasons. No LLM calls.
- scripts/make_seeded_fakes.py: generate >= 100 synthetic fake reviews using several DIFFERENT templates/generators, inserted into a COPY of the DB (never the raw data), with a sidecar truth file; deterministic seed; split 50 dev / 50 test.
- eval/suites/fakes.py: precision and recall on the seeded TEST split, plus a count of organic reviews flagged.

Rules: tune weights and thresholds on the DEV split only; test-split numbers appear only in the final eval.
Tests: each signal on hand-built true positives and near-miss negatives.
```

### P12 — Guardrails + adversarial set  *(Day 5–6 · parallel-safe with P9, P10)*
```
Read @docs/ARCHITECTURE.md §5.8, §5.7 (abstention), §8 (Adversarial row).

Implement:
- guardrails/untrusted.py: spotlighting wrapper (delimiters + "this is data, not instructions" system rule) and a helper that EVERY model-bound prompt builder must use.
- guardrails/pii.py: add the last-mile scan for prompts and responses (reuse P5's detectors). guardrails/abstain.py. Register hooks at stages input, retrieved, prompt, output.
  A guardrail returns pass/redact/block plus reasons that reach the trace.
- eval/data/adversarial.jsonl: >= 20 cases as synthetic reviews/descriptions inserted into a COPY of the DB: >= 5 prompt injections (varied: "ignore previous instructions", fake system message,
  an instruction in Hinglish, an instruction hidden in spec text, a tool-call lookalike), >= 5 PII, >= 3 contradictory specs, >= 3 unanswerable requests. Each has its expected behaviour.
- eval/suites/guardrails.py: runs each case and asserts expected behaviour; 100% required.

Tests: PII checksum true/false positives; a test proving untrusted text never appears un-delimited in ANY prompt built by the project's prompt builders.
```

### P13 — Query understanding  *(Day 6 · parallel-safe with P14)*
```
Read @docs/ARCHITECTURE.md §5.3, §4 (ParsedQuery, SoftPreference), §4.1 (constraint_kinds).

Implement:
- prompts/parser.md with few-shot examples including Hinglish ("40 hazaar tak ka laptop, video editing ke liye", lakh, k, mixed script).
- understanding/parser.py: ONE structured call via gateway role `parser` -> ParsedQuery, then deterministic post-checks: regex budget cross-check (k, lakh, hazaar); category must exist in the taxonomy else null;
  constraint keys validated against the constraint_kinds registry and the spec vocabulary. A rule-based fallback parser when the LLM is unavailable ("Limited understanding mode").
- understanding/clarify.py: needs_clarification when there is no category AND no use-case, or the budget contradicts itself. Exactly ONE question. Support resume: the answer is merged into the previous ParsedQuery.
- The parser sees ONLY the user's text, never catalogue text.
- eval/suites/parser.py: extraction accuracy for budget, category and constraints. Create the JSONL schema; I fill the data.

Tests with the fake provider, plus a golden fixture of 15 Hinglish and 15 English strings (create it with placeholders; I will fill the expected values).
```

### P14 — Review summariser + sentiment  *(Day 6 · parallel-safe with P13)*
```
Read @docs/ARCHITECTURE.md §5.4 (summariser + use-case sentiment), §5.6 (T, U terms), §5.7 (grounding ids).

Implement:
- reviews/summarizer.py: input <= 15 use-case-relevant, unflagged (or downweighted), PII-redacted reviews per product, numbered [R1..R15], wrapped with guardrails/untrusted.py; batch 2–3 products per call;
  output ReviewSummary with review_ids on every point; reject any id not in the input (one retry, then fallback).
- Extractive fallback (top-rated unflagged excerpts, templated) labelled "excerpt-based" for when the LLM is unavailable or the budget is tight.
- reviews/sentiment.py: deterministic trust-weighted use-case sentiment (similarity x flag weight x log(1+helpful votes), Bayesian shrinkage). Register the ranking signals `use_case_sentiment` and `review_trust`.

Tests: fake-provider malformed output; hallucinated-id rejection; an injection review from the adversarial set in the batch does not alter the schema-constrained output; sentiment math on toy inputs.
```

### P15 — Agent core + service  *(Day 6)*
```
Read @docs/ARCHITECTURE.md §5.10, §5.11, §6, §7, §4 (Plan, PlanStep, ToolResult, AdvisorResponse).

Implement:
- agent/state.py (serialisable AgentState), agent/tools.py (thin registered wrappers: parse_query, retrieve, analyse_reviews, rank, compose_answer, ask_user; verify_images as a stub returning "unverifiable" until P17),
  agent/planner.py (template planner emitting the default plan graph; LLM planner behind a feature flag that sees ONLY tool descriptions + the ParsedQuery),
  agent/verifiers.py (every row of the §5.10 verifier table, registered), agent/loop.py (executor per §5.10: dependency order, verdicts retry/replan/degrade/abstain, max_steps, max_replans, RequestBudget, AWAIT_USER pause/resume),
  service.py advise(query, session_id) with an in-memory SessionStore, and tracing of every step, tool call, model call and decision.
- Stub rank (relevance only) and stub compose_answer (template from evidence) are fine until P16/P18, but they must be registered through the same registries.

Tests: termination for cyclic depends_on and for an LLM planner returning junk; retries bounded; clarification pause/resume; budget exhaustion degrades; hard constraints are never relaxed.
Extend tests/test_extension_points.py: register a dummy tool and run it through the REAL executor.
Acceptance: `python -m advisor.service "40 hazaar tak ka laptop"` prints the trace and a stub response.
```

### P16 — Ranking  *(Day 6–7 · parallel-safe with P17, P18)*
```
Read @docs/ARCHITECTURE.md §5.6 and §4 (SignalScore, ScoreBreakdown).

Implement:
- ranking/signals.py: registered signals relevance (RRF min-max), soft_fit, visual (use_case_sentiment and review_trust already exist from P14).
- ranking/scorer.py: generic weighted sum over the signals named in configs/ranking.yaml, dropping None and renormalising; the hard-constraint gate as a separate step; two-pass flow (pre-rank without visual -> top-N -> final); tie-break per §5.6.
- ranking/explain_rank.py: pairwise "why A above B" (per-signal w x (A - B), sorted by contribution). Confidence rule high/medium/low per §5.6.

Tests: renormalisation when visual is None; weights sum to 1; property test that the gate never lets a violator through; pairwise contributions sum EXACTLY to the score difference;
adding a dummy signal via the registry changes the ranking with zero edits to scorer.py (extend tests/test_extension_points.py).
Do not tune weights now; tuning happens on the dev queries in P20.
```

### P17 — Vision  *(Day 7 · parallel-safe with P16, P18)*
```
Read @docs/ARCHITECTURE.md §5.5, §7 (vision row), §4 (VisualCheck).

Implement:
- vision/fetch.py: httpx with timeout, size cap, content-type check, cache by URL hash; broken/HTML/oversize -> skipped and logged.
- vision/claims.py: deterministic claim extraction (ports, numeric keypad, bezel, included accessories) from spec lines and reviews, each keeping source_ref.
- vision/verifier.py: ONE multi-image call per product via gateway role `vision`; structured [VisualCheck]; "unverifiable" is an explicitly allowed answer; images_per_product and top_n from config;
  also extract information MISSING from the text (e.g. box accessories) as image_obs evidence with ids. Replace the verify_images stub.
- Degrade: any failure -> skip vision, drop the visual signal, renormalise, show "Image checks skipped (reason)".
- eval/suites/vision.py: agreement % against eval/data/image_claims.jsonl. Create the schema {product_id, image_url, claim, truth} and a helper that shows me the image + claim so I can mark the truth by hand (>= 30 claims).

Tests: fake provider returning malformed or no vision output; broken URL; oversize image; a disagreement lowers confidence through the `contradiction` verifier.
```

### P18 — Explanation + grounding  *(Day 7 · parallel-safe with P16, P17)*
```
Read @docs/ARCHITECTURE.md §5.7, §4 (Statement, EvidenceRef), §5.8 (Fabrication row).

Implement:
- explain/composer.py: ONE structured call (gateway role `composer`) with the evidence pool as data; returns statements with evidence_ids plus selected review ids (2–4, including >= 1 negative if one exists).
- explain/grounding_validator.py: ids exist and belong to that product; every number/price/spec token in a statement appears in a cited evidence item; violations -> drop the statement, one regeneration, else template fallback.
- explain/render.py: inserts REAL review text (with rating + date) and REAL spec lines by id. The LLM never types a quote.
- Abstention output and the "no product fully meets your request" statement. Nearest-alternatives behaviour behind a config flag (default: strict refuse; pending Hemanth's answer to open question 8).
- Template fallback explanation with no LLM, labelled "Basic explanation mode".

Tests: a fabricated number is rejected; a cross-product evidence id is rejected; an injection inside a cited review cannot change statements; quote rendering is an exact match to the DB text.
```

### P19 — UI  *(Day 7)*
```
Read @docs/ARCHITECTURE.md §2 and §14 (rows 6.2 and 3.6).

Build the Streamlit app in src/advisor/ui/ with three pages, all going through service.advise() (no business logic in the UI):
1. Chat: query box, the clarification turn, ranked recommendation cards with evidence panels (spec lines that satisfy each constraint; 2–4 quotes with rating and date; image observations; confidence; degraded banners;
   a "why A above B" expander).
2. Trace: for the current request, the plan, tool calls, verifier verdicts, retries, model calls with latency, tokens and cache-hit, and the budget report, all rendered from that request's JSONL.
3. Fake-review inspector: flagged reviews with signals and reasons; filter by product; excluded vs downweighted.
Keep it simple and clean; no styling rabbit holes. Sidebar shows the active profile. Network failure shows a clear banner, not a stack trace.
Acceptance: I can run the demo path end-to-end and screen-record it.
```

### P20 — Full eval, tuning, report  *(Day 8–9)*
```
Read @docs/ARCHITECTURE.md §8 and §14 (row 8).

Preconditions: all datasets exist (50 queries incl. >= 10 Hinglish and >= 5 with no answer; graded gold labels; >= 100 seeded fakes; >= 30 image claims; >= 20 adversarial). If any is short, refuse to run and say which.

1. Run live in slices (--resume) to fill the cache. Respect the quota discipline in AGENTS.md.
2. Tune ranking weights and fake-review thresholds on the DEV split ONLY; log every tuning run in eval/reports/tuning_log.md.
3. Run replay on TEST and ALL and generate eval/reports/eval_report.md with every SOW §8 metric, the baseline comparison with margins, latency median/p95, model calls per request, groundedness, and guardrail pass rate.
4. List the ten worst queries with per-signal breakdown. Draft failure analyses for at least three concrete cases using the trace and the data. Mark any cause you cannot prove as a HYPOTHESIS.
5. Commit eval/reports/baseline_metrics.json as the regression baseline.
Do not change code to game a metric. If a target is missed, report it plainly.
```

### P21 — Docs, README, demo script, freeze  *(Day 9)*
```
1. README: one-command setup, run and eval, verified in a clean venv (run the commands and paste the real output).
2. docs/user_guide.md: walkthrough of the three screens.
3. Rewrite docs/ARCHITECTURE.md to as-built with a "Changes since sign-off" section listing every deviation and its ADR.
4. docs/demo_script.md (5–8 minutes): an end-to-end request, the trace, the eval run, and a degradation demo, with exact commands and queries.
5. Fresh-clone test: clone into a temp dir, follow the README literally, report every friction point, fix them.
6. Tag v1.0 at the code-freeze time (Thu 8 Oct, 6 PM). Do not add features.
```

### P22 — Defense rehearsal  *(Day 9–10)*
```
Act as a hostile reviewer from Mirai Labs. Using @docs/ARCHITECTURE.md and the code, generate 40 questions in the style of SOW §11, and for each give the honest answer with file/line references.
Include questions that require you to RUN things: "why A above B" for real queries, "what breaks if Gemini is down" (demonstrate via the fake provider), "inject a hostile review live" (on a COPY of the DB),
"a new product category appears", "change the budget rule", "what does this threshold do". Flag every place where the code and the doc disagree.
Then quiz me one question at a time, wait for my answer, and grade it against the code.
```

### P23 — Extension proof  *(after the final version · optional, and a great live-defense demo)*
```
Prove the architecture is extensible. Add a new ranking signal `warranty` and a new tool `compare_products` WITHOUT editing scorer.py, loop.py, gateway.py or schemas.py.
Show the diff. If any kernel file must change, explain why and propose an ADR and doc change.
Then run `make eval` and show there is no regression against eval/reports/baseline_metrics.json.
```

---

## 5. Utility prompts

**U1 — End-of-day update**
```
Draft docs/daily/<today>.md from `git log --since=midnight` as Done / Blocked / Next, plain language, at most 10 lines. Do not invent work that is not in the log.
```

**U2 — Explain to defend**
```
Explain @<file> as if I must defend it in the live session: purpose, why each non-obvious choice was made, what breaks if it is removed, and three hostile questions with honest answers. Point out anything you cannot justify.
```

**U3 — Conformance review**
```
Review the diff on this branch against @docs/ARCHITECTURE.md. Report (do not fix): contract changes, layering violations, seams not listed in §4.1, hard-coded constants that belong in configs/,
LLM calls that are not cached/budgeted/traced, untrusted text reaching a non-quarantined prompt, and anything that would make a §14 row untrue.
```

**U4 — Doc sync**
```
The code deviates from §<X> because <reason>. Propose the minimal edit to docs/ARCHITECTURE.md and a new ADR in docs/adr/. Do not touch code.
```

**U5 — Agent went off track**
```
Stop. Revert nothing. List what you changed versus the task, which files are outside the allowed directories, and the smallest path back to the task. Wait for my approval before doing anything.
```

---

## 6. eraser.io prompts

How to use: in Eraser press `/` (or Ctrl/Cmd+J), choose **Diagram as Code → AI Diagram**, paste the prompt, pick the diagram type, generate, then refine with follow-up prompts or edit the diagram-as-code. Eraser also has a Data Flow Diagram generator page that accepts the same text. Longer, structured prompts work better than one-liners. A diagram with more than about 12 processes turns into spaghetti, so build the data flow in **three levels**.

### E1 — Data flow, Level 0 (context)  *(type: Flow chart)*
```
Data flow diagram, Level 0 context diagram, titled "AI Product Advisor MVP - Context".
Use standard data flow notation: external entities as rectangles, processes as circles, data stores as cylinders. Label every arrow with the data that flows.
One central process: "Product Advisor System".
External entities: Shopper; Mirai Labs data files (products CSV, reviews CSV); Gemini API (free tier); Groq API (free tier); Product image hosts; Evaluator (eval harness).
Flows: Shopper -> system: shopping request in English or Hinglish, answer to clarifying question. System -> Shopper: clarifying question, ranked recommendations with evidence, abstention message, degraded-mode notices.
Data files -> system: product catalogue, customer reviews (ingested once). System <-> Gemini API: redacted prompts, structured JSON, image analysis. System <-> Groq API: fallback prompts and structured JSON.
Image hosts -> system: product images. Evaluator -> system: evaluation queries; system -> Evaluator: responses, traces, metrics.
```

### E2 — Data flow, Level 1 (offline + online)  *(type: Flow chart)*
```
Data flow diagram, Level 1, titled "AI Product Advisor - Data Flow". Use standard notation: external entities as rectangles, processes as circles, data stores as cylinders. Label every arrow with the data that flows.
Split into two labelled groups: "Offline plane (make ingest, run once)" and "Online plane (per request)".

External entities: Shopper; Mirai Labs CSV files; Gemini API; Groq API; Product image hosts.
Data stores: D1 SQLite (products, product_specs, reviews, review_flags, taxonomy, image_check_cache, FTS5 indexes); D2 ChromaDB (product and review embeddings); D3 LLM response cache (disk); D4 Trace logs (JSONL per request).

Offline processes: 1 Profile and clean data (dedupe, normalise prices, split category tree, parse specs); 2 Redact PII and flag injection text; 3 Build keyword and vector indexes (local bge-small embeddings); 4 Score fake reviews (near-duplicate, burst, extreme sentiment, reviewer pattern).
Offline flows: CSVs -> 1 -> cleaned records -> 2 -> redacted records -> D1; D1 -> 3 -> FTS5 index into D1 and embeddings into D2; D1 reviews -> 4 -> review flags -> D1.

Online processes: 5 Input guardrails; 6 Query understanding (may ask one clarifying question); 7 Hybrid retrieval (hard-constraint filter, then BM25 and vector search over products and reviews, RRF fusion, shortlist of 5-10); 8 Review analysis (cited summaries, use-case sentiment, uses review flags); 9 Visual verification (top 3 products, at most 3 images each); 10 Ranking (hard-constraint gate, weighted signals, confidence); 11 Explanation and grounding validation (LLM cites evidence ids, renderer inserts real quotes and spec lines); 12 LLM gateway (cache, rate limiter, budget, fallback); 13 Agent orchestrator (plans, calls tools, verifies, retries at most twice, degrades on rate limits).
Online flows: Shopper -> query -> 5 -> 6 -> parsed query -> 7 (reads D1 and D2) -> shortlist -> 8 (reads reviews and flags from D1) -> summaries -> 10 -> top candidates -> 9 (fetches images from image hosts) -> visual checks -> 10 -> ranked list with score breakdown -> 11 -> recommendations with evidence, confidence, degraded flags -> Shopper.
Processes 6, 8, 9, 11 call process 12, which uses D3 and calls Gemini API first and Groq API as fallback. Process 6 sends a clarifying question to Shopper and receives the answer. Processes 7 and 10 send an abstention to Shopper when no product meets the hard constraints.
Process 13 controls processes 5 to 11. Every process writes spans to D4.
```

### E3 — Layered system architecture  *(type: Cloud Architecture)*
```
System architecture diagram titled "AI Product Advisor - Layered Architecture", top to bottom, one group per layer, arrows only pointing downward.
L5 Surfaces: Streamlit UI (chat, trace viewer, fake-review inspector), optional FastAPI, evaluation harness CLI.
L4 Orchestration: Agent (plan executor, verifiers, request budget, state). Entry point for L5: Service facade "advise(query, session)".
L3 Capabilities (each a set of plug-ins behind a contract): Query understanding, Hybrid retrieval, Review intelligence (summariser, fake-review detector), Visual verification, Ranking, Explanation and grounding, Guardrails (PII, injection, abstention).
L2 Adapters: Gemini adapter, Groq adapter, SQLite store (FTS5), Chroma vector store, local bge-small embedder, image fetcher.
L1 Ports: LLMProvider, Embedder, KeywordIndex, VectorIndex, ImageFetcher, SessionStore.
L0 Kernel: schemas, registries, config, prompts, tracing, budget, cache, events, run manifest.
Side box to the right: Extension registries (tools, verifiers, ranking signals, fake signals, guardrails, constraint kinds, evidence kinds, retrievers, providers, eval suites) plugging into L3 and L4.
External systems at the bottom: Gemini API, Groq API, product image hosts.
```

### E4 — One request as a sequence diagram  *(type: Sequence; numbered list works well)*
```
Sequence diagram, participants: Shopper, UI, Service, Agent, LLM Gateway, Retrieval, Review Analysis, Vision, Ranking, Explainer.
1. Shopper sends "40 hazaar tak ka laptop, video editing ke liye" to UI.
2. UI calls Service advise(query, session).
3. Service starts Agent, which writes the plan to the trace.
4. Agent asks LLM Gateway to parse the query; Gateway returns ParsedQuery (budget 40000 INR, use-case video editing).
5. Agent calls Retrieval with hard filters, BM25 and vector search, RRF; Retrieval returns a shortlist of 8.
6. Agent calls Review Analysis, which reads review flags, calls LLM Gateway for cited summaries (batched, parallel) and returns summaries and sentiment.
7. Agent pre-ranks and calls Vision for the top 3; Vision fetches images and calls LLM Gateway; returns visual checks.
8. Agent calls Ranking for the final order with the hard-constraint gate; verifiers check constraints and contradictions.
9. Agent asks Explainer to compose a grounded answer; Explainer calls LLM Gateway, the grounding validator checks evidence ids, the renderer inserts real quotes.
10. Agent returns AdvisorResponse with trace id to Service; Service returns it to UI; UI shows ranked cards, evidence panels and the trace tab.
Add an alt block: if the query is too vague, Agent returns one clarifying question to Shopper and resumes when answered. Add a note: on rate-limit or budget exhaustion, Vision is skipped and the response is marked degraded.
```

### E5 — Database ERD  *(type: Entity Relationship)*
```
Entity relationship diagram for the SQLite database: products (product_id PK, name, brand, cat_l1, cat_l2, cat_l3, retail_price_inr, effective_price_inr, description, image_urls, alias_of);
product_specs (spec_id PK "spec:pid:n", product_id FK, raw_line, key, value, unit); reviews (review_id PK, product_id FK, rating, title, text_redacted, review_date, reviewer_id, helpful_votes, injection_flag);
review_flags (review_id PK FK, score, signals, reasons, action); taxonomy (node_id PK, parent_id, level, name); image_check_cache (url_hash PK, status, content_type, bytes);
quarantine_reviews (review_id PK, reason). Relationships: products 1-to-many product_specs; products 1-to-many reviews; reviews 1-to-1 review_flags; taxonomy 1-to-many products.
```

### Extras
- **Paste-your-own-diagram trick:** Eraser accepts a code snippet as the prompt. Paste one of the mermaid blocks from ARCHITECTURE.md §2, §5.10 or §6 to get an Eraser version of it.
- **From inside Antigravity:** Eraser runs an MCP server, so an MCP-capable agent can generate diagrams from the codebase later ("create an architecture diagram for this codebase"). It needs an Eraser account; see Eraser's "AI agent integrations" docs for the current setup.
- **Presentation tip (SOW §11):** export E2 (data flow) for "Execution", E3 for the architecture slide and E4 for the live-demo walkthrough. Regenerate them from the as-built code on Day 9.
