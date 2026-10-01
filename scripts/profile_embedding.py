import logging
import time
from pathlib import Path

from advisor.store.sqlite_store import open_db

logging.basicConfig(level=logging.INFO)

def run():
    print("Connecting to DB...")
    conn = open_db(Path("data/advisor.db"))
    products = conn.execute("SELECT * FROM products WHERE is_canonical = 1 LIMIT 500").fetchall()

    # 1. Model Load Time
    t0 = time.time()
    from advisor.llm.embedder import LocalBgeEmbedder
    embedder = LocalBgeEmbedder()
    t1 = time.time()
    print(f"(a) Model load time: {t1 - t0:.2f}s")

    # Generate texts exactly as build_index.py does
    texts = []
    specs_rows = conn.execute("SELECT product_id, key, value, unit FROM product_specs LIMIT 5000").fetchall()
    specs_by_pid = {}
    for row in specs_rows:
        pid = row["product_id"]
        val = f"{row['key']}: {row['value']} {row['unit'] or ''}".strip()
        if pid not in specs_by_pid:
            specs_by_pid[pid] = val
        else:
            specs_by_pid[pid] += f" | {val}"

    for p in products:
        pid = p["product_id"]
        specs = specs_by_pid.get(pid, "")
        doc = f"{p['name']}\nCategories: {p['cat_l1']} > {p['cat_l2']} > {p['cat_l3']}\nSpecs: {specs}\nDescription: {p['description']}"
        texts.append(doc)


    # 2. Total embedding compute time
    t2 = time.time()
    embeddings = embedder.embed_documents(texts)
    t3 = time.time()
    emb_time = t3 - t2
    print(f"(b) Total embedding compute time (500 items): {emb_time:.2f}s")

    # 3. Total ChromaDB insert time
    # Initialize chromadb
    import chromadb
    client = chromadb.PersistentClient(path="data/chroma_test")
    collection = client.get_or_create_collection("test_col")

    ids = [p['product_id'] for p in products]
    metadatas = [{"price": 1.0} for _ in products]

    t4 = time.time()
    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    t5 = time.time()
    insert_time = t5 - t4
    print(f"(c) Total ChromaDB insert time (500 items): {insert_time:.2f}s")

    print("\n--- Projections for 54,000 items ---")
    mult = 54000 / 500
    print(f"Projected Embedding Time: {emb_time * mult:.2f}s ({emb_time * mult / 60:.2f}m)")
    print(f"Projected Insert Time: {insert_time * mult:.2f}s ({insert_time * mult / 60:.2f}m)")
    print(f"Projected Total Time: {(emb_time + insert_time) * mult / 3600:.2f}h")

if __name__ == "__main__":
    run()
