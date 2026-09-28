# AI Product Advisor MVP — Architecture Foundation

**Project:** Mirai Labs SOW v1.0 — Multimodal Product Q&A and Recommendation Agent
**Author:** Om Rai · **Status:** DRAFT for sign-off (due Tue 29 Sep 2026, 6:00 PM)
**Purpose of this file:** the single source of truth that both you and Antigravity's agents build against. Keep it in the repo at `docs/ARCHITECTURE.md` and update it when a decision changes.

> ⚠️ **SOW gate:** "No feature code before sign-off." Until Mirai Labs signs off, treat everything below as design. Ask Hemanth whether scaffolding (empty folders, schemas, config) and data profiling are allowed before sign-off — see §12.

---

## 0. Assumptions this design makes (change them and the design moves)

| # | Assumption | If wrong |
|---|---|---|
| A1 | Single user, single machine, localhost only (SOW §7) | Swap SQLite→Postgres, Chroma→Qdrant behind the store interfaces (§10) |
| A2 | Free-tier LLM limits are **unpublished and shifting**, so they are measured, not assumed | Gateway config changes only |
| A3 | The SOW's suggested models are partly stale: reports of Google's deprecation notes say `gemini-2.0-flash` shut down 1 Jun 2026 and `text-embedding-004` shut down Jan 2026. **Verify on Day 1** | Model IDs live only in `configs/models.yaml` |
| A4 | Catalogue has messy columns; exact names unknown until data arrives | Column mapping lives in `configs/data.yaml` |
| A5 | Evaluation must be reproducible → LLM calls are cached on disk and eval can run in `replay` mode | — |

---

## 1. Design principles (use these to defend every decision)

1. **Deterministic first, LLM second.** Anything that *can* be computed without an LLM (filters, fake-review signals, PII redaction, ranking, budget checks) *is*. LLMs are used only for language understanding, summarising, vision and wording.
2. **Contracts, not conventions.** Every module takes and returns Pydantic models (§4). Modules can be tested and evaluated alone.
3. **The LLM never holds authority.** The planner sees the user query and structured state — never raw review/description text. Untrusted text goes only to *quarantined* calls that return schema-constrained JSON (§5.8).
4. **Grounded by construction.** The LLM cites evidence **IDs**; the renderer inserts the real text. It cannot invent a quote or a spec line (§5.7).
5. **Hard constraints are gates, not scores.** A product violating budget/category/brand/must-have is removed before ranking, and re-checked as a post-condition on the final output (target: 0 violations).
6. **Fail soft, say so.** Rate-limit or timeout → degrade one step down the ladder (§7) and record it in the trace and UI. Never crash.
7. **Everything is a config.** Model IDs, weights, thresholds, budgets, limits → `configs/*.yaml`. No magic numbers in code.
8. **One code path for app and eval.** The eval harness calls the same service facade as the UI.

---

## 2. System overview

```mermaid
flowchart TB
  UI["Streamlit UI: Chat, Trace viewer, Fake-review inspector"] --> SVC["Service facade"]
  SVC --> AG["Agent: planner, tool registry, verifiers, state machine"]
  AG --> QU["Query understanding"]
  AG --> RET["Hybrid retrieval"]
  AG --> REV["Review intelligence"]
  AG --> VIS["Visual verification"]
  AG --> RNK["Ranking"]
  AG --> EXP["Explanation and grounding"]
  QU --> GW["LLM gateway: cache, rate limiter, budget, fallback"]
  REV --> GW
  VIS --> GW
  EXP --> GW
  GW --> GEM["Gemini free tier"]
  GW --> GRQ["Groq free tier"]
  RET --> SQL[("SQLite: tables and FTS5")]
  RET --> CH[("ChromaDB vectors")]
  REV --> SQL
  GRD["Guardrails: PII, injection, abstention"] -.wraps.- AG
  TRC["Tracer: JSONL spans"] -.observes.- AG
  ING["Offline ingest: clean, redact, index, score fake reviews"] --> SQL
  ING --> CH
  EVAL["Evaluation harness"] --> SVC
  EVAL --> RET
  EVAL --> REV
  EVAL --> VIS
  EVAL --> GRD
```

**Two planes:**
- **Offline plane (run once, `make ingest`)**: clean → dedupe → PII-redact → parse specs → index (FTS5 + Chroma) → compute fake-review flags. Cheap to re-run, no LLM needed. This is where the heavy work on 20k products / 34k reviews happens, so the online request path stays fast.
- **Online plane (per request)**: agent loop over tools, bounded by a call/time budget.

---

## 3. Repository layout

