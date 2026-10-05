"""Tools registry and wrappers (§5.10).

Calling convention: every tool function takes (state: AgentState, context: dict)
and returns a ToolResult.

context keys populated by service.py:
  gateway   — Gateway instance
  tracer    — Tracer instance
  config    — full config dict

Store singletons (embedder, vector index, keyword index, sqlite conn) are now
module-level globals built once on first access.  All advise() calls in the
same running process share them — no per-session or per-context rebuild.
"""
import time
from collections.abc import Callable
from pathlib import Path

from advisor.agent.state import AgentState, ToolResult
from advisor.core.registry import Registry

tools_registry: Registry = Registry("tools")


def tool(name: str) -> Callable:
    return tools_registry.register(name)


# ── module-level store singleton ──────────────────────────────────────────────
# WHY: LocalBgeEmbedder + ChromaDB have a ~15-25s cold-start on CPU.
# Rebuilding them per-context means every new Streamlit tab / advise() call
# pays the full cost.  A module-level tuple is initialised once when the first
# query arrives in this process, then reused for every subsequent call,
# regardless of session, tab or user.

_STORES = None   # type: tuple | None  (conn, kw_prod, kw_rev, vec_prod, vec_rev, embedder)


def _get_stores(context: dict):
    """Return the process-wide store singleton, building it on first call only.

    The `context` dict is kept as a parameter for backward compatibility but is
    only used to source the config on the very first initialisation.
    """
    global _STORES
    if _STORES is None:
        from advisor.core.config import load_config
        from advisor.llm.embedder import LocalBgeEmbedder
        from advisor.store.sqlite_store import SQLiteKeywordIndex, open_db
        from advisor.store.vector_store import ChromaVectorIndex

        cfg = context.get("config") or load_config()
        db_path = Path(cfg.get("database", {}).get("sqlite_path", "data/advisor.db"))
        chroma_path = Path(cfg.get("database", {}).get("chroma_path", "data/chroma"))

        conn = open_db(db_path)
        _STORES = (
            conn,
            SQLiteKeywordIndex(conn, "products_fts"),
            SQLiteKeywordIndex(conn, "reviews_fts"),
            ChromaVectorIndex(chroma_path, "products"),
            ChromaVectorIndex(chroma_path, "reviews"),
            LocalBgeEmbedder(),
        )

    return _STORES


# ── tools ─────────────────────────────────────────────────────────────────────

@tool("parse_query")
def parse_query_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    from advisor.llm.gateway import Gateway
    from advisor.understanding.clarify import apply_ambiguity_rule
    from advisor.understanding.parser import parse_query

    gateway = context.get("gateway")
    if not gateway:
        gateway = Gateway({}, {})
    try:
        t_start_stores = time.time()
        conn = _get_stores(context)[0]
        t_get_stores = time.time() - t_start_stores

        t_start_sql = time.time()
        rows = conn.execute("SELECT DISTINCT cat_l1, cat_l2, cat_l3 FROM products WHERE cat_l1 IS NOT NULL").fetchall()
        t_sql = time.time() - t_start_sql

        t_start_format = time.time()
        taxonomy_map = {}
        for l1, l2, l3 in rows:
            if l1 not in taxonomy_map:
                taxonomy_map[l1] = set()
            l2_str = str(l2) if l2 else "Misc"
            l3_str = str(l3) if l3 else "Misc"
            taxonomy_map[l1].add(f"{l2_str} > {l3_str}")

        tax_strs = []
        for l1, subcats in taxonomy_map.items():
            tax_strs.append(f"{l1} ({', '.join(sorted(subcats))})")
        taxonomy_list = "; ".join(tax_strs)
        valid_categories = set(taxonomy_map.keys())
        t_format = time.time() - t_start_format

        tracer = context.get("tracer")
        if tracer:
            with tracer.span("tool_call", name="parse_query_pre") as s:
                s.output_summary = f"get_stores={t_get_stores:.2f}s sql={t_sql:.2f}s format={t_format:.2f}s"

        pq = parse_query(
            gateway,
            state.query,
            taxonomy_list=taxonomy_list,
            valid_categories=valid_categories,
            valid_subcats=valid_subcats,
            tracer=tracer,
        )
        apply_ambiguity_rule(pq)
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=pq, cost={"model_calls": 1, "ms": ms})
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=False, error=str(e), cost={"model_calls": 0, "ms": ms})


