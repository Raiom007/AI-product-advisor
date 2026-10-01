import json
import random
from pathlib import Path

import pandas as pd
import requests

USD_TO_INR = 83.0

META_URL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Electronics.jsonl"
REVIEW_URL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories/Electronics.jsonl"

def iter_jsonl(url):
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        for line in r.iter_lines(chunk_size=1024*1024):
            if line:
                yield json.loads(line)

def main():
    print("Finding 20k valid products...")

    product_review_counts = {}
    review_pool = []

    # We want ~34k reviews
    for rev in iter_jsonl(REVIEW_URL):
        pid = rev.get('parent_asin', rev.get('asin', ''))
        if not pid:
            continue
        if len(product_review_counts) < 30000 or pid in product_review_counts:
            if pid not in product_review_counts:
                product_review_counts[pid] = 0
            if product_review_counts[pid] < 15:
                review_pool.append({
                    'review_id': f"MCA_REV_{len(review_pool)+1:07d}",
                    'reviewer_id': rev.get('user_id', 'unknown'),
                    'product_id': f"MCA_{pid}",
                    'review_title': rev.get('title', ''),
                    'review_text': rev.get('text', ''),
                    'rating': rev.get('rating', 0.0),
                    'verified_purchase': rev.get('verified_purchase', False)
                })
                product_review_counts[pid] += 1

            if len(review_pool) >= 50000:
                break

    valid_pids = set(pid for pid in product_review_counts if product_review_counts[pid] > 0)
    print(f"Collected {len(review_pool)} reviews for {len(valid_pids)} products. Now finding their metadata...")

    product_pool = []
    pids_found = set()

    for prod in iter_jsonl(META_URL):
        pid = prod.get('parent_asin', prod.get('asin', ''))
        if pid in valid_pids:
            price_str = str(prod.get('price', ''))
            price_usd = 0.0
            try:
                clean_price = price_str.replace('$', '').replace(',', '').strip()
                if clean_price:
                    price_usd = float(clean_price)
            except ValueError:
                pass

            price_inr = round(price_usd * USD_TO_INR) if price_usd > 0 else None

            cats = prod.get('categories', [])
            cat_tree = " >> ".join(cats) if cats else ""

            features = prod.get('features', [])
            spec_text = " | ".join(features) if features else ""

            desc = prod.get('description', [])
            desc_text = " ".join(desc) if desc else ""

            images = prod.get('images', [])
            image_urls = []
            if isinstance(images, list):
                for img in images:
                    if isinstance(img, dict) and 'large' in img:
                        image_urls.append(img['large'])
                    elif isinstance(img, str):
                        image_urls.append(img)

            product_pool.append({
                'product_id': f"MCA_{pid}",
                'product_name': prod.get('title', ''),
                'category_tree': cat_tree,
                'brand': prod.get('brand', ''),
                'retail_price_inr': price_inr,
                'discounted_price_inr': price_inr,
                'specification_text': spec_text,
                'description': desc_text,
                'image_urls': json.dumps(image_urls)
            })
            pids_found.add(pid)

            if len(product_pool) >= 20000:
                break

    print(f"Found {len(product_pool)} products in metadata.")

    final_reviews = [r for r in review_pool if r['product_id'] == f"MCA_{r['product_id'].replace('MCA_', '')}" and r['product_id'].replace('MCA_', '') in pids_found]

    random.seed(42)
    random.shuffle(final_reviews)
    final_reviews = final_reviews[:34000]

    print(f"Final stats: {len(product_pool)} products, {len(final_reviews)} reviews.")

    Path("data/raw").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(product_pool).to_csv("data/raw/products.csv", index=False)
    pd.DataFrame(final_reviews).to_csv("data/raw/reviews.csv", index=False)
    print("Wrote data/raw/products.csv and data/raw/reviews.csv")

if __name__ == "__main__":
    main()