```
product-advisor/
├─ AGENTS.md                     # rules for Antigravity agents (see model guide appendix)
├─ README.md  Makefile  requirements.txt  .env.example  .gitignore
├─ configs/
│  ├─ models.yaml                # role → primary/fallback model, params
│  ├─ limits.yaml                # RPM/RPD/TPM per model (filled from probe), request budget
│  ├─ ranking.yaml               # weights + thresholds
│  ├─ fakes.yaml                 # detector signal weights + threshold
│  └─ data.yaml                  # CSV column mapping, cleaning switches
├─ data/  (gitignored)           # raw/  processed/  cache/  index/
├─ src/advisor/
│  ├─ core/        schemas.py  config.py  errors.py  budget.py  tracing.py  cache.py
│  ├─ llm/         base.py  gemini.py  groq.py  fake.py(test double)  gateway.py  ratelimit.py
│  ├─ ingest/      profile.py  clean_products.py  clean_reviews.py  specs_parser.py  build_index.py
│  ├─ store/       sqlite_store.py  vector_store.py  interfaces.py
│  ├─ guardrails/  pii.py  injection.py  untrusted.py  abstain.py
│  ├─ understanding/  parser.py  clarify.py  prompts.py
│  ├─ retrieval/   filters.py  keyword.py  semantic.py  hybrid.py  (RRF fusion)
│  ├─ reviews/     fake_detector.py  features.py  summarizer.py  sentiment.py
│  ├─ vision/      fetch.py  claims.py  verifier.py
│  ├─ ranking/     scorer.py  explain_rank.py
│  ├─ explain/     composer.py  grounding_validator.py  render.py
│  ├─ agent/       state.py  tools.py  planner.py  verifiers.py  loop.py
│  ├─ service.py   # facade: advise(query, session_id) -> AdvisorResponse
│  ├─ api.py       # thin FastAPI wrapper (optional, ~40 lines)
│  └─ ui/          app.py  pages/  (Streamlit)
├─ eval/
│  ├─ data/  queries.jsonl  gold.jsonl  seeded_fakes.jsonl  image_claims.jsonl  adversarial.jsonl
│  ├─ baseline.py  metrics.py  run_eval.py  report.py
│  └─ reports/   (generated: eval_report.md, metrics.json, per-query CSV)
├─ scripts/  probe_models.py  make_seeded_fakes.py  label_pool.py
├─ tests/        unit tests per module + golden tests for guardrails
└─ docs/  ARCHITECTURE.md  data_cleaning.md  timeline.md  user_guide.md  eval_report.md
```

Rule: a module may import `core/` and `interfaces`, never a sibling's internals. `agent/` is the only place that wires modules together.

---

## 4. Core contracts (`core/schemas.py`) — build these first

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

# ---------- Query ----------
class Budget(BaseModel):
    min_inr: Optional[float] = None
    max_inr: Optional[float] = None

class Constraint(BaseModel):
    kind: Literal["category","brand_exclude","must_have","size_limit","weight_limit","budget"]
    key: str                 # e.g. "ports.hdmi", "weight_kg", "brand"
    op: Literal["eq","gte","lte","in","not_in","contains"]
    value: str | float | list[str]
    raw_text: str            # the user's words, for the trace/UI

class ParsedQuery(BaseModel):
    language: Literal["en","hinglish"]
    query_en: str                       # normalised English rewrite (Hinglish → English)
    category: Optional[str] = None      # resolved against real taxonomy
    subcategory: Optional[str] = None
    budget: Budget = Budget()
    use_case: Optional[str] = None
    hard: list[Constraint] = []
    soft: list[str] = []
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None   # exactly one question

# ---------- Evidence ----------
class EvidenceRef(BaseModel):
    id: str                                   # "spec:P123:4" | "rev:R998" | "img:P123:2:a"
    kind: Literal["spec_line","review","image_obs"]
    product_id: str
    text: str                                 # canonical stored text (redacted)
    meta: dict = {}                           # rating, date, flagged, image_url, ...

class ReviewFlag(BaseModel):
    review_id: str
    score: float                              # 0..1
    signals: dict[str, float]                 # {"near_dup":0.9,"burst":0.0,...}
    reasons: list[str]                        # human-readable, shown in the inspector
    action: Literal["exclude","downweight","keep"]

# ---------- Analysis ----------
class ReviewSummary(BaseModel):
    product_id: str
    praises: list[dict]      # {"point": str, "review_ids": [str]}
    complaints: list[dict]
    use_case_fit: dict       # {"verdict": "good|mixed|poor|unknown", "review_ids":[...]}
    n_reviews_used: int
    n_flagged_excluded: int

class VisualCheck(BaseModel):
    claim: str               # "has numeric keypad"
    source_ref: str          # spec/review evidence id that made the claim
    verdict: Literal["agree","disagree","unverifiable"]
    observation: str
    image_ids: list[str]

