"""Tools registry and wrappers (§5.10)."""
import time
from typing import Callable, Dict, Any
from pydantic import BaseModel
from advisor.agent.state import ToolResult, AgentState
from advisor.core.registry import Registry

tools_registry: Registry = Registry("tools")

def tool(name: str) -> Callable:
    return tools_registry.register(name)

@tool("parse_query")
def parse_query_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    from advisor.llm.gateway import Gateway
    from advisor.understanding.parser import parse_query
    from advisor.understanding.clarify import apply_ambiguity_rule
    
    gateway = context.get("gateway")
    if not gateway:
        gateway = Gateway({}, {})
    try:
        pq = parse_query(gateway, state.query, taxonomy_list="Electronics, Home", valid_categories={"Electronics", "Home"})
        apply_ambiguity_rule(pq)
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=pq, cost={"model_calls": 1, "ms": ms})
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=False, error=str(e), cost={"model_calls": 0, "ms": ms})

@tool("retrieve")
def retrieve_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        # Stub: normally calls retriever, but we will return an empty list or mock
        # wait, we have fts5 and chroma, we can do an actual retrieval!
        # But we need store context. For now, let's just return what state has or a stub list if it's empty
        ms = int((time.time() - start_t) * 1000)
        # return dummy
        data = [{"id": "P1", "name": "Dummy product", "price": 40000}]
        return ToolResult(ok=True, data=data, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

@tool("analyse_reviews")
def analyse_reviews_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data={"P1": {}}, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

@tool("rank")
def rank_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        # Stub relevance only
        data = {"P1": {"total": 1.0, "relevance": 1.0}}
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=data, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

@tool("compose_answer")
def compose_answer_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        from advisor.core.schemas import Recommendation, ScoreBreakdown
        rec = Recommendation(
            product_id="P1",
            rank=1,
            paragraph="Dummy recommendation based on evidence.",
            statements=[],
            constraint_evidence={},
            review_quotes=[],
            image_observations=[],
            score=ScoreBreakdown(relevance=1.0, soft_fit=0.0, use_case_sentiment=0.0, review_trust=0.0, visual=None, total=1.0, weights_used={}),
            confidence="medium"
        )
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=[rec], cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

@tool("ask_user")
def ask_user_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    # Puts state into AWAIT_USER (needs_clarification)
    ms = int((time.time() - start_t) * 1000)
    return ToolResult(ok=True, data=state.parsed.clarifying_question, cost={"model_calls": 0, "ms": ms})

@tool("verify_images")
def verify_images_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        from advisor.vision.verifier import run_vision_for_shortlist
        from advisor.core.config import load_config
        gateway = context.get("gateway")
        if not gateway:
            from advisor.llm.gateway import Gateway
            gateway = Gateway({}, {})

        config = load_config()
        top_n = config.get("ranking", {}).get("thresholds", {}).get("vision_top_n", 3)

        # evidence_map: {product_id: [evidence dicts]}
        evidence_map = state.evidence  # populated by analyse_reviews step

        run_vision_for_shortlist(
            shortlist=state.shortlist,
            evidence_map=evidence_map,
            gateway=gateway,
            budget=state.budget,
            degraded=state.degraded,
            top_n=top_n,
        )
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=None, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        # Vision failure must always degrade, never crash (§7)
        reason = f"vision error: {e}"
        state.degraded.append(reason)
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(
            ok=True,  # ok=True so the loop continues; degrade recorded in state
            data=None,
            degraded=True,
            error=reason,
            cost={"model_calls": 0, "ms": ms},
        )

