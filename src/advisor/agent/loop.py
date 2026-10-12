"""Agent execution loop (§5.10)."""
import logging
import time

from advisor.agent.planner import create_plan
from advisor.agent.state import AgentState
from advisor.agent.tools import tools_registry
from advisor.agent.verifiers import verifiers_registry

logger = logging.getLogger(__name__)

MAX_STEPS = 25
MAX_REPLANS = 2


def run_loop(state: AgentState, context: dict) -> AgentState:
    """Execute the agent plan, emitting one trace span per tool invocation."""
    tracer = context.get("tracer")

    if not state.plan:
        state.plan = create_plan(state)

    while state.step < len(state.plan):
        if sum(state.attempts.values()) > MAX_STEPS:
            state.status = "abstained"
            state.message = "Max steps exceeded"
            break

        step_def = state.plan[state.step]
        tool_name = step_def.tool

        # Check budget before executing
        if state.budget.is_exhausted():
            if "budget_exhausted" not in state.degraded:
                state.degraded.append("budget_exhausted")
            if tool_name in ["verify_images"]:
                logger.info(f"Skipping {tool_name} due to budget exhaustion.")
                state.step += 1
                continue

        # ── per-tool trace span ───────────────────────────────────────────
        t0 = time.monotonic()
        result = None
        span_error = None

        try:
            tool_fn = tools_registry.get(tool_name)
            result = tool_fn(state, context)
            latency_ms = int((time.monotonic() - t0) * 1000)
            is_stub = getattr(result, "_stub", False)   # tools mark themselves
            meta_str = f", meta={result.metadata}" if getattr(result, "metadata", None) else ""
            output_summary = (
                f"ok={result.ok}, degraded={result.degraded}, "
                f"stub={is_stub}{meta_str}"
            )
            if result.error:
                output_summary += f", error={result.error}"
            # WHY: Debug print so we can trace failures in uvicorn logs without a full profiler
            data_len = len(result.data) if isinstance(result.data, (list, dict)) else 'n/a'
            print(f"DEBUG LOOP step={tool_name} ok={result.ok} data_len={data_len} error={result.error!r}")
        except Exception as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            span_error = str(e)
            output_summary = f"EXCEPTION: {e}"
            logger.exception(f"Tool {tool_name} failed.")

        if tracer:
            with tracer.span("tool_call", tool_name) as span:
                span.latency_ms = latency_ms
                span.input_summary = (
                    f"step={state.step}, query={state.query!r:.80}"
                )
                span.output_summary = output_summary
                if span_error:
                    span.error = span_error

        if span_error:
            state.status = "abstained"
            state.message = f"Error in {tool_name}: {span_error}"
            break

        # Update state with result
        if tool_name == "parse_query" and result.ok:
            state.parsed = result.data
        elif tool_name == "retrieve" and result.ok:
            state.shortlist = result.data
        elif tool_name == "analyse_reviews" and result.ok and result.data:
            state.summaries = result.data   # {product_id: ReviewSummary}
        elif tool_name == "rank" and result.ok:
            state.shortlist = result.data   # replace with ranked order
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
            state.message = (
                state.parsed.clarifying_question if state.parsed else "Can you clarify?"
            )
            return state

        elif action == "abstain":
            state.status = "abstained"
            state.message = reason
            break

        elif action == "retry":
            logger.info(f"Retrying step {tool_name}: {reason}")
            continue  # stay on same step

        # Advance step
        state.step += 1

    return state