@tool("retrieve")
def retrieve_tool(state: AgentState, context: dict) -> ToolResult:
    """Wire real hybrid retrieval (FTS5 + ChromaDB + RRF).

    Steps:
    1. Build SQL allow-list from hard constraints.
    2. Run hybrid_search (keyword + semantic, RRF-fused).
    3. Fetch full product rows from SQLite.
    4. Return shortlist as list[dict] ready for scorer.
    """
    start_t = time.time()
    try:
        from advisor.core.config import load_config
        from advisor.retrieval.filters import build_allow_list
        from advisor.retrieval.hybrid import hybrid_search

        conn, products_kw, reviews_kw, products_vec, reviews_vec, embedder = _get_stores(context)
        cfg = context.get("config") or load_config()

        pq = state.parsed
        hard_constraints = list(pq.hard) if pq else []

        if pq:
            from advisor.core.schemas import Constraint
            if pq.category or pq.subcategory:
                cat_val = pq.category if pq.category else pq.subcategory
                ext = {"subcategory": pq.subcategory} if pq.subcategory else {}
                hard_constraints.append(Constraint(
                    kind="category",
                    key="category",
                    op="eq",
                    value=cat_val,
                    raw_text=cat_val,
                    ext=ext
                ))
            if pq.budget and (pq.budget.min_inr is not None or pq.budget.max_inr is not None):
                val = {}
                if pq.budget.min_inr is not None:
                    val["min_inr"] = pq.budget.min_inr
                if pq.budget.max_inr is not None:
                    val["max_inr"] = pq.budget.max_inr
                hard_constraints.append(Constraint(
                    kind="budget",
                    key="price",
                    op="between",
                    value=val,
                    raw_text="budget"
                ))

        # 1. SQL filter → allow-list
        allow_ids, residual = build_allow_list(conn, hard_constraints)

        query_text = pq.query_en if pq else state.query

        # 2. Hybrid retrieval
        results = hybrid_search(
            query=query_text,
            allow_ids=allow_ids,
            products_kw_idx=products_kw,
            reviews_kw_idx=reviews_kw,
            products_vec_idx=products_vec,
            reviews_vec_idx=reviews_vec,
            config=cfg,
        )

        # 3. Fetch full rows for the shortlisted product IDs
        shortlist: list[dict] = []
        for pid, rrf_score, contributors in results:
            row = conn.execute(
                """SELECT product_id, name, brand, cat_l1, cat_l2,
                          effective_price_inr, description, image_urls
                   FROM products WHERE product_id = ?""",
                (pid,),
            ).fetchone()
            if row:
                p = dict(row)
                p["rrf_score"] = rrf_score
                p["contributors"] = contributors
                p["residual_constraints"] = residual
                shortlist.append(p)

        ms = int((time.time() - start_t) * 1000)
        return ToolResult(
            ok=True,
            data=shortlist,
            cost={"model_calls": 0, "ms": ms},
            metadata={"allow_ids": len(allow_ids), "results": len(shortlist)},
        )
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=False, error=str(e), cost={"model_calls": 0, "ms": ms})


