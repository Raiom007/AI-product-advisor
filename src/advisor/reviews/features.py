from collections import defaultdict
from datetime import datetime

from advisor.core.registries import fake_signal

# WHY: We need to calculate signals for all reviews. Each function returns
# a dict mapping review_id -> float score (0.0 to 1.0).

def _get_shingles(text: str, n: int = 5) -> set[str]:
    words = text.lower().split()
    return set(" ".join(words[i:i+n]) for i in range(max(1, len(words) - n + 1)))

def _jaccard(s1: set[str], s2: set[str]) -> float:
    if not s1 and not s2: return 0.0
    return len(s1 & s2) / len(s1 | s2)

@fake_signal("near_dup")
def near_dup_signal(reviews: list[dict], config: dict) -> dict[str, float]:
    """MinHash (word 5-shingles) cosine/Jaccard > tau within and across products."""
    scores = {r["review_id"]: 0.0 for r in reviews}
    threshold = config.get("near_dup_cosine_threshold", 0.85)
    n = config.get("near_dup_shingle_size", 5)

    # Fast path: exact dups (already marked by ingest 'is_duplicate' flag)
    for r in reviews:
        if r.get("is_duplicate", 0) == 1:
            scores[r["review_id"]] = 1.0

    # Group by product
    by_prod = defaultdict(list)
    for r in reviews:
        if scores[r["review_id"]] == 1.0:
            continue

        words = r.get("text", "").split()
        # skip near-dup checking for short reviews (< 15 words)
        if len(words) < 15:
            continue

        by_prod[r["product_id"]].append(r)

    # Scoped per-product only
    for pid, prod_revs in by_prod.items():
        if len(prod_revs) < 2:
            continue

        # build shingles
        rid_to_shingles = {}
        shingle_to_rids = defaultdict(list)
        for r in prod_revs:
            s = _get_shingles(r.get("text", ""), n)
            if not s: continue
            rid_to_shingles[r["review_id"]] = s
            for sh in s:
                shingle_to_rids[sh].append(r["review_id"])

        # Compare
        for rid, shingles in rid_to_shingles.items():
            if scores[rid] == 1.0: continue
            candidates = set()
            for sh in shingles:
                candidates.update(shingle_to_rids[sh])
            candidates.discard(rid)

            for cand_id in candidates:
                if scores[cand_id] == 1.0: continue
                j = _jaccard(shingles, rid_to_shingles[cand_id])
                if j >= threshold:
                    scores[rid] = 1.0
                    scores[cand_id] = 1.0

    return scores

@fake_signal("burst")
def burst_signal(reviews: list[dict], config: dict) -> dict[str, float]:
    """Review burst in 48h window vs baseline."""
    scores = {r["review_id"]: 0.0 for r in reviews}
    window_hrs = config.get("burst_window_hours", 48)

    # Group by product
    by_prod = defaultdict(list)
    for r in reviews:
        date_str = r.get("review_date", "")
        if not date_str: continue
        try:
            # McAuley dates are usually timestamp or ms timestamp or YYYY-MM-DD HH:MM:SS
            if date_str.isdigit():
                dt = datetime.fromtimestamp(int(date_str) / 1000 if len(date_str) > 10 else int(date_str))
            else:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            by_prod[r["product_id"]].append((dt, r["review_id"]))
        except Exception:
            continue

    for pid, prod_reviews in by_prod.items():
        if len(prod_reviews) < 5:
            continue
        prod_reviews.sort(key=lambda x: x[0])
        # Find bursts (a window with unusually many reviews)
        # We'll flag reviews that are part of a dense cluster
        times = [x[0] for x in prod_reviews]
        total_hrs = max(720, (times[-1] - times[0]).total_seconds() / 3600) # min 1 month lifetime
        baseline_rate = len(times) / total_hrs

        for i, (dt, rid) in enumerate(prod_reviews):
            # count reviews within window_hrs
            count = 0
            for j in range(i, len(prod_reviews)):
                if (prod_reviews[j][0] - dt).total_seconds() <= window_hrs * 3600:
                    count += 1
                else:
                    break

            window_rate = count / window_hrs
            ratio = window_rate / baseline_rate if baseline_rate > 0 else 0

            if count >= 5 and ratio >= config.get("burst_ratio_threshold", 5.0):
                for j in range(i, i + count):
                    scores[prod_reviews[j][1]] = 1.0

    return scores

@fake_signal("extreme_no_detail")
def extreme_no_detail_signal(reviews: list[dict], config: dict) -> dict[str, float]:
    """Rating ∈ {1,5} AND short AND low specificity (no product token overlap)."""
    scores = {r["review_id"]: 0.0 for r in reviews}
    max_words = config.get("short_review_max_words", 15)
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "is", "was", "it", "this", "that", "of", "product", "good", "great", "excellent", "terrible", "bad", "awesome", "perfect", "nice", "very", "much"}

    for r in reviews:
        rating = r.get("rating", 0)
        if rating not in (1, 5):
            continue

        text = r.get("text", "")
        if not text:
            scores[r["review_id"]] = 1.0
            continue

        words = text.lower().split()
        if len(words) > max_words:
            continue

        # Specificity check: token overlap with product title or description
        rev_tokens = set(w.strip(".,!?'\"()") for w in words if w.strip(".,!?'\"()"))
        prod_name = (r.get("product_name") or "").lower()
        prod_desc = (r.get("product_description") or "").lower()
        prod_tokens = set(w.strip(".,!?'\"()") for w in (prod_name.split() + prod_desc.split()) if w.strip(".,!?'\"()"))

        rev_tokens_clean = rev_tokens - stopwords
        prod_tokens_clean = prod_tokens - stopwords

        overlap = rev_tokens_clean.intersection(prod_tokens_clean)

        if not overlap:
            scores[r["review_id"]] = 1.0

    return scores

@fake_signal("reviewer_pattern")
def reviewer_pattern_signal(reviews: list[dict], config: dict) -> dict[str, float]:
    """Same reviewer, ≥k products, same day."""
    scores = {r["review_id"]: 0.0 for r in reviews}
    min_prods = config.get("reviewer_min_products", 3)

    # reviewer_id -> day -> list of product_ids
    by_rev = defaultdict(lambda: defaultdict(list))

    for r in reviews:
        rev_id = r.get("reviewer_id", "")
        if not rev_id: continue

        date_str = r.get("review_date", "")
        if not date_str: continue

        try:
            if date_str.isdigit():
                dt = datetime.fromtimestamp(int(date_str) / 1000 if len(date_str) > 10 else int(date_str))
            else:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            day = dt.date()
            by_rev[rev_id][day].append((r["product_id"], r["review_id"]))
        except Exception:
            continue

    for rev_id, days in by_rev.items():
        for day, prod_revs in days.items():
            unique_prods = len(set(x[0] for x in prod_revs))
            if unique_prods >= min_prods:
                for _, rid in prod_revs:
                    scores[rid] = 1.0

    return scores
