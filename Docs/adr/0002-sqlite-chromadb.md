# ADR 0002 — SQLite + ChromaDB as the storage layer

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1, §5.2, §9, §10

---

## Context

The system must store and query ~20k products, ~34k reviews, taxonomy, fake-review flags, image-check cache, and session state. It must support:
- Hard-constraint filtering (price, category, brand) — must be exact and fast.
- Full-text keyword search (BM25) over product names, descriptions, reviews.
- Dense semantic search over product and review text.
- Metadata-filtered vector search (e.g. only products in a price range).
- Offline ingest and online serving from the same files, on a single local machine.

ARCHITECTURE.md §0 assumption A1: "Single user, single machine, localhost only."

---

## Decision

Use **SQLite** as the relational source-of-truth and keyword index, and **ChromaDB** as the vector store.

- **SQLite** holds: `products`, `product_specs` (stable ids `spec:{pid}:{n}`), `reviews`, `review_flags`, `taxonomy`, `quarantine`, `image_check_cache`. FTS5 virtual tables (`products_fts`, `reviews_fts`) provide `bm25()` ranking without a startup rebuild. Hard filters are SQL joins; this makes the filter + search pipeline a single DB-local operation.
- **ChromaDB** holds two persistent collections: `products` (name + category + specs + description) and `reviews` (redacted text), both with metadata fields (`product_id`, `price`, `cat_l1..l3`, `brand`, `flagged`) enabling server-side pre-filtering before ANN search.
- Interfaces (`store/interfaces.py`) abstract both: `KeywordIndex.search(q, allow_ids, k)` and `VectorIndex.search(q_emb, allow_ids, k)`. Retrieval modules never touch SQLite or Chroma directly.

---

## Alternatives rejected

| Alternative | Why rejected (source: §9) |
|-------------|--------------------------|
| PostgreSQL | Overkill for a single-user MVP; non-trivial setup; ships nothing with Python |
| CSV/pandas only | No constraint joins; no FTS; no persistent index |
| FAISS | No metadata filters; would require a separate SQL query + in-memory post-filter per request |
| pgvector / Qdrant | Setup overhead inappropriate for a 1-user MVP; seam in §10 covers migration if scale changes |
| In-memory BM25 (`rank_bm25`) | Requires a full in-memory rebuild on startup; no filter integration with SQL |
| Single store for both | No single open-source store handles FTS5 + ANN + metadata filters at this scale without ops complexity |

---

## Consequences

- **Positive:** Zero ops — both stores are embedded libraries; `make ingest` writes files that `make run` reads.
- **Positive:** Deterministic ingest: running `make ingest` twice produces the same DB and Chroma collection (no external service state).
- **Positive:** Hard filters execute in SQL before the vector search, not as a post-filter — correct by construction.
- **Positive:** Abstracted interfaces mean the swap path (→ OpenSearch/Qdrant for 1M products) is a single-file change per §10.
- **Negative:** SQLite write concurrency is limited (one writer); acceptable for single-user MVP but must change before multi-user.
- **Negative:** ChromaDB's in-process ANN index does not support streaming updates during ingest; ingest and serving must be separated (offline ingest, online read-only).
