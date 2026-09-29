"""Local sentence-transformers embedding provider.

WHY: §9 specifies local bge-small-en-v1.5 on CPU. This avoids quota issues,
is deterministic, and is fast enough for ~54k texts. If Hinglish retrieval
evaluates poorly, the fallback is a multilingual small model behind this
same interface.

Registered under the 'providers' registry.
"""
from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer

from advisor.core.registries import providers
from advisor.store.interfaces import Embedder

logger = logging.getLogger(__name__)

# BGE models use this prefix for queries for optimal retrieval performance.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@providers.register("bge_small_en")
class LocalBgeEmbedder(Embedder):
    """Local embedder using BAAI/bge-small-en-v1.5."""

    def __init__(self) -> None:
        # Load model locally; downloads ~130MB on first run.
        # Uses CPU by default unless torch sees a GPU.
        self._model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self._dim = self._model.get_sentence_embedding_dimension()

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed search queries (adds BGE prefix)."""
        prefixed = [f"{_BGE_QUERY_PREFIX}{t}" for t in texts]
        embeddings = self._model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed catalogue texts (no prefix)."""
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        return self._dim or 384
