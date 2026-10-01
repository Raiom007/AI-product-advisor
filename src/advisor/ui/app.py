"""Streamlit entry point — AI Product Advisor.

Run:  streamlit run src/advisor/ui/app.py  (or  make run)

Pages:
  1. Chat          — query → clarification → recommendation cards
  2. Trace         — JSONL trace for the current request
  3. Fake-review inspector — flagged reviews per product
"""
import os, sys
# Ensure the package root is importable when run directly via streamlit
_root = str(__file__).split("src")[0] + "src"
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st
from advisor.core.config import load_config

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="AI Product Advisor",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar: profile + nav ────────────────────────────────────────────────────
with st.sidebar:
    cfg = load_config()
    profile = cfg.get("_profile", os.environ.get("ADVISOR_PROFILE", "dev"))
    st.markdown(f"### 🛒 AI Product Advisor")
    st.caption(f"Profile: **{profile}**")
    st.divider()

    page = st.radio(
        "Navigate",
        ["💬 Chat", "🔍 Trace", "🚩 Fake-review Inspector"],
        label_visibility="collapsed",
    )

# ── Dispatch to page modules ──────────────────────────────────────────────────
if page == "💬 Chat":
    from advisor.ui.pages import chat as _chat
    _chat.render()
elif page == "🔍 Trace":
    from advisor.ui.pages import trace as _trace
    _trace.render()
elif page == "🚩 Fake-review Inspector":
    from advisor.ui.pages import fake_reviews as _fr
    _fr.render()
