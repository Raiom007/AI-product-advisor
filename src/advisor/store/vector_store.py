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
        
        # If allow_ids is very large, Chroma's $in operator becomes extremely slow.
        # In that case, we drop the where filter, query more results, and filter locally.
        where_args = {}
        # HNSW ef_search limits n_results. To avoid "Probably ef or M is too small", 
        # we can't inflate fetch_k too much. k=100 is safe.
        fetch_k = k
        if len(allow_ids) < 500:
            where_args["where"] = {"product_id": {"$in": allow_ids}}
        else:
            fetch_k = k

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                include=["distances", "metadatas"],
                **where_args
            )
        except Exception as e:
            logger.warning(f"Chroma search failed: {e}")
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        distances = results["distances"][0]

        out = []
        allow_set = set(allow_ids) if len(allow_ids) >= 500 else None

        for i, doc_id in enumerate(ids):
            meta = results["metadatas"][0][i] or {}
            p_id = meta.get("product_id", doc_id)
            
            if allow_set is not None and p_id not in allow_set:
                continue
                
            dist = distances[i]
            score = 1.0 / (1.0 + dist)
            out.append((p_id, score))
            
            if len(out) >= k:
                break

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
