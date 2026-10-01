from pathlib import Path
import advisor.llm.embedder  # noqa: F401
from advisor.retrieval.semantic import semantic_search
from advisor.store.sqlite_store import open_db
from advisor.store.vector_store import ChromaVectorIndex


def test_semantic_restrictive_filter():
    chroma_dir = Path("data/chroma")
    products_vec_idx = ChromaVectorIndex(chroma_dir, "products")
    reviews_vec_idx = ChromaVectorIndex(chroma_dir, "reviews")

    conn = open_db(Path("data/advisor.db"))
    all_rows = conn.execute("SELECT product_id, name FROM products WHERE is_canonical = 1 LIMIT 1000").fetchall()
    conn.close()

    # Build an allow list of 510 items (to trigger >=500 branch)
    # Ensure it contains at least 20 items so we don't starve.
    targets = [r["product_id"] for r in all_rows[:20]]
    others = [r["product_id"] for r in all_rows[20:]]

    allow_ids = targets + others[:500]

    results = semantic_search(
        query=all_rows[0]["name"],
        allow_ids=allow_ids,
        products_idx=products_vec_idx,
        reviews_idx=reviews_vec_idx,
        k=10
    )

    assert len(results) > 0, "Silently starved to zero!"
    assert len(results) <= 10, "Should respect requested k"
    assert len(results) >= 5, f"Expected near k=10, got {len(results)}"
