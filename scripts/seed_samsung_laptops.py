import sqlite3
import json
from datetime import datetime
from pathlib import Path
from advisor.llm.embedder import LocalBgeEmbedder
from advisor.store.vector_store import ChromaVectorIndex

conn = sqlite3.connect("data/advisor.db")
cur = conn.cursor()

samsung_laptops = [
    {
        "product_id": "MCA_B0CT8N15M1",
        "name": "Samsung Galaxy Book4 Laptop: 15.6\" Full HD Display, Intel Core 5 120U Processor, 16GB RAM, 512GB SSD Storage, Intel Graphics, Windows 11 Home, Metal Body - Gray",
        "brand": "Samsung",
        "cat_l1": "Electronics",
        "cat_l2": "Computers & Tablets",
        "cat_l3": "Laptops",
        "retail_price_inr": 84990.0,
        "discounted_price_inr": 69990.0,
        "effective_price_inr": 69990.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "The latest Samsung Galaxy Book4 powered by 13th/14th Gen Intel Core 5 120U processor. Stunning 15.6-inch anti-glare FHD screen, 16GB LPDDR5 RAM for smooth coding and multitasking, 512GB NVMe SSD, Dolby Atmos stereo speakers, and seamless Samsung Galaxy Connected Experience.",
        "image_urls": json.dumps([
            "https://m.media-amazon.com/images/I/71V-r8zGq6L._AC_SX679_.jpg",
            "https://m.media-amazon.com/images/I/718y6Z6rKJL._AC_SX679_.jpg"
        ]),
        "image_url_count": 2,
        "image_url_broken": 0,
        "alias_ids": "",
        "is_canonical": 1,
        "ingested_at": datetime.utcnow().isoformat(),
        "specs": [
            ("Processor", "Intel Core 5 120U (10 Cores, up to 5.0 GHz)", "Intel Core 5 120U (10 Cores, up to 5.0 GHz)"),
            ("Memory", "16GB LPDDR5 RAM", "16GB LPDDR5 RAM"),
            ("Storage", "512GB NVMe M.2 SSD (expandable)", "512GB NVMe M.2 SSD (expandable)"),
            ("Display", "15.6-inch Full HD (1920 x 1080) Anti-Glare Display", "15.6-inch Full HD (1920 x 1080) Anti-Glare Display"),
            ("Battery", "54Wh Battery with 45W Type-C Fast Charger", "54Wh Battery with 45W Type-C Fast Charger"),
            ("Weight", "1.55 kg Lightweight Aluminum Body", "1.55 kg Lightweight Aluminum Body")
        ],
        "review": {
            "title": "Outstanding Samsung laptop for work and coding",
            "text": "Extremely pleased with the Galaxy Book4. 16GB RAM handles Docker, VS Code, and browser tabs effortlessly. Build quality is sleek and premium. Battery lasts 8+ hours easily."
        }
    },
    {
        "product_id": "MCA_B0BSXMRY8C",
        "name": "Samsung Galaxy Book3 360 2-in-1 Touchscreen Laptop: 13.3\" Super AMOLED Display, 13th Gen Intel Core i5-1335U, 16GB RAM, 512GB SSD, S-Pen Support, Windows 11 Home - Graphite",
        "brand": "Samsung",
        "cat_l1": "Electronics",
        "cat_l2": "Computers & Tablets",
        "cat_l3": "Laptops",
        "retail_price_inr": 99990.0,
        "discounted_price_inr": 82990.0,
        "effective_price_inr": 82990.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "Versatile 2-in-1 convertible laptop featuring a vibrant 13.3-inch Super AMOLED touchscreen with 120% DCI-P3 color gamut. Powered by Intel 13th Gen Core i5 with 16GB RAM, responsive S-Pen capability for notes and drawing, and ultra-portable 1.16 kg form factor.",
        "image_urls": json.dumps([
            "https://m.media-amazon.com/images/I/71uKekJ2+OL._AC_SX679_.jpg",
            "https://m.media-amazon.com/images/I/61Nl2d43lVL._AC_SX679_.jpg"
        ]),
        "image_url_count": 2,
        "image_url_broken": 0,
        "alias_ids": "",
        "is_canonical": 1,
        "ingested_at": datetime.utcnow().isoformat(),
        "specs": [
            ("Processor", "Intel 13th Gen Core i5-1335U (10 Cores, up to 4.6 GHz)", "Intel 13th Gen Core i5-1335U (10 Cores, up to 4.6 GHz)"),
            ("Memory", "16GB LPDDR4x RAM", "16GB LPDDR4x RAM"),
            ("Storage", "512GB PCIe Gen4 NVMe SSD", "512GB PCIe Gen4 NVMe SSD"),
            ("Display", "13.3-inch FHD Super AMOLED (1920 x 1080) Touchscreen", "13.3-inch FHD Super AMOLED (1920 x 1080) Touchscreen"),
            ("Battery", "61.1Wh Battery with up to 18 hours life", "61.1Wh Battery with up to 18 hours life"),
            ("Weight", "1.16 kg Ultra-lightweight", "1.16 kg Ultra-lightweight")
        ],
        "review": {
            "title": "Best AMOLED display on any 2-in-1 laptop",
            "text": "The Super AMOLED display is breathtaking for media and programming. Converting to tablet mode for sketching and reviewing code is seamless. Fast and responsive."
        }
    },
    {
        "product_id": "MCA_B0CT8PYXZ9",
        "name": "Samsung Galaxy Book4 Pro 360 2-in-1 Laptop: 16\" 3K Dynamic AMOLED 2X Touchscreen, Intel Core Ultra 7 155H, 16GB LPDDR5X RAM, 512GB SSD, S-Pen Included, Windows 11 - Moonstone Gray",
        "brand": "Samsung",
        "cat_l1": "Electronics",
        "cat_l2": "Computers & Tablets",
        "cat_l3": "Laptops",
        "retail_price_inr": 179990.0,
        "discounted_price_inr": 149990.0,
        "effective_price_inr": 149990.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "Flagship 360-degree convertible laptop featuring Intel Core Ultra 7 AI-enabled processor with Intel Arc Graphics. Breathtaking 16-inch 3K (2880x1800) 120Hz Dynamic AMOLED 2X screen, bundled S-Pen, AKG quad speakers, and premium MIL-STD military durability.",
        "image_urls": json.dumps([
            "https://m.media-amazon.com/images/I/81xU4D6p3mL._AC_SX679_.jpg",
            "https://m.media-amazon.com/images/I/710TJuHTMhL._AC_SX679_.jpg"
        ]),
        "image_url_count": 2,
        "image_url_broken": 0,
        "alias_ids": "",
        "is_canonical": 1,
        "ingested_at": datetime.utcnow().isoformat(),
        "specs": [
            ("Processor", "Intel Core Ultra 7 155H (16 Cores, Intel AI Boost NPU)", "Intel Core Ultra 7 155H (16 Cores, Intel AI Boost NPU)"),
            ("Memory", "16GB LPDDR5X RAM", "16GB LPDDR5X RAM"),
            ("Storage", "512GB NVMe SSD (PCIe 4.0)", "512GB NVMe SSD (PCIe 4.0)"),
            ("Display", "16-inch 3K (2880x1800) Dynamic AMOLED 2X 120Hz Touchscreen", "16-inch 3K (2880x1800) Dynamic AMOLED 2X 120Hz Touchscreen"),
            ("Battery", "76Wh Battery with 65W USB-C fast charging", "76Wh Battery with 65W USB-C fast charging"),
            ("Weight", "1.66 kg Aluminum Chassis", "1.66 kg Aluminum Chassis")
        ],
        "review": {
            "title": "Powerhouse for software development and design",
            "text": "The 3K 120Hz screen is unmatched. Compilation speeds on the Core Ultra 7 are astonishing. Best Windows laptop I have ever used, hands down."
        }
    },
    {
        "product_id": "MCA_B09VG34D35",
        "name": "Samsung Galaxy Book2 Laptop: 15.6\" FHD Display, Intel 12th Gen Core i5-1235U, 8GB RAM, 512GB NVMe SSD, Intel Iris Xe Graphics, Windows 11 Home - Silver",
        "brand": "Samsung",
        "cat_l1": "Electronics",
        "cat_l2": "Computers & Tablets",
        "cat_l3": "Laptops",
        "retail_price_inr": 64990.0,
        "discounted_price_inr": 52990.0,
        "effective_price_inr": 52990.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "Reliable and slim daily driver laptop with 12th Gen Intel Core i5 processor, 15.6-inch Full HD display, 512GB fast NVMe SSD, backlit keyboard, fingerprint power key, and thin 1.81 kg metal body.",
        "image_urls": json.dumps([
            "https://m.media-amazon.com/images/I/71V-r8zGq6L._AC_SX679_.jpg",
            "https://m.media-amazon.com/images/I/718y6Z6rKJL._AC_SX679_.jpg"
        ]),
        "image_url_count": 2,
        "image_url_broken": 0,
        "alias_ids": "",
        "is_canonical": 1,
        "ingested_at": datetime.utcnow().isoformat(),
        "specs": [
            ("Processor", "12th Gen Intel Core i5-1235U (10 Cores, up to 4.4 GHz)", "12th Gen Intel Core i5-1235U (10 Cores, up to 4.4 GHz)"),
            ("Memory", "8GB DDR4 RAM (expandable)", "8GB DDR4 RAM (expandable)"),
            ("Storage", "512GB NVMe M.2 SSD", "512GB NVMe M.2 SSD"),
            ("Display", "15.6-inch FHD (1920x1080) LED Display", "15.6-inch FHD (1920x1080) LED Display"),
            ("Battery", "43Wh Battery with compact USB-C charger", "43Wh Battery with compact USB-C charger"),
            ("Weight", "1.81 kg", "1.81 kg")
        ],
        "review": {
            "title": "Solid budget-friendly Samsung laptop",
            "text": "Great keyboard travel, crisp screen, and very quiet operation. Ideal for students and daily programming tasks."
        }
    },
    {
        "product_id": "MCA_B08T1V948F",
        "name": "Samsung Galaxy Chromebook 2: 13.3\" QLED FHD Touchscreen Display, Intel Core i3-10110U, 8GB RAM, 128GB Storage, WiFi 6, ChromeOS - Fiesta Red",
        "brand": "Samsung",
        "cat_l1": "Electronics",
        "cat_l2": "Computers & Tablets",
        "cat_l3": "Laptops",
        "retail_price_inr": 49990.0,
        "discounted_price_inr": 39990.0,
        "effective_price_inr": 39990.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "World's first Chromebook with a QLED display. Vibrant 13.3-inch touchscreen, Intel Core i3 power, 8GB RAM, Wi-Fi 6 connectivity, and 2-in-1 convertible 360 hinge in head-turning Fiesta Red finish.",
        "image_urls": json.dumps([
            "https://m.media-amazon.com/images/I/71uKekJ2+OL._AC_SX679_.jpg",
            "https://m.media-amazon.com/images/I/61Nl2d43lVL._AC_SX679_.jpg"
        ]),
        "image_url_count": 2,
        "image_url_broken": 0,
        "alias_ids": "",
        "is_canonical": 1,
        "ingested_at": datetime.utcnow().isoformat(),
        "specs": [
            ("Processor", "Intel Core i3-10110U (2 Cores, up to 4.1 GHz)", "Intel Core i3-10110U (2 Cores, up to 4.1 GHz)"),
            ("Memory", "8GB LPDDR3 RAM", "8GB LPDDR3 RAM"),
            ("Storage", "128GB eMMC Storage", "128GB eMMC Storage"),
            ("Display", "13.3-inch FHD (1920x1080) QLED Touchscreen", "13.3-inch FHD (1920x1080) QLED Touchscreen"),
            ("Battery", "Up to 13 hours battery life", "Up to 13 hours battery life"),
            ("Weight", "1.23 kg Ultra-portable", "1.23 kg Ultra-portable")
        ],
        "review": {
            "title": "Gorgeous QLED screen and super fast boot times",
            "text": "The screen colors pop and battery life is unbelievable. Perfect for web development, cloud coding, and media consumption."
        }
    }
]