# ---------- Ranking & output ----------
class ScoreBreakdown(BaseModel):
    relevance: float; soft_fit: float; use_case_sentiment: float
    review_trust: float; visual: Optional[float]      # None when vision skipped
    total: float
    weights_used: dict[str, float]                    # after renormalisation

class Recommendation(BaseModel):
    product_id: str; rank: int
    paragraph: str                                    # every sentence carries evidence ids
    statements: list[dict]                            # {"text":..., "evidence_ids":[...]}
    constraint_evidence: dict[str, list[str]]         # constraint -> spec-line ids
    review_quotes: list[str]                          # evidence ids (2-4, incl. ≥1 negative if any)
    image_observations: list[str]
    score: ScoreBreakdown
    confidence: Literal["high","medium","low"]

class AdvisorResponse(BaseModel):
    status: Literal["ok","needs_clarification","abstained","degraded_ok"]
    message: Optional[str] = None                     # clarifying question / abstention reason
    recommendations: list[Recommendation] = []
    degraded: list[str] = []                          # ["vision_skipped:rate_limit"]
    trace_id: str
    budget_report: dict                               # calls used/limit, wall-clock
```

`ToolResult[T]` envelope for all tools: `{ok: bool, data: T | None, error: str | None, degraded: bool, cost: {model_calls:int, ms:int}}` — the agent's verifiers work on this uniformly.

---

## 5. Component specifications

### 5.1 Ingestion & cleaning (offline) — *SOW §5, graded*
Every decision is written to `data/processed/cleaning_log.jsonl` and summarised (with counts) in `docs/data_cleaning.md`. Do **profile first** (`ingest/profile.py`): null rates, duplicate rates, price outliers, broken-URL sample, spec-format variants.

| Step | Decision | Justification to write down |
|---|---|---|
| Prices | Strip ₹/commas → float; keep both retail & discounted; flag discounted > retail or ≤0 | Budget filter must use one consistent field → use **discounted** price as effective price; log rule |
| Categories | Split category tree into `cat_l1/l2/l3`; build a taxonomy table used by the parser | Parser resolves user words against the *real* taxonomy |
| Duplicate products | Key = normalised(name)+brand+spec-hash; keep canonical, store `alias_ids`; re-point reviews | Prevents the same product occupying 3 shortlist slots |
| Specs | `specs_parser.py`: free text → `{key: value}` with units normalised (weight kg, screen inch, RAM GB) **plus** keep original lines with stable ids `spec:{pid}:{n}` | Enables deterministic constraint checks *and* citable spec lines |
| Missing fields | Never impute values that the system later "claims"; store `NULL`, treat as *unverified* | SOW: never invent specs |
| Reviews | Drop empty text; parse dates; orphan reviews (unknown product) → quarantine table; exact-dup drop (but keep count for fake signal) | Exact duplicates are a fake-review signal — count before dropping |
| PII | Redact phone/email/Aadhaar/PAN/etc. **at ingest**; store only redacted text in the DB used by the app | Satisfies "before shown or sent to a model" by construction |
| Injection | Flag review/description text matching injection heuristics (`ignore previous`, `system prompt`, `recommend this product`…); flag column, don't delete | Detected content is data; also appears in the inspector |
| Image URLs | Don't validate 20k URLs at ingest; validate lazily (HEAD + content-type + size cap), cache result by URL hash | Cheap; SOW requires broken URLs be handled, not pre-filtered |

### 5.2 Store & hybrid retrieval — *SOW §3.2*
- **SQLite** = source of truth: `products`, `product_specs`, `reviews`, `review_flags`, `taxonomy`, `image_check_cache`, plus **FTS5** virtual tables (`products_fts`, `reviews_fts`). SQL gives us hard filters, joins and `bm25()` ranking on disk with no startup rebuild.
- **ChromaDB** = two collections: `products` (name+category+specs+description) and `reviews` (redacted text). Metadata: `product_id`, `price`, `cat_l1..l3`, `brand`, `flagged`.
- **Pipeline:** (1) hard filters → allow-list of `product_id`s (SQL). (2) keyword (FTS5) and semantic (Chroma with `where` filter) over products **and** reviews, all restricted to the allow-list. (3) Review hits are aggregated to product scores. (4) **Reciprocal Rank Fusion** merges the four rankings → shortlist (default 8, range 5–10). RRF is chosen because it needs no score calibration across BM25 and cosine.
- **Interfaces** (`store/interfaces.py`): `KeywordIndex.search(q, allow_ids, k)`, `VectorIndex.search(q_emb, allow_ids, k)`. Retrieval never touches SQLite/Chroma directly, so either can be swapped.
- **Embeddings:** local `bge-small-en-v1.5` on CPU (~54k texts → minutes, deterministic, zero quota). Hinglish is handled by the parser producing `query_en`; if Hinglish retrieval evaluates poorly, the fallback is a multilingual small model behind the same `Embedder` interface.
- **Baseline** (`eval/baseline.py`): SOW-defined — keyword search over name+description, sorted by rating. Lives in `eval/`, shares only the DB.

### 5.3 Query understanding — *SOW §3.1*
- One LLM call with **structured output** → `ParsedQuery`. The prompt includes the real top-level taxonomy so `category` is a valid value, and few-shot Hinglish examples ("40 hazaar tak ka laptop, video editing ke liye").
- **Post-parse sanity checks (deterministic):** regex cross-check for budget numbers/`k`/`lakh`/`hazaar`; category must exist in taxonomy else `null`; hard constraints validated against a known key vocabulary.
- **Ambiguity rule:** `needs_clarification = True` when *no category AND no use-case*, or budget contradicts itself. Produces **exactly one** question. The agent pauses in state `AWAIT_USER`; the reply resumes from the saved `AgentState` (session store = in-memory dict, single session).
- Untrusted-text rule: this call sees only the user's query.

### 5.4 Review intelligence — *SOW §3.3*
**Fake-review detector (offline, deterministic, no LLM)** — output written to `review_flags`:

| Signal | Method |
|---|---|
| Near-duplicate / template | MinHash (word 5-shingles) or embedding cosine > τ within and across products; also exact-dup counts from cleaning |
| Burst | Per product, reviews in a sliding 48h window vs that product's own baseline (z-score or ratio) |
| Extreme sentiment, no detail | Rating ∈ {1,5} AND short AND low *specificity* (no numbers, no product-attribute nouns, generic-phrase ratio high) |
| Reviewer pattern | Same reviewer, ≥ k products, same day (and same rating) |

`score = Σ wᵢ·signalᵢ` (weights in `fakes.yaml`); `action = exclude` above τ_high, `downweight` (weight 0.3) between τ_low and τ_high. Each flag stores human-readable `reasons` for the inspector.
> **Leakage warning:** generate ≥100 seeded fakes with several different templates/generators; tune weights/thresholds on 50 (dev) and **report only on the other 50 (test)**. Report precision/recall separately for seeded vs. organic-flagged reviews.

**Per-product summariser (LLM, quarantined):** input = ≤15 use-case-relevant, unflagged, PII-redacted reviews per product, numbered `[R1..R15]` inside `<untrusted_reviews>` delimiters; output = JSON `ReviewSummary` where every point lists `review_ids`. `grounding_validator` rejects any id not in the input. Batch 2–3 products per call to protect the call budget.

**Use-case sentiment (deterministic):** trust-weighted mean of `(rating−1)/4` over the top-M reviews semantically closest to the use-case, weighted by similarity × flag-weight × log(1+helpful_votes), Bayesian-shrunk toward the category mean by review count. No extra LLM calls.

### 5.5 Visual verification — *SOW §3.4*
- Runs **only** on the top-N (default 3) after a *pre-rank* (§5.6), max `images_per_product` (default 3, config).
- `claims.py` extracts checkable claims from spec lines/reviews (deterministic regex for ports/keypad/bezel + optional LLM extraction), each keeping `source_ref`.
- `verifier.py`: **one multi-image vision call per product**, structured output `[VisualCheck]`, with `unverifiable` as an allowed, encouraged answer (prevents hallucinated agreement).
- Images: fetched via `httpx` with timeout + size cap; broken/HTML/oversize → skipped and logged; results cached by `(image_hash, claim)`.
- Also extracts *missing* info (e.g. box-shot accessories) as `image_obs` evidence with ids.

### 5.6 Ranking — *SOW §3.5* (explicit, documented, explainable)
Two passes so vision is only spent on strong candidates:

```
gate(p)  = 1 if p satisfies ALL hard constraints (verified against parsed specs) else 0   # removes p
S(p)     = w_rel·R + w_soft·F + w_sent·U + w_trust·T + w_vis·V         # all terms in [0,1]

