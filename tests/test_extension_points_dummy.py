
def test_register_dummy_tool():
    from advisor.agent.tools import tool, tools_registry
    from advisor.agent.state import AgentState, ToolResult, PlanStep
    from advisor.agent.loop import run_loop
    
    @tool("_test_dummy_tool")
    def dummy_tool(state: AgentState, context: dict) -> ToolResult:
        state.checks["dummy_run"] = True
        return ToolResult(ok=True, data="dummy")
        
    assert "_test_dummy_tool" in tools_registry.all_names()
    
    state = AgentState(session_id="t1", query="hello")
    state.plan = [PlanStep(tool="_test_dummy_tool", rationale="test")]
    state = run_loop(state, {})
    
    assert state.checks.get("dummy_run") is True
