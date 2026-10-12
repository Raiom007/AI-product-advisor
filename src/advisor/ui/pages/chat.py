"""Chat page — query box, clarification turn, recommendation cards."""
import uuid

import streamlit as st

from advisor.core.schemas import AdvisorResponse, Recommendation
from advisor.service import advise

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
            # Fetch product name from DB to display instead of raw ID
            product_name = rec.product_id
            product_price = ""
            product_image_url = None
            try:
                from pathlib import Path

                from advisor.core.config import load_config
                from advisor.store.sqlite_store import open_db
                cfg = load_config()
                db_path = Path(cfg.get("database", {}).get("sqlite_path", "data/advisor.db"))
                conn = open_db(db_path)
                row = conn.execute("SELECT name, effective_price_inr, image_urls FROM products WHERE product_id = ?", [rec.product_id]).fetchone()
                if row:
                    if row["name"]:
                        product_name = row["name"]
                    if row["effective_price_inr"]:
                        product_price = f" - ₹{row['effective_price_inr']}"
                    if row["image_urls"]:
                        urls = [u for u in row["image_urls"].split("|") if u.strip()]
                        if urls:
                            product_image_url = urls[0]
            except Exception:
                pass

            if product_image_url:
                st.markdown(f'<img src="{product_image_url}" width="150" alt="Product Image" referrerpolicy="no-referrer" />', unsafe_allow_html=True)
            st.subheader(f"#{rank} {product_name}{product_price}")
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

        from advisor.service import _SESSIONS
        state = _SESSIONS.get(st.session_state.session_id)
        evidence_pool = state.evidence if state else {}

        with st.expander("📚 Evidence", expanded=False):
            # Cited specs
            cited_specs = []
            for s in rec.statements:
                for eid in s.get("evidence_ids", []):
                    ref = evidence_pool.get(eid)
                    if ref and ref.kind == "spec_line" and ref.text not in cited_specs:
                        cited_specs.append(ref.text)
            
            if cited_specs:
                st.markdown("**Specs:**")
                for s in cited_specs:
                    st.markdown(f"- {s}")
            
            # Review quotes
            if rec.review_quotes:
                st.markdown("**Reviews:**")
                for eid in rec.review_quotes:
                    ref = evidence_pool.get(eid)
                    if ref:
                        rating = ref.meta.get("rating", "?")
                        date = ref.meta.get("date", "?")
                        st.info(f"⭐ {rating} | 📅 {date}\n\n\"{ref.text}\"")
                    else:
                        st.info(f"\"{eid}\"")

            # Image observations
            if rec.image_observations:
                st.markdown("**Images:**")
                for obs in rec.image_observations:
                    st.markdown(f"- {obs}")
            elif rec.score and rec.score.visual is None:
                st.markdown("*(Image checks skipped: Visual analysis was disabled or degraded)*")

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
                    contrib_data = []
                    for c in contribs:
                        bar_val = c["contribution"]
                        sign = "+" if bar_val >= 0 else ""
                        contrib_data.append({
                            "Signal": c["signal"],
                            "Contribution": f"{sign}{bar_val:.3f}",
                            "Weight (w)": f"{c['w']:.2f}",
                            "Diff (Δ)": f"{c['diff']:+.3f}"
                        })
                    if contrib_data:
                        st.table(contrib_data)
                except Exception as e:
                    st.caption(f"Explanation unavailable: {e}")


# ── main render ───────────────────────────────────────────────────────────────

def render():
    _init()
    st.title("💬 Product Advisor Chat")

    _DEGRADED_MAP = {
        "budget_exhausted": "Some analysis was skipped to stay within limits.",
        "vision_skipped": "Visual verification was skipped.",
        "fake_review_timeout": "Review authenticity checks timed out."
    }

    # Degraded banners from last response
    resp: AdvisorResponse | None = st.session_state.last_response
    if resp and resp.degraded:
        for d in resp.degraded:
            friendly = next((v for k, v in _DEGRADED_MAP.items() if k in d), f"Degraded performance: {d}")
            st.warning(f"⚠ {friendly}")

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
            
    with st.sidebar:
        st.markdown("### Try an example:")
        examples = [
            "I need a good laptop for coding",
            "Best TV under $500",
            "Wireless earbuds with active noise cancellation",
            "40 hazaar tak ka laptop, video editing ke liye",
            "ek acha phone dikhana under 40k"
        ]
        for ex in examples:
            if st.button(ex):
                st.session_state.example_query = ex
                st.rerun()

    query = st.chat_input("Ask for a product recommendation…")
    
    if "example_query" in st.session_state:
        query = st.session_state.example_query
        del st.session_state.example_query
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
            friendly = next((v for k, v in _DEGRADED_MAP.items() if k in d), f"Degraded performance: {d}")
            st.warning(f"⚠ {friendly}")

    # Clarification
    if resp.status == "needs_clarification":
        msg = resp.message or "Could you clarify your request?"
        st.session_state.messages.append({"role": "assistant", "content": f"🤔 {msg}"})
        with st.chat_message("assistant"):
            st.info(f"**Question for you:** {msg}")
        return

    # Abstention
    if resp.status == "abstained":
        msg = resp.message or "No product fully meets your request."
        st.session_state.messages.append({"role": "assistant", "content": f"🚫 {msg}"})
        with st.chat_message("assistant"):
            st.error(f"**Cannot recommend:** {msg}")
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
