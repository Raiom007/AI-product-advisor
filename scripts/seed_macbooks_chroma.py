from pathlib import Path
import sqlite3
from advisor.llm.embedder import LocalBgeEmbedder
from advisor.store.vector_store import ChromaVectorIndex

embedder = LocalBgeEmbedder()
chroma_path = Path("data/chroma")
prod_idx = ChromaVectorIndex(chroma_path, "products")
rev_idx = ChromaVectorIndex(chroma_path, "reviews")

conn = sqlite3.connect("data/advisor.db")
mac_pids = ["MCA_B08GG9QKX6", "MCA_B0B3C4H9NW", "MCA_B0CM5BWT68", "MCA_B0C76C2K26", "MCA_B0CM5J95Y6"]

for pid in mac_pids:
    row = conn.execute("SELECT name, description FROM products WHERE product_id = ?", (pid,)).fetchone()
    if row:
        text = f"{row[0]} {row[1]}"
        emb = embedder.embed_documents([text])[0]
        prod_idx._collection.upsert(
            ids=[pid],
            embeddings=[emb],
            documents=[text],
            metadatas=[{"product_id": pid}]
        )
        print(f"Upserted Chroma product {pid}")

    rev_rows = conn.execute("SELECT review_id, text FROM reviews WHERE product_id = ?", (pid,)).fetchall()
    for rid, rtext in rev_rows:
        remb = embedder.embed_documents([rtext])[0]
        rev_idx._collection.upsert(
            ids=[rid],
            embeddings=[remb],
            documents=[rtext],
            metadatas=[{"product_id": pid, "review_id": rid}]
        )
        print(f"Upserted Chroma review {rid}")

conn.close()
print("Chroma embedding upsert complete!")