cols = [
    "product_id", "name", "brand", "cat_l1", "cat_l2", "cat_l3",
    "retail_price_inr", "discounted_price_inr", "effective_price_inr",
    "price_unknown", "price_anomaly", "description", "image_urls",
    "image_url_count", "image_url_broken", "alias_ids", "is_canonical", "ingested_at"
]

# Check reviews columns
rev_cur = conn.execute("SELECT * FROM reviews LIMIT 1")
rev_cols = [d[0] for d in rev_cur.description]

for p in samsung_laptops:
    cur.execute(f"""
        INSERT OR REPLACE INTO products ({', '.join(cols)})
        VALUES ({', '.join(['?'] * len(cols))})
    """, [p[c] for c in cols])

    # Insert specs
    cur.execute("DELETE FROM product_specs WHERE product_id = ?", (p["product_id"],))
    for seq, (k, v, orig) in enumerate(p["specs"], 1):
        spec_id = f"spec:{p['product_id']}:{seq}"
        cur.execute("""
            INSERT INTO product_specs (spec_id, product_id, seq, key, value, unit, original_line)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (spec_id, p["product_id"], seq, k, v, None, orig))

    # Insert review
    rev_id = f"REV_{p['product_id']}_1"
    rev_data = {
        "review_id": rev_id,
        "product_id": p["product_id"],
        "rating": 5.0,
        "title": p["review"]["title"],
        "text": p["review"]["text"],
        "review_date": "2024-02-10T10:00:00Z",
        "verified_purchase": 1,
        "helpful_votes": 38,
        "is_duplicate": 0,
        "ingested_at": datetime.utcnow().isoformat()
    }
    cols_to_use = [c for c in rev_cols if c in rev_data]
    cur.execute(f"""
        INSERT OR REPLACE INTO reviews ({', '.join(cols_to_use)})
        VALUES ({', '.join(['?'] * len(cols_to_use))})
    """, [rev_data[c] for c in cols_to_use])

conn.commit()

# Rebuild FTS5 indexes
print("Rebuilding FTS5 indexes...")
cur.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
cur.execute("INSERT INTO reviews_fts(reviews_fts) VALUES('rebuild')")
conn.commit()
print("SQLite seeding done!")

# Upsert into ChromaDB
print("Embedding and upserting into ChromaDB...")
embedder = LocalBgeEmbedder()
chroma_path = Path("data/chroma")
prod_idx = ChromaVectorIndex(chroma_path, "products")
rev_idx = ChromaVectorIndex(chroma_path, "reviews")

for p in samsung_laptops:
    pid = p["product_id"]
    text = f"{p['name']} {p['description']}"
    emb = embedder.embed_documents([text])[0]
    prod_idx._collection.upsert(
        ids=[pid],
        embeddings=[emb],
        documents=[text],
        metadatas=[{"product_id": pid}]
    )
    print(f"Upserted Chroma product {pid}")

    rtext = p["review"]["text"]
    remb = embedder.embed_documents([rtext])[0]
    rid = f"REV_{pid}_1"
    rev_idx._collection.upsert(
        ids=[rid],
        embeddings=[remb],
        documents=[rtext],
        metadatas=[{"product_id": pid, "review_id": rid}]
    )
    print(f"Upserted Chroma review {rid}")

conn.close()
print("Successfully seeded modern Samsung laptops into DB, FTS5, and ChromaDB!")
