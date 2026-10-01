from advisor.core.schemas import AdvisorResponse
from advisor.core.config import load_config
from advisor.llm.gateway import Gateway
from advisor.core.budget import RequestBudget
from advisor.agent.state import AgentState
from advisor.agent.loop import run_loop
from advisor.core.tracing import Tracer
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SESSIONS = {}

def advise(query: str, session_id: str) -> AdvisorResponse:
    """Facade for the advisor service."""
    config = load_config()
    
    trace_id = str(uuid.uuid4())
    tracer = Tracer(trace_id=trace_id, traces_dir=Path("data/traces"))
    
    with tracer.span("decision", "advise_start") as span:
        span.input_summary = f"query='{query}', session='{session_id}'"
        
        state = _SESSIONS.get(session_id)
        if not state:
            budget = RequestBudget(max_model_calls=config.get("limits", {}).get("max_model_calls", 12))
            state = AgentState(session_id=session_id, query=query, budget=budget)
            _SESSIONS[session_id] = state
        else:
            if state.status == "needs_clarification":
                state.query += " " + query
                state.status = "ok"
                # Keep step as it is, which is where it paused
                
        state.trace_id = trace_id
        
        # Gateway init
        gateway = Gateway(models_config=config.get("models", {}), limits_config=config.get("limits", {}))
        
        context = {
            "gateway": gateway,
            "tracer": tracer,
            "config": config
        }
        
        # Run loop
        state = run_loop(state, context)
        
        span.output_summary = f"status={state.status}, recommendations={len(state.recommendations)}"
        
        return AdvisorResponse(
            recommendations=state.recommendations,
            status=state.status,
            message=state.message,
            trace_id=trace_id,
            degraded=state.degraded,
            budget_report=state.budget.report()
        )

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "40 hazaar tak ka laptop"
    print(f"Running advise({query!r})...")
    resp = advise(query, session_id="cli-test-session")
    print(resp.model_dump_json(indent=2))
