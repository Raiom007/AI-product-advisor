"""Agent planner (§5.10)."""
from advisor.agent.state import PlanStep, AgentState
from advisor.core.schemas import ParsedQuery

def default_plan(parsed: ParsedQuery) -> list[PlanStep]:
    """Default static plan graph."""
    plan = []
    plan.append(PlanStep(tool="parse_query", rationale="Understand user request"))
    # The verifier for parse_ok will trigger ask_user if ambiguous
    plan.append(PlanStep(tool="retrieve", rationale="Fetch candidates"))
    plan.append(PlanStep(tool="analyse_reviews", rationale="Summarise and compute sentiment"))
    # In a full system, PreRank goes here
    plan.append(PlanStep(tool="verify_images", rationale="Check visual claims"))
    plan.append(PlanStep(tool="rank", rationale="Final ranking"))
    plan.append(PlanStep(tool="compose_answer", rationale="Generate final grounded response"))
    return plan

def create_plan(state: AgentState, use_llm_planner: bool = False, context: dict = None) -> list[PlanStep]:
    """Create a plan for the agent."""
    if use_llm_planner:
        # LLM planner behind feature flag
        # Sees ONLY tool descriptions + ParsedQuery (no raw untrusted text)
        raise NotImplementedError("LLM planner not yet implemented")
    
    return default_plan(state.parsed if state.parsed else ParsedQuery(language="en", query_en=state.query))
