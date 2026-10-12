"""Rule-based verifiers for agent orchestration (§5.10)."""
from collections.abc import Callable

from advisor.agent.state import AgentState, ToolResult
from advisor.core.registry import Registry

verifiers_registry: Registry = Registry("verifiers")

class VerifierResult:
    def __init__(self, action: str, reason: str = ""):
        # actions: continue, retry, replan, degrade, abstain, ask_user
        self.action = action
        self.reason = reason

def verifier(name: str) -> Callable:
    return verifiers_registry.register(name)

@verifier("parse_ok")
def verify_parse_ok(state: AgentState, result: ToolResult) -> VerifierResult:
    """Check if parse needs clarification."""
    # WHY: We check state.step to ensure this only fires right after parse_query,
    # not during any other tool step. The old "asked once" guard (attempts >= 1)
    # was silently swallowing clarification on every turn except the very first
    # in a session — removed it so each new AgentState gets a clean check.
    if state.step >= 0 and state.plan[state.step].tool == "parse_query":
        if result.ok and result.data and getattr(result.data, "needs_clarification", False):
            return VerifierResult("ask_user", "Query is ambiguous")
    return VerifierResult("continue")

@verifier("retrieval_nonempty")
def verify_retrieval_nonempty(state: AgentState, result: ToolResult) -> VerifierResult:
    """Check if retrieval returned 0 candidates."""
    if state.step >= 0 and state.plan[state.step].tool == "retrieve":
        if result.ok and not result.data:
            if state.attempts.get("retrieval_nonempty", 0) < 2:
                state.attempts["retrieval_nonempty"] = state.attempts.get("retrieval_nonempty", 0) + 1
                return VerifierResult("retry", "relax soft prefs")
            else:
                return VerifierResult("abstain", "No candidates found after relaxations")
    return VerifierResult("continue")

@verifier("hard_constraints_hold")
def verify_hard_constraints_hold(state: AgentState, result: ToolResult) -> VerifierResult:
    # Check if any candidate violates hard constraints
    # (Implementation stub)
    return VerifierResult("continue")

@verifier("evidence_sufficient")
def verify_evidence_sufficient(state: AgentState, result: ToolResult) -> VerifierResult:
    if state.step >= 0 and state.plan[state.step].tool == "analyse_reviews":
        # Check if < k unflagged reviews
        pass
    return VerifierResult("continue")

@verifier("contradiction")
def verify_contradiction(state: AgentState, result: ToolResult) -> VerifierResult:
    """Flag any product in shortlist that has a visual 'disagree' verdict."""
    if not state.shortlist:
        return VerifierResult("continue")
    found = False
    for p in state.shortlist:
        checks = p.get("visual_checks", [])
        if any(c.get("verdict") == "disagree" for c in checks):
            p["has_contradiction"] = True
            found = True
    if found:
        # Do not block: mark state so confidence is lowered (done in explain_rank)
        return VerifierResult("continue")
    return VerifierResult("continue")

@verifier("grounding_ok")
def verify_grounding_ok(state: AgentState, result: ToolResult) -> VerifierResult:
    if state.step >= 0 and state.plan[state.step].tool == "compose_answer":
        # Check grounding
        pass
    return VerifierResult("continue")

@verifier("budget_ok")
def verify_budget_ok(state: AgentState, result: ToolResult) -> VerifierResult:
    if state.budget.is_exhausted():
        if "budget exhausted" not in state.degraded:
            return VerifierResult("degrade", "budget exhausted")
    return VerifierResult("continue")
