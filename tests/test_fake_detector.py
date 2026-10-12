from advisor.reviews.features import (
    burst_signal,
    extreme_no_detail_signal,
    near_dup_signal,
    reviewer_pattern_signal,
)


def test_near_dup_signal():
    reviews = [
        {"review_id": "r1", "product_id": "p1", "text": "This product is absolutely amazing and I use it every day"},
        {"review_id": "r2", "product_id": "p1", "text": "This product is absolutely amazing and I use it every day"}, # true positive
        {"review_id": "r3", "product_id": "p1", "text": "Great product, works well but I don't think it is amazing"}, # negative (11 words)
        {"review_id": "r4", "product_id": "p1", "text": "This product is absolutely amazing and I use it every week"}, # near miss / true positive depending on tau
        {"review_id": "r5", "product_id": "p2", "text": "This product is absolutely amazing and I use it every week"}, # scoped out (diff product)
    ]
    cfg = {"near_dup_shingle_size": 3, "near_dup_cosine_threshold": 0.8}
    scores = near_dup_signal(reviews, cfg)
    assert scores["r1"] == 1.0
    assert scores["r2"] == 1.0
    assert scores["r3"] == 0.0
    assert scores["r4"] == 1.0
    assert scores["r5"] == 0.0

def test_burst_signal():
    # True positive: 5 reviews in a short time for p1
    reviews = []
    for i in range(5):
        reviews.append({"review_id": f"burst_{i}", "product_id": "p1", "review_date": "2023-01-01T12:00:00Z"})

    # Near miss negative: 4 reviews
    for i in range(4):
        reviews.append({"review_id": f"miss_{i}", "product_id": "p2", "review_date": "2023-01-01T12:00:00Z"})

    cfg = {"burst_window_hours": 48, "burst_ratio_threshold": 5.0}
    scores = burst_signal(reviews, cfg)
    assert scores["burst_0"] == 1.0
    assert scores["miss_0"] == 0.0

def test_extreme_no_detail_signal():
    reviews = [
        {"review_id": "r1", "rating": 5.0, "text": "Amazing!", "product_name": "laptop"}, # TP (no overlap)
        {"review_id": "r2", "rating": 5.0, "text": "Amazing! Used this laptop for 5 days", "product_name": "laptop"}, # Near miss (has overlap "laptop")
        {"review_id": "r3", "rating": 3.0, "text": "Okay laptop", "product_name": "laptop"}, # Near miss (rating not extreme)
        {"review_id": "r4", "rating": 1.0, "text": "Terrible", "product_name": "laptop"}, # TP
        {"review_id": "r5", "rating": 5.0, "text": "Amazing! " * 20, "product_name": "laptop"}, # Near miss (too long)
    ]
    cfg = {"short_review_max_words": 15}
    scores = extreme_no_detail_signal(reviews, cfg)
    assert scores["r1"] == 1.0
    assert scores["r2"] == 0.0
    assert scores["r3"] == 0.0
    assert scores["r4"] == 1.0
    assert scores["r5"] == 0.0

def test_reviewer_pattern_signal():
    reviews = [
        # Spammer: 3 reviews on same day for different products
        {"review_id": "r1", "reviewer_id": "u1", "product_id": "p1", "review_date": "2023-01-01T10:00:00Z"},
        {"review_id": "r2", "reviewer_id": "u1", "product_id": "p2", "review_date": "2023-01-01T11:00:00Z"},
        {"review_id": "r3", "reviewer_id": "u1", "product_id": "p3", "review_date": "2023-01-01T12:00:00Z"},
        # Normal user: 2 reviews on same day
        {"review_id": "r4", "reviewer_id": "u2", "product_id": "p4", "review_date": "2023-01-01T10:00:00Z"},
        {"review_id": "r5", "reviewer_id": "u2", "product_id": "p5", "review_date": "2023-01-01T11:00:00Z"},
    ]
    cfg = {"reviewer_min_products": 3}
    scores = reviewer_pattern_signal(reviews, cfg)
    assert scores["r1"] == 1.0
    assert scores["r2"] == 1.0
    assert scores["r3"] == 1.0
    assert scores["r4"] == 0.0
    assert scores["r5"] == 0.0
