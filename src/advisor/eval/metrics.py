import math


def dcg_at_k(relevances: list[int], k: int) -> float:
    """Discounted Cumulative Gain at k. Relevances should be 0-3."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += (math.pow(2, rel) - 1) / math.log2(i + 2)
    return dcg

def ndcg_at_k(ranked_relevances: list[int], all_relevances: list[int], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    actual_dcg = dcg_at_k(ranked_relevances, k)
    ideal_relevances = sorted(all_relevances, reverse=True)
    ideal_dcg = dcg_at_k(ideal_relevances, k)

    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg

def recall_at_k(ranked_relevances: list[int], all_relevances: list[int], k: int) -> float:
    """Recall at k. Any relevance > 0 is considered relevant."""
    relevant_in_top_k = sum(1 for r in ranked_relevances[:k] if r > 0)
    total_relevant = sum(1 for r in all_relevances if r > 0)

    if total_relevant == 0:
        return 0.0
    return relevant_in_top_k / total_relevant

def precision(tp: int, fp: int) -> float:
    if tp + fp == 0:
        return 0.0
    return tp / (tp + fp)

def recall(tp: int, fn: int) -> float:
    if tp + fn == 0:
        return 0.0
    return tp / (tp + fn)

def hard_constraint_violations(violations_per_result: list[int]) -> int:
    """Returns the total number of constraint violations across results."""
    return sum(violations_per_result)

def latency_percentiles(latencies: list[float]) -> tuple[float, float]:
    """Returns p50 and p95 latencies."""
    if not latencies:
        return 0.0, 0.0
    sorted_lats = sorted(latencies)

    def percentile(p):
        idx = (len(sorted_lats) - 1) * p
        lower = math.floor(idx)
        upper = math.ceil(idx)
        weight = idx - lower
        if lower == upper:
            return sorted_lats[int(lower)]
        return sorted_lats[int(lower)] * (1 - weight) + sorted_lats[int(upper)] * weight

    return percentile(0.50), percentile(0.95)

def groundedness_rate(grounded_statements: int, total_statements: int) -> float:
    if total_statements == 0:
        return 1.0 # Vacuously true
    return grounded_statements / total_statements
