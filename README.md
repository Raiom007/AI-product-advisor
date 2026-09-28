# AI Product Advisor MVP

An AI-powered product recommendation assistant that helps users discover and compare products using product data, customer reviews, images, and LLM-based reasoning.

## Overview

The AI Product Advisor is a multimodal recommendation system designed to:

- Understand user shopping queries
- Retrieve relevant products from a catalogue
- Analyze reviews and product information
- Verify product details using images
- Provide ranked recommendations with explanations

The system follows an offline + online architecture:

- **Offline phase:** Data preparation, cleaning, indexing, and review analysis
- **Online phase:** User query processing, retrieval, ranking, and recommendation generation

---

## Features (MVP)

- Product search and recommendation
- Natural language query understanding
- Product and review retrieval
- Hybrid search (keyword + semantic search)
- Review intelligence
- Image-based product verification
- Explainable recommendations with evidence
- LLM fallback and caching support
- Evaluation and tracing support

---

## High-Level Architecture
<img width="1739" height="956" alt="AI Product Advisor MVP - Context" src="https://github.com/user-attachments/assets/033c0845-4f3e-42f8-80de-08eafbd05992" />



---

## Tech Stack

### Backend
- Python
- Pydantic
- FastAPI (optional API layer)

### Storage
- SQLite
- ChromaDB

### AI Models
- Gemini API
- Groq API

### UI
- Streamlit

### Testing & Evaluation
- Pytest
- Custom evaluation harness

---

## Project Structure

product-advisor/
├─ AGENTS.md                     # rules for Antigravity agents (see model guide appendix)
├─ README.md  Makefile  requirements.txt  .env.example  .gitignore
├─ configs/
│  ├─ models.yaml                # role → ORDERED candidate list [{provider, model, needs:[vision,json_schema]}]
│  ├─ limits.yaml                # RPM/RPD/TPM per model (filled from probe), request budget
│  ├─ ranking.yaml               # enabled signals + weights + thresholds + unverifiable_policy
│  ├─ fakes.yaml                 # detector signals + weights + thresholds
│  ├─ data.yaml                  # CSV column mapping, cleaning switches
│  ├─ features.yaml              # which plug-ins are enabled (tools, guardrails, retrievers, signals), feature flags, active domain pack
│  └─ profiles/  dev.yaml eval.yaml demo.yaml   # ADVISOR_PROFILE: dev = cache-first + fake LLM · eval = replay · demo = live
├─ prompts/                      # versioned prompt templates (parser, summarizer, vision, composer, planner); content hash goes in cache key + trace
├─ domain/electronics/           # domain pack: taxonomy seed, spec vocabulary + units, use-case lexicon, visual-claim templates, injection patterns
├─ data/  (gitignored)           # raw/  processed/  cache/  index/  traces/
├─ src/advisor/
│  ├─ core/        schemas.py  registry.py  events.py  config.py  prompts.py  errors.py  budget.py  tracing.py  cache.py  manifest.py
│  ├─ plugins/     __init__.py   # explicit import list = the plug-in manifest (no magic auto-discovery)
│  ├─ llm/         base.py  capabilities.py  gemini.py  groq.py  fake.py(test double)  gateway.py  ratelimit.py
│  ├─ ingest/      profile.py  clean_products.py  clean_reviews.py  specs_parser.py  build_index.py
│  ├─ store/       interfaces.py  sqlite_store.py  vector_store.py  session_store.py
│  ├─ guardrails/  pii.py  injection.py  untrusted.py  abstain.py         # each registered with @guardrail(stage=...)
│  ├─ understanding/  parser.py  clarify.py
│  ├─ retrieval/   filters.py  keyword.py  semantic.py  hybrid.py  (RRF fusion over enabled retrievers)
│  ├─ reviews/     fake_detector.py  features.py(fake signals)  summarizer.py  sentiment.py
│  ├─ vision/      fetch.py  claims.py  verifier.py
│  ├─ ranking/     scorer.py(generic sum over registered signals)  signals.py(built-in signals)  explain_rank.py
│  ├─ explain/     composer.py  grounding_validator.py  render.py
│  ├─ agent/       state.py  tools.py(built-in tool wrappers)  planner.py  verifiers.py  loop.py(plan executor)
│  ├─ service.py   # facade: advise(query, session_id) -> AdvisorResponse
│  ├─ api.py       # thin FastAPI wrapper (optional, ~40 lines)
│  └─ ui/          app.py  pages/  (Streamlit)
├─ eval/
│  ├─ data/  queries.jsonl  gold.jsonl  seeded_fakes.jsonl  image_claims.jsonl  adversarial.jsonl
│  ├─ baseline.py  metrics.py  run_eval.py  report.py
│  ├─ suites/    # one file per registered eval suite (retrieval, fakes, vision, guardrails, e2e)
│  └─ reports/   (generated: eval_report.md, metrics.json, per-query CSV) + baseline_metrics.json (committed at the final version)
├─ scripts/  probe_models.py  make_seeded_fakes.py  label_pool.py
├─ tests/        unit tests per module + golden tests for guardrails + contract tests per port + test_extension_points.py
└─ docs/  ARCHITECTURE.md  data_cleaning.md  timeline.md  user_guide.md  eval_report.md  adr/


---

## Data Flow
<img width="2513" height="1619" alt="AI Product Advisor Data Flow" src="https://github.com/user-attachments/assets/9a26a7b3-df7a-4705-bc86-663ac45883a0" />


### Offline Pipeline

1. Load product catalogue and reviews
2. Clean and normalize data
3. Remove sensitive information
4. Build search indexes
5. Generate embeddings
6. Detect review quality issues
7. Store processed data

---

### Online Pipeline

1. User submits a shopping request
2. Query is understood and structured
3. Relevant products are retrieved
4. Reviews and images are analyzed
5. Products are ranked
6. AI generates an evidence-based explanation
7. Recommendation is returned

---

## Running the Project

Coming soon.

Planned commands:

```bash
make setup
make ingest
make run
make eval
make test
