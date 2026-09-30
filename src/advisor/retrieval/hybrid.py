"""Hybrid retrieval strategy.

WHY: §5.2 - Fuses keyword and semantic retrieval results using Reciprocal Rank Fusion.
RRF is used because it needs no score calibration across BM25 and cosine.
Shortlist size defaults to 8 (range 5-10).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from advisor.core.registries import retriever, retrievers
from advisor.store.interfaces import KeywordIndex, VectorIndex

logger = logging.getLogger(__name__)


@retriever("hybrid")
def hybrid_search(
    query: str,
    query_embedding: list[float],
    allow_ids: list[str],
    products_kw_idx: KeywordIndex,
    reviews_kw_idx: KeywordIndex,
    products_vec_idx: VectorIndex,
    reviews_vec_idx: VectorIndex,
    config: dict[str, Any],
) -> list[tuple[str, float, list[str]]]:
    """Execute hybrid search using enabled retrievers.
    
    Returns:
        List of (product_id, rrf_score, contributing_retrievers) sorted by RRF score.
    """
    if not allow_ids:
        return []

    features = config.get("features", {})
    thresholds = config.get("ranking", {}).get("thresholds", {})

    shortlist_size = thresholds.get("shortlist_size", 8)
    shortlist_size = max(5, min(shortlist_size, 10))
    rrf_k = thresholds.get("rrf_k", 60)

    # We fetch more internally to ensure good intersection for fusion
    internal_k = 100

    rankings: dict[str, list[tuple[str, float]]] = {}

    if retrievers.enabled("keyword", features):
        from advisor.retrieval.keyword import keyword_search
        kw_results = keyword_search(
            query, allow_ids, products_kw_idx, reviews_kw_idx, k=internal_k
        )
        rankings["keyword"] = kw_results

    if retrievers.enabled("semantic", features):
        from advisor.retrieval.semantic import semantic_search
        sem_results = semantic_search(
            query_embedding, allow_ids, products_vec_idx, reviews_vec_idx, k=internal_k
        )
        rankings["semantic"] = sem_results

    # Reciprocal Rank Fusion
    rrf_scores: dict[str, float] = defaultdict(float)
    contributors: dict[str, set[str]] = defaultdict(set)

    for r_name, r_results in rankings.items():
        # r_results is sorted by score descending
        for rank, (pid, _score) in enumerate(r_results, start=1):
            rrf_scores[pid] += 1.0 / (rrf_k + rank)
            contributors[pid].add(r_name)

    # Sort descending
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # Cap to shortlist_size
    final_results = sorted_results[:shortlist_size]

    return [(pid, score, list(contributors[pid])) for pid, score in final_results]
