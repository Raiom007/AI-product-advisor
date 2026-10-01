"""Core data contracts for the AI Product Advisor.

Implements §4 of ARCHITECTURE.md exactly: same names, fields, types and
Literals. Do NOT change any field without proposing a diff and writing an ADR.

Additional types added for §4.1 needs:
- ToolResult[T]:  generic envelope for all tool return values (§4, prose after code block)
- Verdict:        verifier outcome (§5.10 verifier table)
- GuardResult:    guardrail outcome (§5.8)
"""
from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# §4 — Query
# ---------------------------------------------------------------------------

class Budget(BaseModel):
    min_inr: float | None = None
    max_inr: float | None = None


class Constraint(BaseModel):
    kind: Literal[
        "category", "brand_exclude", "must_have",
        "size_limit", "weight_limit", "budget",
    ]
    key: str                    # e.g. "ports.hdmi", "weight_kg", "brand"
    # WHY: "between" added (P6) for budget ranges {min_inr, max_inr} — backwards-compatible
    # (new Literal; old callers only use the previous 6). ADR-0007 if this breaks a test.
    op: Literal["eq", "gte", "lte", "in", "not_in", "contains", "between"]
    # WHY: dict added for budget-range value {"min_inr": x, "max_inr": y} — additive only
    value: str | float | list[str] | dict[str, Any]
    raw_text: str               # the user's words, for the trace/UI

    # WHY: ext allows future plug-in constraint kinds to carry extra metadata
    # without breaking the schema contract. Registry validation (not Literal)
    # handles unknown kinds at runtime (§4.1 / P3 requirement 3).
    ext: dict[str, Any] = Field(default_factory=dict)


class ParsedQuery(BaseModel):
    language: Literal["en", "hinglish"]
    query_en: str                        # normalised English rewrite (Hinglish → English)
    category: str | None = None       # resolved against real taxonomy
    subcategory: str | None = None
    budget: Budget = Field(default_factory=Budget)
    use_case: str | None = None
    hard: list[Constraint] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None    # exactly one question


# ---------------------------------------------------------------------------
# §4 — Evidence
# ---------------------------------------------------------------------------

class EvidenceRef(BaseModel):
    id: str                                # "spec:P123:4" | "rev:R998" | "img:P123:2:a"
    kind: Literal["spec_line", "review", "image_obs"]
    product_id: str
    text: str                              # canonical stored text (redacted)
    meta: dict[str, Any] = Field(default_factory=dict)   # rating, date, flagged, image_url, …

    # WHY: ext allows future evidence kinds (e.g. "price_history") to carry
    # extra fields. Registry validation handles unknown kinds (P3 req 3).
    ext: dict[str, Any] = Field(default_factory=dict)


class ReviewFlag(BaseModel):
    review_id: str
    score: float                           # 0..1
    signals: dict[str, float]             # {"near_dup": 0.9, "burst": 0.0, ...}
    reasons: list[str]                    # human-readable, shown in the inspector
    action: Literal["exclude", "downweight", "keep"]


# ---------------------------------------------------------------------------
# §4 — Analysis
# ---------------------------------------------------------------------------

class ReviewSummary(BaseModel):
    product_id: str
    praises: list[dict]       # {"point": str, "review_ids": [str]}
    complaints: list[dict]
    use_case_fit: dict        # {"verdict": "good|mixed|poor|unknown", "review_ids": [...]}
    n_reviews_used: int
    n_flagged_excluded: int

class ReviewSummaryBatch(BaseModel):
    summaries: list[ReviewSummary]


class VisualCheck(BaseModel):
    claim: str                # "has numeric keypad"
    source_ref: str           # spec/review evidence id that made the claim
    verdict: Literal["agree", "disagree", "unverifiable"]
    observation: str
    image_ids: list[str]


# ---------------------------------------------------------------------------
# §4 — Ranking & output
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    relevance: float
    soft_fit: float
    use_case_sentiment: float
    review_trust: float
    visual: float | None = None     # None when vision skipped
    total: float
    weights_used: dict[str, float]     # after renormalisation

    # WHY: ext carries per-signal debug data from plug-in ranking signals
    # so the pairwise explainer can include them without schema changes.
    ext: dict[str, Any] = Field(default_factory=dict)


class Recommendation(BaseModel):
    product_id: str
    rank: int
    paragraph: str                              # every sentence carries evidence ids
    statements: list[dict]                      # {"text": ..., "evidence_ids": [...]}
    constraint_evidence: dict[str, list[str]]   # constraint → spec-line ids
    review_quotes: list[str]                    # evidence ids (2-4, incl. ≥1 negative if any)
    image_observations: list[str]
    score: ScoreBreakdown
    confidence: Literal["high", "medium", "low"]


class AdvisorResponse(BaseModel):
    status: Literal["ok", "needs_clarification", "abstained", "degraded_ok"]
    message: str | None = None               # clarifying question / abstention reason
    recommendations: list[Recommendation] = Field(default_factory=list)
    degraded: list[str] = Field(default_factory=list)   # ["vision_skipped:rate_limit"]
    trace_id: str
    budget_report: dict                         # calls used/limit, wall-clock
    manifest: dict | None = None            # RunManifest.to_dict() stamped by service.py


# ---------------------------------------------------------------------------
# ToolResult[T] — generic envelope (§4 prose after code block)
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ToolCost(BaseModel):
    model_calls: int = 0
    ms: int = 0


class ToolResult(BaseModel, Generic[T]):
    """Uniform envelope returned by every tool in agent/tools.py.

    WHY: verifiers work on this uniformly — they check ok/degraded/error
    without knowing what T is (§4, §5.10).
    """
    ok: bool
    data: T | None = None
    error: str | None = None
    degraded: bool = False
    cost: ToolCost = Field(default_factory=ToolCost)


# ---------------------------------------------------------------------------
# Verdict — verifier outcome (§5.10 verifier table)
# ---------------------------------------------------------------------------

class Verdict(BaseModel):
    """Outcome of one verifier run."""
    verifier: str                                           # name registered in verifiers registry
    passed: bool
    action: Literal["continue", "replan", "ask_user", "abstain", "degrade", "lower_confidence"]
    reason: str | None = None
    ext: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GuardResult — guardrail outcome (§5.8)
# ---------------------------------------------------------------------------

class GuardResult(BaseModel):
    """Outcome of one guardrail check."""
    guardrail: str                           # name registered in guardrails registry
    stage: Literal["input", "retrieved", "prompt", "output", "pre", "post"]
    action: Literal["pass", "redact", "block"]
    reasons: list[str] = Field(default_factory=list)
    threat: str | None = None             # "pii" | "injection" | "grounding" | "constraint_violation"
    detail: str | None = None
    modified_text: str | None = None      # The redacted text if action == 'redact'
    ext: dict[str, Any] = Field(default_factory=dict)
