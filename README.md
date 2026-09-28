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

## Project Structure

```text
product-advisor/
├── AGENTS.md
├── README.md
├── requirements.txt
├── Makefile
├── .env.example
│
├── configs/                     # Configuration and feature flags
│   ├── models.yaml              # Model candidates & capabilities
│   ├── limits.yaml              # Rate/token/request limits
│   ├── ranking.yaml             # Ranking signals & weights
│   ├── fakes.yaml               # Fake-review detection
│   ├── data.yaml                # Data ingestion configuration
│   ├── features.yaml            # Enabled plugins & features
│   └── profiles/                # dev / eval / demo profiles
│
├── prompts/                     # Versioned prompt templates
│
├── domain/
│   └── electronics/             # Electronics domain knowledge pack
│
├── data/                        # Runtime data (gitignored)
│   ├── raw/
│   ├── processed/
│   ├── cache/
│   ├── index/
│   └── traces/
│
├── src/advisor/
│   ├── core/                    # Schemas, config, events, cache, tracing
│   ├── plugins/                 # Explicit plugin registry
│   │
│   ├── llm/                     # Multi-provider LLM gateway
│   ├── ingest/                  # Product/review ingestion & indexing
│   ├── store/                   # SQLite, vector & session stores
│   │
│   ├── guardrails/              # PII, injection, trust & abstention
│   ├── understanding/           # Query parsing & clarification
│   ├── retrieval/               # Keyword, semantic & hybrid retrieval
│   ├── reviews/                 # Fake detection, sentiment & summarization
│   ├── vision/                  # Image fetching & claim verification
│   ├── ranking/                 # Product scoring & ranking signals
│   ├── explain/                 # Grounded explanations & rendering
│   │
│   ├── agent/                   # Agent state, planning, tools & execution
│   │
│   ├── service.py               # Main application facade
│   ├── api.py                   # FastAPI API layer
│   └── ui/                      # Streamlit interface
│
├── eval/
│   ├── data/                    # Evaluation & adversarial datasets
│   ├── suites/                  # Retrieval, fake, vision, guardrail & E2E tests
│   ├── run_eval.py              # Evaluation runner
│   ├── metrics.py               # Evaluation metrics
│   └── reports/                 # Generated evaluation reports
│
├── scripts/                     # Model probing & dataset utilities
├── tests/                       # Unit, contract & golden tests
│
└── docs/
    ├── ARCHITECTURE.md
    ├── data_cleaning.md
    ├── timeline.md
    ├── user_guide.md
    ├── eval_report.md
    └── adr/                     # Architecture Decision Records
```

### Architecture at a Glance

```text
                         ┌───────────────┐
                         │     User      │
                         └───────┬───────┘
                                 │
                                 ▼
                       ┌───────────────────┐
                       │ Query Understanding│
                       └─────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
               Retrieval      Reviews       Vision
                    │            │            │
                    └────────────┼────────────┘
                                 ▼
                         ┌──────────────┐
                         │   Ranking    │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ Agent / Plan │
                         │   Executor   │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │ Context + Guardrails  │
                    │ + Tools + Memory       │
                    └───────────┬───────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │ Multi-LLM    │
                         │ Gateway      │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │ Grounded     │
                         │ Explanation  │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │ Advisor      │
                         │ Response     │
                         └──────────────┘
```

### Design Principles

* **Modular:** Retrieval, ranking, guardrails, LLMs, and other capabilities are independently replaceable.
* **Plugin-based:** Extensions are explicitly registered rather than discovered through implicit magic.
* **Multi-model:** The LLM gateway supports ordered model fallbacks based on capabilities, limits, and configuration.
* **Context-aware:** Relevant memory, retrieved evidence, tool outputs, and application state are assembled before generation.
* **Grounded:** Recommendations and explanations are validated against retrieved product evidence.
* **Config-driven:** Models, ranking signals, feature flags, limits, prompts, and domain behavior are configurable without changing core logic.
* **Evaluation-first:** Retrieval, fake detection, vision, guardrails, and end-to-end behavior are continuously evaluated against reproducible datasets.
* **Observable:** Caching, tracing, manifests, and evaluation reports make system behavior inspectable and reproducible.



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
