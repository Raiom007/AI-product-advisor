"""CLI demo for retrieval strategies.

Usage:
  python -m advisor.retrieval.demo "gaming laptop 16gb"
  
Prints ids, names, prices, scores and which retriever contributed.
Reports per-stage latency.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from advisor.core.config import load_config
from advisor.llm.embedder import LocalBgeEmbedder
from advisor.retrieval.hybrid import hybrid_search
from advisor.store.sqlite_store import SQLiteKeywordIndex, open_db
from advisor.store.vector_store import ChromaVectorIndex

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Search query")
    parser.add_argument("--db", default="data/advisor.db")
    parser.add_argument("--chroma", default="data/chroma")
    args = parser.parse_args()

    config = load_config()

    print("Loading indices...")
    t0 = time.time()

    conn = open_db(Path(args.db))
    # For demo, allow all canonical products
    allow_ids = [r["product_id"] for r in conn.execute("SELECT product_id FROM products WHERE is_canonical = 1").fetchall()]

    products_kw_idx = SQLiteKeywordIndex(conn, "products_fts")
    reviews_kw_idx = SQLiteKeywordIndex(conn, "reviews_fts")

    chroma_dir = Path(args.chroma)
    products_vec_idx = ChromaVectorIndex(chroma_dir, "products")
    reviews_vec_idx = ChromaVectorIndex(chroma_dir, "reviews")

    embedder = LocalBgeEmbedder()

    t1 = time.time()
    print(f"Indices loaded in {t1 - t0:.2f}s")

    print(f"\nRunning hybrid retrieval for: '{args.query}'")
    t4 = time.time()

    results = hybrid_search(
        query=args.query,
        allow_ids=allow_ids,
        products_kw_idx=products_kw_idx,
        reviews_kw_idx=reviews_kw_idx,
        products_vec_idx=products_vec_idx,
        reviews_vec_idx=reviews_vec_idx,
        config=config,
    )

    t5 = time.time()
    print(f"Retrieval complete in {t5 - t4:.2f}s")

    if not results:
        print("No results found.")
        sys.exit(0)

    print("\nResults:")
    print("-" * 80)
    print(f"{'ID':<10} | {'Score':<6} | {'Price':<8} | {'Contributors':<25} | Name")
    print("-" * 80)

    for pid, score, contributors in results:
        row = conn.execute("SELECT name, effective_price_inr FROM products WHERE product_id = ?", [pid]).fetchone()
        name = row["name"][:35] + "..." if len(row["name"]) > 35 else row["name"]
        price = f"INR {row['effective_price_inr']:,.0f}" if row["effective_price_inr"] else "N/A"
        contribs = ",".join(sorted(contributors))

        print(f"{pid:<10} | {score:6.3f} | {price:<8} | {contribs:<25} | {name}")


if __name__ == "__main__":
    main()
