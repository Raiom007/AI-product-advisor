import argparse
import json
from pathlib import Path

from advisor.core.config import load_config
from advisor.eval.baseline import run_baseline
from advisor.retrieval.hybrid import hybrid_search
from advisor.retrieval.keyword import keyword_search
from advisor.store.sqlite_store import SQLiteKeywordIndex, open_db
from advisor.store.vector_store import ChromaVectorIndex
import advisor.llm.embedder  # noqa: F401


def build_pool(queries: list[str], k: int = 20) -> dict:
    """Builds the labeling pool for each query using real retrievers."""
    pool = {}
    config = load_config()

    conn = open_db(Path("data/advisor.db"))
    allow_ids = [r["product_id"] for r in conn.execute("SELECT product_id FROM products WHERE is_canonical = 1").fetchall()]

    products_kw_idx = SQLiteKeywordIndex(conn, "products_fts")
    reviews_kw_idx = SQLiteKeywordIndex(conn, "reviews_fts")

    chroma_dir = Path("data/chroma")
    products_vec_idx = ChromaVectorIndex(chroma_dir, "products")
    reviews_vec_idx = ChromaVectorIndex(chroma_dir, "reviews")

    for q in queries:
        print(f"Building pool for: {q}")
        pids = set()

        # 1. Baseline
        base_res = run_baseline(q, db_path="data/advisor.db", k=k)
        pids.update(pid for pid, _ in base_res)

        # 2. Hybrid
        hybrid_res = hybrid_search(q, allow_ids, products_kw_idx, reviews_kw_idx, products_vec_idx, reviews_vec_idx, config)
        pids.update(pid for pid, _, _ in hybrid_res[:k])

        # 3. BM25-only (Keyword)
        kw_res = keyword_search(q, allow_ids, products_kw_idx, reviews_kw_idx, k=k)
        pids.update(pid for pid, _ in kw_res)

        pool[q] = list(pids)

    conn.close()
    return pool

def terminal_labeller(pool: dict, db_path: str = "data/advisor.db"):
    """Tiny terminal labeller for grading query-product pairs (0-3)."""
    labels = {}
    labels_path = Path("data/eval/labels.json")
    if labels_path.exists():
        with open(labels_path) as f:
            labels = json.load(f)

    print("Welcome to the Product Labeller.")
    print("Enter grade 0 (irrelevant) to 3 (perfect match). Type 'q' to quit, 's' to skip.")

    conn = open_db(Path(db_path))

    try:
        for query, product_ids in pool.items():
            if query not in labels:
                labels[query] = {}

            print(f"\n=== QUERY: {query} ===")
            for pid in product_ids:
                if pid in labels[query]:
                    continue

                row = conn.execute("SELECT name, effective_price_inr, description FROM products WHERE product_id = ?", [pid]).fetchone()
                if not row:
                    continue

                print(f"\nProduct: {pid}")
                print(f"Name: {row['name']}")
                print(f"Price: INR {row['effective_price_inr'] or 'N/A'}")
                print(f"Specs: {row['description'][:200]}...")

                while True:
                    ans = input("Grade (0-3) [q/s]: ").strip().lower()
                    if ans == 'q':
                        raise KeyboardInterrupt
                    elif ans == 's':
                        break
                    elif ans in ['0', '1', '2', '3']:
                        labels[query][pid] = int(ans)
                        break
                    else:
                        print("Invalid input.")
    except KeyboardInterrupt:
        print("\nSaving and exiting...")

    conn.close()
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with open(labels_path, "w") as f:
        json.dump(labels, f, indent=2)
    print(f"Saved to {labels_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Build pool")
    parser.add_argument("--label", action="store_true", help="Run labeller")
    args = parser.parse_args()

    if args.build:
        q_path = Path("data/eval/gold_queries.txt")
        if q_path.exists():
            queries = [line.strip() for line in q_path.read_text().splitlines() if line.strip()]
        else:
            queries = ["laptop under 50k", "gaming phone"]
        
        pool = build_pool(queries)
        Path("data/eval").mkdir(parents=True, exist_ok=True)
        with open("data/eval/pool.json", "w") as f:
            json.dump(pool, f, indent=2)
        print("Pool built.")

    if args.label:
        try:
            with open("data/eval/pool.json") as f:
                pool = json.load(f)
            terminal_labeller(pool)
        except FileNotFoundError:
            print("Pool not found. Run with --build first.")
