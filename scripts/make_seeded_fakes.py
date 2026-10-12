import sqlite3
import random
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def main():
    random.seed(42)
    src_db = Path("data/advisor.db")
    dst_db = Path("data/advisor_fakes.db")
    truth_file = Path("eval/data/seeded_fakes.jsonl")
    
    if not src_db.exists():
        print("advisor.db not found!")
        return
        
    shutil.copy2(src_db, dst_db)
    conn = sqlite3.connect(dst_db)
    
    # Get some valid product ids
    prods = conn.execute("SELECT product_id FROM products LIMIT 100").fetchall()
    prod_ids = [p[0] for p in prods]
    
    fakes = []
    
    # Strategy 1: near_dup (20 reviews in clusters of 4 across 5 products)
    template_text = "This product is absolutely amazing. I cannot believe how well it works. I use it every single day and my life is so much better now. Highly recommend to everyone."
    dup_pids = prod_ids[10:15] # 5 distinct products
    for i in range(20):
        rid = f"fake_dup_{i}"
        pid = dup_pids[i % 5]
        rev = {
            "review_id": rid, "product_id": pid, "rating": 5.0, 
            "text": template_text, "reviewer_id": f"rev_dup_{i}",
            "review_date": "2023-01-01T12:00:00Z"
        }
        fakes.append((rev, "near_dup"))
        
    # Strategy 2: burst (20 reviews on same product in 2 hours)
    burst_pid = prod_ids[0]
    base_time = datetime(2023, 6, 1, 12, 0, 0)
    for i in range(30):
        rid = f"fake_burst_{i}"
        dt = (base_time + timedelta(minutes=i*2)).isoformat() + "Z"
        rev = {
            "review_id": rid, "product_id": burst_pid, "rating": 5.0,
            "text": f"Great! Love it! number {i}", "reviewer_id": f"rev_burst_{i}",
            "review_date": dt
        }
        fakes.append((rev, "burst"))
        
    # Strategy 3: extreme_no_detail (30 reviews)
    for i in range(30):
        rid = f"fake_no_detail_{i}"
        pid = random.choice(prod_ids)
        rating = 5.0 if i % 2 == 0 else 1.0
        text = "Awesome!" if rating == 5 else "Terrible!"
        rev = {
            "review_id": rid, "product_id": pid, "rating": rating,
            "text": text, "reviewer_id": f"rev_nodet_{i}",
            "review_date": "2023-02-01T12:00:00Z"
        }
        fakes.append((rev, "extreme_no_detail"))
        
    # Strategy 4: reviewer_pattern (20 reviews, same reviewer, multiple prods, same day)
    spam_rev = "spammer_999"
    for i in range(20):
        rid = f"fake_pattern_{i}"
        pid = prod_ids[i % len(prod_ids)]
        rev = {
            "review_id": rid, "product_id": pid, "rating": 5.0,
            "text": "Very nice product, works well.", "reviewer_id": spam_rev,
            "review_date": "2023-03-01T14:00:00Z"
        }
        fakes.append((rev, "reviewer_pattern"))
        
    # Shuffle and split
    random.shuffle(fakes)
    split_idx = len(fakes) // 2
    
    # Insert to DB
    for rev, _ in fakes:
        conn.execute(
            """INSERT INTO reviews 
               (review_id, product_id, reviewer_id, rating, text, review_date, is_duplicate, ingested_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rev["review_id"], rev["product_id"], rev["reviewer_id"], rev["rating"], 
             rev["text"], rev["review_date"], 0, datetime.now().isoformat() + "Z")
        )
    conn.commit()
    conn.close()
    
    # Write truth sidecar
    with open(truth_file, "w") as f:
        for i, (rev, signal) in enumerate(fakes):
            split = "dev" if i < split_idx else "test"
            f.write(json.dumps({
                "review_id": rev["review_id"],
                "split": split,
                "signal_expected": signal
            }) + "\n")
            
    print(f"Generated {len(fakes)} fake reviews into {dst_db} and sidecar {truth_file}")

if __name__ == "__main__":
    main()