@tool("analyse_reviews")
def analyse_reviews_tool(state: AgentState, context: dict) -> ToolResult:
    """Summarise reviews for the current shortlist using the LLM summarizer (§5.4 / P14).

    Steps:
    1. Fetch up to 15 reviews per product from SQLite (shortlist is already filtered).
    2. Build batch: {product_id: [review_dicts]} — max 3 products per LLM call to
       stay inside context window.  Multiple calls if shortlist > 3.
    3. Call summarize_reviews (guardrailed, schema-constrained, grounding-validated).
    4. Store results in state.summaries for compose_answer.
    5. Degrade gracefully (extractive fallback inside summarizer) on any failure.
    """
    start_t = time.time()
    try:
        from advisor.reviews.summarizer import summarize_reviews

        conn, _, _, _, _, _ = _get_stores(context)
        gateway = context.get("gateway")
        if not gateway:
            from advisor.llm.gateway import Gateway
            gateway = Gateway({}, {})

        shortlist = state.shortlist or []
        if not shortlist:
            ms = int((time.time() - start_t) * 1000)
            r = ToolResult(ok=True, data={}, cost={"model_calls": 0, "ms": ms})
            r._stub = True
            return r

        # Build per-product review dicts from SQLite
        # WHY: Reviews are already stored and cleaned at ingest time; we only need
        # to fetch them here — no re-scraping, no external calls.
        product_reviews: dict[str, list[dict]] = {}
        for p in shortlist:
            pid = p["product_id"]
            rows = conn.execute(
                """SELECT review_id, text, rating, helpful_votes
                   FROM reviews
                   WHERE product_id = ?
                   ORDER BY helpful_votes DESC, rating DESC
                   LIMIT 15""",
                (pid,),
            ).fetchall()
            if rows:
                product_reviews[pid] = [dict(r) for r in rows]

        if not product_reviews:
            # No reviews in DB for any shortlisted product — skip gracefully
            ms = int((time.time() - start_t) * 1000)
            r = ToolResult(
                ok=True, data={},
                cost={"model_calls": 0, "ms": ms},
                metadata={"products_with_reviews": 0},
            )
            r._stub = True
            return r

        # Batch into groups of ≤3 to stay within summarizer context limit
        # WHY: The summarizer prompt includes full review text; >3 products at once
        # risks hitting the model's context window on long reviews.
        batch_size = 3
        pids = list(product_reviews.keys())
        all_summaries: dict = {}

        for batch_start in range(0, len(pids), batch_size):
            batch_pids = pids[batch_start: batch_start + batch_size]
            batch = {pid: product_reviews[pid] for pid in batch_pids}

            if state.budget.is_exhausted():
                from advisor.reviews.summarizer import _fallback_summarizer
                summaries = _fallback_summarizer(batch)
            else:
                summaries = summarize_reviews(
                    gateway=gateway,
                    query=state.query,
                    batch=batch,
                    budget=state.budget,
                    tracer=context.get("tracer"),
                )
            all_summaries.update(summaries)

        ms = int((time.time() - start_t) * 1000)
        return ToolResult(
            ok=True,
            data=all_summaries,
            cost={"model_calls": len(range(0, len(pids), batch_size)), "ms": ms},
            metadata={
                "products_with_reviews": len(product_reviews),
                "summaries_returned": len(all_summaries),
            },
        )
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"analyse_reviews failed, degrading: {e}")
        r = ToolResult(ok=True, data={}, degraded=True, error=str(e),
                       cost={"model_calls": 0, "ms": ms})
        r._stub = True
        return r


@tool("rank")
def rank_tool(state: AgentState, context: dict) -> ToolResult:
    """Wire real scorer.rank_candidates (§5.6 two-pass weighted sum + gate).

    Input: state.shortlist (list[dict] with rrf_score)
    Output: same list sorted by final_score, truncated to top-5.
    """
    start_t = time.time()
    try:
        from advisor.ranking.scorer import rank_candidates

        pq = state.parsed
        constraints = pq.hard if pq else []

        rank_context = {
            "budget_max_inr": pq.budget.max_inr if pq and pq.budget else None,
            "use_case": pq.use_case if pq else None,
            "vision_skipped": True,  # no vision yet in this pass
        }

        ranked = rank_candidates(state.shortlist or [], rank_context, constraints)
        # Keep top 5 for compose_answer
        top = ranked[:5]

        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=top, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=False, error=str(e), cost={"model_calls": 0, "ms": ms})


