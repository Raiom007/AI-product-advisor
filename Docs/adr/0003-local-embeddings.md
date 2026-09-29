# ADR 0003 — Local embeddings: bge-small-en-v1.5 (sentence-transformers, CPU)

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1, §5.2, §9, §10

---

## Context

The system needs to embed ~54k texts (products + reviews) for semantic search and must continue to produce embeddings during development, testing, and evaluation without consuming quota. ARCHITECTURE.md §0 assumption A3 notes that `text-embedding-004` (the SOW-suggested model) appears to be shut down as of Jan 2026.

Constraints from ARCHITECTURE.md §1:
- "Everything is a config" — model IDs must not be hard-coded.
- "Fail soft" — quota exhaustion on an embedding API would break the offline ingest pipeline.
- Free tier only (§1 constraint 10) — no paid GPU.
- "One code path for app and eval" — embeddings must be reproducible across runs.

ARCHITECTURE.md §5.2: "local `bge-small-en-v1.5` on CPU (~54k texts → minutes, deterministic, zero quota)."
ARCHITECTURE.md §9: embedding choice rationale: "deterministic, no quota for ~54k texts, reproducible."

---

## Decision

Use `bge-small-en-v1.5` via `sentence-transformers`, running on CPU, as the sole embedding model.

- Wrapped behind an `Embedder` interface so the model is swappable without changing retrieval code.
- Model ID lives in `configs/models.yaml` under the `embedder` role — never hard-coded in Python.
- The same `Embedder` instance is used for both ingest (offline) and online query embedding.
- Hinglish queries are handled upstream: `parser.py` normalises them to `query_en` (English rewrite) before the embedding call; if retrieval quality on Hinglish proves insufficient, a multilingual small model is substituted behind the same interface.

---

## Alternatives rejected

| Alternative | Why rejected (source: §9) |
|-------------|--------------------------|
| `text-embedding-004` (Google API) | Reportedly shut down Jan 2026; also: quota-dependent, non-reproducible across runs (API can change model weights), requires internet for every ingest and test run |
| Any other embedding API | Same failure domain as above; quota for ~54k texts would be a significant free-tier constraint |
| Larger local models (e.g. bge-large, e5-large) | Slow on CPU for 54k texts; no accuracy benefit justifies the ingest time for this dataset size |
| OpenAI text-embedding-3-small | Paid; ruled out by SOW "free only" |
| FAISS + any API embedder | Adds API dependency back; non-reproducible |

---

## Consequences

- **Positive:** Zero quota consumption for ingest and test runs — `make ingest` and `make test` work offline.
- **Positive:** Bit-for-bit reproducible: same model weights + same text → same vector → same retrieval results across runs and machines (required for eval replay mode).
- **Positive:** No network dependency during development or CI.
- **Positive:** Seam is in place for upgrade: swap the `Embedder` implementation and model ID in `configs/models.yaml`.
- **Negative:** CPU embedding of 54k texts takes minutes; acceptable for a once-per-dataset offline ingest, not for interactive use.
- **Negative:** `bge-small-en-v1.5` is English-optimised; Hinglish queries are handled by the `query_en` normalisation step — if that step degrades (e.g. parser fallback), retrieval quality may drop for Hinglish inputs.
- **Negative:** Model weights must be downloaded on first `make setup` (requires internet once).
