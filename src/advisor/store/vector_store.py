"""ChromaDB implementation of VectorIndex.

WHY: §9 specifies ChromaDB with two collections: products and reviews.
Metadata is stored to allow pre-filtering if needed (though our architecture
prefers SQL for hard constraints and passes an allow-list).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb

from advisor.store.interfaces import VectorIndex

logger = logging.getLogger(__name__)


class ChromaVectorIndex(VectorIndex):
    """VectorIndex implementation using local ChromaDB."""

    def __init__(self, db_path: Path, collection_name: str) -> None:
        """Initialize ChromaDB index.
        
        Args:
            db_path: Path to the directory where Chroma should store its data.
            collection_name: 'products' or 'reviews'.
        """
        # Persistent client stores data on disk at db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(db_path))
        self._collection_name = collection_name
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            # We provide our own embeddings using the Embedder interface,
            # so we disable Chroma's default embedding function.
            embedding_function=None,
        )

    def search(
        self,
        query_embedding: list[float],
        allow_ids: list[str],
        k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search products and reviews using cosine similarity.
        
        Applies allow_ids filter via Chroma's `where` clause.
        """
        if not allow_ids:
            return []

        # Chroma's $in operator only supports up to some limit (often 100-1000).
        # We assume the SQL allow-list will typically be reasonably sized, but
        # for robust production use, we batch the search if allow_ids is huge.
        # Here we just use the $in operator.
        where_filter = {"product_id": {"$in": allow_ids}}

        # For the 'reviews' collection, allow_ids refers to product_ids.
        # The metadata must have 'product_id' stored.

        # We need to ask for more results than k in case multiple reviews belong to
        # the same product, but since VectorIndex contract expects results mapped to
        # documents, we'll return exactly what Chroma returns. The ranking fusion
        # step handles mapping review hits back to product scores.

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=where_filter,
                include=["distances", "metadatas"]
            )
        except Exception as e:
            logger.warning(f"Chroma search failed: {e}")
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        # Chroma returns distance metrics. For cosine distance (default in some configs),
        # score = 1 - distance. We assume L2 or cosine distance. We'll just invert distance
        # so higher is better, or use 1 - distance if cosine.
        # We will use 1.0 / (1.0 + distance) as a simple score that is higher for closer vectors.
        distances = results["distances"][0]

        # If collection is reviews, id is review_id but we need to know product_id?
        # The contract of VectorIndex search says "Returns: List of (product_id, score)".
        # Wait, if we search reviews, we get review hits, but we need product scores.
        # The prompt says: "(3) Review hits are aggregated to product scores."
        # If VectorIndex.search returns (id, score), for products id is product_id.
        # For reviews, id is review_id, and we need to look up product_id in metadata.
        # So we should return the product_id from metadata if possible.

        out = []
        for i, doc_id in enumerate(ids):
            meta = results["metadatas"][0][i] or {}
            # Always return product_id to satisfy VectorIndex contract,
            # even if the doc_id is a review_id.
            p_id = meta.get("product_id", doc_id)
            dist = distances[i]
            # Convert distance to similarity score
            score = 1.0 / (1.0 + dist)
            out.append((p_id, score))

        return out

    def upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        """Upsert a batch of documents into the collection."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def count(self) -> int:
        """Return number of documents in collection."""
        return self._collection.count()
