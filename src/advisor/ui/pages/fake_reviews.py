"""Fake-review inspector page."""
import json
import sqlite3
import streamlit as st
from advisor.core.config import load_config

def get_db_path() -> str:
    cfg = load_config()
    return cfg.get("database", {}).get("sqlite_path", "data/advisor.db")

def _load_flags(db_path: str, product_id: str = "") -> list[dict]:
    query = """
        SELECT r.product_id, f.review_id, f.score, f.signals, f.reasons, f.action 
        FROM review_flags f
        JOIN reviews r ON f.review_id = r.review_id
    """
    params = []
    if product_id:
        query += " WHERE r.product_id = ?"
        params.append(product_id)
        
    query += " ORDER BY f.score DESC LIMIT 500"
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        st.error(f"DB Error: {e}")
        return []

def render():
    st.title("🚩 Fake-review Inspector")
    st.markdown("Inspect reviews flagged by the fake-review detector (downweighted or excluded).")
    
    db_path = get_db_path()
    
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        product_filter = st.text_input("Filter by Product ID (exact match)", placeholder="e.g. B00XYZ...")
        
    flags = _load_flags(db_path, product_filter)
    
    if not flags:
        st.info("No flagged reviews found (the table might be empty if P11 has not run, or no match).")
        return
        
    # Metrics
    excluded = sum(1 for f in flags if f.get("action") == "exclude")
    downweighted = sum(1 for f in flags if f.get("action") == "downweight")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Flagged", len(flags))
    c2.metric("Excluded", excluded)
    c3.metric("Downweighted", downweighted)
    
    st.divider()
    
    for f in flags:
        action = f.get("action", "unknown")
        color = "red" if action == "exclude" else "orange"
        badge = f":{color}[**{action.upper()}**]"
        
        with st.expander(f"{badge} {f.get('product_id')} — Review `{f.get('review_id')}` (Score: {f.get('score', 0):.2f})"):
            st.markdown("**Reasons:**")
            reasons = f.get("reasons")
            if reasons:
                try:
                    for r in json.loads(reasons):
                        st.markdown(f"- {r}")
                except Exception:
                    st.markdown(f"- {reasons}")
            
            st.markdown("**Signals:**")
            signals = f.get("signals")
            if signals:
                try:
                    st.json(json.loads(signals))
                except Exception:
                    st.code(signals)