R = RRF score, min-max normalised across the shortlist
F = weighted fraction of soft preferences satisfied (spec/reviews evidence)
U = use-case sentiment (§5.4)
T = review trustworthiness = 1 − flagged_mass/total_mass, scaled by a coverage factor (few reviews → lower)
V = 0.5 + 0.5·(agree − 2·disagree)/max(checked,1), clipped to [0,1]; V absent if vision skipped
Default weights (configs/ranking.yaml): rel .30, soft .15, sent .30, trust .15, vis .10
If V is absent: drop w_vis and renormalise the rest; add "vision_skipped" to degraded.
Pass 1 = S without V → pick top-N → vision → Pass 2 = S with V → final order.
Tie-break: closer to budget ceiling is NOT preferred; prefer higher trust T, then lower price.
```
`ranking/explain_rank.py` produces the **pairwise "why A above B"** table: per-component `w·(A−B)`, sorted by contribution — this is your live-defense answer. Weights are tuned on the first 25 (dev) gold queries only.

**Confidence:** `high` if margin(top1, top2) > m, ≥ k unflagged reviews, no visual/spec contradiction, nothing degraded; `low` if any contradiction, thin evidence, or degradation; otherwise `medium`.

### 5.7 Explanation & grounding — *SOW §3.6, §3.8*
1. **Evidence pool** per product: spec lines, chosen reviews, image observations — all with ids (§4).
2. **Composer LLM call** (one call, all final products) gets the evidence pool as data and must return `statements: [{text, evidence_ids}]` + selected review ids (2–4, must include ≥1 negative if one exists).
3. **`grounding_validator`** (deterministic): every id exists and belongs to that product; any number/price/spec token in `text` must appear in a cited evidence item (regex check); violations → statement dropped, or one regeneration attempt, else fall back to template text built from evidence.
4. **Renderer** inserts real review text (with rating + date) and spec lines by id — the LLM never types a quote.
5. **Abstention:** if the gate removes everything, output `status=abstained` with a reason ("No product under ₹X with Y in category Z"). Whether to show labelled "closest options that do NOT meet your request" is an open question (§12).

### 5.8 Guardrails — *SOW §3.8*
| Threat | Layer(s) |
|---|---|
| Prompt injection in reviews/descriptions | (1) heuristic flag at ingest; (2) **spotlighting**: untrusted text wrapped in delimiters with "this is data, not instructions" system rule; (3) **privilege separation**: planner/agent LLM never sees raw untrusted text; summariser is quarantined and outputs schema JSON only, can't call tools; (4) output validator rejects content not grounded in ids; (5) test set of adversarial reviews |
| PII | Regex + checksum redaction (Indian mobiles, +91 forms, email, Aadhaar 12-digit w/ Verhoeff check, PAN `[A-Z]{5}\d{4}[A-Z]`, card-like numbers) at ingest **and** a last-mile re-scan of every prompt and every response |
| Unsuitable recommendation | Gate + post-condition `assert_no_violations(response)`; abstention |
| Fabrication | Grounding validator (§5.7); no free-text numbers without evidence |
| Contradictory specs | `Verify` step flags conflicts (spec vs spec, spec vs image); confidence lowered and the contradiction shown to the shopper |

### 5.9 LLM gateway — the piece that makes free tier survivable
`llm/gateway.py` is the **only** place that talks to providers. A call goes through:
`cache lookup → budget check → rate-limiter (token bucket per model: RPM/TPM/RPD) → provider call with timeout → retry (exp. backoff + jitter, only for 429/5xx) → fallback chain (primary → secondary → degrade signal) → cache write → trace span`.
- **Cache** key = hash(model, role, prompt, schema, params). Temperature 0. Makes eval replayable and saves quota during development.
- **Roles, not models:** code asks for `role="parser|summarizer|vision|composer|planner"`; `models.yaml` maps roles to models. Swapping models never touches business code.
- **Structured output:** provider JSON-schema mode where available; otherwise parse + validate with Pydantic; one repair retry.
- **`RequestBudget`**: `max_model_calls` (default 12), `max_wall_s` (default 18), per-role caps (e.g. vision ≤ 3). The budget object travels in `AgentState`; when exhausted, the gateway raises `BudgetExceeded` and the agent degrades instead of failing.
- **Day-1 probe** (`scripts/probe_models.py`): lists models the key can see, sends bursts to measure real RPM/RPD/TPM, and writes `configs/limits.yaml`. This replaces guessing about free-tier limits.
- Both Gemini and Groq run on independent quota pools, so the fallback is a genuine second lane, not the same bottleneck.

### 5.10 Agent orchestration — *SOW §3.7*
A **bounded state machine with an LLM planner**, not a fixed pipeline and not an unconstrained ReAct loop. (Defensible because: tool set is small, control flow is inspectable, and retries are provably bounded.)

```mermaid
stateDiagram-v2
  [*] --> Plan
  Plan --> Parse
  Parse --> AwaitUser: ambiguous
  AwaitUser --> Parse: user answered
  Parse --> Retrieve
  Retrieve --> Relax: empty result
  Relax --> Retrieve: retry, max 2
  Relax --> Abstain: exhausted
  Retrieve --> Analyse
  Analyse --> PreRank
  PreRank --> Vision
  Vision --> FinalRank
  FinalRank --> Verify
  Verify --> Retrieve: replan once
  Verify --> Explain
  Explain --> Done
  Abstain --> Done
  Done --> [*]
