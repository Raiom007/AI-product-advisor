"""Semantic retrieval strategy.

WHY: §5.2 - ChromaDB semantic search over products and reviews.
Returns products scored by cosine similarity. Review hits are aggregated to product scores.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from advisor.core.registries import retriever
from advisor.store.interfaces import VectorIndex

logger = logging.getLogger(__name__)


@retriever("semantic")
def semantic_search(
    query_embedding: list[float],
    allow_ids: list[str],
    products_idx: VectorIndex,
    reviews_idx: VectorIndex,
    k: int = 100,
) -> list[tuple[str, float]]:
    """Execute semantic search over products and reviews.
    
    Returns:
        List of (product_id, aggregated_score) sorted by score.
    """
    if not allow_ids:
        return []

    p_results = products_idx.search(query_embedding, allow_ids, k=k)
    r_results = reviews_idx.search(query_embedding, allow_ids, k=k)

    # 3. Aggregate hits to product scores
    # We will sum the similarities for a given product.
    scores: dict[str, float] = defaultdict(float)

    for pid, score in p_results:
        scores[pid] += score

    for pid, score in r_results:
        scores[pid] += score

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:k]
