"""Trace page — renders the JSONL trace for the current request."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_TRACES_DIR = Path("data/traces")

_TYPE_ICONS = {
    "plan": "🗺",
    "tool_call": "🔧",
    "model_call": "🤖",
    "verify": "✅",
    "decision": "⚡",
    "budget": "💰",
    "degrade": "⚠",
}


def _load_trace(trace_id: str) -> list[dict]:
    path = _TRACES_DIR / f"{trace_id}.jsonl"
    if not path.exists():
        return []
    spans = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    spans.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return spans


def _span_row(span: dict):
    """Render a single span as a compact row inside an expander."""
    stype = span.get("type", "?")
    name = span.get("name", "")
    latency = span.get("latency_ms")
    icon = _TYPE_ICONS.get(stype, "•")
    label = f"{icon} `{stype}` — **{name}**"
    if latency is not None:
        label += f"  ⏱ {latency} ms"
    if span.get("cache_hit"):
        label += "  📦 cached"
    if span.get("error"):
        label += "  ❌"

    with st.expander(label, expanded=False):
        cols = st.columns([2, 2, 1, 1, 1])
        cols[0].caption("Input summary")
        cols[0].code(span.get("input_summary", "—")[:300], language=None)
        cols[1].caption("Output summary")
        cols[1].code(span.get("output_summary", "—")[:300], language=None)
        if span.get("model"):
            cols[2].metric("Model", span["model"])
        if span.get("tokens_in") is not None:
            cols[3].metric("Tokens in", span["tokens_in"])
        if span.get("tokens_out") is not None:
            cols[4].metric("Tokens out", span["tokens_out"])
        if span.get("error"):
            st.error(span["error"])


def render():
    st.title("🔍 Request Trace")

    # Trace ID from last response or manual input
    resp = st.session_state.get("last_response")
    default_tid = resp.trace_id if resp else ""

    trace_id = st.text_input("Trace ID", value=default_tid, placeholder="Enter trace ID…")

    if not trace_id:
        st.info("Run a query in the Chat page first, or paste a trace ID above.")
        return

    spans = _load_trace(trace_id)
    if not spans:
        st.warning(f"No trace file found for `{trace_id}`. Check `data/traces/`.")
        return

    # Summary metrics
    model_calls = [s for s in spans if s.get("type") == "model_call"]
    tool_calls  = [s for s in spans if s.get("type") == "tool_call"]
    degrade     = [s for s in spans if s.get("type") == "degrade"]
    total_lat   = sum(s.get("latency_ms", 0) or 0 for s in model_calls)
    cache_hits  = sum(1 for s in model_calls if s.get("cache_hit"))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total spans",   len(spans))
    c2.metric("Model calls",   len(model_calls))
    c3.metric("Cache hits",    cache_hits)
    c4.metric("Tool calls",    len(tool_calls))
    c5.metric("LLM latency",   f"{total_lat} ms")

    if degrade:
        st.warning(f"⚠ {len(degrade)} degradation event(s)")

    st.divider()

    # Budget report
    budget_spans = [s for s in spans if s.get("type") == "budget"]
    if budget_spans:
        with st.expander("💰 Budget report"):
            for s in budget_spans:
                st.json(json.loads(s.get("output_summary", "{}")))

    # Timeline — grouped by type
    st.subheader("Timeline")
    type_order = ["plan", "tool_call", "verify", "decision", "model_call", "budget", "degrade"]
    for group in type_order:
        group_spans = [s for s in spans if s.get("type") == group]
        if not group_spans:
            continue
        icon = _TYPE_ICONS.get(group, "•")
        st.markdown(f"**{icon} {group.replace('_', ' ').title()}** ({len(group_spans)})")
        for sp in group_spans:
            _span_row(sp)

    # Raw JSON fallback
    with st.expander("📄 Raw JSONL"):
        st.code("\n".join(json.dumps(s) for s in spans), language="json")
