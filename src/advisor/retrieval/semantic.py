"""Semantic retrieval strategy.

WHY: §5.2 - ChromaDB semantic search over products and reviews.
Returns products scored by cosine similarity. Review hits are aggregated to product scores.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from advisor.core.registries import retriever, providers
from advisor.store.interfaces import VectorIndex

logger = logging.getLogger(__name__)

# Cache the embedder as a singleton
_EMBEDDER = None

def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        # Load from providers registry
        embedder_class = providers.get("bge_small_en")
        _EMBEDDER = embedder_class()
    return _EMBEDDER

@retriever("semantic")
def semantic_search(
    query: str,
    allow_ids: list[str],
    products_idx: VectorIndex,
    reviews_idx: VectorIndex,
    k: int = 100,
) -> list[tuple[str, float]]:
    """Execute semantic search over products and reviews.
    
    Returns:
        List of (product_id, aggregated_score) sorted by score.
    """
    import time
    
    if not allow_ids:
        return []

    t0 = time.time()
    embedder = _get_embedder()
    t1 = time.time()
    
    query_embedding = embedder.embed_queries([query])[0]
    t2 = time.time()
    
    p_results = products_idx.search(query_embedding, allow_ids, k=k)
    r_results = reviews_idx.search(query_embedding, allow_ids, k=k)
    t3 = time.time()
    
    logger.warning(f"Semantic timings - Init/Fetch Embedder: {(t1-t0)*1000:.1f}ms, Embed Query: {(t2-t1)*1000:.1f}ms, Chroma Search: {(t3-t2)*1000:.1f}ms")

    # 3. Aggregate hits to product scores
    scores: dict[str, float] = defaultdict(float)

    for pid, score in p_results:
        scores[pid] += score

    for pid, score in r_results:
        scores[pid] += score

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:k]