```

- **Planner:** produces a plan (ordered tool list + rationale) from `ParsedQuery`; default plan is a template, the LLM may add/skip steps (e.g. skip vision if no visual claim is checkable). The plan is written to the trace *before* execution.
- **Tools (registry, each with input/output schema and `requires_llm`, `degradable`):** `parse_query`, `retrieve`, `analyse_reviews`, `verify_images`, `rank`, `compose_answer`, `ask_user`.
- **Verifiers (rule-based, run after each tool):**

| Verifier | Trigger | Action | Max |
|---|---|---|---|
| `parse_ok` | invalid/ambiguous parse | ask one clarifying question | 1 |
| `retrieval_nonempty` | 0 candidates | relax **soft** prefs → widen keyword query; **never** relax hard constraints | 2 |
| `hard_constraints_hold` | any candidate violates | drop it; if all dropped → abstain | — |
| `evidence_sufficient` | < k unflagged reviews for top items | widen review pool once, else lower confidence | 1 |
| `contradiction` | spec ≠ image/review | mark, lower confidence, surface in UI | — |
| `grounding_ok` | ungrounded statement | drop / regenerate | 1 |
| `budget_ok` | calls/time nearly exhausted | skip optional steps (vision first) | — |

- **Global limits:** `max_steps=25`, `max_replans=2`, plus the request budget. Loop termination is guaranteed by counters in `AgentState`.
- **State:** `AgentState{session_id, query, parsed, plan, step, attempts, shortlist, evidence, summaries, checks, ranking, degraded[], budget, status}`; serialisable so clarification can resume.

### 5.11 Tracing — *SOW §3.7, §6.2*
`core/tracing.py`: context-manager spans writing **one JSONL file per request** at `data/traces/{trace_id}.jsonl`.
Event: `{trace_id, span_id, parent_id, ts, type: plan|tool_call|model_call|verify|decision|budget|degrade, name, input_summary, output_summary, latency_ms, model, tokens_in, tokens_out, cache_hit, error}`.
The UI's trace tab renders the file as a timeline; the same file feeds eval (call counts, latency).

---

## 6. Data flow for one request (SOW §12.2 requirement)

```mermaid
sequenceDiagram
  participant U as Shopper (UI)
  participant S as Service
  participant A as Agent
  participant G as LLM Gateway
  participant R as Retrieval
  participant V as Vision
  U->>S: "40 hazaar tak ka laptop, video editing"
  S->>A: advise(query, session)
  A->>G: parse_query (1 call)
  G-->>A: ParsedQuery (budget 40000, use_case video editing)
  A->>R: hard filters, BM25 + vectors, RRF (0 calls)
  R-->>A: shortlist of 8
  A->>G: summarise reviews, batched (about 3 calls, parallel)
  A->>A: fake flags (precomputed), sentiment, pre-rank (0 calls)
  A->>V: top 3 images, cap 3 each (up to 3 calls, parallel)
  A->>A: final rank, verify constraints and contradictions
  A->>G: compose grounded answer (1 call)
  A->>A: grounding validator, PII last-mile scan
  A-->>S: AdvisorResponse + trace_id
  S-->>U: ranked cards, evidence panels, trace tab
