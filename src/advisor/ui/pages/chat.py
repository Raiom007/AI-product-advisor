"""Chat page — query box, clarification turn, recommendation cards."""
import uuid
import streamlit as st
from advisor.service import advise
from advisor.core.schemas import AdvisorResponse, Recommendation


# ── session state helpers ─────────────────────────────────────────────────────

def _init():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []      # [{role, content}]
    if "last_response" not in st.session_state:
        st.session_state.last_response = None  # AdvisorResponse


def _reset():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.last_response = None


# ── confidence badge ──────────────────────────────────────────────────────────

_CONF_COLOUR = {"high": "green", "medium": "orange", "low": "red"}

def _conf_badge(level: str) -> str:
    col = _CONF_COLOUR.get(level, "grey")
    return f":{col}[**{level.upper()}**]"


# ── recommendation card ───────────────────────────────────────────────────────

def _render_card(rec: Recommendation, rank: int, all_recs: list[Recommendation]):
    with st.container(border=True):
        # Header row
        col_title, col_conf = st.columns([4, 1])
        with col_title:
            st.subheader(f"#{rank}  {rec.product_id}")
        with col_conf:
            st.markdown(f"Confidence {_conf_badge(rec.confidence)}")

        # Score bar
        if rec.score:
            with st.expander("Score breakdown", expanded=False):
                bd = rec.score
                cols = st.columns(5)
                labels = ["Relevance", "Soft fit", "Sentiment", "Trust", "Visual"]
                vals = [
                    bd.relevance, bd.soft_fit,
                    bd.use_case_sentiment, bd.review_trust,
                    bd.visual if bd.visual is not None else 0.0,
                ]
                for c, lbl, v in zip(cols, labels, vals):
                    c.metric(lbl, f"{v:.2f}")
                st.metric("**Total**", f"{bd.total:.3f}")

        # Paragraph
        st.markdown(rec.paragraph)

        # Statements with evidence IDs
        if rec.statements:
            with st.expander("📋 Grounded statements"):
                for s in rec.statements:
                    ids = ", ".join(s.get("evidence_ids", []))
                    st.markdown(f"- {s['text']}  `[{ids}]`")

        # Review quotes
        if rec.review_quotes:
            with st.expander("💬 Review quotes"):
                for q in rec.review_quotes:
                    st.info(q)

        # Image observations
        if rec.image_observations:
            with st.expander("🖼 Image observations"):
                for obs in rec.image_observations:
                    st.markdown(f"- {obs}")

        # Why A above B (pairwise)
        below = [r for r in all_recs if r.rank > rank]
        if below and rec.score:
            with st.expander(f"📊 Why #{rank} above #{below[0].rank}"):
                try:
                    from advisor.ranking.explain_rank import explain_pairwise
                    # Attach score_breakdown to product dicts for explain_pairwise
                    pa = {"score_breakdown": rec.score.model_dump()}
                    pb = {"score_breakdown": below[0].score.model_dump()}
                    contribs = explain_pairwise(pa, pb)
                    for c in contribs:
                        bar_val = c["contribution"]
                        sign = "+" if bar_val >= 0 else ""
                        st.markdown(
                            f"- **{c['signal']}**: {sign}{bar_val:.3f} "
                            f"(w={c['w']:.2f}, Δ={c['diff']:+.3f})"
                        )
                except Exception as e:
                    st.caption(f"Explanation unavailable: {e}")


# ── main render ───────────────────────────────────────────────────────────────

def render():
    _init()
    st.title("💬 Product Advisor Chat")

    # Degraded banners from last response
    resp: AdvisorResponse | None = st.session_state.last_response
    if resp and resp.degraded:
        for d in resp.degraded:
            st.warning(f"⚠ {d}")

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    col_input, col_reset = st.columns([5, 1])
    with col_reset:
        if st.button("🔄 Reset", use_container_width=True):
            _reset()
            st.rerun()

    query = st.chat_input("Ask for a product recommendation…")
    if not query:
        return

    # Show user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Call service
    with st.spinner("Thinking…"):
        try:
            resp = advise(query, session_id=st.session_state.session_id)
            st.session_state.last_response = resp
        except Exception as e:
            st.error(f"Network or service error: {e}")
            return

    # Degraded banners
    if resp.degraded:
        for d in resp.degraded:
            st.warning(f"⚠ {d}")

    # Clarification
    if resp.status == "needs_clarification":
        msg = resp.message or "Could you clarify your request?"
        st.session_state.messages.append({"role": "assistant", "content": msg})
        with st.chat_message("assistant"):
            st.markdown(msg)
        return

    # Abstention
    if resp.status == "abstained":
        msg = resp.message or "No product fully meets your request."
        st.session_state.messages.append({"role": "assistant", "content": f"🚫 {msg}"})
        with st.chat_message("assistant"):
            st.error(msg)
        return

    # Recommendations
    if not resp.recommendations:
        st.info("No recommendations returned.")
        return

    summary = f"Found {len(resp.recommendations)} recommendation(s)."
    st.session_state.messages.append({"role": "assistant", "content": summary})
    with st.chat_message("assistant"):
        st.markdown(summary)

    st.divider()
    for rec in resp.recommendations:
        _render_card(rec, rec.rank, resp.recommendations)

    # Budget report in sidebar
    with st.sidebar:
        st.divider()
        st.caption("Budget report")
        br = resp.budget_report
        st.metric("Model calls", f"{br.get('calls_used', 0)} / {br.get('calls_limit', 12)}")
        st.metric("Wall time", f"{br.get('wall_s', 0):.1f}s / {br.get('wall_limit_s', 18)}s")
        st.caption(f"Trace: `{resp.trace_id}`")
