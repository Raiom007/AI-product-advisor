import math

from advisor.eval.metrics import (
    dcg_at_k,
    groundedness_rate,
    hard_constraint_violations,
    latency_percentiles,
    ndcg_at_k,
    precision,
    recall,
    recall_at_k,
)


def test_ndcg():
    # Toy data:
    # Query returned ranks: [product A (rel 3), product B (rel 2), product C (rel 0), product D (rel 1)]
    # all_relevances = [3, 2, 2, 1, 0, 0]
    ranked = [3, 2, 0, 1]
    all_rel = [3, 2, 2, 1, 0, 0]

    # Hand computing DCG@4:
    # idx 0: rel 3 -> (8-1)/log2(2) = 7
    # idx 1: rel 2 -> (4-1)/log2(3) = 3 / 1.5849 = 1.8927
    # idx 2: rel 0 -> 0
    # idx 3: rel 1 -> (2-1)/log2(5) = 1 / 2.3219 = 0.4306
    # Total DCG = 7 + 1.8927 + 0.4306 = 9.3233

    # Hand computing IDCG@4:
    # ideal = [3, 2, 2, 1]
    # idx 0: rel 3 -> 7
    # idx 1: rel 2 -> 3 / 1.5849 = 1.8927
    # idx 2: rel 2 -> 3 / log2(4) = 3 / 2 = 1.5
    # idx 3: rel 1 -> 1 / log2(5) = 0.4306
    # Total IDCG = 7 + 1.8927 + 1.5 + 0.4306 = 10.8233

    # NDCG@4 = 9.3233 / 10.8233 = 0.8614

    dcg = dcg_at_k(ranked, 4)
    assert math.isclose(dcg, 9.3234, rel_tol=1e-3)

    ndcg = ndcg_at_k(ranked, all_rel, 4)
    assert math.isclose(ndcg, 0.8614, rel_tol=1e-3)

def test_recall_at_k():
    ranked = [3, 2, 0, 1]
    all_rel = [3, 2, 2, 1, 0, 0] # 4 relevant items in total (>0)

    # In top 3, we have 2 relevant items (3, 2) and 1 irrelevant (0)
    rec = recall_at_k(ranked, all_rel, 3)
    assert math.isclose(rec, 0.5) # 2/4

    # In top 4, we have 3 relevant items
    rec = recall_at_k(ranked, all_rel, 4)
    assert math.isclose(rec, 0.75) # 3/4

def test_precision_recall():
    assert precision(tp=8, fp=2) == 0.8
    assert recall(tp=8, fn=2) == 0.8

def test_hard_constraint_violations():
    assert hard_constraint_violations([0, 1, 0, 2]) == 3

def test_latency_percentiles():
    lats = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50, p95 = latency_percentiles(lats)
    assert p50 == 55.0  # index 4.5 -> avg of 50 and 60
    assert p95 == 95.5  # index 9 * 0.95 = 8.55 -> between 90 and 100

def test_groundedness_rate():
    assert groundedness_rate(8, 10) == 0.8
    assert groundedness_rate(0, 0) == 1.0
