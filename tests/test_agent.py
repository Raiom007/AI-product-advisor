import pytest
from advisor.agent.state import AgentState, PlanStep
from advisor.agent.loop import run_loop
from advisor.core.budget import RequestBudget
from advisor.agent.tools import tools_registry, tool
from advisor.agent.verifiers import verifiers_registry, verifier, VerifierResult
import uuid

def test_termination_llm_planner_junk():
    # If the LLM planner returns junk (e.g. unknown tools), the loop should terminate gracefully.
    state = AgentState(session_id="t2", query="hello")
    state.plan = [PlanStep(tool="nonexistent_tool", rationale="junk")]
    
    state = run_loop(state, {})
    assert state.status == "abstained"
    assert "unknown name" in state.message

def test_retries_bounded():
    # Force a verifier to return retry infinitely, ensure it hits max attempts
    
    @tool("_test_fail_tool")
    def fail_tool(state, context):
        state.attempts["_test_fail"] = state.attempts.get("_test_fail", 0) + 1
        from advisor.agent.state import ToolResult
        return ToolResult(ok=True)
        
    @verifier("_test_fail_verifier")
    def fail_verifier(state, result):
        if state.plan[state.step].tool == "_test_fail_tool":
            return VerifierResult("retry", "keep trying")
        return VerifierResult("continue")
        
    state = AgentState(session_id="t3", query="test")
    state.plan = [PlanStep(tool="_test_fail_tool", rationale="fail")]
    
    state = run_loop(state, {})
    
    assert state.status == "abstained"
    assert state.attempts["_test_fail"] > 0
    assert sum(state.attempts.values()) >= 25 # MAX_STEPS

def test_clarification_pause_resume(monkeypatch):
    from advisor.service import advise, _SESSIONS
    from advisor.llm.gateway import Gateway
    from advisor.llm.base import ProviderResponse
    from advisor.core.schemas import ParsedQuery, Budget
    
    call_count = 0
    def mock_call(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            return ProviderResponse(
                text="{}",
                tokens_in=10,
                tokens_out=10,
                structured_data=ParsedQuery(
                    query_en="hello",
                    language="en",
                    budget=Budget(),
                    needs_clarification=True,
                    clarifying_question="What kind of laptop?"
                )
            )
        else:
            return ProviderResponse(
                text="{}",
                tokens_in=10,
                tokens_out=10,
                structured_data=ParsedQuery(
                    query_en="hello a laptop",
                    language="en",
                    budget=Budget(),
                    needs_clarification=False
                )
            )
            
    monkeypatch.setattr(Gateway, "call", mock_call)
    
    # advise() with "hello" should pause
    resp1 = advise("hello", "session_abc")
    assert resp1.status == "needs_clarification"
    
    state = _SESSIONS["session_abc"]
    assert state.step == 0
    
    # resume
    resp2 = advise("a laptop", "session_abc")
    assert resp2.status == "ok"
    assert "hello a laptop" in state.query

def test_budget_exhaustion_degrades():
    state = AgentState(session_id="t4", query="test")
    state.budget = RequestBudget(max_model_calls=0) # Exhausted
    state.plan = [PlanStep(tool="verify_images", rationale="optional"), PlanStep(tool="rank", rationale="required")]
    
    state = run_loop(state, {})
    assert "budget_exhausted" in state.degraded
    # verify_images skipped, rank executed
    assert state.step == 2
