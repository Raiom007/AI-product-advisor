"""Tests for vector store and FTS5 interfaces."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from advisor.store.interfaces import Embedder, VectorIndex
from advisor.store.sqlite_store import build_fts_indexes, insert_products, insert_reviews, open_db
from advisor.store.vector_store import ChromaVectorIndex


class FakeEmbedder(Embedder):
    """Simple embedder for testing."""
    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def get_dimension(self) -> int:
        return 384


class FakeVectorIndex(VectorIndex):
    """In-memory fake vector index for fast tests."""
    def __init__(self):
        self.docs = []

    def upsert_batch(self, ids, embeddings, metadatas, documents):
        for idx, doc_id in enumerate(ids):
            self.docs.append({
                "id": doc_id,
                "embedding": embeddings[idx],
                "metadata": metadatas[idx],
                "document": documents[idx],
            })

    def search(self, query_embedding, allow_ids, k=10):
        if not allow_ids:
            return []

        results = []
        for doc in self.docs:
            p_id = doc["metadata"].get("product_id", doc["id"])
            if p_id in allow_ids:
                # Fake score
                results.append((p_id, 0.9))

        # Sort and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]


@pytest.fixture
def chroma_idx(tmp_path):
    idx = ChromaVectorIndex(tmp_path / "chroma", "products")
    yield idx


@pytest.fixture
def fake_idx():
    yield FakeVectorIndex()


def run_contract_test(idx, is_fake=False):
    """Contract test that runs against both real and fake adapters."""
    # Insert some data
    idx.upsert_batch(
        ids=["P001", "P002", "P003"],
        embeddings=[[0.1]*384, [0.2]*384, [0.3]*384],
        metadatas=[{"product_id": "P001"}, {"product_id": "P002"}, {"product_id": "P003"}],
        documents=["doc 1", "doc 2", "doc 3"]
    )

    # Test allow-list restriction
    results = idx.search([0.1]*384, allow_ids=["P001", "P003"])
    returned_ids = [r[0] for r in results]

    # Never returns ids outside the allow-list
    assert "P002" not in returned_ids
    assert "P001" in returned_ids
    assert "P003" in returned_ids

    # Test empty allow_list
    assert len(idx.search([0.1]*384, allow_ids=[])) == 0


def test_chroma_contract(chroma_idx):
    run_contract_test(chroma_idx)


def test_fake_contract(fake_idx):
    run_contract_test(fake_idx, is_fake=True)


def test_fts5_rebuild_is_idempotent():
    """Test that FTS5 virtual tables can be safely rebuilt multiple times."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        conn = open_db(db_path)

        # Insert test product and review
        p = {
            "product_id": "P999", "name": "Phone", "brand": "B", "cat_l1": "C1", "cat_l2": "C2", "cat_l3": "C3",
            "retail_price_inr": 100, "discounted_price_inr": 100, "effective_price_inr": 100,
            "price_unknown": 0, "price_anomaly": 0, "description": "Good",
            "image_urls": "", "image_url_count": 0, "image_url_broken": 0,
            "alias_ids": "[]", "is_canonical": 1, "ingested_at": "now"
        }
        insert_products(conn, [p])

        r = {
            "review_id": "R999", "product_id": "P999", "original_product_id": "P999",
            "rating": 5, "title": "Great", "text": "Awesome",
            "review_date": "now", "reviewer_id": "U1", "helpful_votes": 0,
            "injection_flag": 0, "is_duplicate": 0, "ingested_at": "now"
        }
        insert_reviews(conn, [r])

        # Build first time
        build_fts_indexes(conn)
        res1 = conn.execute("SELECT COUNT(*) FROM products_fts").fetchone()[0]
        assert res1 == 1

        # Build second time (idempotent)
        build_fts_indexes(conn)
        res2 = conn.execute("SELECT COUNT(*) FROM products_fts").fetchone()[0]
        assert res2 == 1

        conn.close()
