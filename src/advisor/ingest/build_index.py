"""FTS5 and Vector index builder (ingest pipeline step 2).

WHY: §9 specifies building search indices offline.
FTS5 is rebuilt efficiently in SQLite.
ChromaDB embeddings are batched, resumable, and only run on redacted texts.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from advisor.llm.embedder import LocalBgeEmbedder
from advisor.store.sqlite_store import build_fts_indexes, open_db
from advisor.store.vector_store import ChromaVectorIndex

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BATCH_SIZE = 256


def embed_products(conn: sqlite3.Connection, chroma: ChromaVectorIndex, embedder: LocalBgeEmbedder) -> int:
    """Embed canonical products that are not yet in Chroma.
    
    Format (§5.2): name + category + specs + description.
    """
    # Fetch all canonical products
    # We construct the text to embed: name + category + specs + description.
    # To do this efficiently, we can fetch all products and their specs.

    logger.info("Fetching products for embedding...")
    products = conn.execute(
        "SELECT * FROM products WHERE is_canonical = 1"
    ).fetchall()

    # Check what is already embedded to make it resumable
    # We can query Chroma for all ids or just check in batches, but Chroma doesn't have an easy "get all ids".
    # Wait, Chroma get() supports limit/offset, we can get all existing ids.
    existing_ids = set()
    offset = 0
    while True:
        res = chroma._collection.get(include=[], limit=5000, offset=offset)
        if not res["ids"]:
            break
        existing_ids.update(res["ids"])
        offset += len(res["ids"])

    logger.info(f"Found {len(existing_ids)} products already in Vector DB.")

    # Get all specs to construct the full text
    specs_by_pid: dict[str, str] = {}
    specs_rows = conn.execute("SELECT product_id, key, value, unit FROM product_specs").fetchall()
    for row in specs_rows:
        pid = row["product_id"]
        # Skip raw keys in the text if desired, but including them is fine.
        val = f"{row['key']}: {row['value']} {row['unit'] or ''}".strip()
        if pid not in specs_by_pid:
            specs_by_pid[pid] = val
        else:
            specs_by_pid[pid] += f" | {val}"

    products_to_embed = [p for p in products if p["product_id"] not in existing_ids]
    logger.info(f"{len(products_to_embed)} products to embed.")

    embedded_count = 0
    for i in range(0, len(products_to_embed), BATCH_SIZE):
        batch = products_to_embed[i:i + BATCH_SIZE]
        texts = []
        metadatas = []
        ids = []

        for p in batch:
            pid = p["product_id"]
            specs = specs_by_pid.get(pid, "")
            # Construct document
            doc = f"{p['name']}\nCategories: {p['cat_l1']} > {p['cat_l2']} > {p['cat_l3']}\nSpecs: {specs}\nDescription: {p['description']}"
            texts.append(doc)

            # Metadata: product_id, price, cat_l1..l3, brand, flagged (N/A for products)
            meta = {
                "product_id": pid,
                "price": float(p["effective_price_inr"]) if p["effective_price_inr"] is not None else 0.0,
                "cat_l1": p["cat_l1"] or "",
                "cat_l2": p["cat_l2"] or "",
                "cat_l3": p["cat_l3"] or "",
                "brand": p["brand"] or "",
            }
            metadatas.append(meta)
            ids.append(pid)

        logger.info(f"Embedding product batch {i//BATCH_SIZE + 1}...")
        embeddings = embedder.embed_documents(texts)
        chroma.upsert_batch(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        embedded_count += len(batch)

    return embedded_count


def embed_reviews(conn: sqlite3.Connection, chroma: ChromaVectorIndex, embedder: LocalBgeEmbedder) -> int:
    """Embed reviews that are not yet in Chroma.
    
    Only embeds redacted text.
    """
    logger.info("Fetching reviews for embedding...")
    # exclude quarantined and empty texts
    reviews = conn.execute(
        "SELECT * FROM reviews WHERE text IS NOT NULL AND text != ''"
    ).fetchall()

    existing_ids = set()
    offset = 0
    while True:
        res = chroma._collection.get(include=[], limit=5000, offset=offset)
        if not res["ids"]:
            break
        existing_ids.update(res["ids"])
        offset += len(res["ids"])

    logger.info(f"Found {len(existing_ids)} reviews already in Vector DB.")

    reviews_to_embed = [r for r in reviews if r["review_id"] not in existing_ids]
    logger.info(f"{len(reviews_to_embed)} reviews to embed.")

    # We need to know if a review is flagged, but flags are populated in P11.
    # For now, default to False.
    flags = {row["review_id"]: row["action"] for row in conn.execute("SELECT review_id, action FROM review_flags").fetchall()}

    embedded_count = 0
    for i in range(0, len(reviews_to_embed), BATCH_SIZE):
        batch = reviews_to_embed[i:i + BATCH_SIZE]
        texts = []
        metadatas = []
        ids = []

        for r in batch:
            rid = r["review_id"]
            doc = r["text"]
            texts.append(doc)

            # Metadata: product_id, flagged
            is_flagged = flags.get(rid) in ("exclude", "downweight")
            meta = {
                "product_id": r["product_id"],
                "flagged": is_flagged,
            }
            metadatas.append(meta)
            ids.append(rid)

        logger.info(f"Embedding review batch {i//BATCH_SIZE + 1}...")
        embeddings = embedder.embed_documents(texts)
        chroma.upsert_batch(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        embedded_count += len(batch)

    return embedded_count


def build_all(db_path: Path, chroma_dir: Path) -> dict[str, Any]:
    """Run full index build pipeline."""
    start_t = time.time()

    conn = open_db(db_path)
    logger.info("Building FTS5 indices...")
    build_fts_indexes(conn)
    fts_t = time.time()
    logger.info(f"FTS5 complete in {fts_t - start_t:.1f}s")

    logger.info("Loading embedder...")
    embedder = LocalBgeEmbedder()

    logger.info("Initializing ChromaDB...")
    products_idx = ChromaVectorIndex(chroma_dir, "products")
    reviews_idx = ChromaVectorIndex(chroma_dir, "reviews")

    p_count = embed_products(conn, products_idx, embedder)
    r_count = embed_reviews(conn, reviews_idx, embedder)

    end_t = time.time()

    stats = {
        "products_embedded": p_count,
        "reviews_embedded": r_count,
        "total_products_in_vector_db": products_idx.count(),
        "total_reviews_in_vector_db": reviews_idx.count(),
        "build_time_seconds": round(end_t - start_t, 1)
    }
    logger.info(f"Index build complete: {stats}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/advisor.db")
    parser.add_argument("--chroma", default="data/chroma")
    args = parser.parse_args()

    build_all(Path(args.db), Path(args.chroma))


if __name__ == "__main__":
    main()