@tool("compose_answer")
def compose_answer_tool(state: AgentState, context: dict) -> ToolResult:
    """Wire real fallback template_recommendation.

    Constructs an evidence_pool from the DB (specs + reviews) and uses
    template_recommendation to generate grounded output. Handles abstention.
    """
    start_t = time.time()
    try:
        from advisor.core.schemas import ScoreBreakdown
        from advisor.explain.render import make_abstention_response, template_recommendation

        ranked = state.shortlist or []
        if not ranked:
            abs_dict = make_abstention_response("No products passed filters.", context.get("config"))
            state.status = abs_dict["status"]
            state.message = abs_dict["message"]
            ms = int((time.time() - start_t) * 1000)
            return ToolResult(ok=True, data=[], cost={"model_calls": 0, "ms": ms})

        conn, _, _, _, _, _ = _get_stores(context)
        recommendations = []

        for i, p in enumerate(ranked[:5], start=1):
            pid = p["product_id"]

            # Build evidence pool
            evidence_pool = []

            # Fetch specs (always from DB — deterministic, not LLM-generated)
            specs = conn.execute("SELECT original_line FROM product_specs WHERE product_id = ?", (pid,)).fetchall()
            for s in specs:
                if s["original_line"]:
                    evidence_pool.append({"kind": "spec_line", "text": s["original_line"]})

            # Prefer LLM-generated review summary from analyse_reviews if available.
            # WHY: The summarizer has already done grounding validation (review_ids match
            # input IDs) and extracted signal. Using raw rows here would bypass that work.
            summary = (state.summaries or {}).get(pid)
            if summary:
                for praise in summary.praises:
                    evidence_pool.append({
                        "kind": "review",
                        "text": praise.get("point", ""),
                        "meta": {"source": "summary_praise", "review_ids": praise.get("review_ids", [])},
                    })
                for complaint in summary.complaints:
                    evidence_pool.append({
                        "kind": "review",
                        "text": complaint.get("point", ""),
                        "meta": {"source": "summary_complaint", "review_ids": complaint.get("review_ids", [])},
                    })
                use_case = summary.use_case_fit
                if use_case and use_case.get("verdict") not in (None, "unknown"):
                    evidence_pool.append({
                        "kind": "review",
                        "text": f"Use-case fit: {use_case.get('verdict', '')}",
                        "meta": {"source": "summary_use_case", "review_ids": use_case.get("review_ids", [])},
                    })
            else:
                # Fallback: raw rows when no summary is available (no reviews in DB,
                # or budget exhausted before analyse_reviews ran).
                reviews = conn.execute(
                    "SELECT review_id, text, rating, review_date FROM reviews WHERE product_id = ? LIMIT 5",
                    (pid,),
                ).fetchall()
                for r in reviews:
                    evidence_pool.append({
                        "kind": "review",
                        "id": r["review_id"],
                        "text": r["text"],
                        "meta": {"rating": r["rating"], "date": r["review_date"]},
                    })

            score_brk = p.get("score_breakdown")
            if not score_brk:
                score_brk = ScoreBreakdown(relevance=1.0, soft_fit=0.0, use_case_sentiment=0.0, review_trust=0.0, visual=None, total=1.0, weights_used={})

            rec = template_recommendation(
                product_id=pid,
                rank=i,
                evidence_pool=evidence_pool,
                score=score_brk,
                confidence="medium"
            )
            recommendations.append(rec)

        state.recommendations = recommendations
        state.status = "ok"
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=recommendations, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=False, error=str(e), cost={"model_calls": 0, "ms": ms})


@tool("ask_user")
def ask_user_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    ms = int((time.time() - start_t) * 1000)
    return ToolResult(
        ok=True,
        data=state.parsed.clarifying_question if state.parsed else "Can you clarify?",
        cost={"model_calls": 0, "ms": ms},
    )


@tool("verify_images")
def verify_images_tool(state: AgentState, context: dict) -> ToolResult:
    start_t = time.time()
    try:
        from advisor.core.config import load_config
        from advisor.vision.verifier import run_vision_for_shortlist

        gateway = context.get("gateway")
        if not gateway:
            from advisor.llm.gateway import Gateway
            gateway = Gateway({}, {})

        cfg = context.get("config") or load_config()
        top_n = cfg.get("ranking", {}).get("thresholds", {}).get("vision_top_n", 3)
        evidence_map = getattr(state, "evidence", {}) or {}

        run_vision_for_shortlist(
            shortlist=state.shortlist,
            evidence_map=evidence_map,
            gateway=gateway,
            budget=state.budget,
            degraded=state.degraded,
            top_n=top_n,
        )
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(ok=True, data=None, cost={"model_calls": 0, "ms": ms})
    except Exception as e:
        reason = f"vision error: {e}"
        state.degraded.append(reason)
        ms = int((time.time() - start_t) * 1000)
        return ToolResult(
            ok=True,
            data=None,
            degraded=True,
            error=reason,
            cost={"model_calls": 0, "ms": ms},
        )