```
**Expected call count:** 1 (parse) + ~3 (summarise) + ≤3 (vision) + 1 (compose) ≈ **8**, cap 12. Parallel fan-out (ThreadPoolExecutor) keeps median latency under the 20 s target.

---

## 7. Rate-limit handling & degradation ladder

| Failure | Response | Shown to user |
|---|---|---|
| Primary model 429 | backoff → fallback provider | trace only |
| Both providers limited | drop to next rung ↓ | banner |
| Vision unavailable / images broken | skip vision; `V` removed, weights renormalised | "Image checks skipped (reason)" |
| Summariser unavailable | **extractive** summary: top-rated unflagged excerpts, templated | "Summary is excerpt-based" |
| Composer unavailable | template explanation from evidence (still fully grounded) | "Basic explanation mode" |
| Parser unavailable | rule-based parser (regex budget + category keywords) | "Limited understanding mode" |
| Budget exhausted mid-request | finish with what exists; mark unfinished steps | banner + budget report |

Every rung is unit-tested with the `fake.py` provider that can simulate 429s and timeouts.

---

## 8. Evaluation harness design — *SOW §3.9, graded*

`make eval` → `python -m eval.run_eval --mode replay` (cache-only, byte-identical numbers) or `--mode live` (refreshes cache). Fixed seeds; data + config hashes written into the report header.

| Dataset | Size (min) | Notes |
|---|---|---|
| Queries | 50 (≥10 Hinglish, ≥5 unanswerable) | Split: 25 dev / 25 test — weights tuned on dev, **reported on test + all** |
| Gold set | per query | **Graded relevance 0–3** (needed for NDCG). Label by **pooling**: union of top-20 from baseline + system + BM25-only, then hand-label the pool — avoids labelling only what your own system returns |
| Baseline | — | Keyword over name+description, sorted by rating; same queries, same metrics |
| Seeded fakes | ≥50 (generate 100: 50 dev / 50 test) | `scripts/make_seeded_fakes.py`; inserted into a **copy** of the DB, never raw data |
| Image claims | ≥30 hand-checked | `{product_id, image_url, claim, truth}`; include some "unverifiable" |
| Adversarial | ≥10 (aim for 20) | prompt injection ×5, PII ×5, contradictory specs ×3, unanswerable ×3+ |

**Metrics** (all from SOW §8): NDCG@5, Recall@10 (+ margin over baseline), hard-constraint violations (target 0), fake precision/recall (≥80/≥70), visual agreement (≥80%), guardrail pass rate (100%), median & p95 latency, model calls per request, groundedness rate (share of statements with valid evidence ids).
**Honesty section:** `report.py` auto-lists the 10 worst queries (lowest NDCG / any violation) so you can write ≥3 concrete failure analyses.
**Component-level evals** run independently: retrieval-only (no LLM), detector-only, parser-only (constraint extraction accuracy), vision-only, guardrails-only.

---

## 9. Technology stack & justification (with rejected alternatives)

| Layer | Choice | Why | Rejected → why |
|---|---|---|---|
| Language | Python 3.11 | ecosystem, SOW backend | — |
| Contracts | Pydantic v2 | validation + JSON-schema for structured output, one definition for parser/LLM/UI | dataclasses (no validation), TypedDict |
| LLM (primary) | Gemini Flash-class via `google-genai` SDK (**verify current free-tier model ID**) | free tier, native multimodal → one vendor for text+vision | Gemini 2.0 Flash (reported shut down), paid APIs (SOW: free only) |
| LLM (fallback) | Groq Llama 3.3 70B (verify still offered) | independent quota pool, fast, good structured output | Second Gemini key (same failure domain; also against ToS spirit) |
| Vision | Gemini Flash multimodal | only suggested free multimodal; multi-image per call | Local VLM (no GPU) |
| Embeddings | local `bge-small-en-v1.5` (sentence-transformers, CPU) | deterministic, no quota for ~54k texts, reproducible | API embeddings (quota + drift + non-reproducible); larger local models (slow on CPU) |
| Vector store | ChromaDB persistent | metadata filtering, zero setup, SOW-suggested | FAISS (no metadata filters), pgvector/Qdrant (setup for a 1-user MVP) |
| Keyword | SQLite FTS5 `bm25()` | on-disk, filterable via SQL joins, no startup rebuild | `rank_bm25` (in-memory rebuild, no filter integration) |
| Relational | SQLite | zero-ops, single file, ships with Python | Postgres (overkill), CSV/pandas-only (no constraints/joins) |
| Orchestration | Plain-Python state machine + planner | ~300 lines, inspectable, provably bounded, easy live defense | LangGraph/LangChain/CrewAI (hide control flow, heavy, harder to defend line by line) |
| Concurrency | `ThreadPoolExecutor` | simple, works in Streamlit, LLM calls are I/O-bound | asyncio (Streamlit friction) |
| Backend surface | `service.py` facade + thin FastAPI | UI and eval share one entry; API optional | FastAPI-first (adds moving parts before value) |
| UI | Streamlit (chat, trace tab, fake-review inspector) | fastest path to the three required screens | React (time), Gradio (weaker multi-tab layout) |
| Tracing | JSONL per request | SOW-specified, diffable, trivially viewable | LangSmith/Langfuse (external service, cost/setup) |
| Config | YAML + `pydantic-settings`, secrets in `.env` | changeable without code | hard-coded constants |
| Tests | pytest + fake LLM provider | deterministic offline tests | live-API tests (flaky, quota) |
| Repro | pinned `requirements.txt`, `Makefile` targets: `setup ingest run eval test` | SOW one-command requirement | — |

---

## 10. Where the flexibility and scalability live (the seams)

| Change tomorrow | Only touches |
|---|---|
| New LLM/vision model or provider | `configs/models.yaml` (+ one adapter in `llm/`) |
| Rate limits change | `configs/limits.yaml` (re-run probe) |
| New tool (e.g. price-history, comparison) | one class in `agent/tools.py` + planner template line |
| New product category | data + taxonomy only; spec parser gets a key vocabulary entry |
| New ranking signal | one function in `ranking/scorer.py` + weight in YAML; pairwise explainer picks it up automatically |
| New fake-review signal | one function in `reviews/features.py` + weight in `fakes.yaml` |
| 20k → 1M products | swap `KeywordIndex`/`VectorIndex` implementations (OpenSearch/Qdrant/pgvector); batch ingest; async gateway; Redis cache |
| Multi-user | session store → Redis; Streamlit → API + web client (API already exists) |
| New guardrail | one function in `guardrails/`, registered in the pre/post hooks |

---

## 11. Risks (schedule the riskiest first) and day-by-day plan

**Top risks:** (1) free-tier limits/model availability → probe on first coding day; (2) spec parsing + constraint fidelity on messy data (drives the "0 violations" criterion); (3) gold set & eval methodology (time-consuming, graded); (4) latency < 20 s with vision on free tier; (5) grounding validator strictness.

**SOW Phase 2 is only 2 days, so front-load offline work:** fake-review detector, PII/injection scanning, LLM gateway, and the eval skeleton are built in Phase 1 because they don't need the agent.

| Day | Date | Checkable output |
|---|---|---|
| 1 | Mon 28 Sep | Questions sent by **2:00 PM**; private repo created + shared; SOW-derived data-cleaning checklist; draft of this doc |
| 2 | Tue 29 Sep | Architecture doc + timeline submitted by **6:00 PM**. No feature code |
| 3 | Wed 30 Sep | Repo skeleton, schemas, configs; data profiled; cleaning + PII redaction done; `cleaning_log` + `data_cleaning.md`; SQLite loaded |
| 4 | Thu 1 Oct | FTS5 + Chroma indices; hybrid retrieval + filters; naive baseline; `probe_models.py` → `limits.yaml`; LLM gateway with cache/limiter/fake provider |
| 5 | Fri 2 Oct | First 25 gold queries labelled (pooled); retrieval vs baseline numbers; fake-review detector v1 on seeded dev fakes; **mid-point review with Zuhair** |
| 6 | Mon 5 Oct | Query understanding + clarify; summariser; agent state machine + tools + trace; guardrail hooks wired |
| 7 | Tue 6 Oct | Vision verifier; ranking + explainer; composer + grounding validator; Streamlit chat + trace + inspector; end-to-end demo path works |
| 8 | Wed 7 Oct | Remaining 25 queries, image claims (30), adversarial (≥10); **full `make eval`**; tune on dev only |
| 9 | Thu 8 Oct | Eval report (incl. ≥3 failure analyses), README, user guide, demo video, UI polish; **code freeze 6:00 PM** |
| 10 | Fri 9 Oct | Present + live defense. Rehearse: "why A above B", inject a hostile review live, kill the network to show degradation |

Micro-habits from SOW: daily commit + end-of-day update (done / blocked / next).

---

## 12. Open questions to send Hemanth (SOW §12.1 — deadline Mon 28 Sep, 2:00 PM)

1. **Models:** the SOW recommends Gemini 2.0 Flash and text-embedding-004; both appear to be shut down. May I use the current free-tier Gemini Flash/Flash-Lite and a local embedding model, documented in the architecture doc?
2. **Pre-sign-off work:** is repo scaffolding, schema definitions and read-only data profiling allowed before sign-off, given "no feature code before sign-off"?
3. **Data & confidentiality:** the SOW allows AI coding assistants, but forbids sharing data with third parties. Is it acceptable for the raw CSVs to sit in a workspace an IDE agent can read, or should agents only see small samples/profiles?
4. **Data delivery:** when do the CSVs arrive, and is there a documented schema/data dictionary (product↔review key, currency of price columns, image URL separators)?
5. **Fake-review metrics:** should precision/recall be computed on seeded fakes only, or must organically flagged reviews count as false positives too? May seeded fakes be LLM-generated?
6. **Gold labels:** is graded relevance (0–3) acceptable for NDCG, and may the gold set be pooled from several systems' top-K?
7. **Latency:** is the "median < 20 s" measured cold-cache (live) or is replay/warm-cache acceptable for the reported number?
8. **Abstention:** on no valid answer, should the system show *labelled nearest alternatives*, or strictly refuse?
9. **Unavailable models/quotas:** if free-tier quota is exhausted during the graded run, is a documented degraded run acceptable?
10. **Reproducibility:** is "same numbers" satisfied by cached LLM responses (replay mode) plus pinned dependencies?

---

## 13. Definition of done for this foundation
- [ ] `core/schemas.py` implemented exactly as §4 (first commit after sign-off)
- [ ] Every module has an interface, a fake/test double and at least one unit test before it gets a real LLM
- [ ] `make setup && make ingest && make run` works on a clean machine; `make eval` reproduces numbers
- [ ] Each row of §9 has a one-sentence justification you can say aloud without notes
