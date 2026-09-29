# ADR 0005 — LLM roles with ordered candidate lists

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1, §5.9, §9, §10

---

## Context

The system uses LLMs for five distinct tasks — parsing, summarising, vision, composing, and planning — each with different capability requirements (structured output, multimodal, speed, context size). Free-tier quotas are small and unstable, and at least one SOW-recommended model appears deprecated (§0, A2, A3).

ARCHITECTURE.md §5.9: "Roles, not models: code asks for `role='parser|summarizer|vision|composer|planner'`; `models.yaml` maps roles to models."
ARCHITECTURE.md §1 principle 7: "Everything is a config. Model IDs, weights, thresholds, budgets, limits → `configs/*.yaml`. No magic numbers in code."
AGENTS.md constraint 9: "Only `llm/gateway.py` talks to providers, by role, never by model name."
AGENTS.md constraint 4: "Never hard-code a model ID in Python."

---

## Decision

`configs/models.yaml` maps each **role** to an ordered list of **candidate model descriptors** (provider, model-id, params). `llm/gateway.py` is the only module that resolves a role to a concrete model; all other business code requests a role only.

- The first working candidate (within budget and rate limits) is used; on 429 / timeout / deprecation, the gateway steps to the next candidate.
- The `fake.py` test double is registered as a candidate for `ADVISOR_PROFILE=dev` — it never touches a real API.
- Day-1 probe (`scripts/probe_models.py`) lists the models a key can actually see and measures real RPM/RPD/TPM, then writes the confirmed IDs to `configs/limits.yaml`. This is the authoritative source, replacing guesses.
- "One door to LLMs" (AGENTS.md): every call goes through cache lookup → budget check → rate limiter → provider call → fallback chain → cache write → trace span.

---

## Alternatives rejected

| Alternative | Why rejected (source: §9, §5.9) |
|-------------|--------------------------------|
| Hard-coded model IDs in Python | Ruled out by AGENTS.md constraint 4; breaks when a model is deprecated without a code change |
| One model for all roles | Different roles need different capabilities (vision vs. structured output vs. speed); a single model wastes quota on simple tasks and may not support all roles |
| Separate gateway per provider | Duplicates rate-limiting, caching, budget, and tracing logic; no unified fallback |
| LangChain/LiteLLM abstraction | External dependency; requires an ADR; hides the gateway logic that must be defensible line by line |
| Two separate Gemini API keys as fallback | Uses the same failure domain and may violate ToS (§9 "Second Gemini key" row) |

---

## Consequences

- **Positive:** Swapping a model (e.g. when `gemini-flash` is deprecated again) requires one line change in `configs/models.yaml`, zero Python changes.
- **Positive:** Groq (Llama 3.3 70B) and Gemini operate on independent quota pools — the fallback is a genuine second lane, not the same bottleneck.
- **Positive:** `fake.py` provider gives the dev and test profiles deterministic, offline LLM responses at zero cost.
- **Positive:** The trace span records `model`, `tokens_in`, `tokens_out`, `cache_hit` per call — full observability of which candidate was actually used.
- **Negative:** The gateway is a critical path component; bugs there affect all LLM calls. Must be tested thoroughly with `fake.py`.
- **Negative:** Provider-specific structured-output APIs differ (JSON-schema mode vs. constrained decoding); the gateway must normalise these, adding complexity.
