import logging
import uuid
from pathlib import Path

from advisor.agent.loop import run_loop
from advisor.agent.state import AgentState
from advisor.core.budget import RequestBudget
from advisor.core.config import load_config
from advisor.core.schemas import AdvisorResponse
from advisor.core.tracing import Tracer
from advisor.llm.gateway import Gateway

import json
import hashlib

logger = logging.getLogger(__name__)

_SESSIONS = {}
_RESPONSE_CACHE = {}

def advise(query: str, session_id: str, chat_history: list[dict] = None) -> AdvisorResponse:
    """Facade for the advisor service."""
    config = load_config()
    chat_history = chat_history or []

    key_input = json.dumps({"query": query, "history": chat_history}, sort_keys=True)
    cache_key = hashlib.md5(key_input.encode()).hexdigest()

    if cache_key in _RESPONSE_CACHE:
        logger.info(f"Memory cache hit for query: {query!r}")
        cached_resp = _RESPONSE_CACHE[cache_key]
        
        # MUST populate _SESSIONS so that if the cached response is "needs_clarification",
        # the next turn correctly appends the user's answer to this query.
        state = AgentState(
            session_id=session_id, 
            query=query, 
            budget=RequestBudget.from_config(config.get("limits", {})), 
            chat_history=chat_history
        )
        state.status = cached_resp.status
        _SESSIONS[session_id] = state
        
        return cached_resp.model_copy(update={"trace_id": str(uuid.uuid4())})

    trace_id = str(uuid.uuid4())
    tracer = Tracer(trace_id=trace_id, traces_dir=Path("data/traces"))

    with tracer.span("decision", "advise_start") as span:
        span.input_summary = f"query='{query}', session='{session_id}'"

        state = _SESSIONS.get(session_id)
        if not state:
            budget = RequestBudget.from_config(config.get("limits", {}))
            state = AgentState(session_id=session_id, query=query, budget=budget, chat_history=chat_history)
            _SESSIONS[session_id] = state
        else:
            if state.status == "needs_clarification":
                prior_q = state.query
                prior_msg = state.message or "Can you clarify?"
                state.query += " " + query
                if not chat_history:
                    chat_history = [
                        {"role": "user", "content": prior_q},
                        {"role": "assistant", "content": prior_msg}
                    ]
                state.chat_history = chat_history
                state.status = "ok"
                # Keep step as it is, which is where it paused
            else:
                budget = RequestBudget.from_config(config.get("limits", {}))
                # New turn in conversation
                state = AgentState(session_id=session_id, query=query, budget=budget, chat_history=chat_history)
                _SESSIONS[session_id] = state

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

        suggested = state.parsed.suggested_answers if state.parsed else []
        resp = AdvisorResponse(
            recommendations=state.recommendations,
            status=state.status,
            message=state.message,
            suggested_answers=suggested,
            trace_id=trace_id,
            degraded=state.degraded,
            budget_report=state.budget.report()
        )
        
        _RESPONSE_CACHE[cache_key] = resp
        return resp

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "40 hazaar tak ka laptop"
    print(f"Running advise({query!r})...")
    resp = advise(query, session_id="cli-test-session")
    print(resp.model_dump_json(indent=2))
