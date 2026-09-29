# ADR 0001 — No orchestration framework: plain-Python state machine + planner

**Date:** 2026-09-29
**Status:** Accepted
**Refs:** ARCHITECTURE.md §1, §5.10, §9, §10

---

## Context

The agent must execute a bounded, inspectable tool sequence across retrieval, review analysis, vision, ranking, explanation, and clarification. Several open-source frameworks (LangGraph, LangChain, CrewAI) provide orchestration abstractions for similar pipelines.

ARCHITECTURE.md §9 states: "The owner must be able to explain and defend every line in a live session."
ARCHITECTURE.md §5.10 describes the design as "a bounded state machine with an LLM planner, not a fixed pipeline and not an unconstrained ReAct loop."
ARCHITECTURE.md constraint 10 (§1) rules out LangChain/LangGraph/CrewAI without an ADR.

---

## Decision

Implement the agent as a plain-Python state machine (`agent/loop.py`) with:
- An `AgentState` dataclass carrying session, plan, step counters, shortlist, evidence, budget, and `degraded[]`.
- A planner LLM call that produces an ordered tool list from `ParsedQuery`; the default plan is a template the LLM may trim.
- Per-tool `Verifier` functions (rule-based, not LLM) that enforce post-conditions.
- Hard limits: `max_steps=25`, `max_replans=2`, plus `RequestBudget` counters in `AgentState`.

---

## Alternatives rejected

| Alternative | Why rejected (source: §9) |
|-------------|--------------------------|
| LangGraph | Hides control flow; heavy dependency; harder to defend line by line during live examination |
| LangChain | Same; also ruled out by AGENTS.md constraint 10 without ADR |
| CrewAI | Same; multi-agent overhead unnecessary for a single-user, bounded tool set |
| Fixed pipeline (no planner) | Cannot handle conditional steps (e.g. skip vision when no visual claim is checkable) |
| Unconstrained ReAct loop | Not provably bounded; loop termination would require additional guarantees |

---

## Consequences

- **Positive:** ~300 lines of inspectable Python; every control-flow branch is visible; loop termination guaranteed by counters; easy to unit-test with fake tools.
- **Positive:** Supports live defense: "why did the agent skip vision on this query?" is answered by reading the planner output in the trace.
- **Positive:** No new external dependency; satisfies the "free tier only" rule.
- **Negative:** Team must maintain its own state machine instead of relying on a library's abstractions.
- **Negative:** If the tool set grows substantially post-MVP, the hand-rolled planner may need to be extended (see §10 seam: "New tool → one class in `agent/tools.py` + planner template line").
