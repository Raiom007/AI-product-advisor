"""Retrieval and embedding interfaces.

WHY: Separates the retrieval strategy from the storage technology (SQLite/Chroma).
This allows injecting fake implementations for tests and supports the degradation
ladder (e.g. falling back to keyword-only if the vector DB or embedder fails).
"""
from __future__ import annotations

import abc
from typing import Protocol


class KeywordIndex(Protocol):
    """Protocol for BM25/keyword retrieval."""

    def search(
        self,
        query: str,
        allow_ids: list[str],
        k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search products and reviews using keyword matching.

        Args:
            query: The search terms (e.g. "gaming laptop 16gb").
            allow_ids: List of product_ids that passed hard SQL filters.
            k: Maximum number of results to return.

        Returns:
            List of (product_id, bm25_score) tuples, sorted by score descending.
        """
        ...


class VectorIndex(Protocol):
    """Protocol for semantic retrieval."""

    def search(
        self,
        query_embedding: list[float],
        allow_ids: list[str],
        k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search products and reviews using cosine similarity.

        Args:
            query_embedding: The embedded query vector.
            allow_ids: List of product_ids that passed hard SQL filters.
            k: Maximum number of results to return.

        Returns:
            List of (product_id, cosine_score) tuples, sorted by score descending.
        """
        ...


class Embedder(abc.ABC):
    """Base class for embedding models."""

    @abc.abstractmethod
    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of search queries."""
        pass

    @abc.abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document texts (products, reviews)."""
        pass

    @abc.abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimension of this embedder."""
        pass
