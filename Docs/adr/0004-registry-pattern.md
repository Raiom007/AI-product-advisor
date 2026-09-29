# ADR 0004 — Registry pattern for all extension points

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1 (contracts), §4.1, §9, §10

---

## Context

The system has multiple categories of components that must be independently replaceable and testable: tools, verifiers, ranking signals, fake-review signals, guardrails, retrievers, constraint kinds, evidence kinds, LLM providers, and eval suites. ARCHITECTURE.md §4.1 names all these extension points explicitly.

ARCHITECTURE.md §1 principle 2: "Contracts, not conventions. Every module takes and returns Pydantic models. Modules can be tested and evaluated alone."
ARCHITECTURE.md constraint 3 (AGENTS.md): "A new tool, ranking signal, fake-review signal, guardrail, retriever, constraint kind, evidence kind, provider or eval suite is a registered plug-in (§4.1). Do not add seams that are not in §4.1."
ARCHITECTURE.md §9 (Orchestration row): "Extensions are explicitly registered rather than discovered through implicit magic."

---

## Decision

Implement a generic `Registry[T]` class in `core/registry.py`, instantiated once per extension category in `core/registries.py`. Each extension is registered via a decorator (e.g. `@tool`, `@ranking_signal`, `@guardrail(stage=...)`).

- `enabled()` checks `configs/features.yaml` so extensions can be disabled without code changes.
- Registration is explicit: an unknown name raises an error at startup, not at runtime.
- `agent/` is the only module that wires registries together; all other modules register into them without knowing about each other.
- Runtime validation: an unknown `Constraint.kind` or `EvidenceRef.kind` is caught by a registry check, not by the Pydantic schema, so new kinds can be added without touching `core/schemas.py`.

Named extension points (§4.1): `tools`, `verifiers`, `ranking_signals`, `fake_signals`, `guardrails`, `constraint_kinds`, `evidence_kinds`, `retrievers`, `providers`, `eval_suites`.

---

## Alternatives rejected

| Alternative | Why rejected (source: §9 "Plugin-based" principle) |
|-------------|---------------------------------------------------|
| Implicit discovery (e.g. `importlib` scanning a directory) | "Extensions are explicitly registered rather than discovered through implicit magic" — hard to inspect, debug, or disable selectively |
| Hard-coded if/elif dispatch | Every new extension requires editing core business logic; no enable/disable without code change |
| Dependency injection framework | Adds a dependency without adding expressiveness for this scale; harder to explain during live defense |
| Feature flags in business code | Mixes infrastructure and domain logic; features.yaml approach keeps the flag check in one place |

---

## Consequences

- **Positive:** Adding a new ranking signal, fake-review signal, or guardrail requires exactly one file: implement + decorate, add a weight/config key, done — zero edits to `core/`.
- **Positive:** `enabled()` makes features toggleable per profile (`dev`, `eval`, `demo`) without code changes.
- **Positive:** Test isolation: tests can register a dummy extension without polluting the real registry.
- **Positive:** Registry state is inspectable at startup: `make run` can log all registered extensions and their enabled status.
- **Negative:** Every new extension category requires a registry entry in `core/registries.py` — this is intentional friction to prevent undocumented seams.
- **Negative:** Decorator-style registration means the module must be imported for the extension to appear in the registry; `agent/` must import all modules at startup.
