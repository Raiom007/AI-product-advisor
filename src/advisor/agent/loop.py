"""Agent execution loop (§5.10)."""
import logging
from advisor.agent.state import AgentState
from advisor.agent.planner import create_plan
from advisor.agent.tools import tools_registry
from advisor.agent.verifiers import verifiers_registry

logger = logging.getLogger(__name__)

MAX_STEPS = 25
MAX_REPLANS = 2

def run_loop(state: AgentState, context: dict) -> AgentState:
    """Execute the agent plan."""
    if not state.plan:
        state.plan = create_plan(state)
        
    while state.step < len(state.plan):
        if sum(state.attempts.values()) > MAX_STEPS: # or some other step counter
            state.status = "abstained"
            state.message = "Max steps exceeded"
            break
            
        step_def = state.plan[state.step]
        tool_name = step_def.tool
        
        # Check budget before executing
        if state.budget.is_exhausted():
            state.degraded.append("budget_exhausted")
            if tool_name in ["verify_images"]:
                logger.info(f"Skipping {tool_name} due to budget exhaustion.")
                state.step += 1
                continue
                
        # Execute tool
        try:
            tool_fn = tools_registry.get(tool_name)
            result = tool_fn(state, context)
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed.")
            state.status = "abstained"
            state.message = f"Error in {tool_name}: {e}"
            break
            
        # Update state with result
        if tool_name == "parse_query" and result.ok:
            state.parsed = result.data
        elif tool_name == "retrieve" and result.ok:
            state.shortlist = result.data
        elif tool_name == "compose_answer" and result.ok:
            state.recommendations = result.data
            
        # Run verifiers
        actions = []
        for v_name in verifiers_registry.all_names():
            v_fn = verifiers_registry.get(v_name)
            v_res = v_fn(state, result)
            if v_res.action != "continue":
                actions.append(v_res)
                
        # Resolve verifier actions
        action = "continue"
        reason = ""
        for a in actions:
            if a.action == "ask_user":
                action = "ask_user"
                reason = a.reason
                break
            elif a.action == "abstain":
                action = "abstain"
                reason = a.reason
                break
            elif a.action == "retry":
                action = "retry"
                reason = a.reason
            elif a.action == "degrade":
                state.degraded.append(a.reason)
                
        if action == "ask_user":
            state.status = "needs_clarification"
            state.message = state.parsed.clarifying_question if state.parsed else "Can you clarify?"
            # We don't advance step, so resume will re-run or continue from here
            # Wait, if we asked user, next time we come back, we should re-parse with the new info!
            # The planner sets parse_query first.
            return state
            
        elif action == "abstain":
            state.status = "abstained"
            state.message = reason
            break
            
        elif action == "retry":
            logger.info(f"Retrying step {tool_name}: {reason}")
            continue # stay on same step
            
        # Advance step
        state.step += 1
        
    return state
