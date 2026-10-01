"""Tests for retrieval strategies and RRF fusion."""
from __future__ import annotations

import tempfile
from pathlib import Path

from advisor.eval.baseline import run_baseline
from advisor.retrieval.hybrid import hybrid_search
from advisor.store.interfaces import KeywordIndex, VectorIndex
from advisor.store.sqlite_store import (
    build_fts_indexes,
    insert_products,
    insert_reviews,
    open_db,
)


class DummyKeywordIndex(KeywordIndex):
    def __init__(self, results: list[tuple[str, float]]):
        self._results = results

    def search(self, query: str, allow_ids: list[str], k: int = 10) -> list[tuple[str, float]]:
        return [r for r in self._results if r[0] in allow_ids][:k]


class DummyVectorIndex(VectorIndex):
    def __init__(self, results: list[tuple[str, float]]):
        self._results = results

    def search(self, query_embedding: list[float], allow_ids: list[str], k: int = 10) -> list[tuple[str, float]]:
        return [r for r in self._results if r[0] in allow_ids][:k]


def test_rrf_toy_rankings():
    """Test RRF on toy rankings with known output."""
    # Product A is ranked #1 in keyword, #2 in semantic
    # Product B is ranked #2 in keyword, #1 in semantic
    # Product C is ranked #3 in keyword only
    kw_results = [("A", 10.0), ("B", 5.0), ("C", 1.0)]
    sem_results = [("B", 0.9), ("A", 0.8)]

    p_kw = DummyKeywordIndex(kw_results)
    p_vec = DummyVectorIndex(sem_results)

    # Empty reviews
    r_kw = DummyKeywordIndex([])
    r_vec = DummyVectorIndex([])

    config = {
        "features": {"retrievers": {"keyword": True, "semantic": True}},
        "ranking": {"thresholds": {"shortlist_size": 3, "rrf_k": 60}}
    }

    results = hybrid_search(
        "query", ["A", "B", "C"],
        p_kw, r_kw, p_vec, r_vec, config
    )

    # RRF score calculation (k=60):
    # A: kw rank 1 (1/61) + sem rank 2 (1/62) = 0.01639 + 0.01612 = 0.03251
    # B: kw rank 2 (1/62) + sem rank 1 (1/61) = 0.01612 + 0.01639 = 0.03251
    # Both have same score, order may depend on sort stability.
    # C: kw rank 3 (1/63) = 0.01587

    assert len(results) == 3
    ids = [r[0] for r in results]
    assert "A" in ids[:2]
    assert "B" in ids[:2]
    assert ids[2] == "C"

    score_a = next(r[1] for r in results if r[0] == "A")
    score_c = next(r[1] for r in results if r[0] == "C")
    assert score_a > score_c

    # Check contributors
    contrib_a = next(r[2] for r in results if r[0] == "A")
    assert set(contrib_a) == {"keyword", "semantic"}
    contrib_c = next(r[2] for r in results if r[0] == "C")
    assert set(contrib_c) == {"keyword"}


def test_allow_list_never_violated():
    kw_results = [("A", 10.0), ("B", 5.0), ("C", 1.0)]
    sem_results = [("B", 0.9), ("A", 0.8)]

    p_kw = DummyKeywordIndex(kw_results)
    p_vec = DummyVectorIndex(sem_results)
    r_kw = DummyKeywordIndex([])
    r_vec = DummyVectorIndex([])

    config = {
        "features": {"retrievers": {"keyword": True, "semantic": True}},
        "ranking": {"thresholds": {"shortlist_size": 10, "rrf_k": 60}}
    }

    results = hybrid_search(
        "query", ["A"],  # Only A is allowed
        p_kw, r_kw, p_vec, r_vec, config
    )

    assert len(results) == 1
    assert results[0][0] == "A"


def test_disabling_retriever_changes_results():
    kw_results = [("A", 10.0)]
    sem_results = [("B", 0.9)]

    p_kw = DummyKeywordIndex(kw_results)
    p_vec = DummyVectorIndex(sem_results)
    r_kw = DummyKeywordIndex([])
    r_vec = DummyVectorIndex([])

    # Both enabled
    config_both = {
        "features": {"retrievers": {"keyword": True, "semantic": True}},
    }
    res_both = hybrid_search("q", ["A", "B"], p_kw, r_kw, p_vec, r_vec, config_both)
    assert len(res_both) == 2

    # Disable semantic
    config_no_sem = {
        "features": {"retrievers": {"keyword": True, "semantic": False}},
    }
    res_no_sem = hybrid_search("q", ["A", "B"], p_kw, r_kw, p_vec, r_vec, config_no_sem)
    assert len(res_no_sem) == 1
    assert res_no_sem[0][0] == "A"

    # Disable keyword
    config_no_kw = {
        "features": {"retrievers": {"keyword": False, "semantic": True}},
    }
    res_no_kw = hybrid_search("q", ["A", "B"], p_kw, r_kw, p_vec, r_vec, config_no_kw)
    assert len(res_no_kw) == 1
    assert res_no_kw[0][0] == "B"


def test_baseline_deterministic():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        conn = open_db(db_path)

        # Insert two products
        insert_products(conn, [
            {
                "product_id": "P1", "name": "Phone 1", "brand": "B", "cat_l1": "C", "cat_l2": "C", "cat_l3": "C",
                "retail_price_inr": 100, "discounted_price_inr": 100, "effective_price_inr": 100,
                "price_unknown": 0, "price_anomaly": 0, "description": "Good",
                "image_urls": "", "image_url_count": 0, "image_url_broken": 0,
                "alias_ids": "[]", "is_canonical": 1, "ingested_at": "now"
            },
            {
                "product_id": "P2", "name": "Phone 2", "brand": "B", "cat_l1": "C", "cat_l2": "C", "cat_l3": "C",
                "retail_price_inr": 100, "discounted_price_inr": 100, "effective_price_inr": 100,
                "price_unknown": 0, "price_anomaly": 0, "description": "Good",
                "image_urls": "", "image_url_count": 0, "image_url_broken": 0,
                "alias_ids": "[]", "is_canonical": 1, "ingested_at": "now"
            }
        ])

        # P1 has rating 5, P2 has rating 3
        insert_reviews(conn, [
            {
                "review_id": "R1", "product_id": "P1", "original_product_id": "P1",
                "rating": 5, "title": "", "text": "", "review_date": "now", "reviewer_id": "U1",
                "helpful_votes": 0, "injection_flag": 0, "is_duplicate": 0, "ingested_at": "now"
            },
            {
                "review_id": "R2", "product_id": "P2", "original_product_id": "P2",
                "rating": 3, "title": "", "text": "", "review_date": "now", "reviewer_id": "U2",
                "helpful_votes": 0, "injection_flag": 0, "is_duplicate": 0, "ingested_at": "now"
            }
        ])

        build_fts_indexes(conn)
        conn.close()

        # P1 should sort before P2 because of rating
        results = run_baseline("Phone", str(db_path))

        assert len(results) == 2
        assert results[0][0] == "P1"
        assert results[1][0] == "P2"
