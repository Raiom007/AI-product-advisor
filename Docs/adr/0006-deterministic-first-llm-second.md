# ADR 0006 — Deterministic-first, LLM-second

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1, §5.1, §5.3, §5.4, §5.6, §5.8, §9

---

## Context

LLM calls consume free-tier quota, add latency, introduce non-determinism, and create a trust boundary (outputs are probabilities, not facts). Many tasks in the pipeline can be performed without LLMs: hard-constraint filtering, PII redaction, fake-review signal computation, ranking score calculation, budget tracking, grounding validation, and post-condition checks.

ARCHITECTURE.md §1 principle 1: "Deterministic first, LLM second. Anything that *can* be computed without an LLM (filters, fake-review signals, PII redaction, ranking, budget checks) *is*. LLMs are used only for language understanding, summarising, vision and wording."
ARCHITECTURE.md §1 principle 3: "The LLM never holds authority. The planner sees the user query and structured state — never raw review/description text."

---

## Decision

Assign tasks to layers by nature:

| Task | Layer | Rationale (from §1, §5) |
|------|-------|------------------------|
| Hard-constraint filtering | Deterministic (SQL) | Must be 0-violation; LLM non-determinism is unacceptable |
| Fake-review signal computation | Deterministic (Python + MinHash) | Offline; no quota; reproducible for eval |
| PII redaction | Deterministic (regex + checksum) | Safety requirement; must not depend on model availability |
| Injection detection | Deterministic (heuristic phrases) | Same; must not use the LLM to detect injection in LLM-visible text |
| Ranking score S(p) | Deterministic (weighted formula in §5.6) | Reproducible; explainable per-component in pairwise table |
| Grounding validation | Deterministic (id existence + regex for numbers) | LLM output is untrusted; a second LLM call to validate is circular |
| Budget / rate-limit tracking | Deterministic | Must work even when the LLM is unavailable |
| Query parsing | LLM (structured output) | Requires natural-language understanding; Hinglish normalisation |
| Review summarisation | LLM (quarantined, schema-constrained) | Requires natural-language understanding across 15 reviews |
| Vision claim verification | LLM multimodal | Requires image understanding |
| Answer composition | LLM (evidence pool as data, not instructions) | Requires natural-language wording |

---

## Alternatives rejected

| Alternative | Why rejected (source: §1, §5) |
|-------------|-------------------------------|
| LLM for hard-constraint checking | Non-deterministic; "0 violations" target cannot be met; LLM may miss a price constraint |
| LLM for fake-review detection | Consumes quota for 34k reviews offline; non-reproducible; can be manipulated by the review text itself (injection risk) |
| LLM for PII redaction | Quota-dependent; models have missed known PII formats in benchmarks; regex + checksum is more reliable for Indian PII patterns |
| LLM for ranking | Weights and signals must be explainable and tunable; an LLM score is a black box during the live defense |
| LLM for grounding validation | Circular: using the same provider to validate its own output; deterministic regex on id-presence is sufficient |

---

## Consequences

- **Positive:** Quota is spent only where LLMs add real value; expected ~8 calls per request (§6), cap 12 — well within free-tier daily limits.
- **Positive:** Every deterministic step is unit-testable without a live API (`ADVISOR_PROFILE=dev`).
- **Positive:** Deterministic steps are immune to LLM availability issues; the degradation ladder (§7) only downgrades LLM-dependent steps.
- **Positive:** Hard-constraint violations are 0 by construction (deterministic gate), not by probability.
- **Positive:** Ranking is fully explainable: `explain_rank.py` produces a per-component `w·(A−B)` table for the live defense.
- **Negative:** More code to maintain (custom ranking, fake-review detector) compared to delegating everything to an LLM.
- **Negative:** Fake-review signals are heuristic; a sufficiently sophisticated fake review may evade them — but this is disclosed in the eval report and addressed through seeded-fake precision/recall metrics.
