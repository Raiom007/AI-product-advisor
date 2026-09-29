"""Named registry instances and decorator shortcuts for all §4.1 extension points.

Each extension point is a Registry[T] instance (from core/registry.py).
Decorators are thin wrappers that call registry.register(name) so plug-ins
can use a single import to declare themselves.

Extension points (§4.1 / ARCHITECTURE.md §10 seams table):
  tools            — agent tools (parse_query, retrieve, …)
  verifiers        — post-tool rule-based checks (parse_ok, retrieval_nonempty, …)
  ranking_signals  — scorer components (relevance, soft_fit, …)
  fake_signals     — fake-review detector signals (near_dup, burst, …)
  guardrails       — pre/post safety checks (pii_pre, grounding_post, …)
  constraint_kinds — Constraint.kind values (category, budget, …) + plug-ins
  evidence_kinds   — EvidenceRef.kind values (spec_line, review, …) + plug-ins
  retrievers       — retrieval strategies (keyword, semantic)
  providers        — LLM provider adapters (gemini, groq, fake)
  eval_suites      — eval suite runners (retrieval, detector, …)

Runtime validation (P3 requirement 3):
  validate_constraint_kind(kind) — raises ValueError for unknown kinds
  validate_evidence_kind(kind)   — raises ValueError for unknown kinds
  These are called by the gateway/agent, not the schema, so plug-in kinds
  can extend the set without touching Constraint/EvidenceRef Literals.

Plug-in usage (from OUTSIDE core/):
    from advisor.core.registries import ranking_signals

    @ranking_signals.register("price_competitiveness")
    def price_competitiveness_signal(product, context):
        ...

Zero edits to core/ needed.
"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from advisor.core.registry import Registry

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Registry instances
# ---------------------------------------------------------------------------

#: Agent tools — each has input/output schema, requires_llm, degradable flag.
tools: Registry = Registry("tools")

#: Post-tool rule-based verifiers (§5.10 verifier table).
verifiers: Registry = Registry("verifiers")

#: Ranking signal functions — contribute to ScoreBreakdown (§5.6).
ranking_signals: Registry = Registry("ranking_signals")

#: Fake-review detector signal functions (§5.4).
fake_signals: Registry = Registry("fake_signals")

#: Guardrail check functions — pre or post stage (§5.8).
guardrails: Registry = Registry("guardrails")

#: Known Constraint.kind values + future plug-in kinds.
#: WHY: Literals in schemas.py are the documented contract; this registry is
#: the runtime extension path (P3 requirement 3).
constraint_kinds: Registry = Registry("constraint_kinds")

#: Known EvidenceRef.kind values + future plug-in kinds.
evidence_kinds: Registry = Registry("evidence_kinds")

#: Retrieval strategy implementations (keyword, semantic, …).
retrievers: Registry = Registry("retrievers")

#: LLM/embedding provider adapters (gemini, groq, fake, …).
providers: Registry = Registry("providers")

#: Eval suite runners (retrieval, detector, parser, vision, guardrail, e2e).
eval_suites: Registry = Registry("eval_suites")

# ---------------------------------------------------------------------------
# Built-in kind registrations
# WHY: populate before any plug-in import so validate_*_kind works even if
# no plug-in has been loaded yet.
# ---------------------------------------------------------------------------

# WHY: Built-in kind names are enumerated here so validate_*_kind() works
# even before constraint_checks.py / evidence resolvers are imported.
# The real callable implementations are registered by retrieval/constraint_checks.py
# using @constraint_kinds.register(). Pre-registering placeholders here caused
# duplicate-name errors when that module was imported (P6 fix).
_BUILTIN_CONSTRAINT_KINDS: frozenset[str] = frozenset(
    ("category", "brand_exclude", "must_have", "size_limit", "weight_limit", "budget")
)
_BUILTIN_EVIDENCE_KINDS: frozenset[str] = frozenset(("spec_line", "review", "image_obs"))

for _kind in ("spec_line", "review", "image_obs"):
    @evidence_kinds.register(_kind)
    def _evidence_kind_placeholder(**_): ...  # noqa: E306


# ---------------------------------------------------------------------------
# Decorator shortcuts
# ---------------------------------------------------------------------------

def tool(name: str) -> Callable[[T], T]:
    """Register a tool implementation. Usage: @tool("retrieve")"""
    return tools.register(name)


def verifier(name: str) -> Callable[[T], T]:
    """Register a verifier. Usage: @verifier("parse_ok")"""
    return verifiers.register(name)


def ranking_signal(name: str) -> Callable[[T], T]:
    """Register a ranking signal. Usage: @ranking_signal("relevance")"""
    return ranking_signals.register(name)


def fake_signal(name: str) -> Callable[[T], T]:
    """Register a fake-review signal. Usage: @fake_signal("near_dup")"""
    return fake_signals.register(name)


def guardrail(stage: str) -> Callable[[str], Callable[[T], T]]:
    """Register a guardrail at a given stage. Usage: @guardrail(stage="pre")("pii_pre")

    Returns a decorator factory so the stage is captured.
    Full syntax::

        @guardrail(stage="pre")("pii_pre")
        def pii_pre_check(text): ...
    """
    def outer(name: str) -> Callable[[T], T]:
        def decorator(fn: T) -> T:
            # Store stage as an attribute so the runner can filter by stage.
            fn._guardrail_stage = stage  # type: ignore[attr-defined]
            return guardrails.register(name)(fn)
        return decorator
    return outer


def constraint_kind(name: str) -> Callable[[T], T]:
    """Register a new Constraint.kind plug-in. Usage: @constraint_kind("price_cap")"""
    return constraint_kinds.register(name)


def evidence_kind(name: str) -> Callable[[T], T]:
    """Register a new EvidenceRef.kind plug-in. Usage: @evidence_kind("price_history")"""
    return evidence_kinds.register(name)


def retriever(name: str) -> Callable[[T], T]:
    """Register a retrieval strategy. Usage: @retriever("keyword")"""
    return retrievers.register(name)


def provider(name: str) -> Callable[[T], T]:
    """Register an LLM/embedding provider adapter. Usage: @provider("gemini")"""
    return providers.register(name)


def suite(name: str) -> Callable[[T], T]:
    """Register an eval suite runner. Usage: @suite("retrieval")"""
    return eval_suites.register(name)


# ---------------------------------------------------------------------------
# Runtime validation helpers (P3 requirement 3)
# ---------------------------------------------------------------------------

def validate_constraint_kind(kind: str) -> None:
    """Raise ValueError if kind is not a registered constraint kind.

    WHY: Schema Literals define the documented contract; this check handles
    plug-in kinds that extend the set at runtime without schema changes.
    Called by the parser/gateway, not by Pydantic validators.
    """
    registered = set(constraint_kinds.all_names()) | _BUILTIN_CONSTRAINT_KINDS
    if kind not in registered:
        registered_str = ", ".join(sorted(registered))
        raise ValueError(
            f"Unknown Constraint.kind '{kind}'. "
            f"Registered kinds: {registered_str}. "
            f"Use @constraint_kind('{kind}') to add a new kind."
        )


def validate_evidence_kind(kind: str) -> None:
    """Raise ValueError if kind is not a registered evidence kind."""
    registered = set(evidence_kinds.all_names()) | _BUILTIN_EVIDENCE_KINDS
    if kind not in registered:
        registered_str = ", ".join(sorted(registered))
        raise ValueError(
            f"Unknown EvidenceRef.kind '{kind}'. "
            f"Registered kinds: {registered_str}. "
            f"Use @evidence_kind('{kind}') to add a new kind."
        )
