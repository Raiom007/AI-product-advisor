import time

from advisor.core.registries import suite
from advisor.eval.baseline import run_baseline
from advisor.explain.grounding_validator import validate_statement
from advisor.service import _SESSIONS, advise


@suite("e2e")
def run_e2e_suite(queries: list[dict]=None, gold: list[dict]=None, mode: str="replay", data: list=None) -> dict:
    if not data and not queries:
        raise ValueError("FAIL LOUDLY: no data")
    metrics = {
        "total_queries": len(queries),
        "latency_ms": [],
        "hard_constraint_violations": 0,
        "statements_total": 0,
        "statements_grounded": 0,
        "ndcg_5": 0.0,
        "recall_10": 0.0,
        "baseline_ndcg_5": 0.0,
        "baseline_recall_10": 0.0,
    }

    # Simplistic metrics computation for MVP/Smoketest
    for i, q in enumerate(queries):
        start_t = time.time()
        session_id = f"eval_{q['query_id']}"
        resp = advise(q["text"], session_id=session_id)
        metrics["latency_ms"].append((time.time() - start_t) * 1000)

        # Baseline
        base_res = run_baseline(q["text"], k=10)
        base_ids = [pid for pid, score in base_res]

        sys_ids = [rec.product_id for rec in resp.recommendations]

        # Calculate dummy NDCG/Recall for smoketest
        g = next((g for g in gold if g["query_id"] == q["query_id"]), None)
        if g:
            rel = g.get("relevance", {})
            # Recall@10 = number of relevant items in top 10 / total relevant items
            relevant_items = [pid for pid, score in rel.items() if score > 0]
            if relevant_items:
                sys_hits = len([p for p in sys_ids[:10] if p in relevant_items])
                base_hits = len([p for p in base_ids[:10] if p in relevant_items])
                metrics["recall_10"] += sys_hits / len(relevant_items)
                metrics["baseline_recall_10"] += base_hits / len(relevant_items)

                metrics["ndcg_5"] += 1.0 if sys_hits > 0 else 0.0  # Dummy calculation
                metrics["baseline_ndcg_5"] += 1.0 if base_hits > 0 else 0.0 # Dummy

        # Grounding check via real validator
        state = _SESSIONS.get(session_id)
        if state:
            evidence_pool = state.evidence
            for rec in resp.recommendations:
                for stmt_dict in rec.statements:
                    metrics["statements_total"] += 1
                    # stmt_dict is a dict, but validate_statement expects a StatementOut
                    # To be DRY and real, we mock StatementOut
                    from advisor.explain.composer import StatementOut
                    stmt = StatementOut(text=stmt_dict.get("text", ""), evidence_ids=stmt_dict.get("evidence_ids", []))
                    res = validate_statement(stmt, rec.product_id, evidence_pool)
                    if res.ok:
                        metrics["statements_grounded"] += 1

    # Averages
    if metrics["total_queries"] > 0:
        metrics["recall_10"] /= metrics["total_queries"]
        metrics["baseline_recall_10"] /= metrics["total_queries"]
        metrics["ndcg_5"] /= metrics["total_queries"]
        metrics["baseline_ndcg_5"] /= metrics["total_queries"]

    return metrics
