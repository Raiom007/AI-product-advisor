"""Latency testing script for retrieval."""
import time
import numpy as np
from pathlib import Path
from advisor.core.config import load_config
from advisor.llm.embedder import LocalBgeEmbedder
from advisor.store.sqlite_store import SQLiteKeywordIndex, open_db
from advisor.store.vector_store import ChromaVectorIndex
from advisor.retrieval.keyword import keyword_search
from advisor.retrieval.semantic import semantic_search
from advisor.retrieval.hybrid import hybrid_search

def run_latency_test():
    config = load_config()
    conn = open_db(Path("data/advisor.db"))
    allow_ids = [r["product_id"] for r in conn.execute("SELECT product_id FROM products WHERE is_canonical = 1").fetchall()]
    
    products_kw_idx = SQLiteKeywordIndex(conn, "products_fts")
    reviews_kw_idx = SQLiteKeywordIndex(conn, "reviews_fts")
    
    chroma_dir = Path("data/chroma")
    products_vec_idx = ChromaVectorIndex(chroma_dir, "products")
    reviews_vec_idx = ChromaVectorIndex(chroma_dir, "reviews")
    
    queries = [
        "gaming laptop 16gb",
        "best budget phone for elderly",
        "DSLR camera for beginners",
        "wireless noise cancelling headphones",
        "smart watch with ecg and long battery",
        "lightweight ultrabook for programming",
        "4k monitor for video editing",
        "android tablet for reading pdfs",
        "mechanic keyboard with red switches",
        "iphone 15 pro max case"
    ]
    
    kw_times = []
    sem_times = []
    hybrid_times = []
    
    for q in queries:
        t0 = time.time()
        keyword_search(q, allow_ids, products_kw_idx, reviews_kw_idx)
        kw_times.append(time.time() - t0)
        
        t1 = time.time()
        semantic_search(q, allow_ids, products_vec_idx, reviews_vec_idx)
        sem_times.append(time.time() - t1)
        
        t2 = time.time()
        hybrid_search(
            q, allow_ids,
            products_kw_idx, reviews_kw_idx,
            products_vec_idx, reviews_vec_idx, config
        )
        hybrid_times.append(time.time() - t2)
        
    print(f"Keyword-only average latency: {np.mean(kw_times)*1000:.1f}ms")
    print(f"Semantic-only average latency: {np.mean(sem_times)*1000:.1f}ms")
    print(f"Fused/hybrid average latency: {np.mean(hybrid_times)*1000:.1f}ms")
    
if __name__ == "__main__":
    run_latency_test()
