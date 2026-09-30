"""Keyword retrieval strategy.

WHY: §5.2 - FTS5 BM25 search over products and reviews.
Returns products scored by BM25. Review hits are aggregated to product scores.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from advisor.core.registries import retrievers
from advisor.store.interfaces import KeywordIndex

logger = logging.getLogger(__name__)


@retrievers.register("keyword")
def keyword_search(
    query: str,
    allow_ids: list[str],
    products_idx: KeywordIndex,
    reviews_idx: KeywordIndex,
    k: int = 100,
) -> list[tuple[str, float]]:
    """Execute keyword search over products and reviews.
    
    Returns:
        List of (product_id, aggregated_score) sorted by score.
    """
    if not allow_ids:
        return []

    # 1. Product hits
    # Get more than k to ensure good aggregation, then we can truncate
    p_results = products_idx.search(query, allow_ids, k=k)

    # 2. Review hits
    # The reviews_idx returns (product_id, score) directly based on our implementation
    r_results = reviews_idx.search(query, allow_ids, k=k)

    # 3. Aggregate hits to product scores
    # WHY: A product mentioned in 5 relevant reviews should score higher than one
    # mentioned in 1, but we use max() or sum(). RRF later merges rankings.
    # We will sum the BM25 scores for a given product.
    scores: dict[str, float] = defaultdict(float)

    for pid, score in p_results:
        scores[pid] += score

    for pid, score in r_results:
        scores[pid] += score

    # Sort descending
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:k]
