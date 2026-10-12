"""Agent state and data schemas (§5.10, §4)."""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from advisor.core.budget import RequestBudget
from advisor.core.schemas import ParsedQuery, Recommendation

T = TypeVar("T")

class ToolResult(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: str | None = None
    degraded: bool = False
    cost: dict[str, int] = Field(default_factory=lambda: {"model_calls": 0, "ms": 0})
    metadata: dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    tool: str
    rationale: str
    depends_on: list[str] = []

class AgentState(BaseModel):
    session_id: str
    query: str
    chat_history: list[dict] = Field(default_factory=list)
    parsed: ParsedQuery | None = None
    plan: list[PlanStep] = []
    step: int = 0
    attempts: dict[str, int] = Field(default_factory=dict)

    # Tool outputs
    shortlist: list[dict] = []
    evidence: dict[str, list[dict]] = Field(default_factory=dict)
    summaries: dict[str, Any] = Field(default_factory=dict)
    checks: dict[str, Any] = Field(default_factory=dict)
    ranking: dict[str, Any] = Field(default_factory=dict)

    # End outputs
    degraded: list[str] = []
    budget: RequestBudget = Field(default_factory=RequestBudget)
    status: str = "ok" # ok, needs_clarification, abstained, degraded_ok
    message: str | None = None
    recommendations: list[Recommendation] = []
    trace_id: str = "stub"
